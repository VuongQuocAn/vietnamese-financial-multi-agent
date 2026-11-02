"""D-07 bounded offline source investigation; không sửa accepted inputs/Gateway."""

import argparse
import json
import re
from pathlib import Path

import pypdfium2 as pdfium
from evaluate_d01_coverage import compare_observations
from evaluate_d04_closure import save
from evaluate_m4_01_eligibility import inputs as metric_inputs
from evaluate_m4_01_eligibility import regression_queries
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.accounting import (
    ContextEvidence,
    FinancialSourceReference,
    evidence_from_ocr_scope_choices,
    resolve_financial_context,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRPage
from vietnamese_financial_multi_agent.evidence import (
    EvidenceAnchor,
    EvidenceGraph,
    ExecutionCompatibilityApproval,
    ReportingScopeReview,
    SnapshotCatalog,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)

KEYWORDS = re.compile(
    r"hợp nhất|riêng|công ty con|công ty mẹ|đơn vị trực thuộc|cơ sở lập|phạm vi",
    re.IGNORECASE,
)


def text_fields(value, pointer=""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = pointer + "/" + key
            if key in {"text", "raw_text"} and isinstance(child, str):
                yield path, child
            elif key == "context" and isinstance(child, list):
                yield from (
                    (path + "/" + str(i), t) for i, t in enumerate(child) if isinstance(t, str)
                )
            else:
                yield from text_fields(child, path)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from text_fields(child, pointer + "/" + str(i))


def manifest(root):
    paths = set(load(root / "artifacts/evidence/M4-01/verified/hashes-before.json"))
    for path in (root / "artifacts/evidence/M4-01").rglob("*"):
        if path.is_file():
            paths.add(path.relative_to(root).as_posix())
    paths.add("configs/m4-execution-policies.json")
    return {p: digest(root / p) for p in sorted(paths)}


def render(root, output, inventory, requests):
    records = []
    for row in inventory:
        assert digest(root / row["pdf"]) == row["sha256"]
        with pdfium.PdfDocument(root / row["pdf"]) as pdf:
            for number in sorted(set(requests[row["year"]])):
                target = output / f"source-{row['year']}-{number}.png"
                if target.exists():
                    raise ValueError("Use a new render filename; never overwrite evidence")
                page = pdf[number - 1]
                bitmap = page.render(scale=1.5)
                try:
                    bitmap.to_pil().save(target)
                finally:
                    bitmap.close()
                    page.close()
                records.append(
                    dict(
                        year=row["year"],
                        document_id="sha256:" + row["sha256"],
                        pdf_sha256=row["sha256"],
                        pdf_page=number,
                        render=target.name,
                        render_sha256=digest(target),
                        method="original_pdf_render",
                    )
                )
    return records


def prepare(root, output):
    if output.exists():
        raise ValueError("Use a NEW ignored output directory")
    output.mkdir(parents=True)
    save(output / "hashes-before.json", manifest(root))
    inventory = load(root / "artifacts/evidence/D-01/inventory.json")
    search, pages = [], []
    for row in inventory:
        year = row["year"]
        paths = sorted(
            (root / f"data/processed/Financial_Report_OCR/BBS/{year}/ocr_json").glob("*.json")
        )
        for path in paths:
            raw = load(path)
            number = raw["page"]["page"]
            fields = list(text_fields(raw))
            hits = [dict(selector=p, text=t) for p, t in fields if KEYWORDS.search(t)]
            pages.append(
                dict(
                    year=year,
                    pdf_page=number,
                    cache=path.relative_to(root).as_posix(),
                    cache_sha256=digest(path),
                    text_fields=len(fields),
                    keyword_hits=len(hits),
                    binding="candidate_only_until_original_pdf_visual_verification",
                )
            )
            search.extend(
                dict(year=year, pdf_page=number, cache=path.relative_to(root).as_posix(), **h)
                for h in hits
            )
        normalized = root / f"artifacts/evidence/D-01/evaluation/{year}/normalized-result.json"
        for record in load(normalized)["records"]:
            for pointer, text in text_fields(record["response"]["output"]["payload"]):
                if KEYWORDS.search(text):
                    search.append(
                        dict(
                            year=year,
                            pdf_page=record["source"]["page"]["page"],
                            cache=normalized.relative_to(root).as_posix(),
                            selector=pointer,
                            text=text,
                        )
                    )
    save(output / "cache-inventory.json", pages)
    save(output / "cache-candidates.json", search)
    # Source pages requested by Tech Lead plus cover/audit opinion of each filing.
    requests = {
        2021: [1, 2, 3, 4, 5, 10, 13, 14],
        2022: [1, 2, 3, 4, 9, 12],
        2023: [1, 2, 3, 4, 9, 10, 12, 13],
        2024: [1, 2, 3, 4, 5, 6, 11, 14, 15],
        2025: [1, 2, 3, 4, 9, 12, 13],
    }
    save(output / "renders.json", render(root, output, inventory, requests))
    print(
        json.dumps(
            dict(
                cached_pages=len(pages),
                candidate_hits=len(search),
                renders=sum(len(p) for p in requests.values()),
            )
        ),
        flush=True,
    )
    for year in requests:
        matches = [r for r in search if r["year"] == year]
        print(
            json.dumps(
                dict(
                    year=year,
                    candidate_pages=sorted({r["pdf_page"] for r in matches}),
                    excerpts=[
                        dict(page=r["pdf_page"], text=r["text"])
                        for r in matches
                        if re.search(
                            r"hợp nhất|công ty con|công ty mẹ|báo cáo tài chính riêng",
                            r["text"],
                            re.I,
                        )
                    ],
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )


def evaluate(root, output):
    """Controlled readings của38 renders đã đọc; không tự suy scope từ absence."""
    hashes = load(output / "hashes-before.json")
    assert hashes == manifest(root), "protected_input_changed"
    renders = load(output / "renders.json")
    if (output / "extra-renders.json").is_file():
        renders += load(output / "extra-renders.json")
    assert len(renders) == 38
    for record in renders:
        assert digest(output / record["render"]) == record["render_sha256"]
    search = load(output / "cache-candidates.json")
    inspections = [
        dict(
            r,
            reading_method="controlled_original_pdf_visual_read",
            finding="explicit_selected_filing_scope_option"
            if (r["year"], r["pdf_page"]) == (2024, 1)
            else "no_explicit_filing_scope_in_inspected_page",
            cache_quotes=[
                dict(selector=c["selector"], text=c["text"])
                for c in search
                if (c["year"], c["pdf_page"]) == (r["year"], r["pdf_page"])
            ],
        )
        for r in renders
    ]
    save(output / "source-inspections.json", inspections)
    data, scopes, target = metric_inputs(root)
    original_contexts = [f.model_dump_json() for f in data["facts"]]
    reviews, before_after = [], []
    evidence_root = root / "artifacts/evidence"
    reference = output.relative_to(evidence_root).as_posix()
    basis_pages = {2021: 10, 2022: 9, 2023: 9, 2024: 11, 2025: 9}
    for year, scope in scopes.items():
        descriptor = next(
            d
            for d in data["descriptors"]
            if (d.document_id, d.snapshot_id) == (scope["document_id"], scope["snapshot_id"])
        )
        page_number = 1 if year == 2024 else basis_pages[year]
        path = (
            root
            / f"data/processed/Financial_Report_OCR/BBS/{year}/ocr_json/page_{page_number}.json"
        )
        raw = OCRPage.model_validate_json(path.read_text(encoding="utf-8-sig"))
        identity = RawPageIdentity(
            symbol=raw.page.symbol,
            year=raw.page.year,
            page=page_number,
            image=raw.page.image,
            source_ref=descriptor.document_id,
        )
        render_record = next(
            r for r in renders if (r["year"], r["pdf_page"]) == (year, page_number)
        )
        if year == 2024:
            choices = evidence_from_ocr_scope_choices(raw, source_page=identity)
            assert len(choices) == 3
            assert [c.scope_selection for c in choices] == ["selected", "unselected", "unselected"]
            # Original-PDF control: selected checkbox is "BCTC riêng", others unchecked.
            assert (
                choices[0].raw_text
                == "BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc);"
            )
            legacy = resolve_financial_context(
                [ContextEvidence(raw_text=c.raw_text, provenance=c.provenance) for c in choices]
            )
            assert legacy.context.reporting_scope is None
            assert resolve_financial_context(choices).context.reporting_scope is None
        else:
            index, cell = next(
                (i, e)
                for i, e in enumerate(raw.elements)
                if "Cơ sở lập báo cáo" in getattr(e, "text", "")
            )
            choices = [
                ContextEvidence(
                    raw_text=cell.text,
                    status="unresolved",
                    provenance=[
                        FinancialSourceReference(
                            anchor=SourceAnchor(
                                page=identity, element_id=cell.id, status="uncertain"
                            ),
                            source_pointer=f"/elements/{index}/text",
                            provenance_level="element",
                        )
                    ],
                )
            ]
        for item in choices:
            verified = item.model_copy(update={"status": "resolved"}, deep=True)
            scope_value = resolve_financial_context([verified]).context.reporting_scope
            reviews.append(
                ReportingScopeReview(
                    document_id=descriptor.document_id,
                    snapshot_id=descriptor.snapshot_id,
                    pdf_sha256=descriptor.pdf_sha256,
                    pdf_page=page_number,
                    source_quote=item.raw_text,
                    evidence_role="filing_scope" if year == 2024 else "inspected_context",
                    reporting_scope=scope_value if year == 2024 else None,
                    evidence=verified,
                    sources=[
                        EvidenceAnchor(
                            document_id=descriptor.document_id,
                            snapshot_id=descriptor.snapshot_id,
                            reference=p.model_copy(deep=True),
                        )
                        for p in verified.provenance
                    ],
                    method="controlled_original_pdf_visual_read",
                    review_image_sha256=render_record["render_sha256"],
                    verification_reference=f"{reference}/source-inspections.json#{year}/page/{page_number}",
                    inspection_reference=f"{reference}/source-inspections.json",
                )
            )
        before_after.append(
            dict(
                year=year,
                **scope,
                original_scope_values=sorted(
                    {
                        str(f.context.reporting_scope)
                        for f in data["facts"]
                        if (f.document_id, f.snapshot_id)
                        == (descriptor.document_id, descriptor.snapshot_id)
                    }
                ),
                root_cause="context_transport_and_selected_option_resolver_gap"
                if year == 2024
                else "insufficient_explicit_scope_source_after_bounded_inspection",
                inspected_pdf_pages=sorted(r["pdf_page"] for r in renders if r["year"] == year),
                all_cached_pages_searched=sum(
                    r["year"] == year for r in load(output / "cache-inventory.json")
                ),
            )
        )
    save(output / "reporting-scope-reviews.json", [r.model_dump(mode="json") for r in reviews])
    restarted = [
        ReportingScopeReview.model_validate_json(json.dumps(r))
        for r in load(output / "reporting-scope-reviews.json")
    ]
    assert restarted == reviews
    policy = load(root / "configs/m4-execution-policies.json")
    preparation = load(root / "configs/d02-analytical-policies.json")
    graph = EvidenceGraph.model_validate_json(
        (root / "artifacts/evidence/D-04-review/graph.json").read_text(encoding="utf-8")
    )
    catalog = SnapshotCatalog(
        **data,
        graph=graph,
        reporting_scope_reviews=restarted,
        approval=PreparationApproval(**preparation["preparation_approval"]),
        execution_approval=ExecutionCompatibilityApproval(**policy["execution_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in policy["formula_policies"]],
        formula_approvals=[
            FormulaExecutionApproval(**a) for a in policy["formula_execution_approvals"]
        ],
    )
    for row in before_after:
        resolution = catalog.get_reporting_scope(row["document_id"], row["snapshot_id"])
        assert resolution.reporting_scope == ("separate" if row["year"] == 2024 else None)
        assert resolution.evidence_status == (
            "confirmed" if row["year"] == 2024 else "insufficient"
        )
        assert not resolution.cross_document_execution_approved
        fresh = SnapshotCatalog(
            data["descriptors"], reporting_scope_reviews=reviews
        ).get_reporting_scope(row["document_id"], row["snapshot_id"])
        assert fresh == resolution
        row["after"] = resolution.model_dump(mode="json")
    save(output / "scope-results.json", before_after)
    print(
        "Scope: 2024 separate confirmed;2021/2022/2023/2025 unresolved source insufficient;restart exact",
        flush=True,
    )
    old_rows = load(root / "artifacts/evidence/M4-01/verified/metrics.json")
    assessed = {}
    for descriptor in data["descriptors"]:
        selection = catalog.select(descriptor.document_id, descriptor.snapshot_id)
        assert selection.status == "selected"
        assessed.update((c.metric_id, c) for c in selection.candidates[0].metrics)
    for metric, old in zip(data["metrics"], old_rows, strict=True):
        assert metric.metric_id == old["metric_id"]
        assert assessed[metric.metric_id].model_dump(mode="json") == old["closure"]
        descriptor = next(
            d
            for d in data["descriptors"]
            if (d.document_id, d.snapshot_id)
            == (metric.request.document_id, metric.request.snapshot_id)
        )
        assert (
            catalog.reviewed_lineage(descriptor, metric.metric_id).model_dump(mode="json")
            == old["reviewed_lineage"]
        )
        assert metric.result is None
    effective, queries = regression_queries(root, data, scopes, target)
    pairs = compare_observations(effective)
    assert pairs == load(root / "artifacts/evidence/D-02/cross-year-after-recovery.json")
    assert len(pairs) == 36 and all(p["status"] == "undetermined" for p in pairs)
    assert [f.model_dump_json() for f in data["facts"]] == original_contexts
    save(
        output / "metric-closures.json",
        [assessed[m.metric_id].model_dump(mode="json") for m in data["metrics"]],
    )
    save(output / "cross-document.json", pairs)
    after_hashes = manifest(root)
    assert hashes == after_hashes
    save(output / "hashes-after.json", after_hashes)
    summary = dict(
        pdf_count=5,
        cached_pages_searched=133,
        original_pdf_pages_visually_checked=len(renders),
        resolved_scopes={str(r["year"]): r["after"]["reporting_scope"] for r in before_after},
        source_insufficient_years=[
            r["year"] for r in before_after if r["after"]["evidence_status"] == "insufficient"
        ],
        baseline_eligible=15,
        recovery_eligible=3,
        metric_closures_exact=len(assessed),
        lineages_exact=18,
        cross_document_pairs_undetermined=len(pairs),
        retrieval_queries_exact=len(queries),
        persisted_restart_exact=True,
        original_facts_unchanged=True,
        protected_hashes=len(hashes),
        input_hashes_unchanged=True,
        gateway_calls=0,
        computed_metrics=0,
        cross_document_execution_approved=False,
    )
    assert all(c.calculation_eligible for c in assessed.values()) and len(assessed) == 18
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-07"))
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    root, output = Path.cwd().resolve(), args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    if args.prepare:
        prepare(root, output)
    else:
        evaluate(root, output)
