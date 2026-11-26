"""JSON source bindings for the existing SnapshotCatalog; no PDF review claims."""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from ..accounting.automated_extraction import parse_vietnamese_number
from .contracts import is_json_reference


def resolve_pointer(value, pointer):
    for key in pointer.strip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def json_snapshot_issues(catalog, descriptor):
    descriptors = [
        d
        for d in catalog.descriptors
        if (d.document_id, d.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
    ]
    if len(descriptors) != 1 or descriptors[0] != descriptor:
        return ["json_snapshot_ambiguous"]
    if (
        not re.fullmatch(r"[0-9a-f]{64}", descriptor.json_sha256 or "")
        or descriptor.document_id != "json:sha256:" + (descriptor.json_sha256 or "")
        or not descriptor.json_pages
        or descriptor.parent_snapshot_id is not None
    ):
        return ["json_snapshot_identity_invalid"]
    sources = getattr(catalog, "json_sources", {})
    if any(digest not in sources for digest in descriptor.json_pages.values()):
        return ["json_original_sources_unavailable"]
    raw_sources = getattr(catalog, "json_source_bytes", {})
    if any(
        digest not in raw_sources
        or hashlib.sha256(raw_sources[digest]).hexdigest() != digest
        or json.loads(raw_sources[digest]) != sources[digest]
        for digest in descriptor.json_pages.values()
    ):
        return ["json_original_sources_changed"]
    return []


def json_fact_bound(catalog, fact):
    return json_fact_issue(catalog, fact) is None


def json_fact_issue(catalog, fact):
    """Replay JSON value/selector binding and return the first unresolved condition."""
    selected = [
        d
        for d in catalog.descriptors
        if (d.document_id, d.snapshot_id) == (fact.document_id, fact.snapshot_id)
        and d.source_kind == "json"
    ]
    if len(selected) != 1 or json_snapshot_issues(catalog, selected[0]) or not fact.sources:
        return "json_snapshot_or_sources_unavailable"
    identity = fact.observation_identity()
    if (
        identity is None
        or catalog.json_fact_pins.get(identity.model_dump_json())
        != hashlib.sha256(fact.model_dump_json().encode()).hexdigest()
    ):
        return "json_observation_pin_mismatch"
    if not fact.company_id or fact.value.status != "resolved":
        return "json_fact_identity_or_value_unresolved"
    if not fact.context.period or not fact.context.period_type:
        return "json_fact_period_unresolved"
    if not fact.value.unit or not fact.context.currency or not fact.context.scale:
        return "json_fact_unit_unresolved"
    if fact.context.currency != fact.value.unit or fact.context.scale <= 0:
        return "json_fact_unit_conflict"
    if not fact.quality_context or any(
        q.decision not in {"usable", "usable_with_caveat"} for q in fact.quality_context
    ):
        return "json_fact_quality_ineligible"
    descriptor = selected[0]
    try:
        for source in fact.sources:
            ref = source.reference
            if (
                ref is None
                or not is_json_reference(ref)
                or (source.document_id, source.snapshot_id) != (fact.document_id, fact.snapshot_id)
            ):
                return "json_fact_source_identity_mismatch"
            digest = descriptor.json_pages[ref.anchor.page.page]
            if ref.anchor.page.source_ref != "json:sha256:" + digest:
                return "json_fact_page_hash_mismatch"
            resolve_pointer(catalog.json_sources[digest], ref.source_pointer)
        ref = fact.sources[0].reference
        raw = resolve_pointer(
            catalog.json_sources[descriptor.json_pages[ref.anchor.page.page]], ref.source_pointer
        )
        if (
            raw != fact.value.raw_value
            or parse_vietnamese_number(raw) != fact.value.normalized_value
        ):
            return "json_fact_cell_value_mismatch"
        return None
    except (KeyError, IndexError, TypeError, ValueError):
        return "json_fact_source_pointer_unresolved"


def json_reporting_scope(catalog, descriptor):
    """Read explicit filing titles/options, never infer separate from absence."""
    from ..accounting.context_resolution import ContextEvidence, resolve_financial_context
    from .refined_context import context_lines
    from .refined_import import _reference
    from .reporting_scope import ReportingScopeResolution

    items = []
    for number, digest in descriptor.json_pages.items():
        if number > 5:
            continue
        page = catalog.json_sources.get(digest, {})
        for i, block in enumerate(page.get("blocks", [])):
            if block.get("uncertain") or not isinstance(block.get("text"), str):
                continue
            ref = _reference(page, {"sha256": digest}, f"/blocks/{i}/text")
            for line in block["text"].splitlines():
                option = re.fullmatch(r"\s*\[\s*([xX?]?)\s*\]\s*(.+?)\s*[;.]?", line)
                if option:
                    if option[1] == "":
                        continue  # An unselected option is not a scope declaration.
                    if not re.match(r"(?:bctc|báo cáo tài chính)\b", option[2], re.I):
                        continue  # Other yes/no checkboxes do not describe filing scope.
                    items.append(
                        ContextEvidence(
                            raw_text=option[2].rstrip(";.").strip(),
                            provenance=[ref],
                            scope_selection="selected" if option[1].lower() == "x" else "unknown",
                        )
                    )
                else:
                    # context_lines retains the exact source pointer when projecting a title.
                    items.extend(
                        e
                        for e in context_lines([ContextEvidence(raw_text=line, provenance=[ref])])
                        if re.fullmatch(
                            r"báo cáo tài chính (hợp nhất|riêng)", e.raw_text.strip(), re.I
                        )
                    )
    context = resolve_financial_context(items)
    scopes = {
        f.context.reporting_scope
        for f in catalog.facts
        if (f.document_id, f.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
        and f.context.reporting_scope is not None
    }
    if context.context.reporting_scope:
        scopes.add(context.context.reporting_scope)
    conflict = len(scopes) > 1 or "conflicting_candidates" in context.reporting_scope.issues
    resolved = (
        len(scopes) == 1
        and not conflict
        and not catalog.ancestry(descriptor)[1]
        and (not items or context.reporting_scope.status == "resolved")
    )
    return ReportingScopeResolution(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        reporting_scope=next(iter(scopes)) if resolved else None,
        status="resolved" if resolved else "conflicted" if conflict else "unresolved",
        evidence_status="json_bound" if resolved else "conflicted" if conflict else "insufficient",
        reviews=[],
        context_resolution=context,
        reasons=["json_scope_not_pdf_reviewed"]
        + (
            []
            if resolved
            else ["scope_conflicting_evidence" if conflict else "scope_source_insufficient"]
        ),
    )


def json_evidence_bound(catalog, descriptor, record):
    """Replay text/table payload against original bytes before exposing search results."""
    if (record.document_id, record.snapshot_id) != (descriptor.document_id, descriptor.snapshot_id):
        return False
    try:
        checked = set()
        for source in [*record.sources, *getattr(record, "member_sources", [])]:
            ref = source.reference
            if (source.document_id, source.snapshot_id) != (
                record.document_id,
                record.snapshot_id,
            ) or not is_json_reference(ref):
                return False
            digest = descriptor.json_pages[ref.anchor.page.page]
            if ref.anchor.page.source_ref != "json:sha256:" + digest:
                return False
            if digest not in checked:
                raw = catalog.json_source_bytes[digest]
                if (
                    hashlib.sha256(raw).hexdigest() != digest
                    or json.loads(raw) != catalog.json_sources[digest]
                ):
                    return False
                checked.add(digest)
            resolve_pointer(catalog.json_sources[digest], ref.source_pointer)
        ref = record.sources[0].reference
        value = resolve_pointer(
            catalog.json_sources[descriptor.json_pages[ref.anchor.page.page]], ref.source_pointer
        )
        if record.kind == "text":
            return value == record.raw_text
        expected = [
            (r, c, text)
            for r, row in enumerate([value["columns"], *value["rows"]])
            for c, text in enumerate(row)
        ]
        return record.source_metadata.get("original_table") == value and expected == [
            (c.row, c.col, c.text) for c in record.structure.cells
        ]
    except (KeyError, IndexError, AttributeError, TypeError, ValueError):
        return False


def json_page_context(page, digest):
    """Use the same pinned text and context normalization as the refined importer."""
    from ..accounting.context_resolution import ContextEvidence
    from .refined_context import context_lines
    from .refined_import import _reference

    return context_lines(
        [
            ContextEvidence(
                raw_text=block["text"],
                provenance=[_reference(page, {"sha256": digest}, f"/blocks/{i}/text")],
            )
            for i, block in enumerate(page["blocks"])
            if not block.get("uncertain") and block.get("text")
        ]
    )


def json_filing_issuer(catalog, descriptor, company_id):
    """Resolve the role of issuer from pinned front matter, including mixed audit covers."""
    from ..accounting.extraction_semantics import text_key
    from .refined_context import company_binding, filing_cover

    if json_snapshot_issues(catalog, descriptor):
        return set(), None
    front = {
        digest: catalog.json_sources[digest]
        for number, digest in descriptor.json_pages.items()
        if number <= 5
    }
    by_page = {digest: json_page_context(page, digest) for digest, page in front.items()}
    cover = filing_cover(
        [item for items in by_page.values() for item in items],
        {page["page"] for page in front.values() if all("table" not in b for b in page["blocks"])},
    )
    owner, _ = company_binding(cover)
    if owner != company_id:
        return set(), None
    legal_form = re.compile(r"^cong ty (?:co phan|cp|tnhh)(?: |$)")

    def company(item):
        key = text_key(item.raw_text)
        if not legal_form.match(key):
            return None
        name = item.raw_text.strip()
        ref = item.provenance[0]
        if not legal_form.sub("", key):
            original = resolve_pointer(
                front[ref.anchor.page.source_ref.rsplit(":", 1)[-1]], ref.source_pointer
            ).splitlines()
            if len(original) > 1 and text_key(original[0]) == key:
                name += " " + original[1].strip()
        short = legal_form.sub("", text_key(name))
        return (short, name, ref) if short else None

    names = {row[0]: row for item in cover if (row := company(item))}
    if len(names) != 1:
        # On a joint cover, the company directly attached to the filing title
        # has the issuer role. Other headings (including auditor) confer no alias.
        primary = {}
        for items in by_page.values():
            for prior, item in zip(items[:-1], items[1:], strict=True):
                if not re.fullmatch(
                    r"bao cao tai chinh(?: hop nhat| rieng)?(?: da duoc kiem toan)?"
                    r"(?: (?:cho )?nam tai chinh ket thuc(?: vao)? ngay .+)?",
                    text_key(item.raw_text),
                ):
                    continue
                if row := company(prior):
                    primary[row[0]] = (*row, item.provenance[0])
        if len(primary) != 1:
            return set(), None
        short, name, ref, title_ref = next(iter(primary.values()))
        issuer_refs = [ref, title_ref]
        # The legacy key may have been derived from the auditor heading. A
        # document key in that state is not an issuer alias.
        keys = set()
    else:
        short, name, ref = next(iter(names.values()))
        issuer_refs = [ref]
        keys = {company_id}

    tickers = {page["document_id"].rsplit("_", 1)[0] for page in front.values()}
    if len(tickers) != 1:
        return set(), None
    declared = (
        {
            match[1].strip()
            for item in cover
            if (
                match := re.fullmatch(
                    r"t\u00ean vi\u1ebft t\u1eaft\s*:\s*(.+)", item.raw_text.strip(), re.I
                )
            )
        }
        if len(names) == 1
        else set()
    )
    return (
        {short, name, *keys, *tickers, *(declared if len(declared) == 1 else ())},
        dict(name=name, provenance=[ref.model_dump(mode="json") for ref in issuer_refs]),
    )


def json_table_cells(catalog, descriptor, record, cells, scope):
    """Project only returned cells of a replayable JSON table, keeping their source selectors."""
    from ..accounting.context_resolution import ContextEvidence, resolve_financial_context
    from ..accounting.extraction_semantics import item_unit, numeric_token_issues, text_key
    from ..accounting.statement_resolution import resolve_statement_type
    from .refined_context import (
        context_lines,
        header_context,
        header_unit,
        projected,
        stock_page_context,
    )

    if (
        record.kind != "table"
        or record.source_metadata.get("uncertain")
        or scope.status not in {"resolved", "unresolved"}
        or not json_evidence_bound(catalog, descriptor, record)
    ):
        return
    root = record.sources[0].reference
    digest = descriptor.json_pages[root.anchor.page.page]
    page_context = json_page_context(catalog.json_sources[digest], digest)
    table = record.source_metadata["original_table"]
    anchors = {s.reference.source_pointer: s.reference for s in record.member_sources}

    def context_value(pointer, raw):
        return ContextEvidence(raw_text=raw, provenance=[anchors[pointer]])

    title = ContextEvidence(
        raw_text=table.get("title", ""),
        provenance=[root.model_copy(update={"source_pointer": root.source_pointer + "/title"})],
    )
    title_statement, page_statement = (
        resolve_statement_type(
            [
                projected(item, re.sub(r"\(tiếp\)$", "(tiếp theo)", item.raw_text, flags=re.I))
                for item in items
            ]
        )
        for items in (context_lines([title]), page_context)
    )
    statement = title_statement.statement_type or page_statement.statement_type
    if (not statement and not title.raw_text.strip()) or (
        title_statement.statement_type
        and page_statement.statement_type
        and title_statement.statement_type != page_statement.statement_type
    ):
        return
    table_context = resolve_financial_context([*page_context, title] if statement else [title])

    # Keep reporting dates local to the statement heading, never signature dates.
    def heading_dates(items, resolution):
        refs = {
            ref.source_pointer
            for candidate in resolution.candidates
            if candidate.signal == "title"
            and candidate.status == "resolved"
            and candidate.value.statement_type == statement
            for ref in candidate.evidence.provenance
        }
        return stock_page_context(
            [item for item in items if item.provenance[0].source_pointer in refs], statement
        )

    report_dates = heading_dates(page_context, page_statement)
    columns = table["columns"]
    previous = descriptor.json_pages.get(root.anchor.page.page - 1)
    previous_dates = []
    if (
        previous
        and resolve_financial_context(report_dates).period.status == "unresolved"
        and any(re.search(r"[(]tiếp(?: theo)?[)]", item.raw_text, re.I) for item in report_dates)
    ):
        from .refined_context import company_binding

        page = catalog.json_sources[previous]
        previous_context = json_page_context(page, previous)
        issuer = company_binding(page_context)[0]
        if (
            issuer
            and company_binding(previous_context)[0] == issuer
            and any(
                b.get("table", {}).get("columns") == columns
                for b in page["blocks"]
                if b.get("table") and not b.get("uncertain")
            )
        ):
            previous_dates = heading_dates(
                previous_context, resolve_statement_type(previous_context)
            )
    keys = [text_key(column) for column in columns]
    code_col = next((i for i, key in enumerate(keys) if key in {"ma so", "ms"}), None)
    label_col = next(
        (i for i, key in enumerate(keys) if key in {"chi tieu", "tai san", "nguon von"}),
        1 if keys and keys[0] in {"stt", "so tt"} and len(keys) > 1 else 0,
    )
    if not columns or table_context.unit.status == "conflicted":
        return
    base = root.source_pointer
    # Continuation pages and note tables may omit the reporting year. Use only
    # an explicit calendar-year boundary on a pinned financial-report cover.
    cover_dates = []
    for page_number, page_digest in descriptor.json_pages.items():
        if page_number > 5:
            continue
        items = json_page_context(catalog.json_sources[page_digest], page_digest)
        if not any(
            re.fullmatch(r"báo cáo tài chính(?: hợp nhất| riêng)?", i.raw_text.strip(), re.I)
            for i in items
        ):
            continue
        for item in items:
            match = re.fullmatch(
                r"(?:cho )?năm tài chính kết thúc(?: tại| vào)? ngày (?:31 tháng 12 năm |31/12/)(\d{4})",
                item.raw_text.strip(),
                re.I,
            )
            if match:
                cover_dates.append((match[1], item))
    cover_years = {year for year, _ in cover_dates}
    if len(cover_years) != 1:
        cover_dates = []
    cover_stock = [projected(item, f"Tại ngày 31/12/{year}") for year, item in cover_dates]
    cover_flow = [projected(item, f"Năm {year}") for year, item in cover_dates]
    continuation_context = resolve_financial_context(previous_dates)
    # Notes can continue a numbered, same-header sequence across a page boundary.
    # Carry only an explicit unit-bearing section heading, with pinned provenance.
    note_unit_context = None
    if not statement and previous and table_context.unit.status == "unresolved":
        from .refined_context import company_binding

        previous_page = catalog.json_sources[previous]
        previous_items = json_page_context(previous_page, previous)
        current_page = catalog.json_sources[digest]
        previous_blocks = previous_page["blocks"]
        current_blocks = current_page["blocks"][: int(base.split("/")[2]) + 1]
        issuer = company_binding(page_context)[0]

        def sequence(blocks):
            result = []
            for block in blocks:
                table_ = block.get("table")
                match = re.match(r"^(\d+)\.\s+", (table_ or {}).get("title") or "")
                if not match or block.get("uncertain") or table_["columns"] != columns:
                    return []
                result.append(int(match[1]))
            return result

        if issuer and company_binding(previous_items)[0] == issuer:
            for i in range(len(previous_blocks) - 1, -1, -1):
                block = previous_blocks[i]
                text = block.get("text", "")
                if not text or block.get("uncertain"):
                    continue
                # Both sides must be contiguous numbered tables after a section heading.
                if not re.match(r"^[IVXLCDM]+\.\s+", text):
                    break
                prior_sequence = sequence(previous_blocks[i + 1 :])
                first = next(
                    (j for j, b in enumerate(current_blocks) if b.get("table")), len(current_blocks)
                )
                this_sequence = sequence(current_blocks[first:])
                numbers = prior_sequence + this_sequence
                if prior_sequence and this_sequence and numbers == list(range(1, len(numbers) + 1)):
                    unit_items = [
                        item
                        for item in previous_items
                        if item.provenance[0].source_pointer == f"/blocks/{i}/text"
                    ]
                    candidate = resolve_financial_context(context_lines(unit_items))
                    if candidate.unit.status == "resolved":
                        note_unit_context = candidate
                break
    column_context = {}
    for col, column in enumerate(columns):
        if col in {code_col, label_col} or re.search(r"thuyet|^tm$|^stt$|^note", keys[col]):
            continue
        header = context_value(f"{base}/columns/{col}", column)
        period = header_context(header, report_dates, statement, previous_dates)
        if period.period.status == "unresolved":
            period = header_context(
                header, report_dates, statement, cover_stock if statement == "B01" else cover_flow
            )
        first_row = table["rows"][0] if table["rows"] else []
        # A leading unit row has empty identifier cells and only explicit units.
        # In particular a number or line-item name cannot serve as a unit.
        unit_row = (
            len(first_row) == len(columns)
            and all(not first_row[i].strip() for i in {label_col, code_col} - {None})
            and all(
                text_key(value)
                in {
                    "",
                    "vnd",
                    "dong",
                    "nghin dong",
                    "trieu dong",
                    "ngan dong",
                    "nghin vnd",
                    "ngan vnd",
                    "trieu vnd",
                }
                for value in first_row
            )
        )
        unit_sources = [header_unit(header)]
        if unit_row and first_row[col].strip():
            unit_sources.insert(
                0, header_unit(context_value(f"{base}/rows/0/{col}", first_row[col]))
            )
        resolved_units = [item for item in unit_sources if item.unit.status == "resolved"]
        if not resolved_units:
            resolved_units = [
                item
                for item in (table_context, continuation_context, note_unit_context)
                if item is not None and item.unit.status == "resolved"
            ]
        if len({(item.context.currency, item.context.scale) for item in resolved_units}) > 1:
            continue
        unit_context = resolved_units[0] if resolved_units else table_context
        column_context[col] = (header, period, unit_context)
    group = None
    groups = {}
    for row, values in enumerate(table["rows"]):
        if len(values) != len(columns):
            group = None
            continue
        if values[label_col].strip() and all(
            not value.strip() for i, value in enumerate(values) if i != label_col
        ):
            group = row
        groups[row] = group
    for cell in cells:
        if not cell.row or cell.column is None or cell.row - 1 not in groups:
            continue
        row, col = cell.row - 1, cell.column
        if col not in column_context:
            continue
        raw = table["rows"][row][col]
        if cell.text != raw or numeric_token_issues(raw):
            continue
        label = table["rows"][row][label_col]
        code = table["rows"][row][code_col].strip() if code_col is not None else None
        if not label.strip():
            continue
        pointer = f"{base}/rows/{row}/{col}"
        if pointer != cell.source_pointer:
            continue
        header, period, unit_context = column_context[col]
        # Some notes place the reporting boundary on the row, not the column.
        # Preserve the exact row selector and use the existing period resolver.
        if period.period.status == "unresolved":
            row_header = context_value(f"{base}/rows/{row}/{label_col}", label)
            relative = {"tai ngay dau nam": "Số đầu năm", "tai ngay cuoi nam": "Số cuối năm"}
            row_period = header_context(
                projected(row_header, relative.get(text_key(label), label)),
                report_dates or page_context,
                statement or "B01",
                previous_dates or cover_stock,
            )
            if row_period.period.status == "resolved":
                period = row_period
        unit, scale, _ = item_unit(
            statement, code, label, unit_context.context.currency, unit_context.context.scale
        )
        group_row = groups[row]
        group_label = table["rows"][group_row][label_col] if group_row is not None else None
        refs = [anchors[pointer], anchors[f"{base}/rows/{row}/{label_col}"], *header.provenance]
        if title.raw_text.strip():
            refs.extend(title.provenance)
        if code_col is not None:
            refs.append(anchors[f"{base}/rows/{row}/{code_col}"])
        if group_row is not None:
            refs.append(anchors[f"{base}/rows/{group_row}/{label_col}"])
        refs.extend(
            ref
            for candidate in [
                *period.period.candidates,
                *unit_context.unit.candidates,
                *(
                    title_statement.candidates
                    if title_statement.statement_type
                    else page_statement.candidates
                ),
                *(
                    scope.context_resolution.reporting_scope.candidates
                    if scope.context_resolution
                    else ()
                ),
            ]
            for ref in candidate.evidence.provenance
            if ref.source_pointer
        )
        yield dict(
            statement=statement,
            label=label,
            code=code,
            table=record.original_table_id,
            title=table.get("title"),
            group=group_label,
            period=period.context.period,
            period_type=period.context.period_type,
            unit=unit,
            scale=str(scale) if scale else None,
            scope=scope.reporting_scope if scope.status == "resolved" else None,
            header=columns[col],
            raw_value=raw,
            source_pointer=pointer,
            provenance=[
                ref.model_dump(mode="json")
                for ref in {ref.model_dump_json(): ref for ref in refs}.values()
            ],
            caveat="json_source_not_pdf_verified",
        )


def json_cell_observation(descriptor, cell, issuer, company_id):
    """Adapt an eligible pinned JSON cell to the existing SourceFact contract."""
    from ..accounting.context_resolution import ContextEvidence
    from ..accounting.contracts import FinancialContext, FinancialSourceReference, FinancialValue
    from ..accounting.extraction_semantics import text_key
    from ..accounting.item_mapping import map_item_label
    from .contracts import EvidenceAnchor, SourceFact, TaskQualityContext

    if not cell["period"] or not cell["period_type"]:
        return None, "period_unresolved"
    if not cell["unit"] or not cell["scale"]:
        return None, "unit_unresolved"
    if not issuer:
        return None, "unsupported_document_operand"
    value, scale = parse_vietnamese_number(cell["raw_value"]), Decimal(cell["scale"])
    if value is None or not value.is_finite() or not scale.is_finite() or scale <= 0:
        return None, "missing_numeric_cell"
    refs = [
        FinancialSourceReference.model_validate(ref)
        for ref in [*cell["provenance"], *issuer["provenance"]]
    ]
    first = refs[0]
    if not is_json_reference(first) or first.source_pointer != cell["source_pointer"]:
        return None, "missing_numeric_cell"
    # Shared printed labels need the pinned statement and row code to distinguish them.
    label = ContextEvidence(raw_text=cell["label"], provenance=[refs[1]])
    mapping = map_item_label(label, cell["statement"]) if cell["statement"] else None
    if mapping and "ambiguous_label" in mapping.issues and cell["code"]:
        mapping = map_item_label(label, cell["statement"], source_code=cell["code"])
    else:
        mapping = None
    observation_id = f"json-cell:{first.anchor.page.page}:{first.source_pointer}"
    pins = dict(document_id=descriptor.document_id, snapshot_id=descriptor.snapshot_id)
    row_label = cell["label"]
    if cell["title"] and not cell["statement"] and text_key(row_label) in {"tong cong", "cong"}:
        row_label = f"{cell['title']} — {row_label}"
    fact = SourceFact(
        **pins,
        local_observation_id=observation_id,
        company_id=company_id,
        canonical_item_id=mapping.canonical_item_id if mapping else None,
        source_item_code=cell["code"] or None,
        raw_header=cell["header"],
        source_metadata=dict(
            source_kind="refined_json",
            projection="document_cell",
            table_id=cell["table"],
            table_title=cell["title"],
            json_pointer=cell["source_pointer"],
            source_column=int(first.source_pointer.rsplit("/", 1)[-1]),
            row_path=[label for label in (cell["group"], cell["label"]) if label],
        ),
        context=FinancialContext(
            raw_item_label=row_label,
            statement_type=cell["statement"],
            period=cell["period"],
            period_type=cell["period_type"],
            reporting_scope=cell["scope"],
            currency=cell["unit"],
            scale=scale,
        ),
        value=FinancialValue(
            raw_value=cell["raw_value"],
            normalized_value=value,
            unit=cell["unit"],
            status="resolved",
        ),
        sources=[
            EvidenceAnchor(**pins, reference=ref)
            for ref in {ref.model_dump_json(): ref for ref in refs}.values()
        ],
        quality_context=[
            TaskQualityContext(
                task_type="direct_qa",
                decision="usable_with_caveat",
                evidence_ids=[observation_id],
                caveats=[cell["caveat"]],
            )
        ],
    )
    return fact, None


def json_document_composition(catalog):
    """Bind one already selected JSON snapshot; 'verified' means byte fidelity only."""
    from .composition import CompositionSource, EvidenceComposition, EvidencePin, payload_sha256

    if len(catalog.descriptors) != 1 or catalog.descriptors[0].source_kind != "json":
        raise ValueError("one_explicit_json_snapshot_required")
    descriptor = catalog.descriptors[0]
    if json_snapshot_issues(catalog, descriptor):
        raise ValueError("json_snapshot_binding_invalid")
    if not catalog.evidence or any(
        not json_evidence_bound(catalog, descriptor, e) for e in catalog.evidence
    ):
        raise ValueError("json_evidence_payload_mismatch")
    pins = [
        EvidencePin(
            identity=e.evidence_identity(), payload_sha256=payload_sha256(e.model_dump(mode="json"))
        )
        for e in catalog.evidence
    ]
    return EvidenceComposition(
        composition_id="json-composition:"
        + payload_sha256([p.model_dump(mode="json") for p in pins]),
        logical_document_id=descriptor.document_id,
        financial_snapshot=descriptor,
        sources=[
            CompositionSource(
                descriptor=descriptor,
                original_source="pinned_refined_json",
                artifact_sha256=descriptor.json_sha256,
                status="verified",
                evidence=pins,
            )
        ],
    )


def load_json_composition(manifest, repository):
    from .composition import payload_sha256
    from .snapshots import SnapshotCatalog

    descriptor = manifest.financial_snapshot
    if (
        len(manifest.sources) != 1
        or manifest.logical_document_id != descriptor.document_id
        or repository.descriptors != [descriptor]
        or json_snapshot_issues(repository, descriptor)
    ):
        raise ValueError("json_composition_snapshot_mismatch")
    source = manifest.sources[0]
    if (
        source.descriptor != descriptor
        or source.status != "verified"
        or source.pages
        or source.artifact_sha256 != descriptor.json_sha256
    ):
        raise ValueError("json_composition_source_mismatch")
    records = {
        e.evidence_identity().model_dump_json(): e
        for e in repository.list_by_document(descriptor.document_id, descriptor.snapshot_id)
    }
    rows, seen = [], set()
    for pin in source.evidence:
        key = pin.identity.model_dump_json()
        record = records.get(key)
        if (
            key in seen
            or record is None
            or payload_sha256(record.model_dump(mode="json")) != pin.payload_sha256
            or not json_evidence_bound(repository, descriptor, record)
        ):
            raise ValueError("json_composition_evidence_mismatch")
        seen.add(key)
        rows.append(record)
    return SnapshotCatalog([descriptor], evidence=rows, json_sources=repository.json_source_bytes)


def _complete_json_observations(catalog, descriptor):
    """Complete missing period/unit of existing observations from exact pinned cells."""
    from ..accounting.contracts import FinancialSourceReference
    from .composition import payload_sha256
    from .contracts import EvidenceAnchor
    from .search import _cells

    tables = {r.original_table_id: r for r in catalog.evidence if r.kind == "table"}
    scope = catalog.get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)
    missing = {"missing_period", "missing_period_type", "missing_unit"}
    cells, issuers, original = {}, {}, {}
    for i, fact in enumerate(catalog.facts):
        context = fact.context
        if (
            all(
                (
                    context.period,
                    context.period_type,
                    context.currency,
                    context.scale,
                    fact.value.unit,
                )
            )
            or fact.value.status != "resolved"
            or not fact.sources
            or not fact.quality_context
            or any(
                q.decision == "conflicted"
                or (
                    q.decision == "insufficient"
                    and (
                        "missing_period" not in {issue.code for issue in q.issues}
                        or {issue.code for issue in q.issues}
                        - missing
                        - {"missing_canonical_mapping"}
                    )
                )
                for q in fact.quality_context
            )
            or any(issue.code == "m2_extraction_issue" for issue in fact.resolution_issues)
            or (table_id := fact.source_metadata.get("table_id")) not in tables
        ):
            continue
        if fact.company_id not in issuers:
            _, issuers[fact.company_id] = json_filing_issuer(catalog, descriptor, fact.company_id)
        issuer = issuers[fact.company_id]
        if not issuer:
            continue
        record = tables[table_id]
        if table_id not in cells:
            cells[table_id] = {
                row["source_pointer"]: row
                for row in json_table_cells(catalog, descriptor, record, _cells(record), scope)
            }
        ref = fact.sources[0].reference
        row = cells[table_id].get(ref.source_pointer) if ref else None
        if not row or not all(row[k] for k in ("period", "period_type", "unit", "scale")):
            continue
        expected = (
            row["label"],
            row["code"] or None,
            row["header"],
            row["statement"],
            row["raw_value"],
        )
        if (
            expected
            != (
                context.raw_item_label,
                fact.source_item_code,
                fact.raw_header,
                context.statement_type,
                fact.value.raw_value,
            )
            or parse_vietnamese_number(row["raw_value"]) != fact.value.normalized_value
        ):
            continue
        refs = [
            FinancialSourceReference.model_validate(source)
            for source in [*row["provenance"], *issuer["provenance"]]
        ]
        if (
            not refs
            or refs[0] != ref
            or fact.source_metadata.get("source_column")
            != int(ref.source_pointer.rsplit("/", 1)[-1])
        ):
            continue
        update = dict(
            period=row["period"],
            period_type=row["period_type"],
            currency=row["unit"],
            scale=Decimal(row["scale"]),
        )
        if any(getattr(context, key) not in (None, value) for key, value in update.items()) or (
            fact.value.unit not in (None, row["unit"])
            or context.reporting_scope
            and row["scope"]
            and context.reporting_scope != row["scope"]
        ):
            continue
        revised = fact.model_copy(
            update=dict(
                context=context.model_copy(update=update),
                value=fact.value.model_copy(update={"unit": row["unit"]}),
                sources=[
                    EvidenceAnchor(
                        document_id=fact.document_id, snapshot_id=fact.snapshot_id, reference=source
                    )
                    for source in {source.model_dump_json(): source for source in refs}.values()
                ],
                quality_context=[
                    q.model_copy(
                        update=dict(
                            decision="usable_with_caveat",
                            issues=[issue for issue in q.issues if issue.code not in missing],
                            caveats=[c for c in q.caveats if c not in missing],
                        )
                    )
                    for q in fact.quality_context
                ],
                resolution_issues=[
                    issue for issue in fact.resolution_issues if issue.code not in missing
                ],
            )
        )
        original[fact.local_observation_id] = payload_sha256(fact.model_dump(mode="json"))
        catalog.facts[i] = revised
    return original


def load_json_catalog(root: Path, bundle: Path):
    """Load persisted artifacts and re-pin original JSON; no Gold or PDF needed."""
    from .document_repository import DocumentEvidenceRepository
    from .graph import EvidenceGraph, build_graph, validate_graph
    from .refined_import import read_refined
    from .repository import CanonicalFactRepository
    from .snapshots import SnapshotCatalog, SnapshotDescriptor

    manifest = json.loads((bundle / "manifest.json").read_bytes())
    _, current = read_refined(root, manifest["document_alias"], manifest.get("projection_version"))
    if current != manifest:
        raise ValueError("json_import_manifest_changed")
    doc, snapshot = manifest["document_id"], manifest["snapshot_id"]
    facts = CanonicalFactRepository(bundle).list_by_document(doc, snapshot)
    evidence = DocumentEvidenceRepository(bundle).list_by_document(doc, snapshot)
    graph = EvidenceGraph.model_validate_json((bundle / "graph.json").read_bytes())
    validation = validate_graph(graph, facts, evidence)
    if any(a.status != "valid" for a in [*validation.nodes, *validation.edges, *validation.inputs]):
        raise ValueError("json_import_graph_invalid")
    descriptor = SnapshotDescriptor(
        document_id=doc,
        snapshot_id=snapshot,
        source_kind="json",
        pdf_sha256=None,
        json_sha256=doc.rsplit(":", 1)[1],
        json_pages={p["page"]: p["sha256"] for p in manifest["pages"]},
        origin="normalized_projection",
    )
    sources = {p["sha256"]: (root / p["path"]).read_bytes() for p in manifest["pages"]}
    catalog = SnapshotCatalog(
        [descriptor], facts=facts, evidence=evidence, graph=graph, json_sources=sources
    )
    original = _complete_json_observations(catalog, descriptor)
    if original:
        catalog = SnapshotCatalog(
            [descriptor],
            facts=catalog.facts,
            evidence=evidence,
            graph=build_graph(catalog.facts, evidence),
            json_sources=sources,
        )
        catalog.json_import_fact_hashes = original
    return catalog


def load_json_corpus_document(root: Path, corpus: Path, document_alias: str, *, cache=None):
    """Select a filing; optional caller-owned cache holds read-only batch resources.

    Requests must keep using request_snapshot() for detached mutable tool state.
    """
    index = json.loads((corpus / "catalog-index.json").read_bytes())
    if index["version"] != "vifinbench-json-corpus-v1":
        raise ValueError("unsupported_json_corpus_index")
    entry = index["documents"][document_alias]
    if not re.fullmatch(r"[A-Z0-9]+_20\d{2}", document_alias) or entry["bundle"] != document_alias:
        raise ValueError("invalid_json_corpus_bundle")
    bundle = (corpus / entry["bundle"]).resolve()
    if not bundle.is_relative_to(corpus.resolve()):
        raise ValueError("json_corpus_bundle_outside_root")
    # Caller owns this batch cache. Content hashes include original pages and all
    # persisted projections, so a changed snapshot never reuses a previous load.
    key = None
    if cache is not None:
        manifest = json.loads((bundle / "manifest.json").read_bytes())
        paths = [*bundle.rglob("*.json"), *bundle.rglob("*.jsonl")]
        paths.extend(root / p["path"] for p in manifest["pages"])
        symbol, year = document_alias.split("_")
        paths.extend((root / symbol / year).glob("page_*.json"))
        key = (
            str(root.resolve()),
            str(corpus.resolve()),
            document_alias,
            hashlib.sha256((corpus / "catalog-index.json").read_bytes()).hexdigest(),
            tuple(
                (str(p.resolve()), hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted(set(paths))
            ),
        )
        if document_alias in cache and cache[document_alias][0] == key:
            return cache[document_alias][1]
    catalog = load_json_catalog(root, bundle)
    descriptor = catalog.descriptors[0]
    if (descriptor.document_id, descriptor.snapshot_id) != (
        entry["document_id"],
        entry["snapshot_id"],
    ):
        raise ValueError("json_corpus_index_identity_mismatch")
    if cache is not None:
        cache[document_alias] = (key, catalog)
    return catalog
