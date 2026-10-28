"""Đánh giá offline trên nhãn đối chiếu ảnh; không gọi model hoặc sửa outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def normalize_value(value: str) -> str | None:
    """Chỉ số nguyên VND: dấu chấm nhóm nghìn; không suy dấu/decimal/dash."""
    value = normalize_text(value)
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)", value):
        return None
    return str(int(value.replace(".", "")))


def distance(left, right) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def ratio(numerator: int, denominator: int) -> dict:
    return {
        "correct": numerator,
        "total": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def select(document, pointer: list):
    for key in pointer:
        document = document[key]
    return document


def load_inputs(benchmark: dict, root: Path) -> dict:
    """Hash-pin mọi ảnh, raw và persisted output; relative paths, fail closed."""
    documents = {}
    for name, record in benchmark["files"].items():
        path = (root / record["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("input_outside_root")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"snapshot_mismatch:{name}")
        documents[name] = json.loads(payload) if path.suffix == ".json" else None
    return documents


def evaluate(benchmark: dict, documents: dict) -> dict:
    pages = {p["id"]: p for p in benchmark["pages"]}
    if len(pages) != len(benchmark["pages"]):
        raise ValueError("duplicate_page")
    labels = benchmark["labels"]
    if len({label["id"] for label in labels}) != len(labels):
        raise ValueError("duplicate_label")
    for label in labels:
        page = pages[label["page"]]
        if (
            label["verification"] != "direct_image_review"
            or not label.get("region")
            or label["image_sha256"] != benchmark["files"][page["image"]]["sha256"]
        ):
            raise ValueError("unverified_label")
    pipelines = benchmark["pipelines"]
    if not pipelines or any(not set(p["pages"]) <= pages.keys() for p in pipelines.values()):
        raise ValueError("invalid_pipeline_pages")
    common = set.intersection(*(set(p["pages"]) for p in pipelines.values()))
    result = {
        "mode": "persisted_replay",
        "new_requests": 0,
        "common_pages": sorted(common),
        "pipelines": {},
    }
    for name, pipeline in pipelines.items():
        structures = [
            select(documents[b["file"]], b["pointer"]) for b in pipeline.get("structures", [])
        ]
        schemas = [select(documents[b["file"]], b["pointer"]) for b in pipeline.get("schemas", [])]
        result["pipelines"][name] = {
            "schema_valid": ratio(sum(s == "schema_valid" for s in schemas), len(schemas)),
            "structure_accepted": ratio(
                sum(s in {"resolved", "accepted"} for s in structures), len(structures)
            ),
        }
        for scope, page_ids in (("available", set(pipeline["pages"])), ("common", common)):
            rows = []
            for label in labels:
                if label["page"] not in page_ids:
                    continue
                binding = label.get("bindings", {}).get(name)
                observation = None
                if binding:
                    observation = select(documents[binding["file"]], binding["pointer"])
                text = observation.get("text") if observation else None
                expected = normalize_text(label["expected"])
                actual = normalize_text(text) if isinstance(text, str) else ""
                layout = observation.get("layout", {}) if observation else {}
                position = (
                    [
                        layout.get("row", observation.get("row")),
                        layout.get("column", observation.get("col")),
                    ]
                    if observation
                    else None
                )
                grounded = False
                if observation and binding.get("source_pointer") is not None:
                    source = select(documents[binding["file"]], binding["source_pointer"])
                    grounded = source == pages[label["page"]]["identity"]
                    if binding.get("image_pointer") is not None:
                        grounded &= (
                            select(documents[binding["file"]], binding["image_pointer"])
                            == label["image_sha256"]
                        )
                    if binding.get("cell_id") is not None:
                        grounded &= observation.get("id") == binding["cell_id"]
                rows.append(
                    {
                        "id": label["id"],
                        "present": isinstance(text, str),
                        "exact": actual == expected,
                        "raw_exact": text == label["expected"],
                        "numeric": label["kind"] == "financial",
                        "value_exact": normalize_value(actual) is not None
                        and normalize_value(actual) == normalize_value(expected),
                        "char_errors": distance(expected, actual),
                        "chars": len(expected),
                        "word_errors": distance(expected.split(), actual.split()),
                        "words": len(expected.split()),
                        "grounded": grounded,
                        "grounding_checked": bool(
                            binding and binding.get("source_pointer") is not None
                        ),
                        "has_position": "position" in label,
                        "has_cell_link": bool(binding and binding.get("cell_id")),
                        "alignment": position == label.get("position"),
                    }
                )
            numeric = [r for r in rows if r["numeric"]]
            aligned = [r for r in rows if r["has_position"]]
            result["pipelines"].setdefault(name, {})[scope] = {
                "pages": sorted(page_ids),
                "labels": len(rows),
                "coverage": ratio(sum(r["present"] for r in rows), len(rows)),
                "text_em": ratio(sum(r["exact"] for r in rows), len(rows)),
                "cer": ratio(sum(r["char_errors"] for r in rows), sum(r["chars"] for r in rows)),
                "wer": ratio(sum(r["word_errors"] for r in rows), sum(r["words"] for r in rows)),
                "financial_raw": ratio(sum(r["raw_exact"] for r in numeric), len(numeric)),
                "financial_normalized": ratio(sum(r["value_exact"] for r in numeric), len(numeric)),
                "cell_alignment": ratio(sum(r["alignment"] for r in aligned), len(aligned)),
                "grounding": ratio(
                    sum(r["grounded"] for r in rows), sum(r["grounding_checked"] for r in rows)
                ),
                "cell_linkage": ratio(
                    sum(r["grounded"] and r["has_cell_link"] for r in rows),
                    sum(r["has_cell_link"] for r in rows),
                ),
                "bbox_quality": None,
                "merged_cells": None,
                "classification_accuracy": None,
                "observations": rows,
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    result = evaluate(benchmark, load_inputs(benchmark, args.root))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
