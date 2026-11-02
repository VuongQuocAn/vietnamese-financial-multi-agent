"""Offline BBS evidence inventory/retrieval và exact M4-03 execution lineage replay."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_d01_coverage import compare_observations
from evaluate_d04_closure import save
from evaluate_d06_validation import SNAPSHOT, selected_facts
from evaluate_m4_01_eligibility import d06_regression, regression_queries
from evaluate_m4_02_retrieval import hydrate, partial_scope_regression
from evaluate_m4_03_calculator import independent_check, protected_inputs
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    RetrievalReference,
    SnapshotCatalog,
    SnapshotDescriptor,
)
from vietnamese_financial_multi_agent.evidence.graph import record_sources
from vietnamese_financial_multi_agent.tools import (
    EvidenceRetrievalTools,
    EvidenceToolResponse,
    FinancialCalculationResponse,
    FinancialCalculator,
    FinancialRetrievalTools,
    FindDocumentEvidenceRequest,
    FindFinancialFactsRequest,
    GetEvidenceAnchorRequest,
    GetEvidenceItemRequest,
    GetEvidenceSourcesRequest,
    GetFinancialFactRequest,
    GetMetricEvidenceLineageRequest,
)


def manifest(root):
    hashes = protected_inputs(root)
    hashes.update(
        (p.relative_to(root).as_posix(), digest(p))
        for p in (root / "artifacts/evidence/M4-03-final").rglob("*")
        if p.is_file()
    )
    return dict(sorted(hashes.items()))


def persisted_evidence(root, scopes, target):
    records = []
    for year, scope in scopes.items():
        folder = root / f"artifacts/evidence/D-01/evaluation/{year}/document-evidence"
        assert (folder / "document-evidence.json").is_file()
        repo = DocumentEvidenceRepository(folder)
        rows = repo.list_by_document(**scope)
        assert all(repo.get(e.evidence_identity()) == e for e in rows)
        records.extend(rows)
    folder = root / "artifacts/evidence/D-04-review/document-evidence"
    assert (folder / "document-evidence.json").is_file()
    repo = DocumentEvidenceRepository(folder)
    rows = repo.list_by_document(target.document_id, target.snapshot_id)
    assert all(repo.get(e.evidence_identity()) == e for e in rows)
    return records + rows


def negative_controls(catalog, tools, target):
    """Real identities, intentional missing/wrong bindings; không sửa persisted graph."""
    record = catalog.evidence[0]
    exact = GetEvidenceItemRequest(
        document_id=record.document_id,
        snapshot_id=record.snapshot_id,
        local_evidence_id=record.local_evidence_id,
        kind=record.kind,
    )
    anchor = next(n for n in catalog.graph.nodes if n.kind == "anchor")
    metric = next(m for m in catalog.metrics if m.request.snapshot_id == target.snapshot_id)
    cases = [
        (
            "missing_evidence",
            tools.get_evidence_item(
                exact.model_copy(update={"local_evidence_id": "M4-04/missing"})
            ),
            "not_found",
        ),
        (
            "missing_snapshot",
            tools.get_evidence_item(exact.model_copy(update={"snapshot_id": "M4-04/missing"})),
            "not_found",
        ),
        (
            "missing_anchor",
            tools.get_evidence_anchor(GetEvidenceAnchorRequest(anchor_id="M4-04/missing")),
            "unavailable",
        ),
        (
            "wrong_anchor_document",
            tools.get_evidence_anchor(
                GetEvidenceAnchorRequest(anchor_id=anchor.node_id, document_id="M4-04/wrong")
            ),
            "not_found",
        ),
        (
            "recovery_metric_original_guard",
            tools.get_metric_evidence_lineage(
                GetMetricEvidenceLineageRequest(
                    metric_id=metric.metric_id, snapshot_id=target.parent_snapshot_id
                )
            ),
            "not_found",
        ),
        (
            "unsupported_period",
            tools.find_document_evidence(
                FindDocumentEvidenceRequest(
                    document_id=record.document_id, snapshot_id=record.snapshot_id, period="2025"
                )
            ),
            "unavailable",
        ),
    ]
    no_graph = SnapshotCatalog(catalog.descriptors, facts=catalog.facts, evidence=catalog.evidence)
    cases.append(
        (
            "graph_unavailable",
            EvidenceRetrievalTools(no_graph).get_evidence_anchor(
                GetEvidenceAnchorRequest(anchor_id=anchor.node_id)
            ),
            "unavailable",
        )
    )
    rows = []
    for case, response, expected in cases:
        assert response.status == expected and not response.matches and not response.metric_matches
        rows.append(dict(case=case, response=response.model_dump(mode="json")))
    return rows


def evaluate_source_controls(root, output):
    """Targeted replay sau source availability correction; không lặp inventory/anchors."""
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = manifest(root)
    save(output / "hashes-before.json", hashes)
    data, scopes, target = hydrate(root)
    catalog = SnapshotCatalog(**data)
    tools = EvidenceRetrievalTools(catalog)
    controls = negative_controls(catalog, tools, target)
    save(output / "negative-controls.json", controls)
    corrected = selected_facts(root, "artifacts/evidence/D-06-final", SNAPSHOT)
    corrected_catalog = SnapshotCatalog(
        [
            SnapshotDescriptor(**r)
            for r in load(root / "artifacts/evidence/D-06-final/snapshots.json")
        ],
        facts=[f for rows in corrected.values() for f in rows],
    )
    cases = []
    for selected in (catalog, corrected_catalog):
        evidence = EvidenceRetrievalTools(selected)
        financial = FinancialRetrievalTools(selected)
        for fact in selected.facts:
            retrieved = financial.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=fact.document_id,
                    snapshot_id=fact.snapshot_id,
                    local_observation_id=fact.local_observation_id,
                )
            )
            assert retrieved.status == "found"
            response = evidence.get_evidence_sources(
                GetEvidenceSourcesRequest(reference=retrieved.matches[0].reference)
            )
            assert response.status == "found"
            assert response.matches[0].record == retrieved.matches[0].record
            assert response.matches[0].citations == retrieved.matches[0].citations
            assert response.source_reviews == [retrieved.matches[0].source_review]
            cases.append(
                dict(identity=fact.observation_identity().model_dump(), status=response.status)
            )
        print(f"Source availability regression: {len(cases)} exact financial facts", flush=True)
    for record in catalog.evidence:
        result = tools.get_evidence_sources(
            GetEvidenceSourcesRequest(
                reference=RetrievalReference(
                    kind=record.kind,
                    evidence=record.evidence_identity(),
                )
            )
        )
        assert result.status == "found" and result.matches[0].record == record
    _, queries = regression_queries(root, data, scopes, target)
    save(output / "retrieval-regression.json", queries)
    save(output / "exact-fact-sources.json", cases)
    after = manifest(root)
    assert after == hashes
    save(output / "hashes-after.json", after)
    summary = dict(
        exact_fact_sources=len(cases),
        exact_evidence_sources=len(catalog.evidence),
        accepted_retrieval_queries=len(queries),
        real_negative_controls=len(controls),
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        gateway_calls=0,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = manifest(root)
    save(output / "hashes-before.json", hashes)
    data, scopes, target = hydrate(root)
    records = persisted_evidence(root, scopes, target)
    assert sorted(e.model_dump_json() for e in records) == sorted(
        e.model_dump_json() for e in data["evidence"]
    )
    data["evidence"] = records
    catalog = SnapshotCatalog(**data)
    tools, financial = EvidenceRetrievalTools(catalog), FinancialRetrievalTools(catalog)
    controls = negative_controls(catalog, tools, target)
    save(output / "negative-controls.json", controls)
    original = [r.model_dump_json() for r in [*data["facts"], *records, *data["metrics"]]]
    inventory_rows, exact_rows, page_rows, anchor_rows, fact_rows, metric_rows = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    inventory = load(root / "artifacts/evidence/D-01/inventory.json")
    year_by_document = {s["document_id"]: y for y, s in scopes.items()}
    print(
        f"Pinned {len(hashes)} inputs; checking {len(records)} persisted evidence records",
        flush=True,
    )
    for descriptor in data["descriptors"]:
        year = year_by_document[descriptor.document_id]
        rows = [
            r
            for r in records
            if (r.document_id, r.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
        ]
        total_pages = next(r["pages"] for r in inventory if r["year"] == year)
        coverage = {
            kind: sorted(
                {
                    s.reference.anchor.page.page
                    for r in rows
                    if r.kind == kind
                    for s in record_sources(r)
                    if s.reference
                    and (s.document_id, s.snapshot_id) == (r.document_id, r.snapshot_id)
                }
            )
            for kind in ("text", "table")
        }
        anchors = [
            n
            for n in data["graph"].nodes
            if n.kind == "anchor"
            and (n.anchor.document_id, n.anchor.snapshot_id)
            == (descriptor.document_id, descriptor.snapshot_id)
        ]
        inventory_rows.append(
            dict(
                year=year,
                descriptor=descriptor.model_dump(mode="json"),
                pdf_pages=total_pages,
                text=sum(r.kind == "text" for r in rows),
                table=sum(r.kind == "table" for r in rows),
                anchors=len(anchors),
                coverage=coverage,
                pages_without_text=[
                    p for p in range(1, total_pages + 1) if p not in coverage["text"]
                ],
                pages_without_table=[
                    p for p in range(1, total_pages + 1) if p not in coverage["table"]
                ],
                pages_without_any_record=[
                    p
                    for p in range(1, total_pages + 1)
                    if p not in {*coverage["text"], *coverage["table"]}
                ],
            )
        )
        for page in range(1, total_pages + 1):
            # Test both kinds separately as well as the combined page view.
            for kind in (None, "text", "table"):
                request = FindDocumentEvidenceRequest(
                    document_id=descriptor.document_id,
                    snapshot_id=descriptor.snapshot_id,
                    source_page=page,
                    evidence_type=kind,
                )
                result = tools.find_document_evidence(request)
                expected = [
                    r
                    for r in rows
                    if kind in {None, r.kind}
                    and any(
                        s.reference
                        and s.reference.anchor.page.page == page
                        and (s.document_id, s.snapshot_id) == (r.document_id, r.snapshot_id)
                        for s in record_sources(r)
                    )
                ]
                assert {m.reference.evidence for m in result.matches} == {
                    e.evidence_identity() for e in expected
                }
                assert result.status == (
                    "ambiguous" if len(expected) > 1 else "found" if expected else "not_found"
                )
                page_rows.append(
                    dict(request=request.model_dump(), status=result.status, records=len(expected))
                )
    save(output / "inventory.json", inventory_rows)
    save(output / "pages.json", page_rows)
    for record in records:
        result = tools.get_evidence_item(
            GetEvidenceItemRequest(
                document_id=record.document_id,
                snapshot_id=record.snapshot_id,
                local_evidence_id=record.local_evidence_id,
                kind=record.kind,
            )
        )
        assert result.status == "found" and result.matches[0].record == record
        assert result.matches == catalog.api.get_evidence(record.evidence_identity()).matches
        sources = tools.get_evidence_sources(
            GetEvidenceSourcesRequest(reference=result.matches[0].reference)
        )
        assert sources.matches == result.matches
        assert EvidenceToolResponse.model_validate_json(result.model_dump_json()) == result
        exact_rows.append(result.model_dump(mode="json"))
    save(output / "exact-evidence.json", exact_rows)
    for node in data["graph"].nodes:
        if node.kind != "anchor":
            continue
        result = tools.get_evidence_anchor(
            GetEvidenceAnchorRequest(
                anchor_id=node.node_id,
                document_id=node.anchor.document_id,
                snapshot_id=node.anchor.snapshot_id,
            )
        )
        assert result.status == "found" and result.matches[0].record == node.anchor
        assert result.matches == catalog.api.get_anchor(node.node_id).matches
        assert all(c.source == node.anchor for c in result.matches[0].citations)
        anchor_rows.append(
            dict(
                anchor_id=node.node_id,
                status=result.status,
                citations=[c.model_dump(mode="json") for m in result.matches for c in m.citations],
            )
        )
        if len(anchor_rows) % 750 == 0:
            print(f"Checked {len(anchor_rows)} exact anchors", flush=True)
    save(output / "anchors.json", anchor_rows)
    # Five priority items from each original filing, through the public M4-02 reference.
    for year, scope in scopes.items():
        for item, statement, period in (
            ("b01.total_assets", "B01", f"{year}-12-31"),
            ("b01.total_liabilities", "B01", f"{year}-12-31"),
            ("b02.net_revenue", "B02", str(year)),
            ("b02.gross_profit", "B02", str(year)),
            ("b03.operating_cash_flow", "B03", str(year)),
        ):
            found = financial.find_financial_facts(
                FindFinancialFactsRequest(
                    **scope,
                    canonical_item_id=item,
                    statement_type=statement,
                    period=period,
                )
            )
            assert found.status == "found" and len(found.matches) == 1
            match = found.matches[0]
            result = tools.get_evidence_sources(
                GetEvidenceSourcesRequest(reference=match.reference, **scope)
            )
            assert result.status == "found"
            assert result.matches[0].record == match.record
            assert result.matches[0].citations == match.citations
            assert result.source_reviews == [match.source_review]
            for identity in result.matches[0].evidence_references:
                associated = tools.get_evidence_item(
                    GetEvidenceItemRequest(
                        document_id=identity.document_id,
                        snapshot_id=identity.snapshot_id,
                        local_evidence_id=identity.local_id,
                        kind=identity.kind,
                    )
                )
                assert associated.status == "found"
                assert "association_is_not_verified_semantic_support" in result.caveats
            fact_rows.append(dict(year=year, item=item, response=result.model_dump(mode="json")))
    save(output / "priority-fact-sources.json", fact_rows)
    # Compare against ORIGINAL accepted execution artifacts; no replacement baseline.
    calculator = FinancialCalculator(catalog)
    accepted = load(root / "artifacts/evidence/M4-03-final/executions.json")
    assert len(accepted) == len(data["metrics"]) == 18
    for metric, wire in zip(data["metrics"], accepted, strict=True):
        old = FinancialCalculationResponse.model_validate_json(json.dumps(wire))
        assert old.metric_id == metric.metric_id and old.status == "computed"
        assert calculator.calculate_financial_metric(old.request) == old
        assert old.result == independent_check(metric, data["facts"])
        result = tools.get_metric_evidence_lineage(
            GetMetricEvidenceLineageRequest(
                metric_id=metric.metric_id,
                document_id=metric.request.document_id,
                snapshot_id=metric.request.snapshot_id,
            )
        )
        assert result.status == "found" and result.metric_matches == [old.evidence]
        assert result.matches[0].record == old.evidence.reviewed_lineage.lineage
        assert result.matches[0].citations == old.evidence.citations
        assert result.matches[0].record.completeness == "complete"
        assert result.metric_matches[0].record.result is None
        for operand, binding in zip(
            old.trace.operands, result.metric_matches[0].operands, strict=True
        ):
            assert operand.observation == binding.binding.observation
            assert operand.source_fact_node_id == binding.binding.source_fact_node_id
            source = tools.get_evidence_sources(
                GetEvidenceSourcesRequest(
                    reference=RetrievalReference(
                        kind="fact",
                        observation=operand.observation,
                    )
                )
            )
            assert source.matches == binding.facts.matches
            assert source.source_reviews == [binding.source_review]
            if metric.request.snapshot_id == target.snapshot_id:
                assert all(
                    c.snapshot_id == target.snapshot_id for m in source.matches for c in m.citations
                )
        for kind in ("metric", "lineage"):
            sources = tools.get_evidence_sources(
                GetEvidenceSourcesRequest(
                    reference=RetrievalReference(
                        kind=kind,
                        record_id=metric.metric_id,
                    )
                )
            )
            assert sources.matches == result.matches
        metric_rows.append(result.model_dump(mode="json"))
        print(
            f"Exact execution/lineage/reviews/citations: {year_by_document[metric.request.document_id]}/{metric.definition.name}",
            flush=True,
        )
    save(output / "metric-lineages.json", metric_rows)
    fresh, fresh_scopes, fresh_target = hydrate(root)
    fresh["evidence"] = persisted_evidence(root, fresh_scopes, fresh_target)
    restarted = EvidenceRetrievalTools(SnapshotCatalog(**fresh))
    for wire in exact_rows + metric_rows:
        expected = EvidenceToolResponse.model_validate_json(json.dumps(wire))
        actual = getattr(restarted, expected.request.tool)(expected.request)
        assert actual == expected
    # Bounded accepted regression: unchanged modules, no full extraction/benchmark.
    partial_scope = partial_scope_regression(financial, scopes)
    save(output / "partial-scope.json", partial_scope.model_dump(mode="json"))
    effective, queries = regression_queries(root, data, scopes, target)
    pairs = compare_observations(effective)
    assert pairs == load(root / "artifacts/evidence/D-02/cross-year-after-recovery.json")
    assert len(pairs) == 36 and all(p["status"] == "undetermined" for p in pairs)
    save(output / "retrieval-regression.json", queries)
    save(output / "cross-document.json", pairs)
    save(output / "d06-regression.json", d06_regression(root))
    for year, scope in scopes.items():
        expected = next(
            r["after"]
            for r in load(root / "artifacts/evidence/D-07/scope-results.json")
            if r["year"] == year
        )
        assert catalog.get_reporting_scope(**scope).model_dump(mode="json") == expected
    assert original == [r.model_dump_json() for r in [*data["facts"], *records, *data["metrics"]]]
    after = manifest(root)
    assert after == hashes
    save(output / "hashes-after.json", after)
    summary = dict(
        available=dict(
            text=sum(r.kind == "text" for r in records),
            table=sum(r.kind == "table" for r in records),
            anchor=len(anchor_rows),
            metric_lineage=len(metric_rows),
        ),
        retrieved=dict(
            text=sum(r["request"]["kind"] == "text" for r in exact_rows),
            table=sum(r["request"]["kind"] == "table" for r in exact_rows),
            anchor=len(anchor_rows),
            metric_lineage=len(metric_rows),
        ),
        blocked_unavailable_records=0,
        real_negative_controls=len(controls),
        page_queries=len(page_rows),
        page_queries_without_records=sum(r["records"] == 0 for r in page_rows),
        priority_fact_sources=len(fact_rows),
        fact_source_associations=sum(
            bool(r["response"]["matches"][0]["evidence_references"]) for r in fact_rows
        ),
        evidence_caveats=dict(Counter(c for r in exact_rows for c in r["caveats"])),
        anchor_limitations=dict(
            Counter(c for r in anchor_rows for s in r["citations"] for c in s["limitations"])
        ),
        computed=18,
        independent_arithmetic=18,
        original_execution_artifacts_exact=18,
        baseline_eligible=15,
        recovery_eligible=3,
        accepted_retrieval_queries=len(queries),
        cross_document_pairs_undetermined=len(pairs),
        reporting_scope_views_exact=5,
        partial_scope_coverage_exact=True,
        d06_qa09_qa15_exact=True,
        json_restart_exact=True,
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        gateway_calls=0,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-04"))
    parser.add_argument("--source-controls-only", action="store_true")
    args = parser.parse_args()
    run = evaluate_source_controls if args.source_controls_only else evaluate
    run(Path.cwd().resolve(), args.output.resolve())
