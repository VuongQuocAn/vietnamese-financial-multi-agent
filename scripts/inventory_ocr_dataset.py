"""Khảo sát OCR chỉ đọc; artifacts local, không phải contracts hay đánh giá OCR."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

VERSION = 1
ROOTS = {"raw": "raw/Financial_Report", "processed": "processed/Financial_Report_OCR"}
ARTIFACTS = (
    "inventory_summary.json",
    "element_schema_summary.json",
    "page_manifest.jsonl",
    "representative_pages.json",
    "pilot_candidates.json",
    "inventory_warnings.jsonl",
)


def kind(value):
    return "null" if value is None else type(value).__name__


class Schema:
    """Đếm field theo số object cha, kể cả object rỗng và trường null."""

    def __init__(self):
        self.objects = Counter()
        self.fields = defaultdict(Counter)

    def observe(self, value, path="$"):
        if isinstance(value, dict):
            self.objects[path] += 1
            for key, child in value.items():
                name = f"{path}.{key}"
                self.fields[name][kind(child)] += 1
                self.observe(child, name)
        elif isinstance(value, list):
            for child in value:
                self.fields[path + "[]"][kind(child)] += 1
                self.observe(child, path + "[]")

    def result(self):
        result = {}
        for name, counts in sorted(self.fields.items()):
            count = sum(counts.values())
            parent = self.objects.get(name.rsplit(".", 1)[0]) if not name.endswith("[]") else None
            result[name] = {"occurrences": count, "types": dict(sorted(counts.items()))}
            if parent is not None:
                result[name].update(
                    parent_objects=parent,
                    missing=parent - count,
                    observed_in_all_parents=count == parent,
                )
        return result


def bbox_valid(value):
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
        and value[0] < value[2]
        and value[1] < value[3]
    )


def snapshot(root):
    """Metadata đầy đủ trước/sau, không hash nội dung toàn dataset."""
    result = {}
    for relative in ROOTS.values():
        base = root / relative
        if not base.is_dir():
            raise ValueError(f"Dataset directory missing: {relative}")
        for path in sorted(base.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlink in dataset is unsupported; source not modified")
            stat = path.stat()
            result[path.relative_to(root).as_posix()] = (
                path.is_file(),
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ino,
            )
    return result


def reference_status(value, root, symbol, year):
    """Đối chiếu root + toàn suffix + mã/năm, tuyệt đối không tìm basename."""
    if not isinstance(value, str) or not value.strip():
        return "missing"
    parts = PurePosixPath(value.replace("\\", "/")).parts
    if ".." in parts:
        return "ambiguous"
    matches = [
        (marker, parts.index(marker))
        for marker in ("Financial_Report", "Financial_Report_OCR")
        if parts.count(marker) == 1
    ]
    if len(matches) != 1:
        return "ambiguous"
    marker, index = matches[0]
    tail = parts[index + 1 :]
    if len(tail) < 3 or tuple(tail[:2]) != (symbol, year):
        return "ambiguous"
    local = root / (ROOTS["raw"] if marker == "Financial_Report" else ROOTS["processed"])
    local = local.joinpath(*tail)
    colab = "drive" in parts or "content" in parts or ".shortcut-targets-by-id" in parts
    if colab:
        return "colab_suffix_exists" if local.is_file() else "colab_suffix_missing"
    original = Path(value)
    if not original.is_absolute():
        original = root / original
    if original.resolve() == local.resolve() and local.is_file():
        return "local_exists"
    return "root_suffix_exists" if local.is_file() else "unmapped"


def fold(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c))


def text_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "text" and isinstance(child, str):
                yield child
            elif isinstance(child, (list, dict)):
                yield from text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from text_values(child)


def inspect_page(document, relative, root, schemas, taxonomy, provenance, warn):
    parts = PurePosixPath(relative).parts
    symbol, year = parts[2:4]
    page = document.get("page")
    if not isinstance(page, dict):
        page = {}
        warn("missing_page_metadata")
    number = page.get("page")
    if page.get("symbol") != symbol or str(page.get("year")) != year:
        warn("page_identity_mismatch")
    if type(number) is not int:
        warn("invalid_page_number")
    elements = document.get("elements")
    if not isinstance(elements, list):
        warn("missing_or_invalid_elements")
        elements = []
    schemas["page_json"].observe(document)
    prov = document.get("provenance")
    if not isinstance(prov, dict):
        warn("missing_or_invalid_provenance")
        prov = {}
    for key in ("architecture", "layout_engine", "text_detector", "text_recognizer"):
        value = prov.get(key)
        provenance[key][json.dumps(value, ensure_ascii=False, sort_keys=True)] += 1

    refs = Counter()

    def record_ref(value, role):
        status = reference_status(value, root, symbol, year)
        refs[f"{role}:{status}"] += 1
        if status not in ("colab_suffix_exists", "root_suffix_exists", "local_exists"):
            warn(f"{role}_reference_{status}")

    record_ref(page.get("image"), "page_image")

    def nested_refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("crop", "image", "path") or key.endswith(("_crop", "_path", "_image")):
                    record_ref(child, "crop" if "crop" in key else "other")
                elif isinstance(child, (dict, list)):
                    nested_refs(child)
        elif isinstance(value, list):
            for child in value:
                nested_refs(child)

    counts = Counter()
    tables = []
    boxes = []
    for element in elements:
        if not isinstance(element, dict):
            warn("invalid_element")
            continue
        etype = element.get("type")
        if not isinstance(etype, str):
            etype = "<missing_or_invalid>"
            warn("missing_element_type")
        counts[etype] += 1
        taxonomy[etype]["count"] += 1
        schemas[f"element:{etype}"].observe(element)
        nested_refs(element)
        if etype != "text" and "crop" not in element:
            warn("nontext_element_missing_crop")
        if not bbox_valid(element.get("bbox")):
            warn("element_bbox_missing_or_invalid")
        elif etype == "text":
            boxes.append(element["bbox"])
        if etype != "table":
            continue
        cells = element.get("cells")
        if not isinstance(cells, list):
            warn("table_missing_or_invalid_cells")
            cells = []
        if not cells:
            warn("table_without_cells")
        positions = Counter()
        rows, cols = Counter(), Counter()
        for cell in cells:
            if not isinstance(cell, dict):
                warn("invalid_cell")
                continue
            if not bbox_valid(cell.get("bbox")):
                warn("cell_bbox_missing_or_invalid")
            row, col = cell.get("row"), cell.get("col")
            if type(row) is int and type(col) is int and row >= 0 and col >= 0:
                positions[(row, col)] += 1
                rows[row] += 1
                cols[col] += 1
            else:
                warn("cell_row_col_invalid")
            lines = cell.get("lines", [])
            if not isinstance(lines, list):
                warn("cell_lines_invalid")
            if not str(cell.get("text") or "").strip():
                warn("cell_text_empty")
        duplicates = sum(n - 1 for n in positions.values())
        if duplicates:
            warn("duplicate_row_col", duplicates)
        occupied = len(positions)
        area = ((max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)) if rows and cols else 0
        suspects = []
        if area and occupied < area:
            suspects.append("sparse_grid_or_merged_cells_unverified")
        if any(
            cell.get("rowspan", 1) > 1 or cell.get("colspan", 1) > 1
            for cell in cells
            if isinstance(cell, dict)
            and type(cell.get("rowspan", 1)) is int
            and type(cell.get("colspan", 1)) is int
        ):
            suspects.append("spans_present_header_unverified")
        tables.append(
            {
                "id": element.get("id"),
                "cells": len(cells),
                "rows": dict(sorted(rows.items())),
                "cols": dict(sorted(cols.items())),
                "duplicate_positions": duplicates,
                "suspicions": suspects,
            }
        )
    for etype in counts:
        taxonomy[etype]["pages"] += 1
    texts = list(text_values(elements))
    normalized = fold(" ".join(texts))
    patterns = {
        "B01": r"b\s*0?1\s*[-–]?\s*dn|bang can doi ke toan",
        "B02": r"b\s*0?2\s*[-–]?\s*dn|bao cao ket qua (?:hoat dong )?kinh doanh",
        "B03": r"b\s*0?3\s*[-–]?\s*dn|bao cao luu chuyen tien te",
        "B09": r"b\s*0?9\s*[-–]?\s*dn|thuyet minh bao cao tai chinh",
    }
    forms = [key for key, pattern in patterns.items() if re.search(pattern, normalized)]
    numeric = sum(bool(re.search(r"\d[\d.,() -]*", value)) for value in texts)
    ratio = numeric / len(texts) if texts else 0
    # Nhóm tọa độ 20 px; yêu cầu lặp ở cả hai trục. Chỉ là heuristic.
    aligned_rows = sum(n >= 3 for n in Counter(round(b[1] / 20) for b in boxes).values())
    aligned_cols = sum(n >= 4 for n in Counter(round(b[0] / 20) for b in boxes).values())
    period = bool(re.search(r"nam nay|nam truoc|dau nam|cuoi nam|20[12]\d", normalized))
    implicit = (
        not tables
        and len(boxes) >= 15
        and ratio >= 0.25
        and aligned_rows >= 3
        and aligned_cols >= 2
    )
    if not texts:
        warn("no_text_content")
    return {
        "source": relative,
        "symbol": symbol,
        "year": year,
        "page": number,
        "element_types": dict(sorted(counts.items())),
        "table_count": len(tables),
        "tables": tables,
        "references": dict(sorted(refs.items())),
        "form_candidates": forms,
        "form_status": "unverified",
        "text_count": counts["text"],
        "numeric_text_ratio": round(ratio, 6),
        "aligned_rows": aligned_rows,
        "aligned_cols": aligned_cols,
        "period_signal": period,
        "implicit_table_candidate": implicit,
    }


def select_samples(pages):
    """Định thứ tự ổn định: phủ báo cáo, rồi bổ sung đặc trưng chưa phủ và mã cân bằng."""
    candidates = [p for p in pages if type(p["page"]) is int]
    features = {}
    for p in candidates:
        # Nhiều tên biểu mẫu trên cùng trang thường là phần dẫn/kiểm toán.
        # Chỉ một tên vẫn chưa đủ xác minh, nhưng thích hợp hơn cho chọn mẫu.
        tags = {f"form:{p['form_candidates'][0]}"} if len(p["form_candidates"]) == 1 else set()
        tags.update(f"object:{t}" for t in p["element_types"] if t not in ("text", "table"))
        if p["implicit_table_candidate"]:
            tags.add("implicit_table_unverified")
        if p["text_count"] >= 40:
            tags.add("text_heavy")
        if sum(t["cells"] for t in p["tables"]) >= 100:
            tags.add("complex_table_unverified")
        tags.update(f"anomaly:{code}" for code in p["warnings"])
        features[p["source"]] = tags
    chosen, covered, by_symbol = [], set(), Counter()

    def choose(pool, reason):
        best = min(
            pool,
            key=lambda p: (
                -len(features[p["source"]] - covered),
                by_symbol[p["symbol"]],
                -len(features[p["source"]]),
                p["source"],
            ),
        )
        tags = features[best["source"]]
        chosen.append({**best, "selection_reason": reason, "selection_features": sorted(tags)})
        covered.update(tags)
        by_symbol[best["symbol"]] += 1
        candidates.remove(best)

    for group in sorted({(p["symbol"], p["year"]) for p in candidates}):
        choose([p for p in candidates if (p["symbol"], p["year"]) == group], "report_coverage")
    while candidates and len(chosen) < 24:
        minimum = min(by_symbol[s] for s in {p["symbol"] for p in candidates})
        choose(
            [p for p in candidates if by_symbol[p["symbol"]] == minimum],
            "feature_and_symbol_coverage",
        )
    pilot = []
    remaining = list(chosen)
    covered = set()
    by_symbol.clear()

    def pilot_gain(page):
        return sum(
            3 if tag.startswith(("form:", "object:", "implicit_table")) else 1
            for tag in set(page["selection_features"]) - covered
        )

    while remaining and len(pilot) < 6:
        best = min(
            remaining,
            key=lambda p: (
                by_symbol[p["symbol"]],
                -pilot_gain(p),
                p["source"],
            ),
        )
        pilot.append(best)
        remaining.remove(best)
        covered.update(best["selection_features"])
        by_symbol[best["symbol"]] += 1
    return chosen[:24], pilot


def inventory(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not root.is_dir():
        raise ValueError("Dataset root does not exist")
    if output == root or root.is_relative_to(output):
        raise ValueError("Output must not contain the dataset root")
    for source in ("raw", "processed"):
        base = root / source
        if output.is_relative_to(base.resolve()):
            raise ValueError("Output must be outside raw/processed sources")
    # Không ghi đè bất kỳ file lạ hoặc symlink tại đích artifacts.
    for name in ARTIFACTS:
        destination = output / name
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError("Unsafe artifact destination")
        if destination.exists() and destination.stat().st_nlink > 1:
            raise ValueError("Hard-linked artifact destination is unsafe")
    before = snapshot(root)
    files = {p: m for p, m in before.items() if m[0]}
    groups = defaultdict(
        lambda: {"files": 0, "bytes": 0, "extensions": Counter(), "roles": Counter()}
    )
    schemas = defaultdict(Schema)
    taxonomy = defaultdict(Counter)
    provenance = defaultdict(Counter)
    warnings, pages = [], []
    roles = Counter()
    for relative, metadata in sorted(files.items()):
        path = root / relative
        parts = PurePosixPath(relative).parts
        symbol, year = parts[2:4] if len(parts) >= 5 else ("unknown", "unknown")
        group = groups[f"{symbol}/{year}"]
        extension = path.suffix.lower() or "<none>"
        group["files"] += 1
        group["bytes"] += metadata[1]
        group["extensions"][extension] += 1
        page_warnings = Counter()

        def warn(code, count=1, counter=page_warnings):
            counter[code] += count

        document = None
        page_location = relative.startswith(ROOTS["processed"] + "/") and "ocr_json" in parts
        if extension == ".json":
            try:
                document = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError, RecursionError):
                warn("json_unreadable_or_invalid")
            is_page = page_location or (
                isinstance(document, dict) and "page" in document and "elements" in document
            )
            role = "page_json" if is_page else "aux_json"
            if is_page:
                if isinstance(document, dict):
                    page = inspect_page(
                        document, relative, root, schemas, taxonomy, provenance, warn
                    )
                    page["warnings"] = dict(sorted(page_warnings.items()))
                    pages.append(page)
                elif not page_warnings:
                    warn("page_json_not_object")
        elif extension == ".jsonl":
            role = "aux_jsonl"
            try:
                with path.open(encoding="utf-8-sig") as handle:
                    for line in handle:
                        if line.strip():
                            try:
                                json.loads(line)
                            except (ValueError, RecursionError):
                                warn("jsonl_invalid_line")
            except (OSError, UnicodeError):
                warn("jsonl_unreadable")
        elif extension == ".png":
            role = (
                "raw_png"
                if parts[0] == "raw"
                else "crop_png"
                if "ocr_crops" in parts
                else "other_png"
            )
        else:
            role = "other"
        group["roles"][role] += 1
        roles[role] += 1
        warnings.extend(
            {"source": relative, "code": c, "count": n} for c, n in sorted(page_warnings.items())
        )
    pages.sort(key=lambda p: (p["symbol"], p["year"], str(p["page"]), p["source"]))
    identities = Counter((p["symbol"], p["year"], p["page"]) for p in pages)
    duplicates = sum(n - 1 for n in identities.values())
    refs = Counter()
    for page in pages:
        refs.update(page["references"])
    selected, pilot = select_samples(pages)
    after = snapshot(root)
    if before != after:
        raise RuntimeError("Source metadata changed during inventory; outputs not written")
    metadata_bytes = json.dumps(before, sort_keys=True).encode()
    summary = {
        "version": VERSION,
        "files": len(files),
        "bytes": sum(m[1] for m in files.values()),
        "roles": dict(sorted(roles.items())),
        "groups": dict(sorted(groups.items())),
        "parsed_page_json": len(pages),
        "unique_page_identities": len(identities),
        "duplicate_page_identities": duplicates,
        "pages_by_report": dict(
            sorted(Counter(f"{p['symbol']}/{p['year']}" for p in pages).items())
        ),
        "tables_by_report": {
            g: sum(p["table_count"] for p in pages if f"{p['symbol']}/{p['year']}" == g)
            for g in sorted(groups)
        },
        "table_count": sum(p["table_count"] for p in pages),
        "cell_count": sum(t["cells"] for p in pages for t in p["tables"]),
        "cells_per_table": dict(
            sorted(Counter(t["cells"] for p in pages for t in p["tables"]).items())
        ),
        "table_suspicions": dict(
            Counter(s for p in pages for t in p["tables"] for s in t["suspicions"])
        ),
        "taxonomy": dict(sorted(taxonomy.items())),
        "provenance_values": dict(provenance),
        "references": dict(sorted(refs.items())),
        "warning_counts": dict(
            sorted(sum((Counter({w["code"]: w["count"]}) for w in warnings), Counter()).items())
        ),
        "implicit_table_candidates": sum(p["implicit_table_candidate"] for p in pages),
        "form_candidate_counts": dict(Counter(f for p in pages for f in p["form_candidates"])),
        "metadata_unchanged": before == after,
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "sampling": {
            "method": "report coverage then new features, symbol balance, lexical tie-break v1",
            "representatives": len(selected),
            "pilot": len(pilot),
            "visual_images_opened": 0,
        },
    }
    output.mkdir(parents=True, exist_ok=True)

    def write(name, value):
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    write("inventory_summary.json", summary)
    write(
        "element_schema_summary.json",
        {name: schema.result() for name, schema in sorted(schemas.items())},
    )
    write("representative_pages.json", selected)
    write("pilot_candidates.json", pilot)
    for name, values in (("page_manifest.jsonl", pages), ("inventory_warnings.jsonl", warnings)):
        (output / name).write_text(
            "".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values),
            encoding="utf-8",
        )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root", type=Path, default=Path(os.environ.get("DATASET_ROOT", "data"))
    )
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/dataset-inventory"))
    parser.add_argument("--summary", action="store_true", help="Chỉ in số tổng hợp ra terminal")
    args = parser.parse_args(argv)
    try:
        result = inventory(args.dataset_root, args.output_dir)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Inventory failed: {error}\n")
    if args.summary:
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "files",
                        "bytes",
                        "roles",
                        "parsed_page_json",
                        "table_count",
                        "cell_count",
                        "implicit_table_candidates",
                        "metadata_unchanged",
                    )
                },
                indent=2,
            )
        )
    else:
        print(
            f"Inventory complete: {result['files']} files, {result['parsed_page_json']} page JSON; local artifacts written."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
