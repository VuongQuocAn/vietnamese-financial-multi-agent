"""Synthetic citation controls; saved BBS evaluation is reported separately."""

import json
import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceCitation
from vietnamese_financial_multi_agent.outputs import (
    CitationRenderer,
    GroundedFinancialReport,
    RenderedCitationOutput,
    VietnameseQAResponse,
    validate_rendered_citations,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import _answer_text
from vietnamese_financial_multi_agent.outputs.qa_contracts import (
    GroundedAnswerPlan,
    GroundedSegment,
    QAClaimContext,
    QAValidationResult,
)
from vietnamese_financial_multi_agent.outputs.report_outline_contracts import ReportOutlineScope
from vietnamese_financial_multi_agent.outputs.report_writer_contracts import (
    ReportParagraph,
    ReportParagraphContext,
    ReportSection,
)


def citation(*, selector="first", page=7, level="page", document="doc", snapshot="snap"):
    return EvidenceCitation.model_validate(
        {
            "anchor_id": f"anchor-{document}-{snapshot}-{selector}",
            "document_id": document,
            "snapshot_id": snapshot,
            "pdf_page": page,
            "provenance_level": level,
            "limitations": ["Nguồn chưa kiểm tra PDF độc lập."],
            "source": {
                "document_id": document,
                "snapshot_id": snapshot,
                "reference": {
                    "anchor": {
                        "page": {
                            "symbol": "TEST",
                            "year": "2025",
                            "page": page,
                            "image": "page.png",
                            "source_ref": "source-run",
                        },
                        "element_id": selector if level == "element" else None,
                        "table_id": "table-original" if level == "cell" else None,
                        "cell_id": selector if level == "cell" else None,
                        "status": "resolved",
                    },
                    "source_pointer": f"/elements/{selector}",
                    "provenance_level": level,
                },
            },
        }
    )


def qa_source(citations=None, *, count=2, status="answered"):
    cs = citations if citations is not None else [citation(), citation(selector="second")]
    ctx = QAClaimContext(company_id="TEST", document_id="doc", snapshot_id="snap", period="2025")
    segments = [
        GroundedSegment(
            segment_id=f"seg-{i}",
            content="Doanh thu được ghi nhận theo nội dung ACCEPT.",
            verified_claim_ids=[f"claim-{i}"],
            citations=cs if i == 0 else cs[:1],
            context=ctx.model_copy(deep=True),
            caveats=["Caveat gốc"],
            limitations=["Giới hạn gốc"],
        )
        for i in range(count)
    ]
    source = VietnameseQAResponse(
        question="Doanh thu?",
        status=status,
        answer_vi="",
        grounded_segments=segments,
        citations=cs if count else [],
        used_verified_claim_ids=[f"claim-{i}" for i in range(count)],
        caveats=["Caveat gốc"],
        limitations=["Giới hạn gốc"],
        plan=GroundedAnswerPlan(),
        validation_result=QAValidationResult(valid=True),
    )
    source.answer_vi = _answer_text(source)
    return source


def report_source():
    qa = qa_source()
    paragraphs = [
        ReportParagraph(
            paragraph_id=s.segment_id,
            paragraph_type="grounded_analysis",
            text_vi=s.content,
            source_slot_ids=[f"slot-{i}"],
            verified_claim_ids=s.verified_claim_ids,
            citations=s.citations,
            caveats=s.caveats,
            limitations=s.limitations,
            context=[
                ReportParagraphContext(
                    source_slot_id=f"slot-{i}",
                    claim_context=s.context,
                    period_role="exact_period",
                    claim_kind="fact",
                )
            ],
        )
        for i, s in enumerate(qa.grounded_segments)
    ]
    section = ReportSection(
        section_id="profitability",
        title_vi="Khả năng sinh lời",
        order=1,
        status="supported",
        paragraphs=paragraphs,
        citations=qa.citations,
    )
    return GroundedFinancialReport(
        report_title="Báo cáo",
        status="partial",
        scope=ReportOutlineScope(
            company_id="TEST",
            document_id="doc",
            snapshot_id="snap",
            period="2025",
            included_periods=["2025"],
        ),
        sections=[section],
        body_vi="# Báo cáo\n\n## 1. Khả năng sinh lời\n\n"
        + "\n\n".join(p.text_vi for p in paragraphs),
        citations=qa.citations,
        used_verified_claim_ids=qa.used_verified_claim_ids,
        caveats=qa.caveats,
        limitations=qa.limitations,
        validation_result=QAValidationResult(valid=True),
    )


@pytest.mark.parametrize("mode", ["qa", "report"])
def test_exact_placement_reuse_duplicate_text_and_roundtrip(mode):
    source = qa_source() if mode == "qa" else report_source()
    before = source.model_dump_json()
    render = getattr(CitationRenderer(), "render_" + mode)
    result = render(source)
    assert result == render(source)
    assert source.model_dump_json() == before
    assert result == RenderedCitationOutput.model_validate_json(result.model_dump_json())
    assert validate_rendered_citations(result, source).valid
    assert len(result.references) == 2  # distinct selectors on the same page
    assert result.citation_bindings[0].display_numbers == [1, 2]
    assert result.citation_bindings[1].display_numbers == [1]
    assert result.references[0].bound_verified_claim_ids == ["claim-0", "claim-1"]
    assert result.references[0].bound_output_segment_ids == ["seg-0", "seg-1"]
    assert "ACCEPT. [1][2]" in result.rendered_text
    assert "ACCEPT. [1]\n" in result.rendered_text
    assert result.original_status == source.status
    with pytest.raises(ValidationError):
        RenderedCitationOutput.model_validate_json(
            json.dumps({**result.model_dump(mode="json"), "fake": 1})
        )


@pytest.mark.parametrize("level", ["page", "element", "cell"])
def test_provenance_and_exact_locator_no_invented_coordinates(level):
    source = qa_source([citation(level=level)], count=1)
    result = CitationRenderer().render_qa(source)
    loc = result.references[0].source_locator
    assert loc.pdf_page == 7  # original page number, never zero based
    assert loc.observed_bbox is None
    assert loc.provenance_level == level
    assert loc.source_ref == "source-run" and loc.source_pointer == "/elements/first"
    assert loc.resource_mapping_status == "not_provided"
    assert ("ô first" in result.rendered_text) == (level == "cell")
    assert "https://" not in result.rendered_text
    assert validate_rendered_citations(result, source).valid


@pytest.mark.parametrize("missing", ["anchor", "page", "uncertain"])
def test_missing_or_uncertain_location_is_explicit(missing):
    c = citation()
    if missing == "anchor":
        c.anchor_id = None
    elif missing == "page":
        c.source.reference = None
        c.pdf_page = c.provenance_level = None
    else:
        c.source.reference.anchor.status = "uncertain"
    result = CitationRenderer().render_qa(qa_source([c], count=1))
    assert result.status == "location_limited"
    assert result.original_status == "answered"
    assert result.references[0].source_locator.resolution_status != "resolved"
    if missing == "page":
        assert result.references[0].source_locator.pdf_page is None
        assert "Trang PDF" not in result.rendered_text


@pytest.mark.parametrize("field", ["snapshot", "document", "selector", "page"])
def test_stable_id_depends_on_exact_source_not_display_number(field):
    first = citation()
    options = {field: "other"} if field != "page" else {"page": 8}
    second = citation(**options)
    # Scope is isolated in separate outputs; cross-document QA remains disallowed.
    a = qa_source([first], count=1)
    b = qa_source([second], count=1)
    for s in b.grounded_segments:
        s.context.document_id = second.document_id
        s.context.snapshot_id = second.snapshot_id
    assert CitationRenderer().render_qa(a).references[0].citation_id != (
        CitationRenderer().render_qa(b).references[0].citation_id
    )
    multi = qa_source([citation(selector="second"), first], count=1)
    assert CitationRenderer().render_qa(a).references[0].citation_id == (
        CitationRenderer().render_qa(multi).references[1].citation_id
    )


@pytest.mark.parametrize(
    "status", ["partial", "abstained", "clarification_required", "unsupported"]
)
def test_partial_or_empty_output_does_not_invent_citations(status):
    source = qa_source(count=1 if status == "partial" else 0, status=status)
    result = CitationRenderer().render_qa(source)
    assert result.original_status == status
    assert len(result.references) == (2 if status == "partial" else 0)
    if status != "partial":
        assert source.answer_vi in result.rendered_text


OUTPUT_ATTACKS = [
    "page",
    "document",
    "snapshot",
    "anchor",
    "cell",
    "bbox",
    "pointer",
    "image",
    "provenance",
    "extra_reference",
    "missing_reference",
    "wrong_marker",
    "binding",
    "claims",
    "context",
    "limitations",
    "caveats",
    "content",
    "number",
    "label",
    "id",
    "source_citation",
    "fingerprint",
    "original_status",
    "resolution",
]


def tamper(output, attack):
    r = output.references[0]
    if attack in {"page", "document", "snapshot", "anchor", "provenance", "number", "label", "id"}:
        field, value = {
            "page": ("pdf_page", 8),
            "document": ("document_id", "other"),
            "snapshot": ("snapshot_id", "other"),
            "anchor": ("anchor_id", "other"),
            "provenance": ("provenance_level", "cell"),
            "number": ("display_number", 2),
            "label": ("display_label", "[9]"),
            "id": ("citation_id", "fabricated"),
        }[attack]
        setattr(r, field, value)
    elif attack in {"cell", "bbox", "pointer", "image", "resolution"}:
        field, value = {
            "cell": ("cell_id", "B12"),
            "bbox": ("observed_bbox", [1, 2, 3, 4]),
            "pointer": ("source_pointer", "/fake"),
            "image": ("image_reference", "other.png"),
            "resolution": ("resolution_status", "unresolved"),
        }[attack]
        setattr(r.source_locator, field, value)
    elif attack == "extra_reference":
        output.references.append(r.model_copy(deep=True))
    elif attack == "missing_reference":
        output.references.pop()
    elif attack == "wrong_marker":
        output.rendered_text = output.rendered_text.replace("[1][2]", "[2][1]", 1)
    elif attack == "binding":
        output.citation_bindings[1].citation_ids = [output.references[1].citation_id]
    elif attack == "claims":
        r.bound_verified_claim_ids = ["other-claim"]
    elif attack == "context":
        output.citation_bindings[0].contexts[0].period = "2024"
    elif attack == "limitations":
        output.limitations.clear()
    elif attack == "caveats":
        output.caveats.clear()
    elif attack == "content":
        output.rendered_text = output.rendered_text.replace("ACCEPT", "MUTATED")
    elif attack == "source_citation":
        r.source_citations[0].pdf_page = 8
    elif attack == "fingerprint":
        output.source_fingerprint = "other"
    elif attack == "original_status":
        output.original_status = "generated"
    else:
        raise AssertionError(attack)


@pytest.mark.parametrize("attack", OUTPUT_ATTACKS)
@pytest.mark.parametrize("mode", ["qa", "report"])
def test_tampering_rejected_against_typed_original(attack, mode):
    source = qa_source() if mode == "qa" else report_source()
    result = getattr(CitationRenderer(), "render_" + mode)(source)
    tamper(result, attack)
    assert not validate_rendered_citations(result, source).valid


@pytest.mark.parametrize(
    "attack", ["context", "page", "anchor_collision", "missing", "invalid", "text"]
)
def test_malformed_original_fails_closed(attack):
    source = qa_source()
    if attack == "context":
        source.grounded_segments[0].context.snapshot_id = "other"
    elif attack == "page":
        source.citations[0].pdf_page = 8
    elif attack == "anchor_collision":
        source.citations[1].anchor_id = source.citations[0].anchor_id
    elif attack == "missing":
        source.citations.pop()
    elif attack == "invalid":
        source.validation_result.valid = False
    else:
        source.answer_vi += "Unapproved content"
    with pytest.raises(ValueError):
        CitationRenderer().render_qa(source)


def test_exact_source_reuse_keeps_all_citation_variants_and_caveats():
    first = citation()
    second = first.model_copy(deep=True)
    second.limitations.append("Giới hạn bổ sung của claim thứ hai")
    result = CitationRenderer().render_qa(qa_source([first, second], count=1))
    assert len(result.references) == 1
    assert result.references[0].source_citations == [first, second]
    assert second.limitations[-1] in result.limitations
    assert result.citation_bindings[0].display_numbers == [1]


def test_observed_bbox_and_line_preserved_proposed_bbox_not_projected():
    c = citation(level="element")
    c.source.reference.anchor.line_id = "original-line"
    c.source.reference.anchor.observed_bbox = [11, 22, 33, 44]
    c.source.reference.anchor.proposed_bbox = [100, 200, 300, 400]
    loc = CitationRenderer().render_qa(qa_source([c], count=1)).references[0].source_locator
    assert loc.observed_bbox == [11, 22, 33, 44] and loc.line_id == "original-line"
    assert "proposed_bbox" not in loc.model_dump()


def test_report_native_period_and_first_occurrence_order_are_preserved():
    source = report_source()
    source.sections[0].paragraphs[0].context[0].claim_context.period = "2025-12-31"
    source.sections[0].paragraphs[0].context[0].period_role = "closing_balance"
    source.scope.included_periods.append("2025-12-31")
    source.citations.reverse()
    source.sections[0].citations.reverse()
    result = CitationRenderer().render_report(source)
    assert result.references[0].anchor_id.endswith("first")
    assert result.citation_bindings[0].contexts[0].period == "2025-12-31"
    assert result.citation_bindings[1].contexts[0].period == "2025"
    assert validate_rendered_citations(result, source).valid


def test_report_nonfinancial_id_collision_rejected():
    source = report_source()
    source.sections[0].paragraphs.append(
        ReportParagraph(paragraph_id="seg-0", paragraph_type="scope_description", text_vi="Phạm vi")
    )
    source.body_vi += "\n\nPhạm vi"
    with pytest.raises(ValueError, match="duplicate_output_segment_id"):
        CitationRenderer().render_report(source)


def test_empty_report_and_unanswered_qa_keep_original_messages():
    source = report_source()
    source.sections = []
    source.citations = []
    source.used_verified_claim_ids = []
    source.status = "abstained"
    source.body_vi = "Không có đủ claim trong ledger."
    result = CitationRenderer().render_report(source)
    assert not result.references and source.body_vi in result.rendered_text
    from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement

    response = qa_source(status="partial")
    response.unanswered_requirements = [
        QARequirement(requirement_id="unanswered-1", text="ROE?", kind="unsupported")
    ]
    response.answer_vi = _answer_text(response)
    rendered = CitationRenderer().render_qa(response)
    assert "Các yêu cầu chưa đáp ứng: unanswered-1." in rendered.rendered_text


def test_frozen_citation_oracle_pin_accepts_only_newline_equivalence(tmp_path):
    root = Path(__file__).resolve().parents[2]
    functions = runpy.run_path(str(root / "scripts/evaluate_m7_04_citations.py"))
    oracle = root / "evaluation/m7-04-scenarios.json"
    assert functions["oracle_hash"](oracle) == functions["ORACLE_SHA256"]
    alternate = tmp_path / "oracle.json"
    alternate.write_bytes(oracle.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert functions["oracle_hash"](alternate) == functions["ORACLE_SHA256"]
    alternate.write_bytes(alternate.read_bytes().replace(b'"page": 7', b'"page": 8', 1))
    assert functions["oracle_hash"](alternate) != functions["ORACLE_SHA256"]


@pytest.mark.parametrize("mode", ["qa", "report"])
def test_empty_source_cannot_claim_a_complete_grounded_status(mode):
    source = qa_source(count=0) if mode == "qa" else report_source()
    if mode == "report":
        source.sections = []
        source.citations = []
        source.used_verified_claim_ids = []
        source.status = "generated"
    with pytest.raises(ValueError, match="source_status_coverage_mismatch"):
        getattr(CitationRenderer(), "render_" + mode)(source)
