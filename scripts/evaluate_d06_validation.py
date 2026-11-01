"""D-06: bounded offline BBS evaluation; never write accepted input snapshots."""

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from evaluate_d01_coverage import compare_observations, fixed_queries, persist
from evaluate_d04_closure import save
from evaluate_d05_corrections import manifest as previous_manifest
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.accounting import (
    FinancialNormalizationResult,
    RelationshipValue,
    evaluate_accounting_relationships,
)
from vietnamese_financial_multi_agent.accounting.automated_extraction import run_automated_pdf
from vietnamese_financial_multi_agent.accounting.completeness import SourceRowInventory
from vietnamese_financial_multi_agent.accounting.item_mapping import ITEM_CATALOG
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.accounting.raw_corrections import extraction_payload
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    DocumentEvidenceRepository,
    EvidenceGraph,
    EvidenceQuery,
    EvidenceRetrieval,
    RetrievalReference,
    SnapshotCatalog,
    SnapshotDescriptor,
    bind_source_review,
    build_graph,
    evaluate_source_validations,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    trace_metric_lineage,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    PreparationApproval,
    PreparedFormulaPolicy,
)

SOURCE = "artifacts/evidence/D-05-review"
SNAPSHOT = "D-06/mapping-v2.1"


def manifest(root):
    paths = set(previous_manifest(root))
    for folder in ("D-05-review", "D-05-review-prep"):
        paths.update(
            p.relative_to(root).as_posix()
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return {p: digest(root / p) for p in sorted(paths)}


def selected_facts(root, folder=SOURCE, snapshot="D-05/corrected-v1"):
    inventory = load(root / "artifacts/evidence/D-01/inventory.json")
    return {
        row["year"]: CanonicalFactRepository(
            root / folder / str(row["year"]) / "canonical"
        ).list_by_document("sha256:" + row["sha256"], snapshot)
        for row in inventory
    }


def normalization(fact):
    return FinancialNormalizationResult(
        contract_version="financial_normalization_v1",
        value=fact.value,
        context=fact.context,
        provenance=[s.reference for s in fact.sources if s.reference],
    )


def coverage(facts):
    groups = {}
    for f in facts:
        key = f"{f.context.statement_type}/{f.source_item_code}"
        row = groups.setdefault(key, Counter())
        row["slots"] += 1
        row["mapped"] += bool(f.canonical_item_id)
        row["numeric"] += f.value.normalized_value is not None
    return {key: dict(value) for key, value in sorted(groups.items())}


def qa09(facts, snapshot):
    document = facts[0].document_id
    return (
        EvidenceRetrieval(
            facts,
            coverage=[
                CanonicalCoverage(
                    document_id=document,
                    snapshot_id=snapshot,
                    canonical_extraction="available",
                    missing_canonical_items=[]
                    if any(f.canonical_item_id == "b01.short_term_liabilities" for f in facts)
                    else ["b01.short_term_liabilities"],
                    inventory_reference="D-06/source-slot-inventory",
                )
            ],
        )
        .find_facts(
            EvidenceQuery(
                document_id=document,
                snapshot_id=snapshot,
                canonical_item_id="b01.short_term_liabilities",
                period="2024-12-31",
            )
        )
        .model_dump(mode="json")
    )


def before(root, output):
    if output.exists():
        raise ValueError("Use a new output directory")
    output.mkdir(parents=True)
    save(output / "hashes-before.json", manifest(root))
    facts = selected_facts(root)
    assert sum(map(len, facts.values())) == 910
    values = [
        RelationshipValue(
            pdf_sha256=f.document_id.removeprefix("sha256:"), extraction=normalization(f)
        )
        for f in facts[2023]
    ]
    checks = evaluate_accounting_relationships(values)
    identity = [c.model_dump(mode="json") for c in checks if c.rule_id == "b01.balance_identity"]
    save(
        output / "before.json",
        dict(
            snapshot="D-05/corrected-v1",
            qa09=qa09(facts[2024], "D-05/corrected-v1"),
            qa15=identity,
            coverage=coverage([f for fs in facts.values() for f in fs]),
            source_slots=[
                f.model_dump(mode="json")
                for fs in facts.values()
                for f in fs
                if (f.context.statement_type, f.source_item_code)
                in {("B01", c) for c in ("100", "200", "270", "300", "310", "400", "440")}
                | {("B02", "01"), ("B02", "02"), ("B03", "50"), ("B03", "60")}
            ],
        ),
    )
    print("Before: QA09=" + qa09(facts[2024], "D-05/corrected-v1")["status"])
    print("QA15=" + str([(c["status"], c["issues"], c["missing_inputs"]) for c in identity]))


def accepted_regressions(root):
    """Rebuild accepted catalog/graph/lineages/queries from persisted inputs, no replay."""
    base = root / "artifacts/evidence/D-01/evaluation"
    d04 = root / "artifacts/evidence/D-04-review"
    descriptors = [SnapshotDescriptor(**d) for d in load(d04 / "snapshots.json")]
    facts, evidence, scopes = [], [], {}
    for row in load(base.parent / "inventory.json"):
        result = load(base / str(row["year"]) / "normalized-result.json")
        facts.extend(
            CanonicalFactRepository(base / str(row["year"]) / "canonical").list_by_document(
                result["document_id"], result["attempt_id"]
            )
        )
        evidence.extend(evidence_from_persisted_result(result))
        scopes[row["year"]] = dict(
            document_id=result["document_id"], snapshot_id=result["attempt_id"]
        )
    target = next(d for d in descriptors if d.parent_snapshot_id)
    recovered = CanonicalFactRepository(d04 / "canonical").list_by_document(
        target.document_id, target.snapshot_id
    )
    recovered_evidence = DocumentEvidenceRepository(d04 / "document-evidence").list_by_document(
        target.document_id, target.snapshot_id
    )
    all_facts, all_evidence = facts + recovered, evidence + recovered_evidence
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m))
        for p in (base / "metrics.json", d04 / "metrics.json")
        for m in load(p)
    ]
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for p in (
            root / "artifacts/evidence/D-02/source-reviews.json",
            root / "artifacts/evidence/D-02/recovery-source-reviews.json",
            d04 / "source-reviews.json",
        )
        for r in load(p)
    ]
    bases = [
        AccountingBasisReview(**b)
        for p in (
            root / "artifacts/evidence/D-02/accounting-basis-reviews.json",
            d04 / "accounting-basis-reviews.json",
        )
        for b in load(p)
    ]
    policy = load(root / "configs/d02-analytical-policies.json")
    graph = build_graph(all_facts, all_evidence, metrics)
    assert graph == EvidenceGraph.model_validate_json(
        (d04 / "graph.json").read_text(encoding="utf-8")
    )
    catalog = SnapshotCatalog(
        descriptors,
        all_facts,
        all_evidence,
        metrics,
        graph=graph,
        source_reviews=reviews,
        accounting_bases=bases,
        approval=PreparationApproval(**policy["preparation_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in policy["formula_policies"]],
    )
    entries = [
        catalog.select(d.document_id, d.snapshot_id).candidates[0].model_dump(mode="json")
        for d in descriptors
    ]
    assert entries == load(d04 / "catalog.json")
    assert [
        trace_metric_lineage(
            m, graph, all_facts, all_evidence, expected_formula=m.definition
        ).model_dump(mode="json")
        for m in metrics[:15]
    ] == load(base / "lineages.json")
    assert [
        catalog.reviewed_lineage(target, m.metric_id).model_dump(mode="json") for m in metrics[15:]
    ] == load(d04 / "lineages.json")
    effective = [f for f in facts if f.document_id != target.document_id] + recovered
    assert compare_observations(effective) == load(
        root / "artifacts/evidence/D-02/cross-year-after-recovery.json"
    )
    scopes[2022]["snapshot_id"] = target.snapshot_id
    api = EvidenceRetrieval(
        effective,
        [e for e in evidence if e.document_id != target.document_id] + recovered_evidence,
        coverage=[
            CanonicalCoverage(
                **s,
                canonical_extraction="available",
                missing_canonical_items=["b01.short_term_liabilities"],
                inventory_reference="D-01/inventory",
            )
            for s in scopes.values()
        ],
    )
    queries = load(root / "artifacts/evidence/D-02-final/retrieval.json")
    assert [q["case"] for q in queries] == fixed_queries()
    for q in queries:
        case = q["case"]
        scope = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            scope["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**scope, canonical_item_id=case["item"], period=case.get("period"))
        if case["operation"] == "different_snapshots":
            legacy = facts_from_persisted_result(load(base.parent / "2021/result.json"))
            result = EvidenceRetrieval([*effective, *legacy]).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
        assert result.model_dump(mode="json") == q["result"], case["id"]
        if case["operation"] == "get_sources":
            assert [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ] == q["sources"]
    assert all(
        catalog.api.get_fact(f.observation_identity()).matches[0].record == f for f in all_facts
    )
    return dict(
        baseline_ready=sum(
            e["preparation_ready_metrics"]
            for e in entries
            if not e["descriptor"]["parent_snapshot_id"]
        ),
        recovery_ready=sum(
            e["preparation_ready_metrics"] for e in entries if e["descriptor"]["parent_snapshot_id"]
        ),
        eligible=sum(e["calculation_eligible_metrics"] for e in entries),
        graph_exact=True,
        baseline_lineages_exact=15,
        recovery_lineages_exact=3,
        queries_exact=len(queries),
        cross_year_pairs_exact=36,
        accepted_fact_lookups_exact=len(all_facts),
    )


def projection_queries(root, facts, evidence, results):
    scopes = {
        year: dict(document_id=r["document_id"], snapshot_id=SNAPSHOT)
        for year, r in results.items()
    }
    api = EvidenceRetrieval(
        facts,
        evidence,
        coverage=[
            CanonicalCoverage(
                **scope,
                canonical_extraction="available",
                inventory_reference="D-06/selected-projection",
            )
            for scope in scopes.values()
        ],
    )
    rows = []
    for case in fixed_queries():
        scope = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            scope["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**scope, canonical_item_id=case["item"], period=case.get("period"))
        if case["operation"] == "different_snapshots":
            legacy = facts_from_persisted_result(
                load(root / "artifacts/evidence/D-01/2021/result.json")
            )
            result = EvidenceRetrieval(facts + legacy).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
        row = dict(case=case, result=result.model_dump(mode="json"))
        if case["operation"] == "get_sources":
            row["sources"] = [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ]
        rows.append(row)
    assert len(rows) == 29
    gap = next(r for r in rows if r["case"]["id"] == "Q25")
    assert gap["result"]["status"] == "ambiguous" and len(gap["result"]["matches"]) == 2
    return rows


def evaluate(root, output, projection_source=None):
    if projection_source is not None:
        if output.exists():
            raise ValueError("Use a new report output directory")
        output.mkdir(parents=True)
        for name in ("hashes-before.json", "before.json"):
            save(output / name, load(projection_source / name))
    projection_hashes = (
        {
            p.relative_to(projection_source).as_posix(): digest(p)
            for p in projection_source.rglob("*")
            if p.is_file()
        }
        if projection_source
        else None
    )
    hashes = load(output / "hashes-before.json")
    assert hashes == manifest(root)
    baseline = selected_facts(root)
    after_facts, results, descriptors, document_evidence, added = [], {}, [], [], []
    source_inventory = SourceRowInventory(**load(root / SOURCE / "source-inventory.json"))
    roles = {r.canonical_item_id: r.semantic_role for r in ITEM_CATALOG}
    for row in load(root / "artifacts/evidence/D-01/inventory.json"):
        year = row["year"]
        old = load(root / SOURCE / str(year) / "normalized-result.json")
        assert digest(root / row["pdf"]) == row["sha256"]
        if projection_source:
            result = load(projection_source / str(year) / "normalized-result.json")
            assert result["attempt_id"] == SNAPSHOT
            assert result["parent_snapshot_id"] == old["attempt_id"]
            records = result["records"]
        else:
            records = []
            for record in old["records"]:
                number = record["source"]["page"]["page"]
                records.extend(
                    run_automated_pdf(
                        root / row["pdf"],
                        symbol=record["source"]["page"]["symbol"],
                        year=record["source"]["page"]["year"],
                        pages=[number],
                        cached_records={number: record},
                        source_inventories={number: source_inventory}
                        if year == 2024 and number == 9
                        else None,
                    )
                )
        assert [r["response"] for r in records] == [r["response"] for r in old["records"]]
        for r, prior in zip(records, old["records"], strict=True):
            assert r.get("raw_corrections") == prior.get("raw_corrections")
            assert r.get("structure_corrections") == prior.get("structure_corrections")
        quality = assess_evidence_for_task(evidence_from_automated_records(records))
        result = dict(
            deepcopy(old),
            attempt_id=SNAPSHOT,
            parent_snapshot_id=old["attempt_id"],
            records=records,
            quality=quality.model_dump(mode="json"),
            mapping_version="financial-item-mapping-v2",
        )
        results[year] = result
        facts = facts_from_persisted_result(
            result, company_id=old["metadata_binding"]["company_id"]
        )
        old_index = {f.local_observation_id: f for f in baseline[year]}
        assert len(facts) == len(old_index)
        for f in facts:
            f.semantic_role = roles.get(f.canonical_item_id)
            prior = old_index[f.local_observation_id]
            assert f.value == prior.value
            assert f.context.model_copy(update={"mapped_item_code": None}) == (
                prior.context.model_copy(update={"mapped_item_code": None})
            )
            assert [s.reference for s in f.sources] == [s.reference for s in prior.sources]
            if prior.canonical_item_id:
                assert f.canonical_item_id == prior.canonical_item_id
                if all(
                    q.decision not in {"insufficient", "conflicted"} for q in prior.quality_context
                ):
                    assert all(
                        q.decision not in {"insufficient", "conflicted"} for q in f.quality_context
                    ), f.observation_identity()
            elif f.canonical_item_id:
                added.append(
                    dict(
                        year=year,
                        before=prior.observation_identity().model_dump(),
                        after=f.model_dump(mode="json"),
                    )
                )
        after_facts.extend(facts)
        evidence = evidence_from_persisted_result(result)
        document_evidence.extend(evidence)
        descriptors.append(
            SnapshotDescriptor(
                document_id=old["document_id"],
                pdf_sha256=row["sha256"],
                snapshot_id=SNAPSHOT,
                parent_snapshot_id=old["attempt_id"],
                origin="normalized_projection",
            )
        )
        folder = (projection_source or output) / str(year)
        if not projection_source:
            folder.mkdir(exist_ok=True)
            save(folder / "normalized-result.json", result)
            for f in facts:
                persist(CanonicalFactRepository(folder / "canonical"), f)
            for e in evidence:
                persist(DocumentEvidenceRepository(folder / "document-evidence"), e)
        assert (
            CanonicalFactRepository(folder / "canonical").list_by_document(
                old["document_id"], SNAPSHOT
            )
            == facts
        )
        assert (
            DocumentEvidenceRepository(folder / "document-evidence").list_by_document(
                old["document_id"], SNAPSHOT
            )
            == evidence
        )
        print(f"Projection {year}: {len(facts)} slots, exact restart", flush=True)
    # Explicit new controlled readings, only the seven rows actually visually reviewed.
    readings = {
        (2023, "100"): (5, "216.373.509.875", "A - TÀI SẢN NGẮN HẠN"),
        (2023, "200"): (5, "82.983.235.082", "B - TÀI SẢN DÀI HẠN"),
        (2023, "270"): (5, "299.356.744.957", "TỔNG CỘNG TÀI SẢN"),
        (2023, "300"): (6, "192.158.253.057", "C - NỢ PHẢI TRẢ"),
        (2023, "400"): (6, "107.198.491.900", "D - VỐN CHỦ SỞ HỮU"),
        (2023, "440"): (6, "299.356.744.957", "TỔNG CỘNG NGUỒN VỐN"),
        (2024, "310"): (8, "183.476.510.255", "I. Nợ ngắn hạn"),
    }
    reviews = []
    for (year, code), (number, raw_value, label) in readings.items():
        result = results[year]
        f = next(
            f
            for f in after_facts
            if f.document_id == result["document_id"]
            and f.source_item_code == code
            and f.context.statement_type == "B01"
            and f.context.period == f"{year}-12-31"
        )
        record = next(r for r in result["records"] if r["source"]["page"]["page"] == number)
        reference = f"artifacts/evidence/D-02/{year}-{number}.png"
        reviews.append(
            bind_source_review(
                f,
                dict(
                    observation=f.observation_identity(),
                    pdf_sha256=f.document_id.removeprefix("sha256:"),
                    pdf_page=number,
                    review_reference=reference,
                    review_image_sha256=digest(root / reference),
                    method="controlled_original_pdf_visual_read",
                    level="value_row_verified",
                    raw_value=raw_value,
                    raw_label=label,
                    raw_header=f"31/12/{year}",
                    period=f"{year}-12-31",
                    statement_type="B01",
                ),
                extraction_payload(record),
            )
        )
    validations = []
    for year, result in results.items():
        descriptor = next(d for d in descriptors if d.document_id == result["document_id"])
        for period in (f"{year}-12-31", f"{year}-01-01", str(year), str(year - 1)):
            checks = evaluate_source_validations(
                descriptor, after_facts, period=period, source_reviews=reviews
            )
            # Keep only the stock or flow rules belonging to this selector.
            checks = [c for c in checks if (c.rule_id.startswith("b01") == ("-" in period))]
            validations.extend(dict(filing=year, **c.model_dump(mode="json")) for c in checks)
    if projection_source and (projection_source / "summary.json").is_file():
        # Accepted inputs are hash-identical; these pure catalog checks were already run.
        regression = load(projection_source / "summary.json")["regression"]
        assert regression["baseline_ready"] == 15 and regression["recovery_ready"] == 3
        assert regression["queries_exact"] == 29 and regression["eligible"] == 0
    else:
        regression = accepted_regressions(root)
    new_queries = projection_queries(root, after_facts, document_evidence, results)
    old_descriptors = [SnapshotDescriptor(**d) for d in load(root / SOURCE / "snapshots.json")]
    old_facts = [f for fs in baseline.values() for f in fs]
    catalog = SnapshotCatalog(
        old_descriptors + descriptors,
        old_facts + after_facts,
        document_evidence,
        source_reviews=reviews,
    )
    for desc in descriptors:
        assert catalog.select(desc.document_id).status == "ambiguous"
        selected = catalog.select(desc.document_id, desc.snapshot_id)
        assert selected.status == "selected"
        assert selected.candidates[0].preparation_ready_metrics == 0
    after_qa09 = qa09(
        [f for f in after_facts if f.document_id == results[2024]["document_id"]], SNAPSHOT
    )
    qa15 = [
        c
        for c in validations
        if c["filing"] == 2023
        and c["period"] == "2023-12-31"
        and c["rule_id"] in {"b01.balance_identity", "b01.assets_liabilities_equity"}
    ]
    assert after_qa09["status"] == "found"
    assert all(c["status"] == "consistent" and c["check"]["difference"] == "0" for c in qa15)
    assert manifest(root) == hashes
    if projection_source:
        assert projection_hashes == {
            p.relative_to(projection_source).as_posix(): digest(p)
            for p in projection_source.rglob("*")
            if p.is_file()
        }
        save(output / "projection-hashes.json", projection_hashes)
    summary = dict(
        snapshot=SNAPSHOT,
        parent="D-05/corrected-v1",
        observations=len(after_facts),
        new_canonical_items=8,
        added_mapped_slots=len(added),
        added_numeric_slots=sum(a["after"]["value"]["normalized_value"] is not None for a in added),
        added_quality_blocked_slots=sum(
            any(
                q["decision"] in {"insufficient", "conflicted"}
                for q in a["after"]["quality_context"]
            )
            for a in added
        ),
        mapped_before=sum(bool(f.canonical_item_id) for f in old_facts),
        mapped_after=sum(bool(f.canonical_item_id) for f in after_facts),
        unmapped_after=sum(not f.canonical_item_id for f in after_facts),
        unmapped_statement_code_pairs=len(
            {
                (f.context.statement_type, f.source_item_code)
                for f in after_facts
                if not f.canonical_item_id
            }
        ),
        validation_statuses=dict(Counter(c["status"] for c in validations)),
        evaluated_rules=len(
            {
                c["rule_id"]
                for c in validations
                if c["check"] and c["check"]["difference"] is not None
            }
        ),
        projection_queries=len(new_queries),
        projection_query_statuses=dict(Counter(r["result"]["status"] for r in new_queries)),
        source_reviews=len(reviews),
        d05_corrected_slots_preserved=len(after_facts),
        eps_per_share_slots_preserved=sum(f.value.unit == "VND/share" for f in after_facts),
        raw_corrections_preserved=sum(
            len(r.get("raw_corrections", []))
            for result in results.values()
            for r in result["records"]
        ),
        terminal_coverage=next(
            r for r in results[2024]["records"] if r["source"]["page"]["page"] == 9
        )["extraction"]["completeness"]["status"],
        regression=regression,
        input_hashes_unchanged=len(hashes),
        projection_reference=(projection_source or output).relative_to(root).as_posix()
        if (projection_source or output).is_absolute()
        else (projection_source or output).as_posix(),
        gateway_calls=0,
        financial_fact_verified=False,
    )
    for name, value in (
        ("summary.json", summary),
        ("coverage-after.json", coverage(after_facts)),
        ("added-mappings.json", added),
        ("validation.json", validations),
        ("retrieval-after.json", new_queries),
        ("qa-after.json", dict(qa09=after_qa09, qa15=qa15)),
        (
            "unmapped.json",
            [f.model_dump(mode="json") for f in after_facts if not f.canonical_item_id],
        ),
        ("source-reviews.json", [r.model_dump(mode="json") for r in reviews]),
        ("snapshots.json", [d.model_dump(mode="json") for d in old_descriptors + descriptors]),
        ("hashes-after.json", manifest(root)),
    ):
        save(output / name, value)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-06"))
    parser.add_argument("--before", action="store_true")
    parser.add_argument("--from-projection", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.before:
        before(root, args.output)
    else:
        evaluate(root, args.output, projection_source=args.from_projection)
