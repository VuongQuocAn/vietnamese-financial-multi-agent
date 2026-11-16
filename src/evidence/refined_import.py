"""Offline refined JSON import; JSON fidelity is not PDF/financial verification."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from ..accounting.automated_extraction import column_period_evidence, parse_vietnamese_number
from ..accounting.context_resolution import ContextEvidence, resolve_financial_context
from ..accounting.contracts import (
    FinancialContext,
    FinancialNormalizationResult,
    FinancialSourceReference,
    FinancialValue,
)
from ..accounting.extraction_semantics import item_unit, text_key
from ..accounting.item_mapping import map_item_label
from ..accounting.quality import AssessableEvidence, assess_evidence_for_task
from ..accounting.statement_resolution import resolve_statement_type
from ..document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
    UnderstoodCell,
    UnderstoodTable,
)
from .adapter import fact_from_m2
from .contracts import EvidenceAnchor, TaskQualityContext
from .document_evidence import TableEvidence, TextEvidence
from .refined_context import (
    company_binding,
    context_lines,
    filing_cover,
    header_context,
    header_unit,
    stock_page_context,
)

IMPORT_VERSION = "vifinbench-refined-import-v2"
JSON_CAVEAT = "json_source_not_pdf_verified"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_refined(root: Path, document: str, projection_version=None):
    """Read only one explicit document below root; no benchmark/metadata inputs."""
    if not re.fullmatch(r"[A-Z0-9]+_20\d{2}", document):
        raise ValueError("invalid_document_alias")
    symbol, year = document.split("_")
    root = root.resolve()
    directory = (root / symbol / year).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("source_outside_refined_root")
    pages, pins = [], []
    for path in sorted(directory.glob("page_*.json")):
        if not path.resolve().is_relative_to(root):
            raise ValueError("source_outside_refined_root")
        data = path.read_bytes()
        page = json.loads(data)
        number = page["page"]
        if (
            page["document_id"] != document
            or type(number) is not int
            or number < 1
            or path.stem != f"page_{number:04d}"
            or not isinstance(page["blocks"], list)
        ):
            raise ValueError("refined_page_identity_or_shape_mismatch")
        for block in page["blocks"]:
            if block["type"] == "table":
                table = block["table"]
                if not isinstance(table["columns"], list) or not isinstance(table["rows"], list):
                    raise ValueError("invalid_refined_table")
                if any(not isinstance(r, list) for r in table["rows"]):
                    raise ValueError("invalid_refined_row")
                if any(type(c) is not str for r in [table["columns"], *table["rows"]] for c in r):
                    raise ValueError("invalid_refined_cell")
            elif not isinstance(block.get("text"), str):
                raise ValueError("invalid_refined_text")
        pages.append(page)
        pins.append(dict(page=number, path=path.relative_to(root).as_posix(), sha256=sha256(data)))
    if not pages:
        raise ValueError("no_refined_pages")
    digest = sha256(json.dumps(pins, sort_keys=True, separators=(",", ":")).encode())
    manifest = dict(
        version=IMPORT_VERSION,
        source_kind="refined_json",
        document_alias=document,
        document_id=f"json:sha256:{digest}",
        snapshot_id=f"{IMPORT_VERSION}:{digest}",
        pages=pins,
        missing_pages=sorted(
            set(range(1, max(p["page"] for p in pages) + 1)) - {p["page"] for p in pages}
        ),
        completeness_verified=False,
        pdf_verified=False,
        financial_fact_verified=False,
    )
    if projection_version:
        manifest["projection_version"] = projection_version
        manifest["snapshot_id"] += ":" + projection_version
    return pages, manifest


def _reference(page, pin, pointer):
    symbol, year = page["document_id"].split("_")
    return FinancialSourceReference(
        anchor=SourceAnchor(
            page=RawPageIdentity(
                symbol=symbol,
                year=year,
                page=page["page"],
                image="",
                source_ref="json:sha256:" + pin["sha256"],
            ),
            status="uncertain",
        ),
        source_pointer=pointer,
        provenance_level="page",
    )


def _period(header, page_context, statement):
    # Split visible header lines, retaining the original header pointer. No year
    # from the directory; relative labels use the existing annual resolver only.
    evidence = []
    for line in header.raw_text.splitlines():
        item = header.model_copy(update={"raw_text": line})
        evidence.append(column_period_evidence(item, page_context, statement))
    return resolve_financial_context(evidence)


def import_refined_document(root: Path, document: str, *, projection_version=None):
    """Return existing evidence contracts plus an explicit JSON-source manifest."""
    pages, manifest = read_refined(root, document, projection_version)
    doc, snapshot = manifest["document_id"], manifest["snapshot_id"]
    records, observations, table_reports = [], [], []
    document_context = context_lines(
        [
            ContextEvidence(
                raw_text=b["text"], provenance=[_reference(page, pin, f"/blocks/{i}/text")]
            )
            for page, pin in zip(pages, manifest["pages"], strict=True)
            for i, b in enumerate(page["blocks"])
            if b["type"] != "table" and not b.get("uncertain")
        ]
    )
    # Only explicit cover context identifies the filing company, never notes.
    cover = filing_cover(
        document_context,
        {p["page"] for p in pages if all(b["type"] != "table" for b in p["blocks"])},
    )
    company_id, company_source = company_binding(cover)
    doc_resolution = resolve_financial_context(
        [
            i
            for i in document_context
            if re.fullmatch(
                r"báo cáo tài chính (hợp nhất|riêng)|đơn vị(?: tính)?: .+", i.raw_text.strip(), re.I
            )
        ]
    )

    def anchor(ref):
        return EvidenceAnchor(document_id=doc, snapshot_id=snapshot, reference=ref)

    for page, pin in zip(pages, manifest["pages"], strict=True):

        def ref(pointer, page=page, pin=pin):
            return _reference(page, pin, pointer)

        metadata = dict(
            source_kind="refined_json",
            source_artifact=pin["path"],
            artifact_sha256=pin["sha256"],
            import_version=IMPORT_VERSION,
            model=page.get("model"),
            prompt_version=page.get("prompt_version"),
            upstream_status=page.get("status"),
            warnings=page.get("warnings", []),
            pdf_verified=False,
        )
        context = [
            ContextEvidence(
                raw_text=b["text"],
                provenance=[ref(f"/blocks/{i}/text")],
                status="uncertain" if b.get("uncertain") else "resolved",
            )
            for i, b in enumerate(page["blocks"])
            if b["type"] != "table"
        ]
        page_statement = resolve_statement_type(context)
        context = context_lines(context)
        table_number = 0
        for bi, block in enumerate(page["blocks"]):
            pointer = f"/blocks/{bi}"
            binding = dict(
                document_id=doc,
                snapshot_id=snapshot,
                local_evidence_id=f"page/{page['page']}/block/{bi}",
                sources=[
                    anchor(ref(pointer + ("/table" if block["type"] == "table" else "/text")))
                ],
                source_metadata={
                    **metadata,
                    "block_index": bi,
                    "uncertain": block.get("uncertain", False),
                },
                resolution_issues=[JSON_CAVEAT]
                + (["upstream_uncertain"] if block.get("uncertain") else []),
            )
            if block["type"] != "table":
                records.append(
                    TextEvidence(
                        **binding,
                        raw_text=block["text"],
                        structural_role=block["type"],
                    )
                )
                continue
            table_number += 1
            table = block["table"]
            base = pointer + "/table"
            table_id = f"{document}_p{page['page']:03d}_t{table_number:03d}"
            ragged = [i for i, row in enumerate(table["rows"]) if len(row) != len(table["columns"])]
            issues = (["ragged_rows"] if ragged else []) + (
                [] if table["rows"] else ["empty_table"]
            )
            cells, members = [], []
            for ri, row in enumerate([table["columns"], *table["rows"]]):
                for ci, text in enumerate(row):
                    ptr = f"{base}/columns/{ci}" if ri == 0 else f"{base}/rows/{ri - 1}/{ci}"
                    source = ref(ptr)
                    members.append(anchor(source))
                    cells.append(
                        UnderstoodCell(
                            id=ptr,
                            row=ri,
                            col=ci,
                            text=text,
                            anchors=[source.anchor],
                            status="uncertain",
                        )
                    )
            binding["source_metadata"].update(original_table=table, ragged_row_indices=ragged)
            records.append(
                TableEvidence(
                    **binding,
                    original_table_id=table_id,
                    structure=UnderstoodTable(
                        id=table_id,
                        origin="ocr_table",
                        anchors=[ref(base).anchor],
                        cells=cells,
                        status="uncertain",
                    ),
                    member_sources=members,
                    structural_issues=issues,
                )
            )
            title = ContextEvidence(
                raw_text=table.get("title", ""), provenance=[ref(base + "/title")]
            )
            statement = resolve_statement_type([title])
            statement_type = statement.statement_type or page_statement.statement_type
            report = dict(
                table_id=table_id,
                page=page["page"],
                statement_type=statement_type,
                issues=issues,
                observations=0,
            )
            table_reports.append(report)
            if issues or statement_type is None:
                if statement_type is None:
                    report["issues"] = [*issues, "statement_unresolved"]
                continue
            headers = [
                ContextEvidence(raw_text=c, provenance=[ref(f"{base}/columns/{i}")])
                for i, c in enumerate(table["columns"])
            ]
            keys = [text_key(h.raw_text) for h in headers]
            code_col = next((i for i, k in enumerate(keys) if k in {"ma so", "ms"}), None)
            label_col = next(
                (i for i, k in enumerate(keys) if k in {"chi tieu", "tai san", "nguon von"}),
                1 if keys and keys[0] in {"stt", "so tt"} and len(keys) > 1 else 0,
            )
            context = stock_page_context(context, statement_type)
            periods = {
                i: header_context(h, context, statement_type, cover) for i, h in enumerate(headers)
            }
            value_cols = [
                i
                for i, h in enumerate(headers)
                if i not in {label_col, code_col}
                and not re.search(r"thuyet|^tm$|^stt$|^note", keys[i])
                and (
                    periods[i].period.candidates
                    or any(parse_vietnamese_number(r[i]) is not None for r in table["rows"])
                )
            ]
            unit_context = resolve_financial_context([*context, title])
            section = None
            section_pointer = None
            for ri, row in enumerate(table["rows"]):
                label = row[label_col]
                code = row[code_col].strip() if code_col is not None else None
                if label.strip() and not code and all(not row[c].strip() for c in value_cols):
                    section = label
                    section_pointer = f"{base}/rows/{ri}/{label_col}"
                if not label.strip() or not (
                    code or any(parse_vietnamese_number(row[c]) is not None for c in value_cols)
                ):
                    continue
                label_evidence = ContextEvidence(
                    raw_text=label, provenance=[ref(f"{base}/rows/{ri}/{label_col}")]
                )
                mapping = map_item_label(label_evidence, statement_type, source_code=code or None)
                for ci in value_cols:
                    raw = row[ci]
                    number = parse_vietnamese_number(raw)
                    period = periods[ci]
                    column_unit = header_unit(headers[ci])
                    selected_unit = (
                        column_unit if column_unit.unit.status == "resolved" else unit_context
                    )
                    if selected_unit.unit.status == "unresolved":
                        selected_unit = doc_resolution
                    currency = selected_unit.context.currency
                    scale = selected_unit.context.scale
                    unit_conflict = (
                        column_unit.unit.status == unit_context.unit.status == "resolved"
                        and (column_unit.context.currency, column_unit.context.scale)
                        != (unit_context.context.currency, unit_context.context.scale)
                    )
                    if unit_conflict:
                        currency, scale = None, None
                    non_monetary = bool(re.search(r"%|cổ phiếu", headers[ci].raw_text, re.I))
                    if non_monetary:
                        currency, scale = None, None
                    unit, scale, unit_issues = item_unit(
                        statement_type, code, label, currency, scale
                    )
                    provenance = [
                        ref(f"{base}/rows/{ri}/{ci}"),
                        *label_evidence.provenance,
                        *headers[ci].provenance,
                        *(r for c in selected_unit.unit.candidates for r in c.evidence.provenance),
                        *(r for c in period.period.candidates for r in c.evidence.provenance),
                    ]
                    if code_col is not None:
                        provenance.append(ref(f"{base}/rows/{ri}/{code_col}"))
                    if company_source:
                        provenance.extend(company_source.provenance)
                    if section_pointer:
                        provenance.append(ref(section_pointer))
                    scope_context = (
                        unit_context
                        if unit_context.reporting_scope.status == "resolved"
                        else doc_resolution
                    )
                    provenance.extend(
                        r
                        for c in scope_context.reporting_scope.candidates
                        for r in c.evidence.provenance
                    )
                    provenance = list({p.model_dump_json(): p for p in provenance}.values())
                    context_value = FinancialContext(
                        statement_type=statement_type,
                        raw_item_label=label,
                        mapped_item_code=mapping.canonical_item_id,
                        period=period.context.period,
                        period_type=period.context.period_type,
                        reporting_scope=scope_context.context.reporting_scope,
                        currency=currency,
                        scale=scale,
                    )
                    extraction_issues = (
                        ["upstream_uncertain"] if block.get("uncertain") else []
                    ) + unit_issues
                    if unit_conflict:
                        extraction_issues.append("conflicting_unit_context")
                    if non_monetary:
                        extraction_issues.append("non_monetary_header_unit")
                    observations.append(
                        AssessableEvidence(
                            evidence_id=f"page/{page['page']}/block/{bi}/row/{ri}/column/{ci}",
                            extraction=FinancialNormalizationResult(
                                contract_version="financial_normalization_v1",
                                context=context_value,
                                value=FinancialValue(
                                    raw_value=raw,
                                    normalized_value=number,
                                    unit=unit,
                                    status="resolved" if number is not None else "unresolved",
                                ),
                                provenance=provenance,
                            ),
                            canonical_item_id=mapping.canonical_item_id,
                            source_item_code=code or None,
                            raw_header=headers[ci].raw_text,
                            extraction_issues=extraction_issues,
                            source_metadata={
                                **metadata,
                                "table_id": table_id,
                                "json_pointer": f"{base}/rows/{ri}/{ci}",
                                "mapping_issues": mapping.issues,
                                "row_path": [section, label]
                                if section and section != label
                                else [label],
                                "source_column": ci,
                            },
                        )
                    )
                    report["observations"] += 1
    quality = assess_evidence_for_task(observations)
    facts = [
        fact_from_m2(
            item.evidence,
            document_id=doc,
            snapshot_id=snapshot,
            company_id=company_id,
            quality_context=[
                TaskQualityContext(
                    task_type="direct_qa",
                    decision="usable_with_caveat" if item.decision == "usable" else item.decision,
                    evidence_ids=[item.evidence.evidence_id],
                    issues=item.issues,
                    caveats=[*item.caveats, JSON_CAVEAT],
                )
            ],
        )
        for item in quality.items
    ]
    summary = dict(
        pages=len(pages),
        missing_pages=manifest["missing_pages"],
        text_records=sum(r.kind == "text" for r in records),
        table_records=len(table_reports),
        facts=len(facts),
        numeric_values=sum(f.value.normalized_value is not None for f in facts),
        mapped_facts=sum(f.canonical_item_id is not None for f in facts),
        facts_with_period=sum(f.context.period is not None for f in facts),
        facts_with_unit=sum(f.value.unit is not None for f in facts),
        quality_counts=dict(Counter(f.quality_context[0].decision for f in facts)),
        tables=table_reports,
        pdf_verified=False,
        financial_fact_verified=False,
    )
    return manifest, facts, records, summary
