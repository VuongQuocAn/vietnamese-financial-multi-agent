"""Offline region audit against explicitly selected saved pages; never calls an LLM."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.document_processing.region_geometry import (
    bind_selectors,
    crop_region,
    resolve_region,
)


def evaluate(case):
    saved = json.loads(Path(case["saved_page"]).read_bytes())
    raw = json.loads(Path(case["raw_ocr"]).read_bytes())
    source = saved["source"]["page"]
    page = load_pages(
        Path(case["pdf"]),
        symbol=source["symbol"],
        year=source["year"],
        pages=[source["page"]],
        dpi=saved["provenance"]["render_dpi"],
        raw_ocr={source["page"]: raw},
    )[0]
    assert page.source == saved["provenance"]
    pointer = case["selector"]
    index = int(pointer.rsplit("/", 1)[1])
    text = saved["output"]["text_elements"][index]["text"]
    geometry = bind_selectors(page.geometry, [(pointer, text, None)])
    t = perf_counter()
    resolved = resolve_region(page.image, geometry, pointer, text)
    elapsed = (perf_counter() - t) * 1000
    return page, geometry, resolved, elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for i, case in enumerate(json.loads(args.cases.read_bytes())):
        page, geometry, resolved, elapsed = evaluate(case)
        prefix = args.output / str(i)
        prefix.with_suffix(".geometry.json").write_text(
            json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if resolved["status"] == "resolved":
            prefix.with_suffix(".crop.png").write_bytes(crop_region(page.image, resolved).content)
        results.append(
            dict(
                selector=case["selector"],
                page=page.image.identity.model_dump(mode="json"),
                resolution=resolved,
                resolver_ms=elapsed,
                crop_created=resolved["status"] == "resolved",
                gemini_calls=0,
            )
        )
    (args.output / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps([{k: v for k, v in row.items() if k != "page"} for row in results]))


if __name__ == "__main__":
    main()
