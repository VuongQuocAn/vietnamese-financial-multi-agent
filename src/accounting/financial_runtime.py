"""Small PDF-to-evidence composition and one-shot targeted recovery."""

from ..document_processing.financial_discovery import discover_financial_pages
from ..document_processing.gemini_ingestion import MODEL, load_pages
from .automated_extraction import extract_financial_page, run_automated_pdf
from .quality import assess_evidence_for_task, evidence_from_automated_records


def process_financial_pdf(
    path,
    *,
    symbol,
    year,
    pages=None,
    service=None,
    credential_ref="",
    cached_records=None,
    model=MODEL,
    dpi=200,
    discovery_cache=None,
    discovery_service=None,
    on_discovery_page=None,
):
    """Keep good pages when another response is unavailable; binding errors still raise.

    Omit pages for automatic discovery; explicit selection keeps the previous path.
    Reuse public PDF cache validation without an M1 unified/manual dependency.
    Input selection/render failures raise; invalid provider responses remain records.
    """
    inventory = None
    if pages is None:
        inventory = discover_financial_pages(
            path,
            symbol=symbol,
            year=year,
            service=discovery_service or service,
            credential_ref=credential_ref,
            cached_predictions=discovery_cache,
            model=model,
            on_page=on_discovery_page,
        )
        pages = [p["page"] for p in inventory if p["selected"]]
    records = (
        run_automated_pdf(
            path,
            symbol=symbol,
            year=year,
            pages=pages,
            service=service,
            credential_ref=credential_ref,
            cached_records=cached_records,
            model=model,
            dpi=dpi,
        )
        if pages
        else []
    )
    valid = [r for r in records if "invalid_extraction_response" not in r["extraction"]["issues"]]
    evidence = evidence_from_automated_records(valid)
    return dict(
        inventory=inventory,
        records=records,
        evidence=evidence,
        quality=assess_evidence_for_task(evidence),
        page_issues={
            r["source"]["page"]["page"]: r["extraction"]["issues"]
            for r in records
            if r["extraction"]["issues"]
        },
    )


def recover_financial_target(
    path,
    *,
    selector,
    target,
    evidence,
    symbol,
    year,
    service=None,
    credential_ref="",
    cached_record=None,
    model=MODEL,
    dpi=200,
):
    """At most one Gateway request for a caller-selected PDF page and target.

    Replays require the exact stored target/model as well as PDF/image binding.
    Return original plus recovery evidence; quality identifies conflicting values.
    Caller persists the returned record separately and decides whether to ask again.
    """
    page = load_pages(path, symbol=symbol, year=year, pages=[selector.page], dpi=dpi)[0]
    if selector.document_id != page.image.identity.source_ref:
        raise ValueError("recovery_document_mismatch")
    request = dict(target=target, model=model)
    if cached_record is not None:
        if cached_record.get("recovery_request") != request:
            raise ValueError("recovery_request_mismatch")
        actual_model = ((cached_record.get("response") or {}).get("provenance") or {}).get(
            "requested_model"
        ) or {}
        if actual_model.get("model") != model:
            raise ValueError("recovery_model_mismatch")
        records = run_automated_pdf(
            path,
            symbol=symbol,
            year=year,
            pages=[selector.page],
            cached_records={selector.page: cached_record},
            dpi=dpi,
        )
        record = records[0]
    elif service is not None:
        record = extract_financial_page(
            service, page, credential_ref=credential_ref, model=model, target=target
        )
        record["recovery_request"] = request
    else:
        raise ValueError("service_or_recovery_cache_required")
    recovered = []
    if "invalid_extraction_response" not in record["extraction"]["issues"]:
        recovered = evidence_from_automated_records([record])
        for e in recovered:
            e.evidence_id += "/recovery/" + record["response"]["request_id"]
    combined = {e.evidence_id: e.model_copy(deep=True) for e in [*evidence, *recovered]}
    quality = assess_evidence_for_task(combined.values())
    targets = [i for i in quality.items if selector.matches(i.evidence)]
    recovered_ids = {e.evidence_id for e in recovered}
    success = any(
        i.evidence.evidence_id in recovered_ids and i.decision in {"usable", "usable_with_caveat"}
        for i in targets
    ) and not any(i.decision == "conflicted" for i in targets)
    return dict(
        record=record, evidence=list(combined.values()), quality=quality, target_recovered=success
    )
