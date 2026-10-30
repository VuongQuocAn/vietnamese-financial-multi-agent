"""M3-06: inventory read-only và lineage trên persisted M3-05/W-07, zero API calls."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    DerivedMetric,
    MetricLineage,
    build_graph,
    facts_from_persisted_result,
    trace_metric_lineage,
)
from vietnamese_financial_multi_agent.evidence.document_evidence import DocumentEvidence


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def raw_identities(value):
    if isinstance(value, dict):
        if value.get("symbol") == "BBS" and str(value.get("year")) in map(str, range(2021, 2026)):
            yield str(value["year"]), value.get("page")
        for child in value.values():
            yield from raw_identities(child)
    elif isinstance(value, list):
        for child in value:
            yield from raw_identities(child)


def validate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    baseline = load(root / "artifacts/evidence/M3-05/review-final/readiness.json")
    hashes = {p: digest(root / p) for p in baseline["source_hashes"]}

    def preserve(path):
        hashes[path.relative_to(root).as_posix()] = digest(path)

    pdfs, inventory = {}, []
    for year in range(2021, 2026):
        paths = list((root / f"data/raw/Financial_Report_pdf/BBS/{year}").glob("*.pdf"))
        assert len(paths) == 1, "Report missing or ambiguous; inventory scope changed"
        path = paths[0]
        preserve(path)
        document = pdfium.PdfDocument(path)
        chars = []
        for page in document:
            text = page.get_textpage()
            chars.append(text.count_chars())
            text.close()
            page.close()
        pages = len(document)
        document.close()
        pdfs[year] = digest(path)
        ocr = sorted(
            (root / f"data/processed/Financial_Report_OCR/BBS/{year}/ocr_json").glob("*.json")
        )
        texts, tables, seen = 0, 0, []
        for pagepath in ocr:
            preserve(pagepath)
            payload = load(pagepath)
            assert payload["page"]["symbol"] == "BBS"
            assert str(payload["page"]["year"]) == str(year)
            seen.append(payload["page"]["page"])
            texts += sum(e["type"] == "text" for e in payload["elements"])
            tables += sum(e["type"] == "table" for e in payload["elements"])
        inventory.append(
            dict(
                year=year,
                pdf=path.relative_to(root).as_posix(),
                sha256=pdfs[year],
                pages=pages,
                readable=True,
                text_chars=chars,
                pdf_type="scanned_no_text_layer" if not any(chars) else "text_or_mixed",
                ocr_pages=len(ocr),
                ocr_texts=texts,
                ocr_tables=tables,
                ocr_page_numbers=sorted(seen),
                pdf_ocr_content_binding="not_verified",
            )
        )

    # Inventory references trong M1 artifacts chỉ là metadata, không thành facts/periods.
    m1_refs = defaultdict(set)
    for path in sorted((root / "artifacts").rglob("*.json")):
        if path.is_relative_to(output) or "M3-06" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        for year, _ in raw_identities(load(path)):
            if not rel.startswith("artifacts/evidence/"):
                m1_refs[year].add(rel)

    # Xác định PDF của mọi persisted runtime attempt bằng hash, không filename/ticker.
    attempts = []
    for path in sorted((root / "artifacts").rglob("result.json")):
        payload = load(path)
        if not {"document_id", "attempt_id", "quality"} <= payload.keys():
            continue
        original = path.parents[2] / "original.pdf"
        if not original.exists():
            continue
        matched = [year for year, sha in pdfs.items() if digest(original) == sha]
        if matched:
            preserve(path)
            attempts.append(
                dict(
                    path=path.relative_to(root).as_posix(),
                    year=matched[0],
                    document_id=payload["document_id"],
                    snapshot_id=payload["attempt_id"],
                    quality_available=payload["quality"] is not None,
                )
            )

    catalogs = []
    for folder in ("data/canonical", "data/normalized", "artifacts/evidence"):
        for path in sorted((root / folder).rglob("canonical-facts.json")):
            preserve(path)
            payload = load(path)
            facts = TypeAdapter(list[CanonicalFinancialFact]).validate_json(
                json.dumps(payload["observations"])
            )
            catalogs.append(
                dict(
                    path=path.relative_to(root).as_posix(),
                    facts=len(facts),
                    identities=sorted({(f.document_id, f.snapshot_id) for f in facts}),
                    periods=dict(Counter(f.context.period for f in facts)),
                )
            )

    source = root / "artifacts/evidence/M3-05/review-final/metrics.json"
    preserve(source)
    metrics = TypeAdapter(list[DerivedMetric]).validate_json(source.read_text(encoding="utf-8"))
    assert len(metrics) == 6
    all_facts, evidence = [], []
    for family in ("storage", "fresh-storage"):
        paths = list((root / f"artifacts/w07/{family}").rglob("result.json"))
        assert len(paths) == 1
        all_facts.extend(facts_from_persisted_result(load(paths[0])))
        path = (
            root
            / f"artifacts/evidence/M3-03-real-validation/final/w07-{family}/document-evidence.json"
        )
        preserve(path)
        evidence.extend(
            TypeAdapter(list[DocumentEvidence]).validate_json(json.dumps(load(path)["records"]))
        )
    before = [f.model_dump_json() for f in all_facts]
    graph = build_graph(all_facts, evidence, metrics)
    lineages = [trace_metric_lineage(m, graph, all_facts, evidence) for m in metrics]
    rows = []
    for metric, lineage in zip(metrics, lineages, strict=True):
        for row in lineage.operands:
            if row.binding.status == "bound":
                assert len(row.observations) == 1
                original = next(
                    f for f in all_facts if f.observation_identity() == row.binding.observation
                )
                assert row.observations[0] == original
                assert row.usability.quality_context == original.quality_context
                assert row.anchors == original.sources
        rows.append(
            dict(
                metric=metric.definition.name,
                document_id=metric.request.document_id,
                snapshot_id=metric.request.snapshot_id,
                metric_id=metric.metric_id,
                completeness=lineage.completeness,
                compatibility=lineage.compatibility.status,
                roles={
                    o.binding.role: dict(
                        status=o.binding.status,
                        observations=len(o.observations),
                        anchors=len(o.anchors),
                        associations=len(o.associations),
                        decisions=[q.decision for f in o.observations for q in f.quality_context],
                        grounding=o.usability.grounding_levels if o.usability else [],
                        unresolved=o.unresolved,
                    )
                    for o in lineage.operands
                },
                blockers=lineage.tasks.blockers,
            )
        )
    atomic_json(output / "lineages.json", [lineage.model_dump(mode="json") for lineage in lineages])
    assert (
        TypeAdapter(list[MetricLineage]).validate_json(
            (output / "lineages.json").read_text(encoding="utf-8")
        )
        == lineages
    )
    assert before == [f.model_dump_json() for f in all_facts]

    for row in inventory:
        year = row["year"]
        row["runtime_attempts"] = [a for a in attempts if a["year"] == year]
        row["m1_artifact_references"] = sorted(m1_refs[str(year)])
        row["canonical_catalogs"] = [
            c["path"]
            for c in catalogs
            if any(
                (a["document_id"], a["snapshot_id"]) in c["identities"]
                for a in row["runtime_attempts"]
            )
        ]
        row["discovery"] = (
            "available"
            if row["runtime_attempts"]
            else "full_pdf_not_found; partial_M1_references_only"
        )
        row["financial_extraction"] = "available" if row["runtime_attempts"] else "not_found"
        row["typed_text_table_evidence"] = (
            "available_selected_scope" if year == 2025 else "not_found"
        )
        row["graph_metrics"] = "available_selected_scope" if year == 2025 else "not_found"
        row["lineage_evaluation"] = (
            "evaluated" if year == 2025 else "OCR_AVAILABLE_NO_CANONICAL_FACTS — NOT EVALUATED"
        )
    assert all(digest(root / p) == sha for p, sha in hashes.items())
    numeric = [f for f in all_facts if f.canonical_item_id and f.value.normalized_value is not None]
    preparations = []
    for metric in metrics:
        selected = [
            f
            for f in numeric
            if (f.document_id, f.snapshot_id)
            == (metric.request.document_id, metric.request.snapshot_id)
        ]
        for period in sorted({f.context.period for f in selected}):
            if metric.definition.name == "gross_margin" and period in {"2024", "2025"}:
                roles = {"gross_profit": "b02.gross_profit", "revenue": "b02.net_revenue"}
            elif metric.definition.name == "debt_to_assets" and period in {
                "2025-01-01",
                "2025-12-31",
            }:
                roles = {"liabilities": "b01.total_liabilities", "assets": "b01.total_assets"}
            else:
                continue
            preparations.append(
                dict(
                    metric=metric.definition.name,
                    snapshot_id=metric.request.snapshot_id,
                    period=period,
                    candidates={
                        role: [
                            f.observation_identity().model_dump()
                            for f in selected
                            if f.context.period == period and f.canonical_item_id == item
                        ]
                        for role, item in roles.items()
                    },
                    execution="blocked_policy_and_context",
                    computed=False,
                )
            )
    summary = dict(
        inventory=inventory,
        canonical_catalogs=catalogs,
        rows=rows,
        completeness=dict(Counter(lineage.completeness for lineage in lineages)),
        compatibility=dict(Counter(lineage.compatibility.status for lineage in lineages)),
        operand_occurrences=sum(len(lineage.operands) for lineage in lineages),
        resolved_operands=sum(
            len(o.observations) for lineage in lineages for o in lineage.operands
        ),
        anchor_occurrences=sum(len(o.anchors) for lineage in lineages for o in lineage.operands),
        quality_preserved=True,
        original_context_preserved=True,
        restart_exact=True,
        canonical_numeric_periods=dict(Counter(f.context.period for f in numeric)),
        canonical_numeric_items_by_period={
            p: dict(Counter(f.canonical_item_id for f in numeric if f.context.period == p))
            for p in sorted({f.context.period for f in numeric})
        },
        multi_year_preparations=preparations,
        revenue_comparison=dict(
            available_periods=["2024", "2025"],
            missing_periods=["2021", "2022", "2023"],
            scope="same-document 2025 current and 2024 comparative; two independent snapshots",
            cross_document_original_vs_comparative="not_available",
            prior_2024_yoy="missing 2023 revenue",
            computed=False,
        ),
        missing_financial_extraction_years=[2021, 2022, 2023, 2024],
        multi_year_evaluation="NOT PASS — missing original-filing canonical facts 2021–2024",
        source_hashes=hashes,
        unchanged_files=len(hashes),
        gemini_calls=0,
        ocr_calls=0,
        extraction_calls=0,
        calculation_executed=False,
    )
    atomic_json(output / "report.json", summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "completeness",
                    "compatibility",
                    "operand_occurrences",
                    "resolved_operands",
                    "anchor_occurrences",
                    "canonical_numeric_periods",
                    "unchanged_files",
                )
            }
        )
    )
    for row in rows:
        print(json.dumps(row))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(Path.cwd().resolve(), args.output.resolve())
