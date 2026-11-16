"""JSON source bindings for the existing SnapshotCatalog; no PDF review claims."""

import hashlib
import json
import re
from pathlib import Path

from ..accounting.automated_extraction import parse_vietnamese_number
from .contracts import is_json_reference


def resolve_pointer(value, pointer):
    for key in pointer.strip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def json_snapshot_issues(catalog, descriptor):
    descriptors = [
        d
        for d in catalog.descriptors
        if (d.document_id, d.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
    ]
    if len(descriptors) != 1 or descriptors[0] != descriptor:
        return ["json_snapshot_ambiguous"]
    if (
        not re.fullmatch(r"[0-9a-f]{64}", descriptor.json_sha256 or "")
        or descriptor.document_id != "json:sha256:" + (descriptor.json_sha256 or "")
        or not descriptor.json_pages
        or descriptor.parent_snapshot_id is not None
    ):
        return ["json_snapshot_identity_invalid"]
    sources = getattr(catalog, "json_sources", {})
    if any(digest not in sources for digest in descriptor.json_pages.values()):
        return ["json_original_sources_unavailable"]
    return []


def json_fact_bound(catalog, fact):
    """Replay JSON value/selector binding; never call this a PDF source review."""
    selected = [
        d
        for d in catalog.descriptors
        if (d.document_id, d.snapshot_id) == (fact.document_id, fact.snapshot_id)
        and d.source_kind == "json"
    ]
    if len(selected) != 1 or json_snapshot_issues(catalog, selected[0]) or not fact.sources:
        return False
    identity = fact.observation_identity()
    if (
        identity is None
        or catalog.json_fact_pins.get(identity.model_dump_json())
        != hashlib.sha256(fact.model_dump_json().encode()).hexdigest()
    ):
        return False
    if not all(
        (
            fact.company_id,
            fact.canonical_item_id,
            fact.context.period,
            fact.context.period_type,
            fact.value.unit,
            fact.context.currency,
            fact.context.scale,
            fact.value.status == "resolved",
        )
    ):
        return False
    if fact.context.currency != fact.value.unit or fact.context.scale <= 0:
        return False
    if not fact.quality_context or any(
        q.decision not in {"usable", "usable_with_caveat"} for q in fact.quality_context
    ):
        return False
    descriptor = selected[0]
    try:
        for source in fact.sources:
            ref = source.reference
            if (
                ref is None
                or not is_json_reference(ref)
                or (source.document_id, source.snapshot_id) != (fact.document_id, fact.snapshot_id)
            ):
                return False
            digest = descriptor.json_pages[ref.anchor.page.page]
            if ref.anchor.page.source_ref != "json:sha256:" + digest:
                return False
            resolve_pointer(catalog.json_sources[digest], ref.source_pointer)
        ref = fact.sources[0].reference
        raw = resolve_pointer(
            catalog.json_sources[descriptor.json_pages[ref.anchor.page.page]], ref.source_pointer
        )
        return (
            raw == fact.value.raw_value
            and parse_vietnamese_number(raw) == fact.value.normalized_value
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def load_json_catalog(root: Path, bundle: Path):
    """Load persisted artifacts and re-pin original JSON; no Gold or PDF needed."""
    from .document_repository import DocumentEvidenceRepository
    from .graph import EvidenceGraph, validate_graph
    from .refined_import import read_refined
    from .repository import CanonicalFactRepository
    from .snapshots import SnapshotCatalog, SnapshotDescriptor

    manifest = json.loads((bundle / "manifest.json").read_bytes())
    _, current = read_refined(root, manifest["document_alias"], manifest.get("projection_version"))
    if current != manifest:
        raise ValueError("json_import_manifest_changed")
    doc, snapshot = manifest["document_id"], manifest["snapshot_id"]
    facts = CanonicalFactRepository(bundle).list_by_document(doc, snapshot)
    evidence = DocumentEvidenceRepository(bundle).list_by_document(doc, snapshot)
    graph = EvidenceGraph.model_validate_json((bundle / "graph.json").read_bytes())
    validation = validate_graph(graph, facts, evidence)
    if any(a.status != "valid" for a in [*validation.nodes, *validation.edges, *validation.inputs]):
        raise ValueError("json_import_graph_invalid")
    descriptor = SnapshotDescriptor(
        document_id=doc,
        snapshot_id=snapshot,
        source_kind="json",
        pdf_sha256=None,
        json_sha256=doc.rsplit(":", 1)[1],
        json_pages={p["page"]: p["sha256"] for p in manifest["pages"]},
        origin="normalized_projection",
    )
    return SnapshotCatalog(
        [descriptor],
        facts=facts,
        evidence=evidence,
        graph=graph,
        json_sources={p["sha256"]: (root / p["path"]).read_bytes() for p in manifest["pages"]},
    )


def load_json_corpus_document(root: Path, corpus: Path, document_alias: str):
    """Select one explicit filing from the import index; reuse the existing loader."""
    index = json.loads((corpus / "catalog-index.json").read_bytes())
    if index["version"] != "vifinbench-json-corpus-v1":
        raise ValueError("unsupported_json_corpus_index")
    entry = index["documents"][document_alias]
    if not re.fullmatch(r"[A-Z0-9]+_20\d{2}", document_alias) or entry["bundle"] != document_alias:
        raise ValueError("invalid_json_corpus_bundle")
    bundle = (corpus / entry["bundle"]).resolve()
    if not bundle.is_relative_to(corpus.resolve()):
        raise ValueError("json_corpus_bundle_outside_root")
    catalog = load_json_catalog(root, bundle)
    descriptor = catalog.descriptors[0]
    if (descriptor.document_id, descriptor.snapshot_id) != (
        entry["document_id"],
        entry["snapshot_id"],
    ):
        raise ValueError("json_corpus_index_identity_mismatch")
    return catalog
