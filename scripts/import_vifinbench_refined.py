"""VFB-IMPORT-01: real JSON import/restart/retrieval smoke; zero model calls."""

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.evidence.graph import (
    EvidenceGraph,
    build_graph,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.refined_import import (
    import_refined_document,
    read_refined,
    sha256,
)
from vietnamese_financial_multi_agent.evidence.repository import CanonicalFactRepository
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceQuery, EvidenceRetrieval
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)

PILOT_DOCUMENTS = ("BBS_2025", "BED_2023", "AME_2024", "BCC_2025")


def check_fidelity(root, manifest, facts, evidence):
    """Resolve every imported pointer against the pinned original JSON bytes."""
    pages = {}
    for pin in manifest["pages"]:
        data = (root / pin["path"]).read_bytes()
        assert sha256(data) == pin["sha256"], "source_hash_changed"
        pages[pin["page"]] = json.loads(data)
    checked = Counter()
    for record in evidence:
        if record.kind == "table":
            original = record.source_metadata["original_table"]
            actual = pages[record.sources[0].reference.anchor.page.page]["blocks"][
                record.source_metadata["block_index"]
            ]["table"]
            assert original == actual
            checked["tables"] += 1
            assert [c.text for c in record.structure.cells] == [
                c for row in [original["columns"], *original["rows"]] for c in row
            ]
            sources = record.member_sources
            values = [c.text for c in record.structure.cells]
        else:
            sources, values = record.sources, [record.raw_text]
        for source, expected in zip(sources, values, strict=True):
            ref = source.reference
            value = pages[ref.anchor.page.page]
            for key in ref.source_pointer.strip("/").split("/"):
                value = value[int(key)] if isinstance(value, list) else value[key]
            assert value == expected
            checked["cell_or_text_pointers"] += 1
    for fact in facts:
        ref = fact.sources[0].reference
        value = pages[ref.anchor.page.page]
        for key in ref.source_pointer.strip("/").split("/"):
            value = value[int(key)] if isinstance(value, list) else value[key]
        assert value == fact.value.raw_value
        checked["fact_value_pointers"] += 1
    pins = {p["page"]: p for p in manifest["pages"]}
    for record in [*facts, *evidence]:
        for source in [*record.sources, *getattr(record, "member_sources", [])]:
            ref = source.reference
            page = ref.anchor.page
            assert page.source_ref == "json:sha256:" + pins[page.page]["sha256"]
            assert page.image == "" and ref.anchor.status == "uncertain"
            value = pages[page.page]
            for key in ref.source_pointer.strip("/").split("/"):
                value = value[int(key)] if isinstance(value, list) else value[key]
            checked["all_source_pointers"] += 1
    return dict(checked)


def run_pilot(root, output, documents=PILOT_DOCUMENTS):
    root, output = root.resolve(), output.resolve()
    if root == output or root in output.parents or output in root.parents:
        raise ValueError("output_must_be_separate_from_source")
    # A new run never overwrites earlier source/evidence/checkpoint artifacts.
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    for alias in documents:
        started = perf_counter()
        manifest, facts, evidence, summary = import_refined_document(root, alias)
        target = output / alias
        target.mkdir()
        # One atomic write per repository snapshot; avoid quadratic per-record put
        # on a large table corpus. Reload through the existing repository APIs.
        atomic_json(
            target / "canonical-facts.json",
            dict(
                version="canonical_facts_v1",
                observations=[f.model_dump(mode="json") for f in facts],
                quarantine=[],
            ),
        )
        atomic_json(
            target / "document-evidence.json",
            dict(
                version="document_evidence_v1",
                records=[e.model_dump(mode="json") for e in evidence],
                quarantine=[],
            ),
        )
        doc, snapshot = manifest["document_id"], manifest["snapshot_id"]
        fact_repo, evidence_repo = (
            CanonicalFactRepository(target),
            DocumentEvidenceRepository(target),
        )
        restored_facts = fact_repo.list_by_document(doc, snapshot)
        restored_evidence = evidence_repo.list_by_document(doc, snapshot)
        assert restored_facts == facts and restored_evidence == evidence, "restart_payload_mismatch"
        if restored_facts:
            assert fact_repo.put(restored_facts[0]) == "idempotent"
        assert evidence_repo.put(restored_evidence[0]) == "idempotent"
        graph = build_graph(restored_facts, restored_evidence)
        atomic_json(target / "graph.json", graph.model_dump(mode="json"))
        graph = EvidenceGraph.model_validate_json((target / "graph.json").read_bytes())
        validation = validate_graph(graph, restored_facts, restored_evidence)
        statuses = Counter(
            a.status for a in [*validation.nodes, *validation.edges, *validation.inputs]
        )
        assert (
            not statuses["invalid"] and not statuses["unresolved"] and not validation.orphan_nodes
        )
        atomic_json(target / "graph-validation.json", validation.model_dump(mode="json"))
        api = EvidenceRetrieval(restored_facts, restored_evidence, graph=graph)
        probes = []
        for kind, candidates in [
            ("fact", restored_facts[:1]),
            ("text", [e for e in restored_evidence if e.kind == "text"][:1]),
            ("table", [e for e in restored_evidence if e.kind == "table"][:1]),
        ]:
            if not candidates:
                probes.append(dict(kind=kind, status="not_available_in_source"))
                continue
            record = candidates[0]
            result = (
                api.get_fact(record.observation_identity())
                if kind == "fact"
                else api.get_evidence(record.evidence_identity())
            )
            assert result.status in {"found", "conflicted"} and result.matches[0].record == record
            assert all(
                c.pdf_page is None and "json_source_not_pdf_verified" in c.limitations
                for c in result.matches[0].citations
            )
            probes.append(
                dict(kind=kind, status=result.status, response=result.model_dump(mode="json"))
            )
        assert api.find_facts(EvidenceQuery(document_id="wrong-document")).status == "not_found"
        assert (
            api.find_evidence(EvidenceQuery(document_id=doc, snapshot_id="wrong-snapshot")).status
            == "not_found"
        )
        # Exercise the existing Financial Tools boundary honestly: JSON imports
        # have no PDF SnapshotDescriptor and must not receive one with a fake hash.
        financial = FinancialRetrievalTools(
            SnapshotCatalog([], facts=restored_facts, evidence=restored_evidence, graph=graph)
        )
        financial_probe = financial.get_financial_fact(
            GetFinancialFactRequest(
                document_id=doc,
                snapshot_id=snapshot,
                local_observation_id=restored_facts[0].local_observation_id
                if restored_facts
                else "not-present-in-source",
            )
        )
        assert financial_probe.status != "found"
        atomic_json(
            target / "retrieval-probes.json",
            dict(probes=probes, financial_tools=financial_probe.model_dump(mode="json")),
        )
        summary.update(
            document_alias=alias,
            document_id=doc,
            snapshot_id=snapshot,
            graph_nodes=len(graph.nodes),
            graph_edges=len(graph.edges),
            graph_relations=dict(Counter(e.relation for e in graph.edges)),
            graph_status_counts=dict(statuses),
            orphan_nodes=len(validation.orphan_nodes),
            fidelity=check_fidelity(root, manifest, restored_facts, restored_evidence),
            restart_exact=True,
            retrieval={p["kind"]: p["status"] for p in probes},
            financial_tools_status=financial_probe.status,
            financial_tools_reasons=financial_probe.reasons,
            seconds=round(perf_counter() - started, 3),
        )
        atomic_json(target / "manifest.json", manifest)
        atomic_json(target / "summary.json", summary)
        summaries.append(summary)
        print(
            json.dumps({k: v for k, v in summary.items() if k != "tables"}, ensure_ascii=False),
            flush=True,
        )
    # Recheck all source hashes after the run, without relying on mtime.
    for summary in summaries:
        manifest = json.loads((output / summary["document_alias"] / "manifest.json").read_bytes())
        _, current = read_refined(root, summary["document_alias"])
        assert current == manifest, "source_manifest_changed"
    atomic_json(
        output / "summary.json",
        dict(documents=summaries, source_hashes_unchanged=True, model_calls=0),
    )
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("ViFinBench/refined"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/VFB-IMPORT-01/pilot-v1")
    )
    parser.add_argument("--documents", nargs="+", default=list(PILOT_DOCUMENTS))
    args = parser.parse_args()
    run_pilot(args.root, args.output, args.documents)
