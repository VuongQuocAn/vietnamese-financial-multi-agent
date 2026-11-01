"""Exact-bound raw correction overlays. Original Gateway response is immutable."""

from copy import deepcopy

from .extraction_semantics import numeric_token_issues


def extraction_payload(record):
    payload = deepcopy(record["response"]["output"]["payload"])
    for correction in record.get("structure_corrections", []):
        page = record["source"]["page"]
        table = payload["tables"][correction["table"]]
        if (
            correction["document_id"] != page["source_ref"]
            or correction["pdf_page"] != page["page"]
            or correction["request_id"] != record["response"]["request_id"]
            or correction["method"] != "controlled_original_pdf_visual_read"
            or not correction["review_reference"].strip()
            or not correction["review_image_sha256"].strip()
            or correction["original_bounds"] != {k: table[k] for k in ("rows", "columns")}
        ):
            raise ValueError("structure_correction_binding_mismatch")
        cells = table["headers"] + table["cells"]
        if not cells or any(c["row"] is None or c["column"] is None for c in cells):
            raise ValueError("structure_correction_positions_unresolved")
        bounds = dict(
            rows=max(c["row"] for c in cells) + 1, columns=max(c["column"] for c in cells) + 1
        )
        if bounds != correction["corrected_bounds"]:
            raise ValueError("structure_correction_bounds_mismatch")
        table.update(bounds)
    seen = set()
    for correction in record.get("raw_corrections", []):
        selector = correction["selector"]
        parts = selector.strip("/").split("/")
        if len(parts) != 4 or parts[0] != "tables" or parts[2] != "cells" or selector in seen:
            raise ValueError("invalid_or_duplicate_correction_selector")
        seen.add(selector)
        page = record["source"]["page"]
        if (
            correction["document_id"] != page["source_ref"]
            or correction["pdf_page"] != page["page"]
            or correction["request_id"] != record["response"]["request_id"]
            or not correction["review_reference"].strip()
            or not correction["review_image_sha256"].strip()
            or correction["method"] != "controlled_original_pdf_visual_read"
        ):
            raise ValueError("correction_source_binding_mismatch")
        cell = payload["tables"][int(parts[1])]["cells"][int(parts[3])]
        if cell["text"] != correction["original_raw_value"]:
            raise ValueError("correction_original_mismatch")
        # Minimal D-05 correction: reviewed null placeholders only, never digits/zero.
        corrected = correction["corrected_raw_value"]
        if not numeric_token_issues(cell["text"]) or corrected not in {"-", "–", "—", "−"}:
            raise ValueError("correction_requires_reviewed_null_placeholder")
        cell["text"] = corrected
    return payload
