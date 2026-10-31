"""Focused D-02 controls; synthetic PASS không chứng minh accuracy PDF."""

import importlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.accounting.quality import QualityIssue
from vietnamese_financial_multi_agent.evidence import TaskQualityContext
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
    assess_analytical_readiness,
    source_review_status,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
    check_formula_policy,
)

from .test_evidence_contracts import scenario


def registry():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "configs/d02-analytical-policies.json").read_text(
            encoding="utf-8"
        )
    )


def preparation_approval():
    return PreparationApproval(**registry()["preparation_approval"])


def sample():
    spec, operands = scenario()
    for o in operands:
        f = o.fact
        f.document_id = "sha256:" + "a" * 64
        f.value.raw_value = "1.234"
        f.context.reporting_scope = None
        f.raw_header = "Năm 2024"
        f.resolution_issues = [QualityIssue(code="missing_reporting_scope", detail="unknown")]
        f.quality_context = [
            TaskQualityContext(
                task_type="direct_qa",
                decision="usable_with_caveat",
                evidence_ids=[f.local_observation_id],
            )
        ]
        base = f.sources[0]
        base.document_id = f.document_id
        base.reference.anchor.page.source_ref = f.document_id
        base.reference.anchor.status = "uncertain"
        base.reference.source_pointer = "/tables/0/cells/2"
        label, header = base.model_copy(deep=True), base.model_copy(deep=True)
        label.reference.source_pointer = "/tables/0/cells/0"
        header.reference.source_pointer = "/tables/0/headers/0"
        f.sources = [base, label, header]
    reviews = [
        SourceReview(
            observation=f.observation_identity(),
            sources=f.sources,
            pdf_sha256="a" * 64,
            pdf_page=7,
            review_image_sha256="b" * 64,
            review_reference="synthetic-review",
            method="controlled_original_pdf_visual_read",
            level="value_row_verified",
            value_selector="/tables/0/cells/2",
            label_selector="/tables/0/cells/0",
            header_selector="/tables/0/headers/0",
            raw_value=f.value.raw_value,
            raw_label=f.context.raw_item_label,
            raw_header=f.raw_header,
            period=f.context.period,
            statement_type=f.context.statement_type,
        )
        for f in [o.fact for o in operands]
    ]
    bases = [
        AccountingBasisReview(
            document_id=operands[0].fact.document_id,
            snapshot_id="attempt-1",
            pdf_sha256="a" * 64,
            pdf_page=9,
            review_image_sha256="c" * 64,
            review_reference="synthetic-basis",
            method="controlled_original_pdf_visual_read",
            source_quote="synthetic basis evidence",
            basis="VAS/TT200/accrual-historical-cost",
            statement_types=["B01", "B02"],
        )
    ]
    return spec, operands, reviews, bases


def test_candidate_is_separate_from_approval_and_preserves_original_sources():
    spec, operands, reviews, bases = sample()
    before = [o.model_dump_json() for o in operands]
    result = assess_analytical_readiness(spec, operands, reviews, bases)
    assert result["candidate_compatibility"] == "compatible"
    assert result["preparation_source_ready"] is True
    assert result["approved_compatibility"]["status"] == "undetermined"
    assert result["calculation_eligible"] is False
    assert result["policy_status"] == "experimental_pending_tech_lead"
    assert not result["preparation_ready"]
    approved = assess_analytical_readiness(
        spec, operands, reviews, bases, approval=preparation_approval()
    )
    assert approved["global_compatibility"] == result["approved_compatibility"]
    assert approved["approved_profile_compatibility"]["status"] == "compatible"
    assert approved["preparation_ready"] and not approved["calculation_eligible"]
    assert approved["approved_profile_compatibility"]["approval_reference"]
    assert "formula_policy_not_approved" in approved["eligibility_blockers"]
    assert "global_execution_compatibility_not_established" in approved["eligibility_blockers"]
    for field, value in (
        ("profile", "D-02/document-statement-v2"),
        ("purpose", "formula_execution"),
    ):
        with pytest.raises(ValidationError):
            PreparationApproval(**{**registry()["preparation_approval"], field: value})
    assert [o.model_dump_json() for o in operands] == before
    assert source_review_status(operands[0].fact, []) == "unverified"
    page = reviews[0].model_copy(update={"level": "page_resolved"})
    assert source_review_status(operands[0].fact, [page]) == "page_resolved"
    with pytest.raises(ValidationError):
        SourceReview(**{**reviews[0].model_dump(), "level": "cell_verified"})


@pytest.mark.parametrize(
    "control",
    [
        "different_scope",
        "cross_document",
        "wrong_period",
        "wrong_unit",
        "wrong_scale",
        "wrong_value",
        "wrong_row",
        "missing_source",
        "quality_insufficient",
        "quality_conflicted",
        "different_snapshot",
        "unknown_basis",
        "unresolved_context",
        "missing_period",
        "different_statement",
        "wrong_normalized_value",
    ],
)
def test_known_conflicts_and_missing_context_never_become_eligible(control):
    spec, operands, reviews, bases = sample()
    f = operands[1].fact
    if control == "different_scope":
        operands[0].fact.context.reporting_scope = "separate"
        f.context.reporting_scope = "consolidated"
    elif control == "cross_document":
        f.document_id = "sha256:" + "d" * 64
    elif control == "wrong_period":
        f.context.period = "2023"
    elif control == "wrong_unit":
        f.value.unit = "USD"
    elif control == "wrong_scale":
        f.context.scale = Decimal("1000")
    elif control == "wrong_value":
        reviews[1].raw_value = "wrong"
    elif control == "wrong_row":
        reviews[1].raw_label = "another row with same number"
    elif control == "missing_source":
        f.sources = []
    elif control.startswith("quality_"):
        f.quality_context[0].decision = control.removeprefix("quality_")
    elif control == "different_snapshot":
        f.snapshot_id = "attempt-2"
    elif control == "unknown_basis":
        bases = []
    elif control == "unresolved_context":
        f.resolution_issues.append(
            QualityIssue(code="m2_extraction_issue", detail="table_position_conflict")
        )
    elif control == "missing_period":
        f.context.period = None
    elif control == "different_statement":
        f.context.statement_type = "B01"
    elif control == "wrong_normalized_value":
        f.value.normalized_value = Decimal("999")
    result = assess_analytical_readiness(
        spec, operands, reviews, bases, approval=preparation_approval()
    )
    assert result["candidate_compatibility"] in {"undetermined", "incompatible"}
    assert result["calculation_eligible"] is False
    assert result["candidate_blockers"]
    assert result["approved_profile_compatibility"]["status"] != "compatible"
    assert not result["preparation_ready"]


def test_ambiguous_position_and_output_overwrite_are_rejected(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("evaluate_d02_blockers")
    _, operands, reviews, _ = sample()
    f = operands[0].fact
    reading = reviews[0].model_dump(
        exclude={"sources", "value_selector", "label_selector", "header_selector"}
    )
    cells = [
        dict(text=f.context.raw_item_label, row=1, column=0, reading="observed"),
        dict(text="10", row=1, column=1, reading="observed"),
        dict(text=f.value.raw_value, row=1, column=2, reading="observed"),
    ]
    table = dict(
        cells=cells, headers=[dict(text=f.raw_header, row=0, column=2, reading="observed")]
    )
    record = dict(response=dict(output=dict(payload=dict(tables=[table]))))
    assert module.bind_review(f, reading, record).level == "value_row_verified"
    cells.append(dict(cells[2]))
    with pytest.raises(ValueError, match="ambiguous_review_position"):
        module.bind_review(f, reading, record)
    path = tmp_path / "original-attempt.json"
    module.save(path, {"original": True})
    with pytest.raises(ValueError, match="output_changed"):
        module.save(path, {"original": False})
    assert module.load(path) == {"original": True}


@pytest.mark.parametrize("formula_id", ["gross_margin", "debt_to_assets", "revenue_yoy"])
def test_formula_preflight_and_explicit_execution_approval(formula_id, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    definitions = importlib.import_module("validate_m3_metrics")
    definition, periods = next((d, p) for d, p in definitions.examples() if d.name == formula_id)
    policy = PreparedFormulaPolicy(
        **next(p for p in registry()["formula_policies"] if p["formula_id"] == formula_id)
    )
    _, operands, _, _ = sample()
    for operand, req in zip(operands, policy.operands, strict=True):
        operand.role = req.role
        operand.fact.canonical_item_id = req.canonical_item_id
        operand.fact.semantic_role = req.semantic_role
        operand.fact.context.statement_type = req.statement_type
        operand.fact.context.period = periods[req.role]
        operand.fact.context.period_type = "as_of" if req.statement_type == "B01" else "fiscal_year"
    result = check_formula_policy(policy, definition.compatibility, operands, [])
    assert not result["blockers"] and not result["execution_approved"]
    assert result["status"] == "draft_pending_tech_lead"
    assert registry()["formula_execution_approvals"] == []
    original_type = operands[0].fact.context.period_type
    operands[0].fact.context.period_type = "quarter"
    assert (
        "formula_period_type_mismatch"
        in check_formula_policy(policy, definition.compatibility, operands, [])["blockers"]
    )
    operands[0].fact.context.period_type = original_type
    original_item = operands[0].fact.canonical_item_id
    operands[0].fact.canonical_item_id = "wrong.item"
    assert (
        "formula_fact_semantics_mismatch"
        in check_formula_policy(policy, definition.compatibility, operands, [])["blockers"]
    )
    operands[0].fact.canonical_item_id = original_item
    # An explicit reviewed definition/version/digest is needed; a status flag is not input.
    approval = FormulaExecutionApproval(
        formula_id=formula_id,
        version=policy.version,
        definition_sha256=policy.definition_digest(),
        authority="Tech Lead",
        purpose="formula_execution",
        decision_reference="synthetic-only-decision",
        negative_controls_reference="synthetic-only-reviewed-controls",
    )
    assert check_formula_policy(policy, definition.compatibility, operands, [approval])[
        "execution_approved"
    ]
    for field in ("version", "definition_sha256"):
        wrong = approval.model_copy(update={field: "not-the-reviewed-definition"})
        assert not check_formula_policy(policy, definition.compatibility, operands, [wrong])[
            "execution_approved"
        ]
    with pytest.raises(ValidationError):
        FormulaExecutionApproval(**{**approval.model_dump(), "negative_controls_reference": ""})
    for field, value in (
        ("precision", 5),
        ("rounding", "ROUND_DOWN"),
        ("output_unit", "VND"),
        ("output_quantum", "1"),
    ):
        with pytest.raises(ValidationError):
            PreparedFormulaPolicy(**{**policy.model_dump(), field: value})
    denominator = next(o.fact for o in operands if o.role == policy.denominator_role)
    for invalid in (Decimal("0"), Decimal("-1")):
        denominator.value.normalized_value = invalid
        assert (
            "denominator_non_positive_or_missing"
            in check_formula_policy(policy, definition.compatibility, operands, [approval])[
                "blockers"
            ]
        )
    denominator.value.normalized_value = Decimal("1234")
    numerator = operands[0].fact
    numerator.value.normalized_value = Decimal("-1")
    issues = check_formula_policy(policy, definition.compatibility, operands, [])["blockers"]
    assert ("nonnegative_operand_required" in issues) == (formula_id != "gross_margin")
    operands[0].fact.context.period = "2020"
    assert (
        "formula_period_relation_mismatch"
        in check_formula_policy(policy, definition.compatibility, operands, [])["blockers"]
    )
    wrong = policy.model_copy(update={"expression": "assets / liabilities"})
    assert (
        "formula_expression_mismatch"
        in check_formula_policy(wrong, definition.compatibility, operands, [approval])["blockers"]
    )


def test_signing_date_overlay_is_field_scoped_and_source_bound(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("evaluate_d02_final")
    record = dict(
        source=dict(page=dict(source_ref="synthetic", page=8)),
        response=dict(output=dict(payload=dict(context=["synthetic old signature"]))),
    )
    review = dict(
        field="signing_date",
        document_id="synthetic",
        snapshot_id="attempt",
        pdf_page=8,
        context_index=0,
        original_text="synthetic old signature",
        source_quote="ngày 15 tháng 03 năm 2023",
        signing_date="2023-03-15",
        method="controlled_original_pdf_visual_read",
    )
    before = json.dumps(record)
    result = module.signing_date_overlay(record, review, "attempt")
    assert result["usable_for"] == "signing_date_only" and not result["financial_period_override"]
    assert json.dumps(record) == before
    for change in ({"snapshot_id": "another"}, {"signing_date": "2022-03-15"}, {"field": "period"}):
        with pytest.raises(ValueError):
            module.signing_date_overlay(record, {**review, **change}, "attempt")
