"""Plans mẫu thủ công trên BBS persisted; không automated planner hoặc M4 execution."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_d04_closure import save
from evaluate_m4_04_evidence import manifest
from evaluate_m4_05_qa import setup
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    TOOL_CONTRACTS,
    EvidencePlan,
    EvidenceRequirement,
    EvidenceSelector,
    PlanStep,
    QuerySpecification,
    bind_step_request,
    validate_plan,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    EvidenceRetrievalTools,
    FinancialCalculationResponse,
    FinancialRetrievalTools,
    FindFinancialFactsRequest,
    GetMetricEvidenceLineageRequest,
)

STOPS = [
    "all_required_evidence_resolved",
    "missing_required_inputs",
    "unresolved_ambiguity",
    "conflicting_evidence",
    "unsupported_operation",
    "compatibility_gate_blocked",
    "execution_limit_reached",
]


def tool_step(step_id, tool, selector, *, arguments=None, **kwargs):
    return PlanStep(
        step_id=step_id,
        step_type="tool",
        tool=tool,
        selector=selector,
        arguments=arguments if arguments is not None else selector.model_dump(exclude_none=True),
        expected_result_type=TOOL_CONTRACTS[tool][1].__name__,
        **kwargs,
    )


def fact_plan(case_id, question, scope, item, period, *, reporting_scope=None):
    selector = EvidenceSelector(
        **scope, canonical_item_id=item, period=period, reporting_scope=reporting_scope
    )
    plan = EvidencePlan(
        plan_id=case_id,
        query=QuerySpecification(
            original_question=question,
            intent="direct_fact",
            company_alias="BBS",
            analysis_type="direct_fact",
            selectors=[selector],
            required_indicators=[item],
            reporting_periods=[period],
            reporting_scope=reporting_scope,
        ),
        requirements=[
            EvidenceRequirement(
                requirement_id="fact",
                evidence_type="fact",
                canonical_item_id=item,
                selector=selector,
            ),
            EvidenceRequirement(
                requirement_id="citations",
                evidence_type="citations",
                selector=selector,
                dependencies=["fact"],
            ),
        ],
        steps=[
            tool_step("fact", "find_financial_facts", selector, output_evidence_ids=["fact"]),
            tool_step(
                "sources",
                "get_evidence_sources",
                EvidenceSelector(**scope),
                arguments={},
                prerequisite_step_ids=["fact"],
                required_evidence_ids=["fact"],
                output_evidence_ids=["citations"],
                input_bindings=[
                    dict(
                        argument="reference",
                        source_step_id="fact",
                        output_path="matches.0.reference",
                    )
                ],
            ),
        ],
        stop_conditions=STOPS,
    )
    return plan


def metric_plan(case_id, question, scope, metric):
    """Bảy bước tường minh; metric ID lấy từ inventory, không tự lập kế hoạch."""
    selector = EvidenceSelector(**scope)
    formula = metric.definition.name
    requirements = [
        EvidenceRequirement(requirement_id="snapshot", evidence_type="snapshot", selector=selector)
    ]
    steps = [
        PlanStep(
            step_id="select",
            step_type="resolve_snapshot",
            selector=selector,
            output_evidence_ids=["snapshot"],
            expected_result_type="SnapshotSelection",
        )
    ]
    operand_ids = []
    for operand in metric.operands:
        key = operand.role
        operand_ids.append(key)
        operand_selector = EvidenceSelector(
            **scope,
            canonical_item_id=operand.canonical_item_id,
            period=metric.request.operand_periods[key],
            statement_type=operand.context.statement_type,
        )
        requirements.append(
            EvidenceRequirement(
                requirement_id=key,
                evidence_type="fact",
                selector=operand_selector,
                canonical_item_id=operand.canonical_item_id,
                dependencies=["snapshot"],
            )
        )
        steps.append(
            tool_step(
                key,
                "find_financial_facts",
                operand_selector,
                prerequisite_step_ids=["select"],
                required_evidence_ids=["snapshot"],
                output_evidence_ids=[key],
            )
        )
    requirements.extend(
        [
            EvidenceRequirement(
                requirement_id="formula",
                evidence_type="formula",
                formula_id=formula,
                selector=selector,
                dependencies=operand_ids,
            ),
            EvidenceRequirement(
                requirement_id="compatible",
                evidence_type="compatibility",
                formula_id=formula,
                selector=selector,
                dependencies=operand_ids,
            ),
            EvidenceRequirement(
                requirement_id="metric",
                evidence_type="metric",
                formula_id=formula,
                selector=selector,
                dependencies=["formula", "compatible"],
            ),
            EvidenceRequirement(
                requirement_id="lineage",
                evidence_type="lineage",
                formula_id=formula,
                selector=selector,
                dependencies=["metric"],
            ),
            EvidenceRequirement(
                requirement_id="bundle",
                evidence_type="analysis_bundle",
                selector=selector,
                dependencies=["metric", "lineage"],
            ),
        ]
    )
    steps.extend(
        [
            PlanStep(
                step_id="gate",
                step_type="check_compatibility",
                selector=selector,
                formula_id=formula,
                prerequisite_step_ids=operand_ids,
                required_evidence_ids=operand_ids,
                output_evidence_ids=["formula", "compatible"],
                expected_result_type="MetricSnapshotClosure",
            ),
            tool_step(
                "calculate",
                "calculate_financial_metric",
                selector,
                arguments={"metric_id": metric.metric_id},
                formula_id=formula,
                prerequisite_step_ids=["select", "gate"],
                required_evidence_ids=["formula", "compatible"],
                input_bindings=[
                    dict(
                        argument=field,
                        source_step_id="select",
                        output_path="candidates.0.descriptor." + field,
                    )
                    for field in ("document_id", "snapshot_id")
                ],
                output_evidence_ids=["metric"],
            ),
            tool_step(
                "lineage",
                "get_metric_evidence_lineage",
                selector,
                arguments=scope,
                prerequisite_step_ids=["calculate"],
                required_evidence_ids=["metric"],
                input_bindings=[
                    dict(argument="metric_id", source_step_id="calculate", output_path="metric_id")
                ],
                output_evidence_ids=["lineage"],
            ),
            PlanStep(
                step_id="bundle",
                step_type="prepare_bundle",
                selector=selector,
                prerequisite_step_ids=["calculate", "lineage"],
                required_evidence_ids=["metric", "lineage"],
                output_evidence_ids=["bundle"],
                expected_result_type="candidate_claim_inputs_for_M6",
            ),
        ]
    )
    return EvidencePlan(
        plan_id=case_id,
        query=QuerySpecification(
            original_question=question,
            intent="evidence_explanation" if formula == "debt_to_assets" else "multi_step_analysis",
            company_alias="BBS",
            selectors=[selector],
            analysis_type="metric_with_lineage",
            reporting_periods=list(metric.request.operand_periods.values()),
            required_indicators=[o.canonical_item_id for o in metric.operands],
            requested_formula_ids=[formula],
        ),
        requirements=requirements,
        steps=steps,
        stop_conditions=STOPS,
        specialist_roles=[
            "liquidity_and_leverage" if formula == "debt_to_assets" else "profitability"
        ],
    )


def protected(root):
    hashes = manifest(root)
    for folder in ("M4-04", "M4-05-final", "M4-05a-offline-final"):
        hashes.update(
            (p.relative_to(root).as_posix(), digest(p))
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    hashes["web/next-env.d.ts"] = digest(root / "web/next-env.d.ts")
    return dict(sorted(hashes.items()))


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root)
    save(output / "hashes-before.json", before)
    data, scopes, recovery, _ = setup(root)
    catalog = SnapshotCatalog(**data)
    original_records = [
        r.model_dump_json() for r in [*catalog.facts, *catalog.evidence, *catalog.metrics]
    ]
    financial, evidence = FinancialRetrievalTools(catalog), EvidenceRetrievalTools(catalog)
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(row))
        for row in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]

    def metric(formula):
        matches = [
            m
            for m in catalog.metrics
            if m.request.document_id == scopes[2025]["document_id"]
            and m.request.snapshot_id == scopes[2025]["snapshot_id"]
            and m.definition.name == formula
        ]
        assert len(matches) == 1
        return matches[0]

    cases = [
        (
            fact_plan(
                "direct_2025",
                "Tổng tài sản BBS 2025?",
                scopes[2025],
                "b01.total_assets",
                "2025-12-31",
            ),
            "valid",
        ),
        (
            metric_plan(
                "gross_margin",
                "Phân tích biên lợi nhuận gộp BBS 2025 và nguồn số liệu.",
                scopes[2025],
                metric("gross_margin"),
            ),
            "valid",
        ),
        (
            metric_plan(
                "revenue_yoy_lineage",
                "Nguồn tăng trưởng doanh thu BBS 2025?",
                scopes[2025],
                metric("revenue_yoy"),
            ),
            "valid",
        ),
        (
            metric_plan(
                "debt_operands_sources",
                "Operands và nguồn của Debt-to-Assets BBS 2025?",
                scopes[2025],
                metric("debt_to_assets"),
            ),
            "valid",
        ),
    ]
    multi = fact_plan(
        "multi_step",
        "Phân tích doanh thu và lợi nhuận gộp cùng filing BBS 2025.",
        scopes[2025],
        "b02.net_revenue",
        "2025",
    )
    multi.query.intent = "multi_step_analysis"
    multi.query.selectors = [EvidenceSelector(**scopes[2025])]
    profit_selector = EvidenceSelector(
        **scopes[2025], canonical_item_id="b02.gross_profit", period="2025"
    )
    multi.requirements.append(
        EvidenceRequirement(requirement_id="profit", evidence_type="fact", selector=profit_selector)
    )
    multi.steps.append(
        tool_step("profit", "find_financial_facts", profit_selector, output_evidence_ids=["profit"])
    )
    cases.append((multi, "valid"))
    cases.append(
        (
            fact_plan(
                "snapshot_ambiguity",
                "Tổng tài sản BBS 2022?",
                {"document_id": scopes[2022]["document_id"]},
                "b01.total_assets",
                "2022-12-31",
            ),
            "blocked",
        )
    )
    cross = fact_plan(
        "cross_document",
        "So sánh BBS 2024 và 2025.",
        scopes[2025],
        "b01.total_assets",
        "2025-12-31",
    )
    cross.query.cross_document_comparison = True
    cross.query.selectors.append(EvidenceSelector(**scopes[2024]))
    cases.append((cross, "blocked"))
    # Canonical ID có thật trong item catalog; absence/quality do M4 probe xác nhận.
    from vietnamese_financial_multi_agent.tools.question_understanding import ITEM_RULES

    missing = next(
        item
        for item in ITEM_RULES
        if not any(
            f.document_id == scopes[2025]["document_id"]
            and f.snapshot_id == scopes[2025]["snapshot_id"]
            and f.canonical_item_id == item
            for f in catalog.facts
        )
    )
    cases.append(
        (
            fact_plan(
                "missing_item",
                "Chỉ tiêu chưa có usable evidence trong filing.",
                scopes[2025],
                missing,
                "2025",
            ),
            "blocked",
        )
    )
    for year in (2021, 2022, 2023, 2024):
        cases.append(
            (
                fact_plan(
                    f"direct_{year}",
                    f"Tổng tài sản BBS {year}?",
                    scopes[year],
                    "b01.total_assets",
                    f"{year}-12-31",
                ),
                "valid",
            )
        )
    cases.append(
        (
            fact_plan(
                "recovery_2022",
                "Tổng tài sản BBS 2022 recovery?",
                dict(document_id=recovery.document_id, snapshot_id=recovery.snapshot_id),
                "b01.total_assets",
                "2022-12-31",
            ),
            "valid",
        )
    )
    cases.append(
        (
            fact_plan(
                "scope_required_2025",
                "Tổng tài sản riêng BBS 2025?",
                scopes[2025],
                "b01.total_assets",
                "2025-12-31",
                reporting_scope="separate",
            ),
            "blocked",
        )
    )
    # Constraint chỉ ở query vẫn phải gate plan, dù tool chưa lặp lại argument.
    query_scope = cases[-1][0]
    query_scope.query.selectors = [EvidenceSelector(**scopes[2025])]
    for requirement in query_scope.requirements:
        requirement.selector = requirement.selector.model_copy(update={"reporting_scope": None})
    for step in query_scope.steps:
        step.selector = step.selector.model_copy(update={"reporting_scope": None})
        step.arguments.pop("reporting_scope", None)

    rows = []
    for plan, expected in cases:
        probes = []
        for step in plan.steps:
            if step.tool == "find_financial_facts":
                response = financial.find_financial_facts(
                    FindFinancialFactsRequest(
                        **{
                            **step.arguments,
                            **(
                                {"reporting_scope": plan.query.reporting_scope}
                                if plan.query.reporting_scope
                                else {}
                            ),
                        }
                    )
                )
                probes.append(response.model_dump(mode="json"))
                req = next(
                    r for r in plan.requirements if r.requirement_id in step.output_evidence_ids
                )
                req.resolution = "found" if response.status == "found" else "unresolved"
                req.references = [m.reference for m in response.matches]
                req.citations = [c for m in response.matches for c in m.citations]
                req.caveats = response.caveats
                req.quality_decisions = [
                    q.decision
                    for m in response.matches
                    for q in m.record.quality_context
                    if q.task_type == "direct_qa"
                ]
                if response.status == "found":
                    assert not response.financial_fact_verified
                    assert req.references and req.citations and req.caveats
                    if plan.plan_id.startswith("direct_") or plan.plan_id in {
                        "recovery_2022",
                        "multi_step",
                    }:
                        request = (
                            bind_step_request(plan, "sources", {"fact": response})
                            if step.step_id == "fact"
                            else None
                        )
                        if request:
                            sources = evidence.get_evidence_sources(request)
                            assert sources.status == "found"
                            assert [c.source for m in sources.matches for c in m.citations] == [
                                c.source for m in response.matches for c in m.citations
                            ]
                            probes.append(sources.model_dump(mode="json"))
            elif step.tool == "get_metric_evidence_lineage":
                formula = plan.query.requested_formula_ids[0]
                selected = metric(formula)
                response = evidence.get_metric_evidence_lineage(
                    GetMetricEvidenceLineageRequest(metric_id=selected.metric_id, **scopes[2025])
                )
                assert response.status == "found" and response.metric_matches
                baseline = next(c for c in accepted if c.metric_id == selected.metric_id)
                assert response.metric_matches[0] == baseline.evidence
                # Binding probe dùng accepted calculation, không thực thi bước calculate.
                request = bind_step_request(plan, "lineage", {"calculate": baseline})
                assert request.metric_id == selected.metric_id
                selection = catalog.select(**scopes[2025])
                request = bind_step_request(plan, "calculate", {"select": selection})
                assert request.document_id == selected.request.document_id
                probes.append(
                    dict(
                        accepted_result=baseline.result,
                        accepted_trace_preserved=True,
                        response=response.model_dump(mode="json"),
                    )
                )
        plan = EvidencePlan.model_validate_json(plan.model_dump_json())
        assert EvidencePlan.model_validate_json(plan.model_dump_json()) == plan
        result = validate_plan(plan, catalog=catalog)
        assert result.disposition == expected, (plan.plan_id, result)
        assert result.structurally_valid
        rows.append(
            dict(case_id=plan.plan_id, expected=expected, validation=result.model_dump(mode="json"))
        )
        save(
            output / (plan.plan_id + ".json"),
            dict(
                plan=plan.model_dump(mode="json"),
                validation=result.model_dump(mode="json"),
                m4_probes=probes,
            ),
        )

    # Invalid case tách khỏi blocked; IDs/data thật, chỉ làm sai binding period.
    invalid = cases[0][0].model_dump()
    invalid["steps"][0]["arguments"]["period"] = "2024-12-31"
    result = validate_plan(invalid, catalog=catalog)
    assert result.disposition == "invalid"
    save(
        output / "invalid-period-binding.json",
        dict(plan=invalid, validation=result.model_dump(mode="json")),
    )
    rows.append(
        dict(
            case_id="invalid_period_binding",
            expected="invalid",
            validation=result.model_dump(mode="json"),
        )
    )
    assert original_records == [
        r.model_dump_json() for r in [*catalog.facts, *catalog.evidence, *catalog.metrics]
    ]
    after = protected(root)
    assert before == after
    save(output / "hashes-after.json", after)
    save(output / "cases.json", rows)
    summary = dict(
        manual_contract_cases=len(rows),
        dispositions=dict(Counter(r["validation"]["disposition"] for r in rows)),
        persisted_years=sorted(scopes),
        recovery_2022_preserved=True,
        json_roundtrip_exact=True,
        protected_input_hashes=len(before),
        hashes_unchanged=True,
        m4_records_unchanged=True,
        gateway_calls=0,
        calculation_calls=0,
        automated_planner=False,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.root.resolve(), args.output.resolve())
