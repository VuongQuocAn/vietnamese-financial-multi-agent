"""Kiểm kê read-only neutral corpus; không gọi model hoặc sửa nguồn."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

PAGE_TXT = re.compile(r"^\[PAGE (\d+)\]\s*$", re.M)
PAGE_MD = re.compile(r"<!-- document=([^;]+); page=(\d+) -->")
TABLE_REF = re.compile(r"\[TABLE: ([^\]]+)\]")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())


def integer_value(value: str) -> Decimal | None:
    """Chỉ số nguyên/grouping rõ; blank/dash không tự đổi thành zero."""
    value = value.strip()
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:\.\d{3})+|\d{1,3}(?:,\d{3})+)", value):
        return None
    number = Decimal(value.replace(".", "").replace(",", ""))
    return -number if negative else number


def arithmetic_probes(record: dict) -> list[dict]:
    """Probes cùng bảng/kỳ, chỉ khi headers và mã số có thể đọc trực tiếp."""
    table = record["table"]
    columns, rows = table["columns"], table["rows"]
    if not columns or any(len(row) != len(columns) for row in rows):
        return []
    code_columns = [i for i, c in enumerate(columns) if normalize(c) in {"ma so", "ms"}]
    if len(code_columns) != 1:
        return []
    ci = code_columns[0]
    code_rows = {
        row[ci].strip(): (ri, row)
        for ri, row in enumerate(rows)
        if re.fullmatch(r"\d{2,3}", row[ci].strip())
    }
    title = normalize(table.get("title", "") + " " + " ".join(columns))
    formulas = []
    if "can doi ke toan" in title or "tai san" in title or "nguon von" in title:
        formulas = [("270", [("100", 1), ("200", 1)]), ("440", [("300", 1), ("400", 1)])]
    elif "ket qua" in title:
        formulas = [
            ("10", [("01", 1), ("02", -1)]),
            ("20", [("10", 1), ("11", -1)]),
            ("50", [("30", 1), ("40", 1)]),
            ("60", [("50", 1), ("51", -1), ("52", -1)]),
        ]
    elif "luu chuyen tien" in title:
        formulas = [
            ("50", [("20", 1), ("30", 1), ("40", 1)]),
            ("70", [("50", 1), ("60", 1), ("61", 1)]),
        ]
    checks = []
    for col, header in enumerate(columns):
        if not re.search(
            r"20\d{2}|so cuoi|so dau|nam nay|nam truoc|cuoi ky|dau ky", normalize(header)
        ):
            continue
        for target, operands in formulas:
            codes = [target, *(code for code, _ in operands)]
            if not all(code in code_rows for code in codes):
                continue
            numbers = {code: integer_value(code_rows[code][1][col]) for code in codes}
            if any(value is None for value in numbers.values()):
                continue
            expected = sum(numbers[code] * sign for code, sign in operands)
            checks.append(
                {
                    "table": record["table_id"],
                    "page": record["page"],
                    "column_index_0": col,
                    "header": header,
                    "formula": target + "=" + "+".join(f"{sign}*{code}" for code, sign in operands),
                    "cells": {
                        code: {"row_index_0": code_rows[code][0], "raw": code_rows[code][1][col]}
                        for code in codes
                    },
                    "actual": str(numbers[target]),
                    "expected": str(expected),
                    "difference": str(numbers[target] - expected),
                    "matches": numbers[target] == expected,
                }
            )
    return checks


def page_blocks(text: str, pattern: re.Pattern) -> list[tuple[int, str]]:
    matches = list(pattern.finditer(text))
    return [
        (
            int(match.groups()[-1]),
            text[match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(text)],
        )
        for i, match in enumerate(matches)
    ]


def markdown_table(table: dict) -> str:
    columns, rows = table["columns"], table["rows"]
    width = max([len(columns), 1, *(len(row) for row in rows)])
    columns = columns or [f"Cột {i + 1}" for i in range(width)]

    def line(row: list) -> str:
        values = (row + [""] * width)[:width]
        escaped = [
            str(v if v is not None else "").replace("\n", " ").replace("|", "\\|") for v in values
        ]
        return "| " + " | ".join(escaped) + " |"

    return "\n".join([line(columns), line(["---"] * width), *(line(row) for row in rows)])


def audit(root: Path) -> dict:
    docs, problems, table_keys = [], [], Counter()
    file_hashes, content_tables, content_pages = (
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    totals = Counter()
    manifest, arithmetic = {}, []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        doc_id = directory.name
        match = re.fullmatch(r"([A-Z0-9]+)_(\d{4})", doc_id)
        if not match:
            problems.append({"document": doc_id, "issue": "directory_name"})
            continue
        files = sorted(p for p in directory.iterdir() if p.is_file())
        item = {"document": doc_id, "company": match[1], "year": int(match[2])}
        item["files"] = [p.name for p in files]
        item["bytes"] = sum(p.stat().st_size for p in files)
        totals["files"] += len(files)
        totals["bytes"] += item["bytes"]
        for path in files:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            relative = path.relative_to(root).as_posix()
            manifest[relative] = {"bytes": len(raw), "sha256": digest}
            file_hashes[digest].append(relative)
            if not raw.strip():
                problems.append({"document": doc_id, "issue": "empty_file", "file": path.name})
        partial = any("PARTIAL" in p.name for p in files)
        suffix = "_PARTIAL" if partial else ""
        expected = {f"document{suffix}.txt", f"document{suffix}.md", f"tables{suffix}.json"}
        if set(item["files"]) != expected:
            problems.append({"document": doc_id, "issue": "file_set", "expected": sorted(expected)})
        try:
            txt = (directory / f"document{suffix}.txt").read_text(encoding="utf-8")
            md = (directory / f"document{suffix}.md").read_text(encoding="utf-8")
            duplicate_keys = []

            def object_pairs(pairs: list, duplicate_keys: list = duplicate_keys) -> dict:
                keys = Counter(key for key, _ in pairs)
                duplicate_keys.extend(key for key, count in keys.items() if count > 1)
                return dict(pairs)

            data = json.loads(
                (directory / f"tables{suffix}.json").read_text(encoding="utf-8"),
                object_pairs_hook=object_pairs,
            )
            if duplicate_keys:
                problems.append(
                    {"document": doc_id, "issue": "duplicate_json_keys", "keys": duplicate_keys}
                )
        except (OSError, ValueError) as exc:
            problems.append({"document": doc_id, "issue": "decode_or_parse", "error": str(exc)})
            continue
        tp, mp = page_blocks(txt, PAGE_TXT), page_blocks(md, PAGE_MD)
        pages, md_pages = [p for p, _ in tp], [p for p, _ in mp]
        md_by_page = dict(mp)
        md_text_only = dict(mp)
        item.update(status=data.get("status"), missing_pages=data.get("missing_pages"), pages=pages)
        missing = sorted(set(range(1, max(pages, default=0) + 1)) - set(pages))
        item["inferred_gaps"] = missing
        totals["exported_pages"] += len(pages)
        totals["declared_missing_pages"] += len(data.get("missing_pages", []))
        if pages != md_pages or len(pages) != len(set(pages)) or pages != sorted(pages):
            problems.append({"document": doc_id, "issue": "page_alignment"})
        if data.get("document_id") != doc_id or any(d != doc_id for d, _ in PAGE_MD.findall(md)):
            problems.append({"document": doc_id, "issue": "document_identity"})
        if missing != sorted(data.get("missing_pages", [])):
            problems.append({"document": doc_id, "issue": "missing_page_metadata"})
        if (data.get("status") == "partial") != partial:
            problems.append({"document": doc_id, "issue": "status_filename"})
        refs = [(tid, p) for p, block in tp for tid in TABLE_REF.findall(block)]
        expected_refs = []
        md_cursor = defaultdict(int)
        item["tables"] = len(data.get("tables", []))
        item["table_pages"] = sorted({t.get("page") for t in data.get("tables", [])})
        item["ragged_rows"] = []
        item["empty_tables"] = []
        for record in data.get("tables", []):
            table_keys.update(record.keys())
            tid, page, table = record.get("table_id"), record.get("page"), record.get("table")
            expected_refs.append((tid, page))
            if record.get("document_id") != doc_id or page not in pages:
                problems.append({"document": doc_id, "table": tid, "issue": "table_identity_page"})
            if not re.fullmatch(rf"{re.escape(doc_id)}_p{page:03d}_t\d{{3}}", tid or ""):
                problems.append({"document": doc_id, "table": tid, "issue": "table_id"})
            if (
                not isinstance(table, dict)
                or not isinstance(table.get("columns"), list)
                or not isinstance(table.get("rows"), list)
            ):
                problems.append({"document": doc_id, "table": tid, "issue": "table_structure"})
                continue
            columns, rows = table["columns"], table["rows"]
            if not columns or not rows:
                item["empty_tables"].append(tid)
            for ri, row in enumerate(rows):
                if not isinstance(row, list):
                    problems.append(
                        {"document": doc_id, "table": tid, "row": ri, "issue": "row_type"}
                    )
                    continue
                if len(row) != len(columns):
                    item["ragged_rows"].append(
                        {"table": tid, "row": ri, "columns": len(columns), "cells": len(row)}
                    )
                totals["rows"] += 1
                totals["cells"] += len(row)
                for cell in row:
                    totals["null_cells"] += cell is None
                    totals["non_string_cells"] += not isinstance(cell, str)
                    value = str(cell or "").strip()
                    totals["blank_cells"] += not value
                    totals["dash_cells"] += value in {"-", "–", "—"}
                    totals["parenthesized_numeric_cells"] += bool(
                        re.fullmatch(r"\([\d., ]+\)", value)
                    )
            if all(isinstance(row, list) for row in rows):
                rendered = markdown_table(table)
                block = md_by_page.get(page, "")
                pos = block.find(rendered, md_cursor[page])
                if pos < 0:
                    problems.append(
                        {"document": doc_id, "table": tid, "issue": "md_table_mismatch"}
                    )
                else:
                    md_cursor[page] = pos + len(rendered)
                    clean = md_text_only[page]
                    clean_pos = clean.find(rendered)
                    prefix, tail = clean[:clean_pos], clean[clean_pos + len(rendered) :]
                    heading = "### " + str(table.get("title", ""))
                    if table.get("title") and prefix.rstrip().endswith(heading):
                        prefix = prefix.rstrip()[: -len(heading)]
                    md_text_only[page] = prefix + tail
                signature = json.dumps(table, ensure_ascii=False, sort_keys=True)
                content_tables[hashlib.sha256(signature.encode()).hexdigest()].append(tid)
                arithmetic.extend(arithmetic_probes(record))
        if Counter(refs) != Counter(expected_refs) or len(refs) != len(set(refs)):
            problems.append({"document": doc_id, "issue": "txt_table_references"})
        item["empty_text_pages"] = []
        item["text_md_token_differences"] = []
        for page, block in tp:
            if not block.strip():
                item["empty_text_pages"].append(page)
            plain = TABLE_REF.sub("", block)
            md_plain = md_text_only.get(page, "")
            md_plain = re.sub(r"^## Trang \d+\s*$", "", md_plain, flags=re.M)

            # Chỉ flag khác token; headings/list markup không phải khác nội dung.
            def tokens(s: str) -> list[str]:
                return re.findall(r"\w+", s, re.UNICODE)

            if tokens(plain) != tokens(md_plain):
                item["text_md_token_differences"].append(page)
            normalized = " ".join(block.split())
            if normalized:
                content_pages[hashlib.sha256(normalized.encode()).hexdigest()].append(
                    f"{doc_id}:p{page}"
                )
        item["replacement_characters"] = txt.count("\ufffd") + md.count("\ufffd")
        item["meta_text_flags"] = [
            {"page": p, "pattern": pattern}
            for p, block in tp
            for pattern in [
                r"(?i)gemini|as an ai|language model",
                r"(?i)không (?:thể|đọc được)|không rõ|\[.*?(?:mờ|không đọc).*?\]",
            ]
            if re.search(pattern, block)
        ]
        totals["tables"] += item["tables"]
        totals["ragged_rows"] += len(item["ragged_rows"])
        docs.append(item)
    companies = sorted({d["company"] for d in docs})
    return {
        "root": root.as_posix(),
        "totals": {
            **dict(totals),
            "companies": len(companies),
            "reports": len(docs),
            "statuses": dict(Counter(d["status"] for d in docs)),
        },
        "table_record_fields": dict(table_keys),
        "arithmetic_probes": arithmetic,
        "documents": docs,
        "problems": problems,
        "identical_files": [v for v in file_hashes.values() if len(v) > 1],
        "identical_tables": [v for v in content_tables.values() if len(v) > 1],
        "identical_txt_pages": [v for v in content_pages.values() if len(v) > 1],
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("ViFinBench/neutral"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.root.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        parser.error("Output phải nằm ngoài corpus read-only")
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["totals"], ensure_ascii=False))
    print(f"Structural problems: {len(result['problems'])}; output: {args.output}")


if __name__ == "__main__":
    main()
