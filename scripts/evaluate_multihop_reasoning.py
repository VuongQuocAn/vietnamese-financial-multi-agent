"""FIX-02-MH: offline real-source arithmetic/verification probes, not LLM accuracy."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from evaluate_real_pdf import build, digest, save


def replay_outputs(source, output):
    """Replay saved native proofs and the final M7 contracts without new LLM work."""
    from vietnamese_financial_multi_agent.outputs import CitationRenderer, VietnameseQAComposer
    from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
    from vietnamese_financial_multi_agent.outputs.qa_contracts import (
        QARequirement,
        VietnameseQARequest,
    )
    from vietnamese_financial_multi_agent.tools.financial_calculator import FinancialCalculator
    from vietnamese_financial_multi_agent.verification import (
        VerificationHistory,
        VerifiedClaimLedger,
        VerifiedClaimRepository,
    )
    from vietnamese_financial_multi_agent.verification.ledger import replay_history

    repository = VerifiedClaimRepository(output / "ledger")
    histories = [
        VerificationHistory.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted((source / "cases").glob("*.json"))
    ]
    for history in histories:
        repository.admit(history)
    ledger = VerifiedClaimLedger(repository)
    rows = []
    calculator = FinancialCalculator(build(Path.cwd(), output / "canonical-replay").catalog)
    for history in histories:
        claim = history.outcome.final.original_claim
        proof = claim.reasoning.calculation
        expected = calculator.calculate_dynamic(
            {key: operand.reference for key, operand in proof.operands.items()},
            [step.operation for step in proof.steps],
        )
        if expected != proof:
            raise ValueError("canonical_replay_mismatch:" + claim.candidate_id)
        request = VietnameseQARequest(
            question=history.contexts[0].batch.question,
            company_id=claim.company_id,
            document_id=claim.document_id,
            snapshot_id=claim.snapshot_id,
            period=claim.period,
            answer_requirements=[
                QARequirement(
                    requirement_id=claim.candidate_id,
                    text="Đối chiếu",
                    kind="fact",
                    target_id=claim.supporting_evidence[0].canonical_item_id,
                    interpretation=True,
                    interpretation_topic="dynamic_calculation",
                    required_indicators=[s.canonical_item_id for s in claim.supporting_evidence],
                    reasoning_operations=[s.operation.operator for s in proof.steps],
                    reasoning_periods=sorted({o.period for o in proof.operands.values()}),
                )
            ],
        )
        answer = VietnameseQAComposer(ledger).compose(request)
        rendered = CitationRenderer().render_qa(answer)
        firewall = InformationFirewall(ledger).evaluate_qa(
            request=request, response=answer, rendered=rendered
        )
        rows.append(
            dict(
                id=claim.candidate_id,
                m6=history.outcome.final.decision,
                m7=answer.status,
                firewall=firewall.decision,
                citations=len(rendered.references),
                text=rendered.rendered_text,
            )
        )
    historical = []
    for name in [
        "planner-dependencies/live",
        "controlled-live-9a356bf/run",
        "flexible-contracts/live",
    ]:
        path = Path("artifacts/evidence/FIX-02") / name / "ledger/verified-claims.json"
        before = digest(path)
        entries = json.loads(path.read_bytes())["entries"]
        for entry in entries:
            replay_history(VerificationHistory.model_validate_json(json.dumps(entry["history"])))
        historical.append(dict(path=name, count=len(entries), unchanged=before == digest(path)))
    save(output / "results.json", rows)
    save(
        output / "summary.json",
        dict(
            cases=len(rows),
            answered=sum(r["m7"] == "answered" for r in rows),
            released=sum(r["firewall"] in {"ALLOW", "ALLOW_WITH_CAVEAT"} for r in rows),
            historical=historical,
            provider_calls=0,
            limitation="Saved real-source arithmetic/native proof replay; not LLM analysis accuracy.",
        ),
    )
    print(
        json.dumps(
            dict(
                cases=len(rows),
                answered=sum(r["m7"] == "answered" for r in rows),
                historical=historical,
            )
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-input", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh_output_required")
    if args.replay_input:
        replay_outputs(args.replay_input, args.output)
        return
    from vietnamese_financial_multi_agent.agents import PlannerContext
    from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
        ITEM_LABELS as FLOW,
    )
    from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import (
        ITEM_LABELS as BALANCE,
    )
    from vietnamese_financial_multi_agent.agents.profitability_specialist import (
        ITEM_LABELS as PROFIT,
    )
    from vietnamese_financial_multi_agent.agents.specialist_common import (
        ReasoningProof,
        SpecialistEvidence,
        _number,
    )
    from vietnamese_financial_multi_agent.outputs import CitationRenderer, VietnameseQAComposer
    from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
    from vietnamese_financial_multi_agent.outputs.qa_contracts import (
        QARequirement,
        VietnameseQARequest,
    )
    from vietnamese_financial_multi_agent.tools.financial_calculator import (
        DynamicOperation,
        FinancialCalculator,
        render_dynamic,
    )
    from vietnamese_financial_multi_agent.tools.financial_retrieval import (
        FinancialRetrievalTools,
        GetFinancialFactRequest,
    )
    from vietnamese_financial_multi_agent.verification import (
        BoundedVerificationLoop,
        CandidateClaim,
        ClaimProvenance,
        DeterministicFinancialValidator,
        EvidenceCritic,
        FinancialLogicCritic,
        VerificationHistory,
        VerificationInput,
        VerificationProofContext,
        VerifiedClaimLedger,
    )
    from vietnamese_financial_multi_agent.verification.ledger import replay_history

    root = Path.cwd()
    pipeline = build(root, args.output)
    catalog = pipeline.catalog
    labels = FLOW | BALANCE | PROFIT
    tools, calculator = FinancialRetrievalTools(catalog), FinancialCalculator(catalog)
    # Select the actual accepted BBS filing by its document descriptor, never by values.
    document = next(
        d for d in pipeline.documents if "BBS" in d.company_aliases and d.reporting_year == 2025
    )
    facts = [f for f in catalog.facts if f.document_id == document.document_id]
    snapshot = next(f.snapshot_id for f in facts)
    facts = [f for f in facts if f.snapshot_id == snapshot]
    rev, pat, cfo, gross, costs, assets = (
        "b02.net_revenue",
        "b02.profit_after_tax",
        "b03.operating_cash_flow",
        "b02.gross_profit",
        "b02.cost_of_sales",
        "b01.total_assets",
    )

    def operation(op, inputs, key="result", across=False):
        return DynamicOperation(
            operation_id=key,
            operator=op,
            inputs=inputs,
            period_relation="across_periods" if across else "same",
        )

    cases = [
        (
            "MH01",
            "CFO có lớn hơn lợi nhuận sau thuế?",
            [(cfo, "2025"), (pat, "2025")],
            [operation("greater", ["E1", "E2"])],
        ),
        (
            "MH02",
            "Chênh lệch CFO và lợi nhuận sau thuế?",
            [(cfo, "2025"), (pat, "2025")],
            [operation("subtract", ["E1", "E2"])],
        ),
        (
            "MH03",
            "Tỷ số đối chiếu CFO/PAT là bao nhiêu?",
            [(cfo, "2025"), (pat, "2025")],
            [operation("ratio", ["E1", "E2"])],
        ),
        (
            "MH04",
            "Doanh thu thay đổi bao nhiêu giữa hai kỳ?",
            [(rev, "2025"), (rev, "2024")],
            [operation("percentage_change", ["E1", "E2"], across=True)],
        ),
        (
            "MH05",
            "Lợi nhuận sau thuế thay đổi bao nhiêu?",
            [(pat, "2025"), (pat, "2024")],
            [operation("percentage_change", ["E1", "E2"], across=True)],
        ),
        (
            "MH06",
            "Chênh lệch lợi nhuận gộp hai kỳ?",
            [(gross, "2025"), (gross, "2024")],
            [operation("subtract", ["E1", "E2"], across=True)],
        ),
        (
            "MH07",
            "Lợi nhuận gộp so với doanh thu kỳ này?",
            [(gross, "2025"), (rev, "2025")],
            [operation("ratio", ["E1", "E2"])],
        ),
        (
            "MH08",
            "Lợi nhuận gộp so với doanh thu kỳ trước?",
            [(gross, "2024"), (rev, "2024")],
            [operation("ratio", ["E1", "E2"])],
        ),
        (
            "MH09",
            "Quan hệ lợi nhuận gộp/doanh thu thay đổi thế nào?",
            [(gross, "2025"), (rev, "2025"), (gross, "2024"), (rev, "2024")],
            [
                operation("ratio", ["E1", "E2"], "current"),
                operation("ratio", ["E3", "E4"], "prior"),
                operation("subtract", ["current", "prior"], across=True),
            ],
        ),
        (
            "MH10",
            "Tăng trưởng doanh thu có cao hơn tăng trưởng PAT?",
            [(rev, "2025"), (rev, "2024"), (pat, "2025"), (pat, "2024")],
            [
                operation("percentage_change", ["E1", "E2"], "revenue_growth", True),
                operation("percentage_change", ["E3", "E4"], "profit_growth", True),
                operation("greater", ["revenue_growth", "profit_growth"], across=True),
            ],
        ),
        (
            "MH11",
            "Giá vốn so với doanh thu kỳ này?",
            [(costs, "2025"), (rev, "2025")],
            [operation("ratio", ["E1", "E2"])],
        ),
        (
            "MH12",
            "Tổng tài sản thay đổi bao nhiêu trong năm?",
            [(assets, "2025-12-31"), (assets, "2025-01-01")],
            [operation("percentage_change", ["E1", "E2"], across=True)],
        ),
        (
            "MH13",
            "Đối chiếu CFO/doanh thu với PAT/doanh thu?",
            [(cfo, "2025"), (rev, "2025"), (pat, "2025")],
            [
                operation("ratio", ["E1", "E2"], "cash_share"),
                operation("ratio", ["E3", "E2"], "profit_share"),
                operation("greater", ["cash_share", "profit_share"]),
            ],
        ),
        (
            "MH14",
            "Dòng tiền kinh doanh thay đổi thế nào?",
            [(cfo, "2025"), (cfo, "2024")],
            [operation("subtract", ["E1", "E2"], across=True)],
        ),
        (
            "MH15",
            "Tổng doanh thu của hai kỳ?",
            [(rev, "2025"), (rev, "2024")],
            [operation("sum", ["E1", "E2"], across=True)],
        ),
        (
            "MH16",
            "Doanh thu trung bình hai kỳ?",
            [(rev, "2025"), (rev, "2024")],
            [operation("mean", ["E1", "E2"], across=True)],
        ),
    ]
    results = []
    for case_id, question, targets, operations in cases:
        started = perf_counter()
        row = dict(
            id=case_id,
            question=question,
            evaluation="offline_real_source_derived_only",
            provider_calls=0,
        )
        try:
            sources = []
            for index, (item, period) in enumerate(targets, 1):
                matches = [
                    f for f in facts if f.canonical_item_id == item and f.context.period == period
                ]
                if len(matches) != 1:
                    raise ValueError("source_missing_or_ambiguous:" + item + ":" + period)
                fact = matches[0]
                lookup = tools.get_financial_fact(
                    GetFinancialFactRequest(
                        document_id=fact.document_id,
                        snapshot_id=fact.snapshot_id,
                        local_observation_id=fact.local_observation_id,
                    )
                )
                if lookup.status != "found" or len(lookup.matches) != 1:
                    raise ValueError("source_unavailable")
                match = lookup.matches[0]
                sources.append(
                    SpecialistEvidence(
                        evidence_id=f"E{index}",
                        kind="fact",
                        reference=match.reference,
                        company_id=fact.company_id,
                        document_id=fact.document_id,
                        snapshot_id=fact.snapshot_id,
                        period=period,
                        label=labels[item],
                        value=str(fact.value.normalized_value),
                        unit=fact.value.unit,
                        scale=str(fact.context.scale),
                        canonical_item_id=item,
                        citations=match.citations,
                        caveats=list(
                            set(
                                match.issues
                                + lookup.caveats
                                + [c for citation in match.citations for c in citation.limitations]
                            )
                        ),
                    )
                )
            computation = calculator.calculate_dynamic(
                {s.evidence_id: s.reference for s in sources}, operations
            )
            owner = sources[0]
            refs = [s.reference for s in sources]
            citations = list(
                {c.model_dump_json(): c for s in sources for c in s.citations}.values()
            )
            claim = CandidateClaim(
                candidate_id=case_id,
                kind="supported_interpretation",
                content=render_dynamic(computation, {s.evidence_id: s.label for s in sources}),
                company_id=owner.company_id,
                document_id=owner.document_id,
                snapshot_id=owner.snapshot_id,
                period=owner.period,
                fact_references=refs,
                supporting_evidence_ids=[s.evidence_id for s in sources],
                citations=citations,
                supporting_evidence=sources,
                provenance=ClaimProvenance(
                    m5_candidate_id=case_id, origins=[], origin_roles=[], supporting_references=refs
                ),
                analysis_premises=[
                    f"{s.label} {'tại ngày' if len(s.period) > 4 else 'kỳ'} {s.period} là {_number(s.value)} {s.unit}"
                    + (f" (hệ số đơn vị {s.scale})" if s.scale != "1" else "")
                    + "."
                    for s in sources
                ],
                reasoning=ReasoningProof(
                    claim_type="derived_fact", goal=question, calculation=computation
                ),
            )
            batch = VerificationInput(
                source_version="financial_multi_agent_orchestration_v1",
                source_result_sha256=hashlib.sha256(claim.model_dump_json().encode()).hexdigest(),
                question=question,
                context=PlannerContext(
                    document_id=owner.document_id,
                    snapshot_id=owner.snapshot_id,
                    company_id=owner.company_id,
                ),
                orchestration_status="completed",
                claims=[claim],
            )
            validation = DeterministicFinancialValidator(catalog).validate(batch)
            evidence = EvidenceCritic(catalog).assess(batch, validation)
            logic = FinancialLogicCritic().assess(batch, validation, evidence)
            history = VerificationHistory(
                contexts=[
                    VerificationProofContext(
                        batch=batch, validation=validation, evidence=evidence, logic=logic
                    )
                ],
                outcome=BoundedVerificationLoop().start(
                    batch, validation, evidence, logic, candidate_id=case_id
                ),
            )
            row["decision"] = history.outcome.final.decision
            row["reason_codes"] = history.outcome.final.reason_codes
            row["blockers"] = history.outcome.final.unresolved_blockers
            save(args.output / "cases" / (case_id + ".json"), history.model_dump(mode="json"))
            if row["decision"] == "ACCEPT":
                pipeline.repository.admit(history)
                ledger = VerifiedClaimLedger(pipeline.repository)
                request = VietnameseQARequest(
                    question=question,
                    company_id=owner.company_id,
                    document_id=owner.document_id,
                    snapshot_id=owner.snapshot_id,
                    period=owner.period,
                    answer_requirements=[
                        QARequirement(
                            requirement_id=case_id,
                            text=question,
                            kind="fact",
                            target_id=owner.canonical_item_id,
                            interpretation=True,
                            interpretation_topic="dynamic_calculation",
                            required_indicators=[s.canonical_item_id for s in sources],
                            reasoning_operations=[o.operator for o in operations],
                            reasoning_periods=sorted({s.period for s in sources}),
                        )
                    ],
                )
                answer = VietnameseQAComposer(ledger).compose(request)
                rendered = CitationRenderer().render_qa(answer)
                firewall = InformationFirewall(ledger).evaluate_qa(
                    request=request, response=answer, rendered=rendered
                )
                row.update(
                    m7_status=answer.status,
                    firewall=firewall.decision,
                    citations=len(rendered.references),
                    text=rendered.rendered_text,
                    operations=computation.model_dump(mode="json"),
                )
        except (ValueError, ArithmeticError, KeyError) as error:
            row["error"] = str(error)
        row["elapsed_ms"] = (perf_counter() - started) * 1000
        results.append(row)
        save(args.output / "results.json", results)
        print(case_id, row.get("decision", row.get("error")), row.get("m7_status"), flush=True)
    historical = []
    for name in [
        "planner-dependencies/live",
        "controlled-live-9a356bf/run",
        "flexible-contracts/live",
    ]:
        path = root / "artifacts/evidence/FIX-02" / name / "ledger/verified-claims.json"
        before = digest(path)
        entries = json.loads(path.read_bytes())["entries"]
        for entry in entries:
            replay_history(VerificationHistory.model_validate_json(json.dumps(entry["history"])))
        historical.append(dict(path=name, count=len(entries), unchanged=before == digest(path)))
    save(
        args.output / "summary.json",
        dict(
            cases=len(results),
            accepted=sum(r.get("decision") == "ACCEPT" for r in results),
            answered=sum(r.get("m7_status") == "answered" for r in results),
            historical=historical,
            provider_calls=0,
            limitation="Offline deterministic derived probes; no LLM reasoning or whole-PDF accuracy claim.",
        ),
    )


if __name__ == "__main__":
    main()
