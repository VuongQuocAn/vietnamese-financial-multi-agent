"""Evidence-bound row coverage; no expected-template or model self-certification."""

from typing import Literal

from pydantic import Field

from .contracts import FinancialModel
from .extraction_semantics import text_key


class SourceRow(FinancialModel):
    label: str
    code: str | None = None
    selector: str
    status: Literal["observed", "ambiguous", "unreadable", "not_applicable"] = "observed"
    value_columns: list[int] = Field(default_factory=list)


class SourceRowInventory(FinancialModel):
    version: Literal["source-row-inventory-v1"] = "source-row-inventory-v1"
    document_id: str
    pdf_page: int = Field(ge=1)
    table: int = Field(ge=0)
    statement_type: str
    source_reference: str
    source_image_sha256: str
    method: Literal["controlled_original_pdf_visual_read", "source_ocr_inventory"]
    full_table: bool = False
    terminal_boundary_observed: bool = False
    rows: list[SourceRow]


def assess_row_completeness(page, identity, inventory=None):
    """Coverage is independent of exact lookup success and reported table.rows."""
    if inventory is None:
        return dict(status="coverage_uncertain", rows=[], issues=["source_inventory_missing"])
    if (
        inventory.document_id != identity.source_ref
        or inventory.pdf_page != identity.page
        or inventory.statement_type != page.statement_type
        or inventory.table >= len(page.tables)
        or not inventory.source_reference.strip()
        or not inventory.source_image_sha256.strip()
    ):
        return dict(
            status="coverage_uncertain", rows=[], issues=["source_inventory_binding_mismatch"]
        )
    table = page.tables[inventory.table]
    results = []
    for source in inventory.rows:
        matches = []
        for row in sorted({c.row for c in table.cells if c.row is not None}):
            labels = [c for c in table.cells if c.row == row and c.column == table.label_column]
            codes = [c for c in table.cells if c.row == row and c.column == table.code_column]
            if len(labels) != 1 or len(codes) > 1 or (source.code is not None and not codes):
                continue
            code = codes[0] if codes else None
            if (source.code is not None and code.text == source.code) or text_key(
                labels[0].text
            ) == text_key(source.label):
                matches.append((row, labels[0], code))
        status = {
            "unreadable": "source_unreadable",
            "not_applicable": "not_applicable",
            "ambiguous": "row_ambiguous",
        }.get(source.status)
        if status is None:
            status = "row_missing" if not matches else "row_ambiguous"
            if len(matches) == 1:
                row, label, code = matches[0]
                slots = [
                    [c for c in table.cells if c.row == row and c.column == col]
                    for col in source.value_columns
                ]
                if (
                    text_key(label.text) == text_key(source.label)
                    and (source.code is None or source.code == code.text)
                    and label.reading == "observed"
                    and (code is None or code.reading == "observed")
                    and all(len(s) == 1 and s[0].reading == "observed" for s in slots)
                ):
                    status = "row_present"
        results.append(
            dict(
                source_selector=source.selector,
                label=source.label,
                code=source.code,
                status=status,
                extracted_rows=[r[0] for r in matches],
            )
        )
    uncertain = (
        not inventory.full_table
        or not inventory.terminal_boundary_observed
        or not inventory.rows
        or bool(page.limitations)
        or any(r["status"] in {"row_ambiguous", "source_unreadable"} for r in results)
    )
    return dict(
        status="rows_missing"
        if any(r["status"] == "row_missing" for r in results)
        else "coverage_uncertain"
        if uncertain
        else "covered",
        rows=results,
        issues=["coverage_evidence_incomplete"] if uncertain else [],
    )
