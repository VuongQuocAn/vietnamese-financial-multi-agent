"""D-07 generic scope controls; không chứng nhận financial accuracy toàn PDF."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.accounting import (
    ContextEvidence,
    evidence_from_ocr_scope_choices,
    resolve_financial_context,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
)
from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRPage
from vietnamese_financial_multi_agent.evidence import (
    EvidenceAnchor,
    ReportingScopeReview,
    SnapshotCatalog,
    SnapshotDescriptor,
)

from .test_raw_ocr_contracts import element, payload


def fixture(document=0):
    raw = payload.__wrapped__()
    raw["page"].update(page=2 + document, symbol=f"SYNTHETIC-{document}")
    descriptor = SnapshotDescriptor(
        document_id="sha256:" + ("a", "d")[document] * 64,
        pdf_sha256=("a", "d")[document] * 64,
        snapshot_id=f"snapshot-{document}",
        origin="original_extraction",
    )
    labels = [
        "BCTC riêng (đơn vị lập báo cáo này)",
        "BCTC hợp nhất (đơn vị lập báo cáo này)",
        "BCTC tổng hợp (đơn vị lập báo cáo này)",
    ]
    raw["elements"] = [
        dict(
            element("checkbox"),
            id=f"option-{i}",
            label=text,
            checked=i == document,
            choice="yes" if i == document else "no",
        )
        for i, text in enumerate(labels)
    ]
    page = OCRPage.model_validate(raw)
    identity = RawPageIdentity(
        symbol=page.page.symbol,
        year=page.page.year,
        page=page.page.page,
        image=page.page.image,
        source_ref=descriptor.document_id,
    )
    evidence = evidence_from_ocr_scope_choices(page, source_page=identity)
    reviews = []
    for item in evidence:
        verified = item.model_copy(update={"status": "resolved"}, deep=True)
        reviews.append(
            ReportingScopeReview(
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                pdf_sha256=descriptor.pdf_sha256,
                pdf_page=identity.page,
                source_quote=item.raw_text,
                evidence_role="filing_scope",
                reporting_scope=resolve_financial_context([verified]).context.reporting_scope,
                evidence=verified,
                sources=[
                    EvidenceAnchor(
                        document_id=descriptor.document_id,
                        snapshot_id=descriptor.snapshot_id,
                        reference=p.model_copy(deep=True),
                    )
                    for p in verified.provenance
                ],
                method="controlled_original_pdf_visual_read",
                review_image_sha256="b" * 64,
                verification_reference="synthetic/verified-choices",
                inspection_reference="synthetic/inspection",
            )
        )
    return page, descriptor, evidence, reviews


def test_two_documents_scopes_restart_and_no_parent_fallback():
    all_descriptors, all_reviews = [], []
    for document in (0, 1):
        page, descriptor, evidence, reviews = fixture(document)
        before = page.export_source()
        assert resolve_financial_context(evidence).context.reporting_scope is None
        assert all(e.status == "unresolved" for e in evidence)
        all_descriptors.append(descriptor)
        all_reviews.extend(reviews)
        result = SnapshotCatalog([descriptor], reporting_scope_reviews=reviews).get_reporting_scope(
            descriptor.document_id, descriptor.snapshot_id
        )
        assert result.reporting_scope == ("separate", "consolidated")[document]
        assert result.status == "resolved" and result.evidence_status == "confirmed"
        assert not result.cross_document_execution_approved
        assert page.export_source() == before
    restarted = [ReportingScopeReview.model_validate_json(r.model_dump_json()) for r in all_reviews]
    catalog = SnapshotCatalog(all_descriptors, reporting_scope_reviews=restarted)
    for descriptor in all_descriptors:
        expected = catalog.get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)
        assert len(expected.reviews) == 3
        assert expected == SnapshotCatalog(
            all_descriptors, reporting_scope_reviews=all_reviews
        ).get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)
    parent = all_descriptors[0]
    child = parent.model_copy(
        update={
            "snapshot_id": "child",
            "parent_snapshot_id": parent.snapshot_id,
            "origin": "recovery",
        }
    )
    catalog = SnapshotCatalog([*all_descriptors, child], reporting_scope_reviews=all_reviews)
    assert catalog.get_reporting_scope(parent.document_id, "child").reporting_scope is None
    assert (
        "scope_review_missing_for_selected_snapshot"
        in catalog.get_reporting_scope(parent.document_id, "child").reasons
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "snapshot",
        "document",
        "hash",
        "source",
        "selector",
        "quote",
        "value",
        "verification",
        "unknown_selection",
        "unverified",
        "conflicting",
        "unsupported",
        "parent",
    ],
)
def test_scope_fail_closed(damage):
    _, descriptor, _, reviews = fixture()
    r = reviews[0]
    if damage == "missing":
        reviews = []
    elif damage == "snapshot":
        for record in reviews:
            record.snapshot_id = "other"
    elif damage == "document":
        for record in reviews:
            record.document_id = "sha256:" + "d" * 64
    elif damage == "hash":
        r.pdf_sha256 = "f" * 64
    elif damage == "source":
        r.sources[0].reference.anchor.page.source_ref = "other"
    elif damage == "selector":
        r.sources[0].reference.source_pointer = "/wrong-selector"
    elif damage == "quote":
        r.source_quote = "BCTC hợp nhất"
    elif damage == "value":
        r.reporting_scope = "consolidated"
    elif damage == "verification":
        r.verification_reference = ""
    elif damage == "unknown_selection":
        r.evidence.scope_selection = "unknown"
        r.reporting_scope = None
    elif damage == "unverified":
        r.evidence.status = "unresolved"
        r.reporting_scope = None
    elif damage == "conflicting":
        reviews[1].evidence.scope_selection = "selected"
        reviews[1].reporting_scope = "consolidated"
    elif damage == "unsupported":
        reviews[2].evidence.scope_selection = "selected"
    elif damage == "parent":
        descriptor.parent_snapshot_id = "not-found"
    result = SnapshotCatalog([descriptor], reporting_scope_reviews=reviews).get_reporting_scope(
        descriptor.document_id, descriptor.snapshot_id
    )
    assert result.status != "resolved" and result.reporting_scope is None
    assert result.reasons and not result.cross_document_execution_approved
    if damage == "conflicting":
        assert result.status == "conflicted" and len(result.reviews) == 3


def test_insufficient_and_subsidiary_mentions_do_not_determine_filing_scope():
    _, descriptor, _, reviews = fixture()
    record = reviews[0]
    for quote in (
        "Cơ sở lập báo cáo",
        "Công ty con lập báo cáo tài chính riêng.",
        "Công ty không có công ty con.",
    ):
        record.source_quote = quote
        record.evidence = ContextEvidence(
            raw_text=quote, provenance=deepcopy(record.evidence.provenance)
        )
        record.reporting_scope = None
        result = SnapshotCatalog(
            [descriptor], reporting_scope_reviews=[record]
        ).get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)
        assert result.reporting_scope is None and result.status in {"unresolved", "ambiguous"}
        assert not result.cross_document_execution_approved
    # Even an explicit subsidiary title is not scope of this filing.
    record.source_quote = "Báo cáo tài chính riêng"
    record.evidence = ContextEvidence(
        raw_text=record.source_quote, provenance=deepcopy(record.evidence.provenance)
    )
    record.evidence_role = "other_entity"
    result = SnapshotCatalog([descriptor], reporting_scope_reviews=[record]).get_reporting_scope(
        descriptor.document_id, descriptor.snapshot_id
    )
    assert result.reporting_scope is None and result.evidence_status == "insufficient"
    with pytest.raises(ValueError, match="scope_source_page_binding_mismatch"):
        page, _, evidence, _ = fixture()
        evidence_from_ocr_scope_choices(
            page, source_page=evidence[0].provenance[0].anchor.page.model_copy(update={"page": 99})
        )


def test_scopes_do_not_grant_formula_execution_or_change_compatibility():
    from .test_m4_execution import fixture as metric_fixture

    data = metric_fixture()
    metric = data["metrics"][0]
    before = [f.model_dump_json() for f in data["facts"]]
    _, _, _, reviews = fixture()
    descriptor = data["descriptors"][0]
    for review in reviews:
        review.snapshot_id = descriptor.snapshot_id
        for source in review.sources:
            source.snapshot_id = descriptor.snapshot_id
    data["reporting_scope_reviews"] = reviews
    data["execution_approval"] = None
    catalog = SnapshotCatalog(**data)
    assert (
        catalog.get_reporting_scope(descriptor.document_id, descriptor.snapshot_id).status
        == "resolved"
    )
    closure = catalog.assess_metric(data["descriptors"][0], metric)
    assert not closure.calculation_eligible
    assert closure.readiness["global_compatibility"]["status"] == "undetermined"
    assert [f.model_dump_json() for f in data["facts"]] == before
