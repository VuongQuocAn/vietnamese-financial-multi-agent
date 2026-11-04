"""Exact M4 evidence projections; candidate-provided copies never become sources."""

import json

from ..evidence.document_evidence import TableEvidence, TextEvidence
from ..evidence.retrieval import RetrievalReference
from ..tools.evidence_retrieval import (
    EvidenceRetrievalTools,
    GetEvidenceSourcesRequest,
    GetMetricEvidenceLineageRequest,
)
from .evidence_contracts import EvidenceContext


class EvidenceContextBuilder:
    def __init__(self, catalog):
        self._tools = EvidenceRetrievalTools(catalog)
        self._resolved = {}

    def build(self, claim):
        references = []
        for ref in [
            *claim.fact_references,
            *claim.provenance.supporting_references,
            *[e.reference for e in claim.supporting_evidence],
            *[RetrievalReference(kind="metric", record_id=m) for m in claim.metric_ids],
        ]:
            if ref not in references:
                references.append(ref)
        if len(references) > 16:
            raise ValueError("evidence_reference_limit")
        contexts = []
        for i, ref in enumerate(references):
            key = ref.model_dump_json()
            if key not in self._resolved:
                self._resolved[key] = self._resolve(ref, i)
            contexts.append(
                self._resolved[key].model_copy(deep=True, update={"evidence_id": f"E{i + 1}"})
            )
        return contexts

    def _resolve(self, ref, index):
        if ref.kind in {"metric", "lineage"}:
            result = self._tools.get_metric_evidence_lineage(
                GetMetricEvidenceLineageRequest(metric_id=ref.record_id)
            )
        else:
            result = self._tools.get_evidence_sources(GetEvidenceSourcesRequest(reference=ref))
        context = EvidenceContext(
            evidence_id=f"E{index + 1}",
            reference=ref,
            document_id=None,
            snapshot_id=None,
            citations=[],
            caveats=[*result.caveats, *result.reasons],
        )
        if result.status != "found" or len(result.matches) != 1:
            context.caveats.append("source_retrieval_" + result.status)
            return context
        match = result.matches[0]
        record = match.record
        owner = getattr(record, "request", record)
        context.document_id = owner.document_id
        context.snapshot_id = owner.snapshot_id
        context.citations = match.citations
        context.caveats.extend(match.issues)
        scopes = [
            s
            for s in result.reporting_scopes
            if (s.document_id, s.snapshot_id) == (context.document_id, context.snapshot_id)
        ]
        if len(scopes) == 1:
            context.reporting_scope_status = scopes[0].status
            context.reporting_scope = scopes[0].reporting_scope
        for lookup in result.source_reviews:
            context.caveats.extend("source_review_" + view.status for view in lookup.matches)
        for metric in result.metric_matches:
            for operand in metric.reviewed_lineage.operands:
                for lookup in operand.bindings:
                    context.caveats.extend(
                        "source_review_" + view.status for view in lookup.matches
                    )
        if ref.kind == "fact":
            context.period = record.context.period
            context.content = dict(
                company_id=record.company_id,
                canonical_item_id=record.canonical_item_id,
                value=record.value.model_dump(mode="json"),
                context=record.context.model_dump(mode="json"),
            )
            context.available = match.display_status == "display_with_caveat"
            for quality in record.quality_context:
                context.caveats.extend([quality.decision, *quality.caveats])
        elif isinstance(record, TextEvidence):
            context.content = {"text": (record.raw_text or "")[:6000]}
            context.available = bool(record.raw_text)
            if record.raw_text and len(record.raw_text) > 6000:
                context.caveats.append("source_excerpt_truncated")
        elif isinstance(record, TableEvidence):
            raw = (
                json.dumps(record.structure.model_dump(mode="json"), ensure_ascii=False)
                if record.structure
                else ""
            )
            context.content = {"table_excerpt": raw[:6000]}
            context.available = bool(raw)
            if len(raw) > 6000:
                context.caveats.append("source_excerpt_truncated")
        elif ref.kind in {"metric", "lineage"}:
            context.content = {
                "lineage_status": record.completeness,
                "operands": [
                    {
                        "role": o.binding.role,
                        "references": [r.model_dump(mode="json") for r in o.binding.candidates],
                    }
                    for o in record.operands
                ],
            }
            context.available = bool(record.operands) and record.completeness == "complete"
        # Anchors locate sources but contain no text proving a semantic assertion.
        context.available = context.available and bool(context.citations)
        if any(
            (c.document_id, c.snapshot_id) != (c.source.document_id, c.source.snapshot_id)
            or (c.document_id, c.snapshot_id) != (context.document_id, context.snapshot_id)
            or c.source.reference is None
            or c.pdf_page != c.source.reference.anchor.page.page
            or c.provenance_level != c.source.reference.provenance_level
            or c.anchor_id is None
            for c in context.citations
        ):
            context.available = False
            context.caveats.append("canonical_citation_binding_invalid")
        context.caveats = sorted(set(context.caveats))
        return context
