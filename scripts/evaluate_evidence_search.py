"""Targeted INT-01b probes local; expected IDs chọn trước search từ saved sources.

Không M8/human gold. Corpus/quotes/citations chỉ ghi artifacts ignored.
"""

import argparse
import json
import statistics
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.evidence.composition import EvidenceComposition
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.evidence.search import SearchDocumentEvidenceRequest
from vietnamese_financial_multi_agent.tools import EvidenceRetrievalTools


def probes():
    output = []

    def add(pdf, query, ids=(), category="keyword", **filters):
        output.append(
            dict(
                id=f"P{len(output) + 1:02}",
                pdf=pdf,
                query=query,
                expected_local_ids=list(ids),
                category=category,
                filters=filters,
            )
        )

    def text(page, i):
        return f"unified/page/{page}/text/text_elements/{i}"

    def table(page, i):
        return f"unified/page/{page}/table/tables/{i}"

    add("BBS_2025", "Người lập biểu", [text(7, 6), text(8, 8)], "role_variant")
    add("BBS_2025", "Kế toán trưởng", [text(7, 7), text(8, 9)])
    add("BBS_2025", "ke toan truong", [text(7, 7), text(8, 9)], "accent")
    add("BBS_2025", "KẾ TOÁN TRƯỞNG", [text(7, 7), text(8, 9)], "case")
    add("BBS_2025", "Giám đốc", [text(7, 8), text(8, 10)])
    add("BBS_2025", "Phạm Thị Thanh Hòa", [text(7, 9), text(8, 11)], "phrase", exact_phrase=True)
    add("BBS_2025", "Nợ xấu và dự phòng phải thu khó đòi", [text(15, 4)], "phrase")
    add("BBS_2025", "Các nhân viên quản lý chủ chốt", [text(14, 4)], "phrase")
    add("BBS_2025", "Tiền mặt", [table(14, 0)], "table", source_page=14, evidence_type="table")
    add("BBS_2025", "Tiền gửi ngân hàng", [table(14, 0)], "table", evidence_type="table")
    add(
        "BBS_2025",
        "Cho biết các nhân viên quản lý chủ chốt có quyền và trách nhiệm gì?",
        [text(14, 4)],
        "natural",
    )
    add("BBS_2025", "Tìm thông tin về tiền gửi ngân hàng", [table(14, 0)], "natural_table")
    add(
        "BBS_2025",
        "Chi phí trả trước ngắn hạn",
        [text(15, 5)],
        "section",
        section_hint="B09",
        source_page=15,
    )
    add("BBS_2022", "Nhà cửa vật kiến trúc", ["record/4/page/11/tables/0"], "table")
    add("BBS_2022", "Máy móc thiết bị", ["record/4/page/11/tables/0"], "table")
    add("BBS_2022", "Thuế thu nhập cá nhân", ["record/5/page/18/tables/0"], "table", source_page=18)
    add(
        "BBS_2024",
        "Chi tiết các khoản vay ngắn hạn",
        ["record/4/page/21/context/4"],
        "section",
        section_hint="B09",
    )
    add("BBS_2024", "Shinhan Việt Nam", ["record/4/page/21/tables/0"], "table")
    add("BBS_2024", "Chi phí nguyên liệu vật liệu", ["record/5/page/24/tables/1"], "table")
    add(
        "BBS_2024",
        "Thuyết minh về các khoản vay",
        ["record/4/page/21/context/4", "record/4/page/21/tables/0"],
        "natural",
    )
    add(
        "BCC_2024",
        "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
        ["record/2/page/11/context/4"],
        "phrase",
        exact_phrase=True,
    )
    add(
        "BCC_2024",
        "Doanh thu bán hàng",
        ["record/2/page/11/tables/0"],
        "table",
        source_page=11,
        evidence_type="table",
    )
    add(
        "BCC_2025",
        "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",
        ["record/2/page/7/context/1"],
        "phrase",
        exact_phrase=True,
    )
    add(
        "BCC_2025",
        "Giá vốn hàng bán",
        ["record/2/page/7/tables/0"],
        "table",
        source_page=7,
        evidence_type="table",
    )
    add("BBS_2025", "quantum astrophysics", category="no_answer")
    add("BBS_2025", "ý kiến kiểm toán ngoại trừ", category="coverage_missing")
    add("BCC_2025", "Phạm Thị Thanh Hòa", category="wrong_document")
    add("BCC_2024", "Dương Minh Tuấn", category="wrong_document")
    add("BBS_2022", "phương pháp đường thẳng", category="coverage_missing")
    add(
        "BCC_2025",
        "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
        category="wrong_scope",
        exact_phrase=True,
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/evidence/INT-01a/final"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/INT-01b/final"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def save(name, obj):
        (args.output / name).write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    repo = DocumentEvidenceRepository(args.input / "repository")
    tools, inventory, manifests, gold_checks = {}, {}, {}, []
    expected = probes()
    # Freeze gold BEFORE building/querying BM25; no result-derived expected IDs.
    save("probes.json", expected)
    for name in sorted({p["pdf"] for p in expected}):
        manifest = EvidenceComposition.model_validate_json(
            (args.input / name / "composition.json").read_text(encoding="utf-8")
        )
        manifests[name] = manifest
        tools[name] = EvidenceRetrievalTools.from_composition(
            manifest,
            repo,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
        index = tools[name]._search
        records = {e.local_evidence_id: e for e in index.catalog.evidence}

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for child in value.values():
                    yield from strings(child)
            elif isinstance(value, list):
                for child in value:
                    yield from strings(child)

        # Đối chiếu original JSON được pin, độc lập search results.
        originals = {}
        for source in manifest.sources:
            if source.status == "verified":
                original = json.loads(Path(source.original_source).read_text(encoding="utf-8"))
                originals[source.descriptor.snapshot_id] = set(strings(original))
        for probe in [p for p in expected if p["pdf"] == name]:
            probe["expected_evidence"] = [
                records[i].model_dump(mode="json") for i in probe["expected_local_ids"]
            ]
            for identity in probe["expected_local_ids"]:
                record = records[identity]
                content = (
                    [record.raw_text]
                    if record.kind == "text"
                    else [
                        c.text
                        for field in ("headers", "cells")
                        for c in getattr(record.structure, field, [])
                        if c.text
                    ]
                )
                passed = all(text in originals[record.snapshot_id] for text in content if text)
                gold_checks.append(
                    dict(
                        pdf=name,
                        evidence=record.evidence_identity().model_dump(mode="json"),
                        original_json_content_exact=passed,
                    )
                )
                if not passed:
                    raise ValueError("expected_original_json_content_mismatch")
        inventory[name] = dict(
            units=index.unit_count,
            text=sum(e.kind == "text" for e in records.values()),
            tables=sum(e.kind == "table" for e in records.values()),
            build_ms=index.build_ms,
        )
    save("probes.json", expected)
    results, latencies, recalls, rrs, negatives, table_hits, leakages = [], [], [], [], [], [], []
    for probe in expected:
        m = manifests[probe["pdf"]]
        req = SearchDocumentEvidenceRequest(
            document_id=m.logical_document_id,
            composition_id=m.composition_id,
            query=probe["query"],
            **probe["filters"],
        )
        start = perf_counter()
        response = tools[probe["pdf"]].search_document_evidence(req)
        elapsed = (perf_counter() - start) * 1000
        latencies.append(elapsed)
        ids = [x.evidence.reference.evidence.local_id for x in response.matches]
        relevant = set(probe["expected_local_ids"])
        rank = next((i + 1 for i, identity in enumerate(ids) if identity in relevant), None)
        if relevant:
            recalls.append({k: len(set(ids[:k]) & relevant) / len(relevant) for k in [1, 3, 5]})
            rrs.append(1 / rank if rank else 0)
            if any(e["kind"] == "table" for e in probe["expected_evidence"]):
                table_hits.append(rank is not None)
        else:
            negatives.append(response.status == "not_found")
        pins = {
            pin.identity.model_dump_json()
            for s in m.sources
            if s.status == "verified"
            for pin in s.evidence
        }
        for match in response.matches:
            leakages.extend(
                i.model_dump_json() for i in match.evidence_ids if i.model_dump_json() not in pins
            )
        results.append(
            dict(
                probe=probe["id"],
                pdf=probe["pdf"],
                query=probe["query"],
                rank=rank,
                latency_ms=elapsed,
                passed=bool(rank) if relevant else response.status == "not_found",
                response=response.model_dump(mode="json"),
            )
        )
    # Source-selection negatives on actual composition, including quarantined legacy.
    controls = []
    name = "BBS_2025"
    m = manifests[name]
    for patch in [
        dict(document_id="wrong"),
        dict(composition_id="wrong"),
        dict(snapshot_id="legacy"),
        dict(snapshot_id="D-04/recovery"),
        dict(query=""),
        dict(query="?!"),
        dict(source_page=24),
    ]:
        request = (
            dict(
                document_id=m.logical_document_id,
                composition_id=m.composition_id,
                query="Kế toán trưởng",
            )
            | patch
        )
        response = tools[name].search_document_evidence(SearchDocumentEvidenceRequest(**request))
        controls.append(
            dict(request=request, status=response.status, passed=response.status == "not_found")
        )
    rebuilt = EvidenceRetrievalTools.from_composition(
        m,
        DocumentEvidenceRepository(args.input / "repository"),
        document_id=m.logical_document_id,
        composition_id=m.composition_id,
    )
    request = SearchDocumentEvidenceRequest(
        document_id=m.logical_document_id, composition_id=m.composition_id, query="Kế toán trưởng"
    )
    controls.append(
        dict(
            case="restart_rebuild",
            passed=rebuilt.search_document_evidence(request)
            == tools[name].search_document_evidence(request),
        )
    )
    inventory[name]["rebuild_ms"] = rebuilt._search.build_ms
    rebuilt.close_search()
    metrics = dict(
        probes=len(expected),
        positive=len(recalls),
        negative=len(negatives),
        recall={f"@{k}": statistics.mean(r[k] for r in recalls) for k in [1, 3, 5]},
        mrr=statistics.mean(rrs),
        no_answer_correct=sum(negatives),
        table_hit_at_5=f"{sum(table_hits)}/{len(table_hits)}",
        leakage_count=len(leakages),
        search_ms=dict(median=statistics.median(latencies), max=max(latencies)),
        inventory=inventory,
        controls_passed=sum(c["passed"] for c in controls),
        controls_total=len(controls),
    )
    save("inventory.json", inventory)
    save("gold-source-checks.json", gold_checks)
    save("ranked-results.json", results)
    save("controls.json", controls)
    save("metrics.json", metrics)
    save("failure-analysis.json", [r for r in results if not r["passed"]])
    lines = [
        "# INT-01b — Actual results (local/private)",
        "",
        "| Query | PDF | Expected evidence | Top result | Rank | Source page | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for p, r in zip(expected, results, strict=True):
        top = r["response"]["matches"][:1]
        lines.append(
            f"| {p['query']} | {p['pdf']} | {', '.join(p['expected_local_ids']) or p['category']} | {top[0]['evidence']['reference']['evidence']['local_id'] if top else '—'} | {r['rank']} | {top[0]['pdf_page'] if top else '—'} | {'PASS' if r['passed'] else 'MISS/FALSE POSITIVE'} |"
        )
    lines.extend(["", "## Substantive samples — original content and full citations"])
    for name in inventory:
        result = next(
            r
            for r in results
            if r["pdf"] == name and r["rank"] and r["probe"] in {"P10", "P16", "P18", "P22", "P24"}
        )
        match = result["response"]["matches"][result["rank"] - 1]
        lines.extend(
            [
                "",
                f"### {name}: {result['query']}",
                "",
                match["snippet"],
                "",
                "```json",
                json.dumps(
                    dict(
                        evidence_ids=match["evidence_ids"],
                        cells=match["cells"],
                        citations=match["evidence"]["citations"],
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
            ]
        )
    (args.output / "actual-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for tool in tools.values():
        tool.close_search()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
