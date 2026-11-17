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
    raw_sources = getattr(catalog, "json_source_bytes", {})
    if any(
        digest not in raw_sources
        or hashlib.sha256(raw_sources[digest]).hexdigest() != digest
        or json.loads(raw_sources[digest]) != sources[digest]
        for digest in descriptor.json_pages.values()
    ):
        return ["json_original_sources_changed"]
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


def json_reporting_scope(catalog, descriptor):
    """Read explicit filing titles/options, never infer separate from absence."""
    from ..accounting.context_resolution import ContextEvidence, resolve_financial_context
    from .refined_context import context_lines
    from .refined_import import _reference
    from .reporting_scope import ReportingScopeResolution

    items = []
    for number, digest in descriptor.json_pages.items():
        if number > 5:
            continue
        page = catalog.json_sources.get(digest, {})
        for i, block in enumerate(page.get("blocks", [])):
            if block.get("uncertain") or not isinstance(block.get("text"), str):
                continue
            ref = _reference(page, {"sha256": digest}, f"/blocks/{i}/text")
            for line in block["text"].splitlines():
                option = re.fullmatch(r"\s*\[\s*([xX?]?)\s*\]\s*(.+?)\s*[;.]?", line)
                if option:
                    if option[1] == "":
                        continue  # An unselected option is not a scope declaration.
                    if not re.match(r"(?:bctc|báo cáo tài chính)\b", option[2], re.I):
                        continue  # Other yes/no checkboxes do not describe filing scope.
                    items.append(
                        ContextEvidence(
                            raw_text=option[2].rstrip(";.").strip(),
                            provenance=[ref],
                            scope_selection="selected" if option[1].lower() == "x" else "unknown",
                        )
                    )
                else:
                    # context_lines retains the exact source pointer when projecting a title.
                    items.extend(
                        e
                        for e in context_lines([ContextEvidence(raw_text=line, provenance=[ref])])
                        if re.fullmatch(
                            r"báo cáo tài chính (hợp nhất|riêng)", e.raw_text.strip(), re.I
                        )
                    )
    context = resolve_financial_context(items)
    scopes = {
        f.context.reporting_scope
        for f in catalog.facts
        if (f.document_id, f.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
        and f.context.reporting_scope is not None
    }
    if context.context.reporting_scope:
        scopes.add(context.context.reporting_scope)
    conflict = len(scopes) > 1 or "conflicting_candidates" in context.reporting_scope.issues
    resolved = (
        len(scopes) == 1
        and not conflict
        and not catalog.ancestry(descriptor)[1]
        and (not items or context.reporting_scope.status == "resolved")
    )
    return ReportingScopeResolution(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        reporting_scope=next(iter(scopes)) if resolved else None,
        status="resolved" if resolved else "conflicted" if conflict else "unresolved",
        evidence_status="json_bound" if resolved else "conflicted" if conflict else "insufficient",
        reviews=[],
        context_resolution=context,
        reasons=["json_scope_not_pdf_reviewed"]
        + (
            []
            if resolved
            else ["scope_conflicting_evidence" if conflict else "scope_source_insufficient"]
        ),
    )


def json_evidence_bound(catalog, descriptor, record):
    """Replay text/table payload against original bytes before exposing search results."""
    if (record.document_id, record.snapshot_id) != (descriptor.document_id, descriptor.snapshot_id):
        return False
    try:
        checked = set()
        for source in [*record.sources, *getattr(record, "member_sources", [])]:
            ref = source.reference
            if (source.document_id, source.snapshot_id) != (
                record.document_id,
                record.snapshot_id,
            ) or not is_json_reference(ref):
                return False
            digest = descriptor.json_pages[ref.anchor.page.page]
            if ref.anchor.page.source_ref != "json:sha256:" + digest:
                return False
            if digest not in checked:
                raw = catalog.json_source_bytes[digest]
                if (
                    hashlib.sha256(raw).hexdigest() != digest
                    or json.loads(raw) != catalog.json_sources[digest]
                ):
                    return False
                checked.add(digest)
            resolve_pointer(catalog.json_sources[digest], ref.source_pointer)
        ref = record.sources[0].reference
        value = resolve_pointer(
            catalog.json_sources[descriptor.json_pages[ref.anchor.page.page]], ref.source_pointer
        )
        if record.kind == "text":
            return value == record.raw_text
        expected = [
            (r, c, text)
            for r, row in enumerate([value["columns"], *value["rows"]])
            for c, text in enumerate(row)
        ]
        return record.source_metadata.get("original_table") == value and expected == [
            (c.row, c.col, c.text) for c in record.structure.cells
        ]
    except (KeyError, IndexError, AttributeError, TypeError, ValueError):
        return False


def json_document_composition(catalog):
    """Bind one already selected JSON snapshot; 'verified' means byte fidelity only."""
    from .composition import CompositionSource, EvidenceComposition, EvidencePin, payload_sha256

    if len(catalog.descriptors) != 1 or catalog.descriptors[0].source_kind != "json":
        raise ValueError("one_explicit_json_snapshot_required")
    descriptor = catalog.descriptors[0]
    if json_snapshot_issues(catalog, descriptor):
        raise ValueError("json_snapshot_binding_invalid")
    if not catalog.evidence or any(
        not json_evidence_bound(catalog, descriptor, e) for e in catalog.evidence
    ):
        raise ValueError("json_evidence_payload_mismatch")
    pins = [
        EvidencePin(
            identity=e.evidence_identity(), payload_sha256=payload_sha256(e.model_dump(mode="json"))
        )
        for e in catalog.evidence
    ]
    return EvidenceComposition(
        composition_id="json-composition:"
        + payload_sha256([p.model_dump(mode="json") for p in pins]),
        logical_document_id=descriptor.document_id,
        financial_snapshot=descriptor,
        sources=[
            CompositionSource(
                descriptor=descriptor,
                original_source="pinned_refined_json",
                artifact_sha256=descriptor.json_sha256,
                status="verified",
                evidence=pins,
            )
        ],
    )


def load_json_composition(manifest, repository):
    from .composition import payload_sha256
    from .snapshots import SnapshotCatalog

    descriptor = manifest.financial_snapshot
    if (
        len(manifest.sources) != 1
        or manifest.logical_document_id != descriptor.document_id
        or repository.descriptors != [descriptor]
        or json_snapshot_issues(repository, descriptor)
    ):
        raise ValueError("json_composition_snapshot_mismatch")
    source = manifest.sources[0]
    if (
        source.descriptor != descriptor
        or source.status != "verified"
        or source.pages
        or source.artifact_sha256 != descriptor.json_sha256
    ):
        raise ValueError("json_composition_source_mismatch")
    records = {
        e.evidence_identity().model_dump_json(): e
        for e in repository.list_by_document(descriptor.document_id, descriptor.snapshot_id)
    }
    rows, seen = [], set()
    for pin in source.evidence:
        key = pin.identity.model_dump_json()
        record = records.get(key)
        if (
            key in seen
            or record is None
            or payload_sha256(record.model_dump(mode="json")) != pin.payload_sha256
            or not json_evidence_bound(repository, descriptor, record)
        ):
            raise ValueError("json_composition_evidence_mismatch")
        seen.add(key)
        rows.append(record)
    return SnapshotCatalog([descriptor], evidence=rows, json_sources=repository.json_source_bytes)


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
