"""Focused M5 contracts; synthetic controls không chứng minh financial accuracy."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.agents import (
    SPECIALIST_BOUNDARIES,
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
    FinancialRetrievalTools,
    FindFinancialFactsRequest,
)
from vietnamese_financial_multi_agent.tools.question_understanding import QAUnderstanding

from .test_m4_execution import fixture


def plan_for(data, *, calculated=False):
    fact, metric = data["facts"][0], data["metrics"][0]
    selector = EvidenceSelector(document_id=fact.document_id, snapshot_id=fact.snapshot_id)
    requirement = EvidenceRequirement(
        requirement_id="evidence",
        evidence_type="metric" if calculated else "fact",
        canonical_item_id=None if calculated else fact.canonical_item_id,
        selector=selector
        if calculated
        else EvidenceSelector(**selector.model_dump(exclude_none=True), period=fact.context.period),
    )
    tool = "calculate_financial_metric" if calculated else "find_financial_facts"
    arguments = {
        **selector.model_dump(exclude_none=True),
        **(
            {"metric_id": metric.metric_id}
            if calculated
            else {"canonical_item_id": fact.canonical_item_id, "period": fact.context.period}
        ),
    }
    return EvidencePlan(
        plan_id="independent-control",
        query=QuerySpecification(
            original_question="Câu hỏi kiểm tra",
            intent="calculated_metric" if calculated else "direct_fact",
            analysis_type="control",
            selectors=[selector],
        ),
        requirements=[requirement],
        steps=[
            PlanStep(
                step_id="retrieve",
                step_type="tool",
                tool=tool,
                selector=selector,
                arguments=arguments,
                output_evidence_ids=["evidence"],
                formula_id=metric.definition.name if calculated else None,
                expected_result_type=TOOL_CONTRACTS[tool][1].__name__,
            )
        ],
        stop_conditions=["all_required_evidence_resolved", "compatibility_gate_blocked"],
    )


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_step",
        "duplicate_requirement",
        "unknown_step",
        "unknown_requirement",
        "step_cycle",
        "requirement_cycle",
        "combined_cycle",
        "tool",
        "arguments",
        "selector",
        "completed",
        "binding_path",
        "binding_target",
        "binding_prerequisite",
        "result_type",
        "verified",
    ],
)
def test_structural_rejections(change):
    plan = plan_for(fixture()).model_dump()
    step, requirement = plan["steps"][0], plan["requirements"][0]
    if change == "duplicate_step":
        plan["steps"].append(deepcopy(step))
    elif change == "duplicate_requirement":
        plan["requirements"].append(deepcopy(requirement))
    elif change == "unknown_step":
        step["prerequisite_step_ids"] = ["absent"]
    elif change == "unknown_requirement":
        step["required_evidence_ids"] = ["absent"]
    elif change == "step_cycle":
        step["prerequisite_step_ids"] = [step["step_id"]]
    elif change == "requirement_cycle":
        requirement["dependencies"] = [requirement["requirement_id"]]
    elif change == "combined_cycle":
        step["required_evidence_ids"] = [requirement["requirement_id"]]
    elif change == "tool":
        step["tool"] = "invented_tool"
    elif change == "arguments":
        step["arguments"]["made_up"] = "argument"
    elif change == "selector":
        step["arguments"]["period"] = "1999"
        step["selector"]["period"] = "2000"
    elif change == "completed":
        plan["state"] = "completed"
    elif change.startswith("binding"):
        source = deepcopy(step)
        source["step_id"] = "source"
        plan["steps"].insert(0, source)
        step["prerequisite_step_ids"] = [] if change == "binding_prerequisite" else ["source"]
        step["input_bindings"] = [
            {
                "argument": "bogus" if change == "binding_target" else "document_id",
                "source_step_id": "source",
                "output_path": "matches.0.does_not_exist"
                if change == "binding_path"
                else "matches.0.record.document_id",
            }
        ]
        del step["arguments"]["document_id"]
    elif change == "result_type":
        step["expected_result_type"] = "MadeUpResponse"
    elif change == "verified":
        requirement["financial_fact_verified"] = True
    result = validate_plan(plan)
    assert result.disposition == "invalid" and not result.structurally_valid and result.errors


def test_bindings_roundtrip_and_m4_api_compatibility():
    data = fixture()
    plan = plan_for(data)
    source = plan.steps[0]
    plan.requirements.append(
        EvidenceRequirement(requirement_id="sources", evidence_type="citations")
    )
    plan.steps.append(
        PlanStep(
            step_id="sources",
            step_type="tool",
            tool="get_evidence_sources",
            selector=source.selector,
            prerequisite_step_ids=[source.step_id],
            input_bindings=[
                dict(
                    argument="reference",
                    source_step_id=source.step_id,
                    output_path="matches.0.reference",
                )
            ],
            output_evidence_ids=["sources"],
            expected_result_type="EvidenceToolResponse",
        )
    )
    plan = EvidencePlan.model_validate_json(plan.model_dump_json())
    assert EvidencePlan.model_validate_json(plan.model_dump_json()) == plan
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    response = tools.find_financial_facts(FindFinancialFactsRequest(**source.arguments))
    request = bind_step_request(plan, "sources", {source.step_id: response})
    assert request.reference == response.matches[0].reference
    assert request.tool == "get_evidence_sources"
    bad = response.model_copy(deep=True)
    bad.matches[0].reference.observation = bad.matches[0].reference.observation.model_copy(
        update={"document_id": "wrong"}
    )
    with pytest.raises(ValueError, match="selector_binding_conflict"):
        bind_step_request(plan, "sources", {source.step_id: bad})
    bad = response.model_copy(update={"matches": []})
    with pytest.raises(ValueError, match="binding_output_unavailable"):
        bind_step_request(plan, "sources", {source.step_id: bad})
    parsed = QAUnderstanding(
        intent="calculated_metric", formula_id="gross_margin", reporting_year=2030
    )
    query = QuerySpecification.from_understanding("Biên lợi nhuận?", parsed)
    assert query.requested_formula_ids == ["gross_margin"] and query.reporting_year == 2030
    assert len(SPECIALIST_BOUNDARIES) == 3
    assert all(not b.can_verify_claims for b in SPECIALIST_BOUNDARIES)


@pytest.mark.parametrize(
    "case",
    [
        "eligible",
        "no_catalog",
        "formula",
        "cross_document",
        "ambiguity",
        "missing",
        "optional",
        "limit",
        "scope",
        "quality",
        "completion",
        "source_conflict",
        "requirement_scope",
        "period_unit",
        "lineage",
    ],
)
def test_execution_gate_and_quality(case):
    data = fixture()
    plan = plan_for(data, calculated=case in {"formula", "eligible", "period_unit", "lineage"})
    if case == "formula":
        data["formula_approvals"] = []
    elif case == "cross_document":
        plan.query.cross_document_comparison = True
    elif case == "ambiguity":
        descriptor = data["descriptors"][0].model_copy(update={"snapshot_id": "another"})
        data["descriptors"].append(descriptor)
        plan.steps[0].selector.snapshot_id = None
        plan.steps[0].arguments.pop("snapshot_id")
        plan.requirements[0].selector.snapshot_id = None
    elif case in {"missing", "optional"}:
        req = EvidenceRequirement(
            requirement_id="missing",
            evidence_type="text",
            resolution="missing",
            importance="optional" if case == "optional" else "required",
            reasons=["no_record"],
        )
        plan.requirements.append(req)
    elif case == "limit":
        plan.execution_limit = 1
    elif case == "scope":
        plan.query.reporting_scope = "consolidated"
        plan.steps[0].selector.reporting_scope = "consolidated"
    elif case == "quality":
        for fact in data["facts"]:
            for quality in fact.quality_context:
                quality.decision = "insufficient"
    elif case == "completion":
        plan.requirements[0].resolution = "found"
        plan.state = "completed"
    elif case == "source_conflict":
        data["source_reviews"][0].raw_value = "999"
    elif case == "requirement_scope":
        plan.requirements[0].selector.reporting_scope = "consolidated"
    elif case == "period_unit":
        data["facts"][0].context.currency = "USD"
    elif case == "lineage":
        data["graph"].edges = []
    catalog = None if case == "no_catalog" else SnapshotCatalog(**data)
    result = validate_plan(plan, catalog=catalog, executed_steps=1 if case == "limit" else 0)
    assert result.disposition == (
        "valid"
        if case in {"eligible", "optional"}
        else "invalid"
        if case == "completion"
        else "blocked"
    )
    if case == "eligible":
        assert not result.financial_fact_verified
    if case == "optional":
        assert not next(r for r in result.risks if r.requirement_ids == ["missing"]).blocking
    if case == "completion":
        assert not result.structurally_valid
    if case == "formula":
        assert any(r.code == "formula_not_approved" for r in result.risks)
    if case == "source_conflict":
        assert "conflicting_evidence" in result.triggered_stop_conditions
    if case == "period_unit":
        assert any(r.code == "period_unit_mismatch" for r in result.risks)
    if case == "lineage":
        assert any(r.code == "incomplete_lineage" for r in result.risks)
    with pytest.raises(ValidationError):
        EvidenceRequirement(requirement_id="invalid", evidence_type="fact", resolution="verified")


def test_completion_preserves_quality_and_optional_evidence():
    data = fixture()
    plan = plan_for(data)
    response = FinancialRetrievalTools(SnapshotCatalog(**data)).find_financial_facts(
        FindFinancialFactsRequest(**plan.steps[0].arguments)
    )
    req = plan.requirements[0]
    req.references = [m.reference for m in response.matches]
    req.citations = [c for m in response.matches for c in m.citations]
    req.quality_decisions = ["usable_with_caveat"]
    req.caveats = ["source_grounding_is_not_independent_verification"]
    req.resolution = "resolved"
    plan.steps[0].status = "completed"
    plan.state = "completed"
    plan.requirements.append(
        EvidenceRequirement(
            requirement_id="optional",
            evidence_type="text",
            importance="optional",
            resolution="missing",
            reasons=["not_needed"],
        )
    )
    result = validate_plan(plan, catalog=SnapshotCatalog(**data))
    assert result.execution_eligible
    assert "all_required_evidence_resolved" in result.triggered_stop_conditions
    assert not result.financial_fact_verified
    req.caveats = []
    assert validate_plan(plan).disposition == "invalid"
