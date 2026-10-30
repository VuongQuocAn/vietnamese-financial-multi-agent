"""Focused D-02 controls; synthetic PASS không chứng minh accuracy PDF."""

import importlib
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

from .test_evidence_contracts import scenario


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
    result = assess_analytical_readiness(spec, operands, reviews, bases)
    assert result["candidate_compatibility"] in {"undetermined", "incompatible"}
    assert result["calculation_eligible"] is False
    assert result["candidate_blockers"]


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
