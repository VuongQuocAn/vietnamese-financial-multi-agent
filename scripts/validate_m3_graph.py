"""Read-only BBS_2025 graph review; không chạy extraction/LLM hoặc sửa nguồn."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    EvidenceGraph,
    GraphEdge,
    associate_fact,
    build_graph,
    facts_from_persisted_result,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.document_evidence import DocumentEvidence
from vietnamese_financial_multi_agent.evidence.graph import graph_id, record_sources


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer_value(payload, pointer):
    for key in pointer.lstrip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        payload = payload[int(key)] if isinstance(payload, list) else payload[key]
    return payload


def controls(fact, evidence):
    """Cố ý sửa copies thật, không sửa persisted evidence."""
    output = []
    cases = {
        "document": "source_document_id_mismatch",
        "snapshot": "source_snapshot_id_mismatch",
        "dangling": "dangling_node_reference",
        "domain": "edge_domain_mismatch",
        "page_only": "exact_association_not_established",
        "duplicate_node": "duplicate_node_identity",
        "duplicate_edge": "duplicate_edge_identity",
        "missing_source": "missing_source",
        "cell": "unsupported_cell_provenance",
        "unknown_level": "unknown_provenance_level",
    }
    for case, expected in cases.items():
        f, e = fact.model_copy(deep=True), evidence.model_copy(deep=True)
        if case in {"document", "snapshot"}:
            setattr(f.sources[0], f"{case}_id", "negative-control")
        if case == "page_only":
            for source in [*record_sources(f), *record_sources(e)]:
                ref = source.reference
                ref.source_pointer = None
                for field in ("element_id", "table_id", "cell_id", "line_id", "observed_bbox"):
                    setattr(ref.anchor, field, None)
        if case == "missing_source":
            f.sources = []
        if case in {"cell", "unknown_level"}:
            f.sources[0].reference.provenance_level = "cell" if case == "cell" else "unknown"
        graph = build_graph([f], [e])
        if case == "dangling":
            graph.edges[0].target = "missing"
        if case == "domain":
            graph.edges[0].source, graph.edges[0].target = (
                graph.edges[0].target,
                graph.edges[0].source,
            )
        if case == "duplicate_node":
            graph.nodes.append(graph.nodes[0].model_copy(deep=True))
        if case == "duplicate_edge":
            graph.edges.append(graph.edges[0].model_copy(deep=True))
        if case == "page_only":
            assert not any(edge.relation == "associated_with" for edge in graph.edges)
            ids = [n.node_id for n in graph.nodes if n.kind in {"source_fact", "text", "table"}]
            graph.edges.append(
                GraphEdge(
                    edge_id=graph_id("associated_with", ids),
                    relation="associated_with",
                    source=ids[0],
                    target=ids[1],
                )
            )
        result = validate_graph(graph, [f], [e])
        matches = [a for a in result.nodes + result.edges if expected in a.reasons]
        status = "unresolved" if case in {"page_only", "missing_source"} else "invalid"
        assert matches and all(a.status == status for a in matches), case
        output.append(dict(case=case, reason=expected, status=status, detected=len(matches)))
    return output


def validate(root, output):
    # Scope chốt trước: cả hai W07 attempts và bốn M3-03 final repositories.
    output.mkdir(parents=True, exist_ok=False)
    previous = root / "artifacts/evidence/M3-03-real-validation/final"
    baseline = json.loads((previous / "validation.json").read_text(encoding="utf-8"))
    hashes = {relative: digest(root / relative) for relative in baseline["hashes"]}
    evidence, facts, groups, source_controls = [], [], [], {}
    adapter = TypeAdapter(list[DocumentEvidence])
    for name in ("m1-existing", "m1-native", "w07-storage", "w07-fresh-storage"):
        path = previous / name / "document-evidence.json"
        hashes[path.relative_to(root).as_posix()] = digest(path)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        records = adapter.validate_json(json.dumps(snapshot["records"]))
        quarantine = adapter.validate_json(json.dumps(snapshot["quarantine"]))
        evidence.extend([*records, *quarantine])
        groups.append(dict(group=name, indexed=len(records), quarantine=len(quarantine)))
    # Canonical JSON smoke cũ không còn trên đĩa: public M3-02 adapter trên
    # quality persisted, ghi repo mới rồi restart/read ALL; không replay pipeline.
    for family in ("storage", "fresh-storage"):
        paths = sorted((root / f"artifacts/w07/{family}").rglob("result.json"))
        assert len(paths) == 1, "Selected scope changed; review scope explicitly"
        path = paths[0]
        hashes[path.relative_to(root).as_posix()] = digest(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        for record in raw["records"]:
            page = record["source"]["page"]
            source_controls[(raw["document_id"], raw["attempt_id"], page["page"])] = (
                page,
                record["response"]["output"]["payload"],
            )
        incoming = facts_from_persisted_result(raw)
        repo = CanonicalFactRepository(output / family)
        for f in incoming:
            repo.put(f)
        restarted = CanonicalFactRepository(repo.root)
        loaded = restarted.list_by_document(raw["document_id"], raw["attempt_id"])
        assert [f.model_dump_json() for f in loaded] == [f.model_dump_json() for f in incoming]
        quarantine = restarted.list_quarantine()
        facts.extend([*loaded, *quarantine])
        groups.append(
            dict(group=f"canonical-{family}", indexed=len(loaded), quarantine=len(quarantine))
        )
    graph = build_graph(facts, evidence)
    result = validate_graph(graph, facts, evidence)
    native_path = root / "artifacts/document-understanding/M1-16/native.json"
    native = json.loads(native_path.read_text(encoding="utf-8"))
    for page in native["pages"]:
        identity = page["identity"]
        source = root / f"artifacts/gemini-ingestion/M1-15/pdf/page-{identity['page']}.json"
        payload = json.loads(source.read_text(encoding="utf-8"))["response"]["output"]["payload"]
        source_controls[
            (identity["source_ref"], native_path.relative_to(root).as_posix(), identity["page"])
        ] = (identity, payload)
    selector_checks = 0
    for node in graph.nodes:
        if node.kind != "anchor":
            continue
        anchor = node.anchor
        ref = anchor.reference
        page, payload = source_controls[
            (anchor.document_id, anchor.snapshot_id, ref.anchor.page.page)
        ]
        assert page == ref.anchor.page.model_dump(mode="json")
        assert ref.source_pointer is not None
        pointer_value(payload, ref.source_pointer)
        selector_checks += 1
    atomic_json(output / "graph.json", graph.model_dump(mode="json"))
    restored = EvidenceGraph.model_validate_json(
        (output / "graph.json").read_text(encoding="utf-8")
    )
    assert restored == graph
    atomic_json(output / "validation.json", result.model_dump(mode="json"))
    associations = [e for e in graph.edges if e.relation == "associated_with"]
    f_by_id = {graph_id("source_fact", f.observation_identity().model_dump()): f for f in facts}
    e_by_id = {
        graph_id(e.kind, e.evidence_identity().model_dump()): e
        for e in evidence
        if e.evidence_identity()
    }
    exact_sources = []
    for edge in associations:
        match = associate_fact(f_by_id[edge.source], e_by_id[edge.target])
        assert match is not None
        exact_sources.extend(match.matching_sources)
    samples = []
    for page, codes in (
        (5, ["110", "130", "270"]),
        (6, ["300", "410", "440"]),
        (7, ["10", "20", "60"]),
        (8, ["20", "50", "70"]),
        (14, []),
        (15, []),
    ):
        selected = {
            nid: f
            for nid, f in f_by_id.items()
            if any(s.reference and s.reference.anchor.page.page == page for s in f.sources)
            and f.source_item_code in codes
        }
        links = [e for e in associations if e.source in selected]
        samples.append(
            dict(
                page=page,
                codes=codes,
                observations=len(selected),
                associations=len(links),
                facts_associated=len({e.source for e in links}),
                relationship_status="UNRESOLVED" if selected else "NOT VERIFIED",
                pdf_grounded_correctness="NOT VERIFIED in M3-04; prior M3-03 sample only",
            )
        )
    first = associations[0]
    negatives = controls(f_by_id[first.source], e_by_id[first.target])
    same_page_rejected = 0
    pairs = {(e.source, e.target) for e in associations}
    for fid, f in f_by_id.items():
        for eid, e in e_by_id.items():
            if (f.document_id, f.snapshot_id) != (e.document_id, e.snapshot_id):
                continue
            if not {s.reference.anchor.page.page for s in f.sources if s.reference}.intersection(
                s.reference.anchor.page.page for s in record_sources(e) if s.reference
            ):
                continue
            if associate_fact(f, e) is None:
                assert (fid, eid) not in pairs
                same_page_rejected += 1
    assert all(digest(root / relative) == before for relative, before in hashes.items())
    report = dict(
        groups=groups,
        facts=len(facts),
        evidence=len(evidence),
        nodes=dict(Counter(n.kind for n in graph.nodes)),
        edges=dict(Counter(e.relation for e in graph.edges)),
        node_status=dict(Counter(a.status for a in result.nodes)),
        edge_status=dict(Counter(a.status for a in result.edges)),
        edge_reasons=dict(Counter(r for a in result.edges for r in a.reasons)),
        input_reasons=dict(Counter(r for a in result.inputs for r in a.reasons)),
        orphans=len(result.orphan_nodes),
        associated_facts=len({e.source for e in associations}),
        matching_source_levels=dict(Counter(s.reference.provenance_level for s in exact_sources)),
        anchor_levels=dict(
            Counter(n.anchor.reference.provenance_level for n in graph.nodes if n.kind == "anchor")
        ),
        same_page_without_exact_association_rejected=same_page_rejected,
        samples=samples,
        negative_controls=negatives,
        hashes=hashes,
        source_files_unchanged=len(hashes),
        collisions=sum(
            "collision" in r or "duplicate" in r
            for a in result.nodes + result.inputs
            for r in a.reasons
        ),
        source_binding_conflicts=sum("mismatch" in r for a in result.nodes for r in a.reasons),
        graph_restart_exact=True,
        source_selector_checks=selector_checks,
        financial_fact_verified=False,
    )
    atomic_json(output / "report.json", report)
    print(
        json.dumps({k: v for k, v in report.items() if k != "hashes"}, ensure_ascii=False, indent=2)
    )
    assert not any(a.status == "invalid" for a in result.nodes + result.edges + result.inputs)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(args.root.resolve(), args.output.resolve())
