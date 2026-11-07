"""M6 document checks, critic decisions and replayable proof."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.document_qa_contracts import DocumentCandidate
from ..evidence.composition import payload_sha256
from ..evidence.document_claim_support import consecutive, source_assertion
from .evidence_context import EvidenceContextBuilder
from .evidence_contracts import EvidenceContext


class DocumentDecision(FinancialModel):
    policy_version: Literal["document_verification_v1"] = "document_verification_v1"
    original_claim: DocumentCandidate
    decision: Literal["ACCEPT", "INVESTIGATE", "ABSTAIN"]
    checks: dict[str, bool]
    evidence: list[EvidenceContext]
    reasons: list[str]
    caveats: list[str] = Field(default_factory=list)

    @property
    def supporting_references(self):
        return self.original_claim.references

    @property
    def supporting_citations(self):
        return self.original_claim.citations if self.decision == "ACCEPT" else []


class DocumentVerificationHistory(FinancialModel):
    version: Literal["document_verification_history_v1"] = "document_verification_history_v1"
    final: DocumentDecision


def judge_document(claim, contexts):
    """Replay source, evidence fidelity and relation checks over resolved M4 proof."""
    refs = claim.references
    identity = (claim.source_document_id, claim.snapshot_id)
    source_ok = (
        len(contexts) == len(refs)
        and len({ref.model_dump_json() for ref in refs}) == len(refs)
        and all(
            ref.evidence is not None
            and (ref.evidence.document_id, ref.evidence.snapshot_id) == identity
            and ctx.reference == ref
            and ctx.available
            and (ctx.document_id, ctx.snapshot_id) == identity
            and bool(ctx.citations)
            and all(
                (c.document_id, c.snapshot_id) == identity
                and (c.source.document_id, c.source.snapshot_id) == identity
                and c.source.reference is not None
                and c.pdf_page == c.source.reference.anchor.page.page
                for c in ctx.citations
            )
            for ref, ctx in zip(refs, contexts, strict=True)
        )
    )
    citations_ok = source_ok and claim.citations == [c for ctx in contexts for c in ctx.citations]
    layout_ok = (
        source_ok
        and len({ctx.content.get("request_id") for ctx in contexts}) == 1
        and consecutive([ctx.citations for ctx in contexts])
    )
    assertion = (
        source_assertion(claim.requirement, [ctx.content for ctx in contexts])
        if layout_ok
        else None
    )
    relationship_ok = claim.claim_type != "entity_role" or bool(assertion and assertion[2])
    content_ok = (
        assertion is not None
        and assertion == (claim.quotations, claim.content, claim.person)
        and claim.claim_type == claim.requirement.kind
    )
    source_caveats = {c for ctx in contexts for c in ctx.caveats}
    checks = {
        "source_identity": source_ok,
        "original_citations": citations_ok,
        "source_continuity": layout_ok,
        "content_fidelity": content_ok,
        "relationship_support": relationship_ok,
        "source_caveats": set(claim.caveats) <= source_caveats,
    }
    # Matching saved OCR is insufficient when PDF review has identified a defect.
    # Reviews currently flag whole-page projections; fail closed for those records.
    # Leave clean v1 proofs unchanged so existing valid ledger entries still replay.
    if any(caveat.startswith("pdf_review:") for caveat in source_caveats):
        checks["source_quality"] = False
    reasons = [key for key, passed in checks.items() if not passed]
    return DocumentDecision(
        original_claim=claim,
        decision="ACCEPT" if not reasons else "INVESTIGATE" if citations_ok else "ABSTAIN",
        checks=checks,
        evidence=contexts,
        reasons=reasons or ["exact_source_support"],
        caveats=sorted(source_caveats),
    )


def verify_document_claim(
    claim, builder: EvidenceContextBuilder, manifest, company_id, snapshot_id
):
    pinned = {
        pin.identity.model_dump_json()
        for source in manifest.sources
        if source.status == "verified"
        for pin in source.evidence
    }
    digest = payload_sha256(manifest.model_dump(mode="json"))
    if (
        (claim.document_id, claim.composition_id, claim.composition_sha256, claim.company_id)
        != (manifest.logical_document_id, manifest.composition_id, digest, company_id)
        or (snapshot_id is not None and claim.snapshot_id != snapshot_id)
        or any(
            ref.evidence is None or ref.evidence.model_dump_json() not in pinned
            for ref in claim.references
        )
    ):
        return DocumentVerificationHistory(final=judge_document(claim, []))
    return DocumentVerificationHistory(final=judge_document(claim, builder.build_document(claim)))
