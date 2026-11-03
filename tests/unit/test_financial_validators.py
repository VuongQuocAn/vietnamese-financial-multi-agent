"""Synthetic controls only; persisted-source BBS evaluation is a separate runner."""

from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.agents import PlannerContext
from vietnamese_financial_multi_agent.agents.orchestration_contracts import CandidateConflict
from vietnamese_financial_multi_agent.agents.profitability_specialist import ITEM_LABELS
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistEvidence, _number
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculator,
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)
from vietnamese_financial_multi_agent.verification import (
    CandidateClaim,
    ClaimProvenance,
    DeterministicFinancialValidator,
    ValidationResult,
    VerificationInput,
)
from vietnamese_financial_multi_agent.verification.numeric import extract_assertion, parse_number

from .test_m4_execution import fixture


def batch_for(data, metric=False):
    catalog = SnapshotCatalog(**data)
    if metric:
        calc = FinancialCalculator(catalog).calculate_financial_metric(
            CalculateFinancialMetricRequest(
                metric_id=data["metrics"][0].metric_id,
                document_id=data["descriptors"][0].document_id,
                snapshot_id=data["descriptors"][0].snapshot_id,
            )
        )
        assert calc.status == "computed", calc.reasons
        role = {
            "gross_margin": "revenue",
            "debt_to_assets": "assets",
            "revenue_yoy": "current_revenue",
        }[calc.formula_id]
        operand = next(o for o in calc.trace.operands if o.role == role)
        labels = {
            "gross_margin": "Biên lợi nhuận gộp",
            "debt_to_assets": "Debt to Assets",
            "revenue_yoy": "Tăng trưởng doanh thu",
        }
        evidence = SpecialistEvidence(
            evidence_id="E1",
            kind="metric",
            reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
            company_id=operand.company_id,
            document_id=calc.document_id,
            snapshot_id=calc.snapshot_id,
            period=operand.context.period,
            operand_periods=calc.evidence.record.request.operand_periods,
            label=labels[calc.formula_id],
            value=calc.result,
            unit="percent",
            citations=calc.evidence.citations,
            caveats=calc.caveats,
            calculation=calc,
        )
        refs = [
            RetrievalReference(kind="fact", observation=o.observation) for o in calc.trace.operands
        ]
        phrase = "tại ngày" if calc.formula_id == "debt_to_assets" else "kỳ"
        content = f"{evidence.label} {phrase} {evidence.period} là {_number(evidence.value)}%."
    else:
        calc = None
        fact = data["facts"][0]
        match = (
            FinancialRetrievalTools(catalog)
            .get_financial_fact(
                GetFinancialFactRequest(
                    document_id=fact.document_id,
                    snapshot_id=fact.snapshot_id,
                    local_observation_id=fact.local_observation_id,
                )
            )
            .matches[0]
        )
        evidence = SpecialistEvidence(
            evidence_id="E1",
            kind="fact",
            reference=match.reference,
            company_id=fact.company_id,
            document_id=fact.document_id,
            snapshot_id=fact.snapshot_id,
            period=fact.context.period,
            label=ITEM_LABELS[fact.canonical_item_id],
            canonical_item_id=fact.canonical_item_id,
            value=str(fact.value.normalized_value),
            unit=fact.value.unit,
            scale=str(fact.context.scale),
            citations=match.citations,
            caveats=[],
        )
        refs = [match.reference]
        content = f"{evidence.label} kỳ {evidence.period} là {_number(evidence.value)} VND."
    claim = CandidateClaim(
        candidate_id="C1",
        kind="approved_metric" if metric else "fact",
        content=content,
        company_id=evidence.company_id,
        document_id=evidence.document_id,
        snapshot_id=evidence.snapshot_id,
        period=evidence.period,
        fact_references=refs,
        metric_ids=[calc.metric_id] if calc else [],
        supporting_evidence_ids=["E1"],
        citations=evidence.citations,
        calculation=calc,
        supporting_evidence=[evidence],
        provenance=ClaimProvenance(
            m5_candidate_id="C1",
            origins=[],
            origin_roles=[],
            supporting_references=[evidence.reference],
        ),
    )
    return VerificationInput(
        source_version="financial_multi_agent_orchestration_v1",
        source_result_sha256="a" * 64,
        question="synthetic",
        context=PlannerContext(),
        orchestration_status="completed",
        claims=[claim],
    )


def checks(data, batch):
    return {
        c.check_id: c
        for c in DeterministicFinancialValidator(SnapshotCatalog(**data))
        .validate(batch)
        .claims[0]
        .checks
    }


@pytest.mark.parametrize(
    "text,value",
    [
        ("450.474.531.227", "450474531227"),
        ("-1.234,56", "-1234.56"),
        ("−7,21", "-7.21"),
        ("+7.21", "7.21"),
        ("0", "0"),
        ("1.2.34", None),
    ],
)
def test_decimal_formats(text, value):
    assert parse_number(text) == (Decimal(value) if value is not None else None)


@pytest.mark.parametrize("formula", ["gross_margin", "debt_to_assets", "revenue_yoy"])
def test_independent_metric_replay_roundtrip_and_isolation(formula):
    data = fixture(formula)
    batch = batch_for(data, metric=True)
    validator = DeterministicFinancialValidator(SnapshotCatalog(**data))
    before = batch.model_dump_json()
    result = validator.validate(batch)
    by_id = {c.check_id: c for c in result.claims[0].checks}
    assert all(c.status != "fail" for c in by_id.values()), by_id
    assert all(
        by_id[k].status == "pass"
        for k in (
            "numeric",
            "formula",
            "calculation_result",
            "calculation_trace",
            "calculation_lineage",
        )
    )
    assert ValidationResult.model_validate_json(result.model_dump_json()) == result
    assert batch.model_dump_json() == before and not result.financial_fact_verified
    data["facts"][0].value.normalized_value += 1
    assert validator.validate(batch) == result


def test_fact_prose_and_supporting_copy_are_checked_against_catalog():
    data = fixture()
    batch = batch_for(data)
    correct = checks(data, batch)
    assert correct["numeric"].status == correct["context"].status == "pass"
    claim = batch.claims[0]
    claim.content = claim.content.replace(_number(claim.supporting_evidence[0].value), "999.999")
    claim.supporting_evidence[0].value = "999999"
    observed = checks(data, batch)
    assert observed["numeric"].status == observed["supporting_fact"].status == "fail"
    assert observed["provenance"].status == "pass"


@pytest.mark.parametrize(
    "control,check",
    [
        ("period", "context"),
        ("content_period", "context"),
        ("document_id", "context"),
        ("snapshot_id", "context"),
        ("company_id", "context"),
        ("item", "item"),
        ("unit", "unit_scale"),
        ("scale", "unit_scale"),
        ("citation", "provenance"),
    ],
)
def test_proven_context_corruptions_fail(control, check):
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    if control in {"period", "document_id", "snapshot_id", "company_id"}:
        setattr(claim, control, "wrong")
    elif control == "content_period":
        claim.content = claim.content.replace(claim.period, "2024")
    elif control == "item":
        claim.content = claim.content.replace("Lợi nhuận gộp", "Doanh thu thuần")
    elif control == "unit":
        claim.content = claim.content.replace("VND", "USD")
    elif control == "scale":
        claim.content = claim.content.replace("VND", "triệu đồng")
    else:
        claim.citations[0].pdf_page += 1
    assert checks(data, batch)[check].status == "fail"


@pytest.mark.parametrize(
    "control,check",
    [
        ("content", "numeric"),
        ("result", "calculation_result"),
        ("formula", "formula"),
        ("operand", "calculation_trace"),
        ("lineage", "calculation_lineage"),
        ("trace_missing", "calculation_trace"),
        ("calc_missing", "formula"),
    ],
)
def test_metric_corruptions_and_missing_evidence(control, check):
    data = fixture()
    batch = batch_for(data, metric=True)
    claim = batch.claims[0]
    if control == "content":
        claim.content = claim.content.replace(_number(claim.calculation.result), "999,99")
    elif control == "result":
        claim.calculation.result = "999.99"
    elif control == "formula":
        claim.calculation.formula_id = "ROE"
    elif control == "operand":
        claim.calculation.trace.operands[0].value = "999"
    elif control == "lineage":
        claim.calculation.evidence.reviewed_lineage.lineage.operands.clear()
    elif control == "trace_missing":
        claim.calculation.trace = None
    else:
        claim.calculation = None
    assert checks(data, batch)[check].status == (
        "undetermined" if control in {"trace_missing", "calc_missing"} else "fail"
    )


def test_unresolved_scope_conflict_and_interpretation_do_not_become_decisions():
    data = fixture()
    batch = batch_for(data, metric=True)
    batch.claims[0].kind = "supported_interpretation"
    batch.claims[0].content += " Điều này chứng tỏ doanh nghiệp hoạt động hiệu quả hơn."
    batch.conflicts = [CandidateConflict(conflict_id="conflict", candidate_ids=["C1", "C2"])]
    result = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch)
    by_id = {c.check_id: c for c in result.claims[0].checks}
    assert by_id["numeric"].status == "pass"
    assert by_id["semantic_conclusion"].status == "undetermined"
    assert by_id["reporting_scope"].status == "undetermined"
    assert by_id["candidate_conflict"].candidate_ids == ["C1", "C2"]
    assert result.conflicts == batch.conflicts and batch.claims[0].decision is None
    data["facts"] = []
    assert checks(data, batch)["numeric"].status == "undetermined"


def test_missing_or_ambiguous_prose_never_produces_numeric_pass():
    data = fixture()
    batch = batch_for(data)
    for content in (
        "Không có con số để kiểm tra.",
        "Doanh thu 2025: 100 và 200.",
        batch.claims[0].content + " Doanh thu năm 2030 là 999 VND.",
    ):
        batch.claims[0].content = content
        assert checks(data, batch)["numeric"].status == "undetermined"
    assert extract_assertion("Doanh thu năm 2025 là 450.474.531.227 đồng.").value == Decimal(
        "450474531227"
    )


def test_missing_nested_lineage_and_results_are_undetermined():
    data = fixture()
    batch = batch_for(data, metric=True)
    batch.claims[0].calculation.evidence.reviewed_lineage.lineage = None
    batch.claims[0].calculation.result = None
    result = checks(data, batch)
    assert result["calculation_lineage"].status == "undetermined"
    assert result["calculation_result"].status == "undetermined"
    assert result["numeric"].status == "pass"


def test_one_bad_claim_does_not_hide_other_results_or_quality_caveats():
    data = fixture()
    data["facts"][0].quality_context[0].decision = "usable_with_caveat"
    data["facts"][0].quality_context[0].caveats.append("synthetic-caveat")
    batch = batch_for(data)
    other = batch.claims[0].model_copy(deep=True)
    other.candidate_id = other.provenance.m5_candidate_id = "C2"
    other.content = other.content.replace(_number(other.supporting_evidence[0].value), "999.999")
    batch.claims.insert(0, other)
    result = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch)
    assert len(result.claims) == 2
    numeric = [next(c.status for c in r.checks if c.check_id == "numeric") for r in result.claims]
    assert numeric == ["fail", "pass"]
    assert "synthetic-caveat" in result.claims[1].caveats
