"""One bounded, region-focused recovery using the original full-page image.

Retaining the full image preserves existing PDF/image bindings and section
context. The first response stays immutable. Selection requires PDF review.
"""

import argparse
import time
from pathlib import Path
from types import SimpleNamespace

from complete_document_evidence import atomic_json, digest, native_payload, read
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import (
    ingest_page,
    load_pages,
)
from vietnamese_financial_multi_agent.document_processing.vision_ocr import (
    QUALITY_REF,
    quality_schema,
)
from vietnamese_financial_multi_agent.evidence.composition import (
    EvidenceComposition,
    verify_saved_pages,
)


def recover(output, label, number, focus, *, attempt=1, dpi=None):
    root = Path(".").resolve()
    folder = output / label
    prior = read(folder / "responses" / f"page-{number}.json")
    manifest = EvidenceComposition.model_validate(read(folder / "composition.json"))
    company, year = label.split("_")
    pdf = next((root / f"data/raw/Financial_Report_pdf/{company}/{year}").glob("*.pdf"))
    verify_saved_pages(pdf, [prior])
    if prior["provenance"]["pdf_sha256"] != manifest.financial_snapshot.pdf_sha256:
        raise ValueError("recovery_document_mismatch")
    if attempt not in {1, 2}:
        raise ValueError("recovery_attempt_limit")
    suffix = "" if attempt == 1 else "-attempt-2"
    destination = folder / "responses-recovery" / f"page-{number}{suffix}.json"
    if attempt == 2:
        failed = read(folder / "responses-recovery" / f"page-{number}.json")
        error = (failed.get("response") or {}).get("error") or {}
        provider_retry = (
            native_payload(failed) is None and error.get("provider_error_code") == "http_503"
        )
        reviews_path = folder / "quality-reviews.json"
        reviews = read(reviews_path) if reviews_path.exists() else []
        reviewed_failure = any(
            r["page"] == number
            and r.get("rejected_recovery_sha256")
            == digest(folder / "responses-recovery" / f"page-{number}.json")
            and r.get("requires_higher_resolution_recovery")
            for r in reviews
        )
        higher_resolution = (
            dpi is not None and prior["provenance"]["render_dpi"] < dpi <= 300 and reviewed_failure
        )
        if not (provider_retry or higher_resolution):
            raise ValueError(
                "second_attempt_requires_saved_HTTP503_or_reviewed_higher_DPI_recovery"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    marker = destination.with_suffix(".started.json")
    # At most two groups; the second requires HTTP503 or reviewed higher-DPI recovery.
    with marker.open("x", encoding="utf-8") as stream:
        stream.write("{}")
    service, pool, options = compose_metadata_service(
        SimpleNamespace(root=output), extra_schemas=[(QUALITY_REF, quality_schema())]
    )
    if service is None:
        raise ValueError("existing_gateway_configuration_unavailable")
    started = time.monotonic()
    try:
        page = load_pages(
            pdf,
            symbol=company,
            year=year,
            pages=[number],
            dpi=dpi or prior["provenance"]["render_dpi"],
        )[0]
        record = ingest_page(
            service,
            page,
            credential_ref=options["credential_ref"],
            document_mode=True,
            document_focus=focus,
        )
        atomic_json(destination, record)
        atomic_json(
            destination.with_suffix(".usage.json"),
            dict(
                focus=focus,
                attempts=service.last_attempts,
                elapsed_seconds=time.monotonic() - started,
                original_response=(folder / "responses" / f"page-{number}.json")
                .relative_to(root)
                .as_posix(),
                source_bound=bool(verify_saved_pages(pdf, [record])),
                structural_output_available=native_payload(record) is not None,
                selection="pending_independent_PDF_review",
            ),
        )
    finally:
        pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/EXT-01"))
    parser.add_argument("--document", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--focus", required=True)
    parser.add_argument("--attempt", type=int, choices=[1, 2], default=1)
    parser.add_argument("--dpi", type=int, choices=[200, 300])
    args = parser.parse_args()
    recover(
        args.output.resolve(),
        args.document,
        args.page,
        args.focus,
        attempt=args.attempt,
        dpi=args.dpi,
    )
