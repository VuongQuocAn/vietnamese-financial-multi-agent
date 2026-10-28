"""Hai adapter + quality router deterministic; recovery chỉ là đề xuất."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..core import DataConfig
from .classification import TITLES, _catalog, _supports, blocking_quality_issues
from .contracts.document_understanding import RawPageIdentity
from .contracts.path_mapping import PathMappingRequest
from .contracts.unified_document import (
    ComponentQuality,
    RecoveryDecision,
    UnifiedDocument,
    UnifiedPage,
    UnifiedRegion,
    UnifiedTable,
)
from .gemini_ingestion import IngestionPage, ingest_page, load_pages
from .ocr_loader import load_ocr_page
from .vision_ocr import image_source, quality_schema, validate_components


@dataclass(frozen=True)
class UnderstandingOptions:
    data_config: DataConfig | None = None
    symbol: str = ""
    year: str = ""
    pages: tuple[int, ...] = (1,)
    dpi: int = 200
    # M1-15 records, keyed by ORIGINAL page number; never retry an existing record.
    persisted_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    allow_live_ocr: bool = False
    service: Any = None
    credential_ref: str | None = None


@dataclass(frozen=True)
class PersistedOCRInput:
    """M1-15 manifest + rendered PNGs; PDF hash retained, not reverified here."""

    manifest: dict[str, Any]
    image_directory: Path


def run_document_understanding(
    source: Path | PathMappingRequest | PersistedOCRInput,
    options: UnderstandingOptions | None = None,
) -> UnifiedDocument:
    """Existing JSON dùng request/config của loader; PDF/PNG dùng ingestion M1-15.

    Không ghi file. Thiếu persisted record thì fail closed trừ khi caller opt-in
    live và inject Gateway service. Không có recovery tự động trong MVP.
    """
    options = options or UnderstandingOptions()
    if isinstance(source, PathMappingRequest):
        if options.data_config is None:
            raise ValueError("data_config_required")
        loaded = load_ocr_page(source, options.data_config)
        return UnifiedDocument(pages=[_existing_page(loaded)])
    if isinstance(source, PersistedOCRInput):
        return _replay_manifest(source, options)
    if not isinstance(source, Path):
        raise TypeError("expected_path_or_mapping_request")
    # Preflight tất cả trang trước API, tránh chạy live một phần do thiếu record.
    missing = set(options.pages) - options.persisted_results.keys()
    if missing and not (
        options.allow_live_ocr and options.service is not None and options.credential_ref
    ):
        raise ValueError("persisted_result_required_live_ocr_disabled")
    pages = load_pages(
        source, symbol=options.symbol, year=options.year, pages=list(options.pages), dpi=options.dpi
    )
    # Kiểm tra cả replay batch trước khi cho phép bất kỳ live request nào.
    replayed = {
        p.image.identity.page: _native_page(
            p, options.persisted_results[p.image.identity.page], True
        )
        for p in pages
        if p.image.identity.page in options.persisted_results
    }
    result = []
    for page in pages:
        number = page.image.identity.page
        if number in replayed:
            result.append(replayed[number])
        else:
            record = ingest_page(options.service, page, credential_ref=options.credential_ref)
            result.append(_native_page(page, record, False))
    return UnifiedDocument(pages=result)


def _replay_manifest(source, options):
    result = []
    if not options.pages or len(set(options.pages)) != len(options.pages):
        raise ValueError("invalid_input_selection")
    for number in options.pages:
        matches = [p for p in source.manifest["pages"] if p["page_number"] == number]
        if len(matches) != 1 or number not in options.persisted_results:
            raise ValueError("persisted_manifest_page_missing_or_ambiguous")
        metadata = matches[0]
        if (
            metadata["source_type"] not in {"pdf", "png"}
            or metadata["document_id"] != f"sha256:{metadata['source_sha256']}"
            or (
                metadata["source_type"] == "pdf"
                and metadata["pdf_sha256"] != metadata["source_sha256"]
            )
        ):
            raise ValueError("persisted_manifest_source_mismatch")
        png = load_pages(
            source.image_directory / f"page-{number}.png",
            symbol=options.symbol,
            year=options.year,
            pages=[number],
        )[0]
        if png.image.sha256 != metadata["image_sha256"] or (png.image.width, png.image.height) != (
            metadata["width"],
            metadata["height"],
        ):
            raise ValueError("persisted_image_mismatch")
        identity = png.image.identity.model_copy(update={"source_ref": metadata["document_id"]})
        page = IngestionPage(replace(png.image, identity=identity), metadata)
        adapted = _native_page(page, options.persisted_results[number], True)
        adapted.source_references = dict(
            adapted.source_references,
            integrity_scope="persisted_manifest_and_png_source_document_not_rehashed",
        )
        result.append(adapted)
    return UnifiedDocument(pages=result)


def _region(pointer, raw, *, text_status, layout=None, raw_ids=None):
    accepted = text_status == "accepted"
    layout_ok = layout is not None and layout["status"] == "accepted"
    ids = raw_ids or {}
    return UnifiedRegion(
        source_pointer=pointer,
        **ids,
        provenance_level="cell"
        if ids.get("raw_cell_id")
        else ("element" if ids.get("raw_element_id") else "page"),
        text=raw.get("text") if isinstance(raw.get("text"), str) else None,
        status="accepted"
        if accepted
        else ("unavailable" if text_status == "unavailable" else "unresolved"),
        quality=ComponentQuality(
            text_accepted=accepted,
            layout_accepted=layout_ok,
            downstream_usable=accepted,
            usable_for=["text_evidence"] if accepted else [],
        ),
        # Raw/model bbox vẫn ở source_component; không coi bounds check là verification.
        geometry_status="unresolved"
        if raw.get("bbox") is not None or raw.get("geometry")
        else "unavailable",
        layout_status="accepted" if layout_ok else ("unresolved" if layout else "unavailable"),
        row=layout["row"] if layout_ok else None,
        column=layout["column"] if layout_ok else None,
        source_component=raw,
        issues=[] if accepted else ["text_requires_review"],
    )


def _existing_page(loaded):
    raw = loaded.page
    identity = RawPageIdentity(
        **{key: getattr(raw.page, key) for key in ("symbol", "year", "page", "image")},
        source_ref=loaded.mapping_result.reference.source_ref,
    )
    texts, tables = [], []
    for i, element in enumerate(raw.elements):
        pointer = f"/elements/{i}"
        if element.type == "text":
            texts.append(
                _region(
                    pointer,
                    element.model_dump(mode="json", exclude_unset=True),
                    text_status="accepted" if element.text.strip() else "unresolved",
                    raw_ids=dict(raw_element_id=element.id),
                )
            )
        elif element.type == "table":
            # Raw row/col alone is not a validated layout. No reconstruction by default.
            cells = [
                _region(
                    f"{pointer}/cells/{j}",
                    cell.model_dump(mode="json", exclude_unset=True),
                    text_status="accepted" if cell.text.strip() else "unresolved",
                    layout=dict(status="unresolved", row=cell.row, column=cell.col),
                    raw_ids=dict(
                        raw_element_id=element.id, raw_table_id=element.id, raw_cell_id=cell.id
                    ),
                )
                for j, cell in enumerate(element.cells)
            ]
            tables.append(
                UnifiedTable(
                    source_pointer=pointer,
                    raw_table_id=element.id,
                    status="unresolved",
                    layout_accepted=False,
                    cells=cells,
                    source_component=element.model_dump(mode="json", exclude_unset=True),
                    issues=["raw_layout_not_verified"],
                )
            )
    # M1-11 gate: code/title in independent, disjoint raw regions, no blocking issues.
    catalog = _catalog(raw, identity)
    labels = [label for label in TITLES if _supports(label, catalog)]
    classification = dict(label=None, status="unresolved", evidence=[])
    if len(labels) == 1 and not blocking_quality_issues(raw, catalog, catalog):
        classification = dict(
            label=labels[0],
            status="accepted",
            evidence=[e.anchor.export_result() for e in catalog],
        )
    page = UnifiedPage(
        identity=identity,
        source_type="existing_ocr",
        source_sha256=loaded.source_sha256,
        source_references=dict(
            mapping=loaded.mapping_result.export_result(),
            source_metadata=raw.page.model_dump(mode="json"),
            raw_provenance=raw.provenance.model_dump(mode="json", exclude_unset=True),
            identity_checked=loaded.identity_checked,
        ),
        schema_valid=True,
        text_regions=texts,
        tables=tables,
        classification=classification,
        issues=[
            dict(code=i.code, path=list(i.path), message=i.message) for i in loaded.quality_issues
        ],
        processing_history=["existing_ocr_loader", "unified_adapter", "quality_router"],
    )
    return _route(page)


def _native_page(page, record, replay):
    if record.get("provenance") != page.source or record.get("source") != image_source(page.image):
        raise ValueError("persisted_source_mismatch")
    response = record.get("response") or {}
    output = response.get("output") or {}
    available = (
        response.get("status") in {"success", "malformed"}
        and response.get("finish_reason") == "stop"
        and output.get("format") == "json"
        and output.get("validation_status") != "invalid_json"
        and isinstance(output.get("payload"), dict)
    )
    # Recompute component checks from original payload; persisted status is not proof.
    components = (
        validate_components(output["payload"], page.image, source=record["source"])
        if available
        else dict(text_elements=[], tables=[], issues=["ocr_output_unavailable"])
    )
    schema_valid = available and Draft202012Validator(quality_schema()).is_valid(output["payload"])
    texts = [
        _region(f"/text_elements/{i}", item, text_status=item["status"])
        for i, item in enumerate(components["text_elements"])
    ]
    tables = []
    for i, table in enumerate(components["tables"]):
        cells = [
            _region(
                f"/tables/{i}/cells/{j}", cell, text_status=cell["status"], layout=cell["layout"]
            )
            for j, cell in enumerate(table["cells"])
        ]
        layout_ok = bool(cells) and all(c.quality.layout_accepted for c in cells)
        tables.append(
            UnifiedTable(
                source_pointer=f"/tables/{i}",
                status="accepted" if table["status"] == "accepted" else "unresolved",
                layout_accepted=layout_ok,
                cells=cells,
                source_component=table,
                issues=[] if layout_ok else ["table_layout_unresolved"],
            )
        )
    issues = [dict(code=code) for code in components["issues"]]
    if available and not schema_valid:
        issues.append(dict(code="ocr_schema_invalid_components_retained"))
    issues.extend(
        dict(code="ocr_limitation", message=str(v)) for v in components.get("limitations", [])
    )
    issues.append(dict(code="geometry_not_independently_verified"))
    result = UnifiedPage(
        identity=page.image.identity,
        source_type=page.source["source_type"],
        source_sha256=page.source["source_sha256"],
        source_references=page.source,
        schema_valid=bool(schema_valid),
        text_regions=texts,
        tables=tables,
        # Without independent region anchors, do not weaken M1-11 evidence gate.
        classification=dict(
            label=None, status="unresolved", evidence=[], reason="no_verified_region_anchors"
        ),
        issues=issues,
        processing_history=[
            "persisted_ocr_replay" if replay else "gemini_native_ocr",
            "component_validation",
            "unified_adapter",
            "quality_router",
        ],
    )
    return _route(result)


def _route(page):
    for table in page.tables:
        if not table.layout_accepted:
            page.recovery_decisions.append(
                RecoveryDecision(
                    action="table_reconstruction",
                    source_pointer=table.source_pointer,
                    reason="Table retained; layout needs trusted structural evidence before recovery.",
                )
            )
    for region in [*page.text_regions, *(c for t in page.tables for c in t.cells)]:
        if not region.quality.text_accepted:
            page.recovery_decisions.append(
                RecoveryDecision(
                    action="human_review",
                    source_pointer=region.source_pointer,
                    reason="Uncertain text retained; no automatic OCR correction or vision request.",
                )
            )
    if page.classification["status"] != "accepted" or not (page.text_regions or page.tables):
        page.recovery_decisions.append(
            RecoveryDecision(
                action="human_review",
                source_pointer="/",
                reason="Insufficient evidence for classification or usable page content.",
            )
        )
    return page
