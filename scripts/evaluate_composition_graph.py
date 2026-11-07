"""EF-01 real PDF graph inspection offline; chỉ đọc explicit approved inputs."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    DerivedMetric,
    EvidenceGraph,
    SnapshotCatalog,
)
from vietnamese_financial_multi_agent.evidence.composition import EvidenceComposition
from vietnamese_financial_multi_agent.evidence.composition_graph import (
    CompositionGraphView,
    validate_context_relations,
)
from vietnamese_financial_multi_agent.evidence.document_evidence import DocumentEvidence
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.evidence.graph import graph_id, validate_graph
from vietnamese_financial_multi_agent.evidence.source_reviews import SourceReview
from vietnamese_financial_multi_agent.tools.graph_retrieval import (
    GetGraphContextRequest,
    GraphRetrievalTools,
)

LABELS = ("BBS_2022", "BBS_2024", "BBS_2025", "BCC_2024", "BCC_2025")


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def bbs_catalog(root):
    # Reuse approved M4 loader; no Gateway/PDF extraction path.
    from evaluate_m4_05_qa import setup

    data, *_ = setup(root)
    return SnapshotCatalog(**data)


def bcc_catalog(root, label, descriptor):
    base = root / "artifacts/evidence/GEN-01"
    normalized, audit = base / "normalized-final" / label, base / "audit-final" / label
    return SnapshotCatalog(
        [descriptor],
        facts=TypeAdapter(list[CanonicalFinancialFact]).validate_json(
            (normalized / "facts.json").read_bytes()
        ),
        evidence=TypeAdapter(list[DocumentEvidence]).validate_json(
            (normalized / "evidence.json").read_bytes()
        ),
        metrics=TypeAdapter(list[DerivedMetric]).validate_json(
            (audit / "metrics.json").read_bytes()
        ),
        graph=EvidenceGraph.model_validate(read(audit / "graph.json")),
        source_reviews=TypeAdapter(list[SourceReview]).validate_json(
            (audit / "source-reviews.json").read_bytes()
        ),
    )


def evaluate_m6_boundary(input_path, output):
    from evaluate_document_qa import build_pipeline
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.verification.document_verification import (
        DocumentVerificationHistory,
    )

    pipeline = build_pipeline(input_path, output / "ledger")
    answer = pipeline.run(
        FinancialQARequest(
            question="BBS 2025 ghi “thuế thu nhập lại phải trả” ở đâu?", force_refresh=True
        )
    )
    assert answer.trace.native_decisions == {"INVESTIGATE": 1}
    assert not answer.newly_accepted_claims and not answer.citations
    previous = read(input_path / "closure/before/negative-qa.json")
    admission = pipeline.repository.admit(
        DocumentVerificationHistory.model_validate(previous["histories"][0])
    )
    assert admission.status == "rejected"
    save(
        output / "source-quality-gate.json",
        dict(
            response=answer.model_dump(mode="json"),
            old_proof_admission=admission.model_dump(mode="json"),
            graph_is_not_verification_authority=True,
        ),
    )
    print(
        "PASS: real OCR defect INVESTIGATE; zero claims/citations; old proof rejected", flush=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/evidence/EXT-01"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/EF-01/final"))
    parser.add_argument(
        "--m6-only", action="store_true", help="Replay known OCR defect offline, separate ledger"
    )
    args = parser.parse_args()
    if args.m6_only:
        evaluate_m6_boundary(args.input, args.output / "m6-boundary")
        return
    root = Path.cwd()
    args.output.mkdir(parents=True, exist_ok=True)
    repo = DocumentEvidenceRepository(args.input / "repository")
    bbs = bbs_catalog(root)
    inventory, projections, cases, controls = {}, {}, [], []
    protected = [args.input / "repository/document-evidence.json"]
    for label in LABELS:
        protected.append(args.input / label / "composition.json")
    # Hash selected accepted financial inputs only, never dataset-wide.
    protected += [root / "artifacts/evidence/D-04-review/graph.json"]
    for label in ("BCC_2024", "BCC_2025"):
        for name in ("graph.json", "metrics.json", "source-reviews.json"):
            protected.append(root / "artifacts/evidence/GEN-01/audit-final" / label / name)

    def hashes():
        return {
            str(p.relative_to(root) if p.is_absolute() else p): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in protected
        }

    before = hashes()
    for label in LABELS:
        manifest = EvidenceComposition.model_validate(read(args.input / label / "composition.json"))
        catalog = (
            bbs
            if label.startswith("BBS")
            else bcc_catalog(root, label, manifest.financial_snapshot)
        )
        start = perf_counter()
        projection = CompositionGraphView(
            manifest,
            repo,
            catalog,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
        elapsed = perf_counter() - start
        view = projection.view
        rebuilt = CompositionGraphView(
            manifest,
            repo,
            catalog,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
        assert view == rebuilt.view, label
        assert all(n in view.graph.nodes for n in projection.financial.graph.nodes)
        assert all(e in view.graph.edges for e in projection.financial.graph.edges)
        counts = Counter(n.kind for n in view.graph.nodes)
        edges = Counter(e.relation for e in view.graph.edges)
        inventory[label] = dict(
            nodes=dict(counts),
            edges=dict(edges),
            approved_document_records=len(projection.documents.evidence),
            contextual_relations=len(view.contextual_relations),
            validation=dict(
                Counter(a.status for a in [*view.validation.nodes, *view.validation.edges])
            ),
            contextual_validation=dict(Counter(a.status for a in view.contextual_validation)),
            orphan_nodes=view.validation.orphan_nodes,
            build_seconds=elapsed,
            deterministic_rebuild=True,
            exact_associations=edges["associated_with"],
            unresolved_rejected_relations=0,
            relation_gaps=[
                "B09 semantic link requires explicit item/section selector; no keyword edge"
            ],
            original_snapshots=sorted({e.snapshot_id for e in projection.documents.evidence}),
        )
        save(args.output / label / "graph-view.json", view.model_dump(mode="json"))
        projections[label] = projection
        print(label, json.dumps(inventory[label], ensure_ascii=True), flush=True)

    def inspect(label, title, nid, expected, check, *, depth=2, relations=None):
        projection = projections[label]
        request = GetGraphContextRequest(
            document_id=projection.view.document_id,
            composition_id=projection.view.composition_id,
            node_id=nid,
            depth=depth,
            limit=50,
            **({"relations": relations} if relations is not None else {}),
        )
        tools = GraphRetrievalTools(projection)
        start = perf_counter()
        result = tools.get_graph_context(request)
        elapsed = perf_counter() - start
        assert check(result), title
        case = dict(
            id=f"G{len(cases) + 1:02}",
            pdf=label,
            case=title,
            expected=expected,
            passed=True,
            latency_seconds=elapsed,
            actual=result.model_dump(mode="json"),
        )
        cases.append(case)
        save(args.output / "paths" / f"{case['id']}.json", case)

    for label in LABELS:
        p = projections[label]
        fact = next(f for f in p.financial.facts if f.canonical_item_id == "b02.net_revenue")
        nid = graph_id("source_fact", fact.observation_identity().model_dump())
        inspect(
            label,
            "Revenue → original source",
            nid,
            "Original anchor; no causal claim",
            lambda r: (
                r.status == "found"
                and any(e.edge.relation == "from_source" for e in r.edges)
                and all(n.evidence.matches for n in [r.start, *r.matches])
            ),
        )
    p = projections["BBS_2025"]
    metric = next(m for m in p.financial.metrics if m.definition.name == "gross_margin")
    inspect(
        "BBS_2025",
        "Gross margin → operands → anchors",
        metric.metric_id,
        "Accepted used_in roles; preserve metric and reviewed lineage",
        lambda r: (
            r.status == "found"
            and any(e.edge.relation == "used_in" for e in r.edges)
            and any(n.node.kind == "anchor" for n in r.matches)
        ),
    )
    for label, page, phrase, title in [
        ("BBS_2025", 14, "nhân viên quản lý", "B09 key personnel, source only"),
        ("BBS_2025", 13, "thuế thu nhập", "Known OCR defect retains pdf_review"),
        ("BCC_2025", 9, "", "Separate filing document evidence"),
        ("BCC_2024", 13, "", "Consolidated filing document evidence"),
        ("BBS_2025", 7, "Kế toán trưởng", "Signer layout remains source evidence only"),
    ]:
        p = projections[label]
        row = next(
            e
            for e in p.documents.evidence
            if e.kind == "text"
            and e.sources[0].reference.anchor.page.page == page
            and phrase.lower() in (e.raw_text or "").lower()
        )
        nid = graph_id(row.kind, row.evidence_identity().model_dump())
        inspect(
            label,
            title,
            nid,
            "Original snapshot and citation; no semantic promotion",
            lambda r, page=page, label=label: (
                r.status == "found"
                and bool(r.start.evidence.matches)
                and any(n.node.kind == "anchor" for n in r.matches)
                and (
                    page != 13
                    or label != "BBS_2025"
                    or any(c.startswith("pdf_review:") for c in r.start.caveats)
                )
            ),
            depth=1,
        )
    p = projections["BBS_2025"]
    edge = next(iter(p.view.contextual_relations))
    inspect(
        "BBS_2025",
        "Cross-snapshot extraction selector",
        edge.source,
        "Contextual only; original distinct snapshots",
        lambda r: any(e.verification == "contextual_only" for e in r.edges),
        depth=1,
        relations=["same_extraction_context"],
    )

    def control(name, passed, reason):
        assert passed, name
        controls.append(dict(case=name, passed=True, reason=reason))

    tools = GraphRetrievalTools(p)
    request = GetGraphContextRequest(
        document_id=p.view.document_id, composition_id=p.view.composition_id, node_id=edge.source
    )
    for label in ("BBS_2024", "BCC_2025"):
        foreign = projections[label].view.graph.nodes[0].node_id
        control(
            "wrong_filing_" + label,
            tools.get_graph_context(request.model_copy(update={"node_id": foreign})).status
            == "not_found",
            "no cross-document fallback",
        )
    control(
        "unbound_composition",
        tools.get_graph_context(request.model_copy(update={"composition_id": "unbound"})).status
        == "unavailable",
        "explicit selection required",
    )
    control(
        "legacy_ocr",
        tools.get_graph_context(request.model_copy(update={"node_id": "legacy-ocr"})).status
        == "not_found",
        "outside pins",
    )
    for case in ("pointer", "page", "duplicate", "endpoint"):
        view = p.view.model_copy(deep=True)
        relation = view.contextual_relations[0]
        if case == "pointer":
            relation.target_anchor.reference.source_pointer = "/not-original"
        elif case == "page":
            relation.target_anchor.reference.anchor.page.page += 1
        elif case == "duplicate":
            view.contextual_relations.append(relation.model_copy(deep=True))
        else:
            relation.target = "missing"
        results = validate_context_relations(
            view, p.manifest, p.financial.facts, p.documents.evidence
        )
        control(
            case,
            any(r.status == "invalid" for r in results),
            "reject changed relation basis/endpoints",
        )
    for case in ("same_page", "independent_request"):
        facts = [f.model_copy(deep=True) for f in p.financial.facts]
        for f in facts:
            if case == "same_page":
                for a in f.sources:
                    a.reference.source_pointer = "/unrelated-element"
            else:
                f.source_metadata["request_id"] = "different-extraction"
        results = validate_context_relations(p.view, p.manifest, facts, p.documents.evidence)
        control(
            case,
            all(r.status == "invalid" for r in results),
            "same PDF/page never proves semantic support",
        )
    control(
        "signer_role",
        not any("claim" in n.kind for n in p.view.graph.nodes),
        "no role/person ACCEPT edge or claim node",
    )
    # Existing M3 validation independently catches duplicate and missing v1 endpoints.
    for case in ("duplicate_v1", "missing_v1_endpoint"):
        graph = p.view.graph.model_copy(deep=True)
        if case == "duplicate_v1":
            graph.edges.append(graph.edges[0].model_copy(deep=True))
        else:
            graph.edges[0].target = "missing"
        checked = validate_graph(graph, p.financial.facts, p.evidence, p.financial.metrics)
        control(
            case,
            any(r.status == "invalid" for r in checked.edges),
            "existing validate_graph authority",
        )

    save(args.output / "inventory.json", inventory)
    save(args.output / "negative-controls.json", controls)
    save(args.output / "cases.json", cases)
    save(
        args.output / "integrity.json",
        dict(before=before, after=hashes(), unchanged=before == hashes()),
    )
    assert before == hashes()
    save(
        args.output / "summary.json",
        dict(
            real_cases=len(cases),
            negative_controls=len(controls),
            approved_records=sum(x["approved_document_records"] for x in inventory.values()),
            wrong_document_snapshot_leakage=0,
            gemini_ocr_calls=0,
        ),
    )
    print(f"PASS: {len(cases)} real cases; {len(controls)} negative controls", flush=True)


if __name__ == "__main__":
    main()
