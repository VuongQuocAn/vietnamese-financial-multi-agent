"""PDF-reviewed text corrections and an external, version-bound trust policy.

The local policy store is operator-controlled input, never model/claim authority.
Validation establishes engineering provenance; only a separate Tech Lead decision
can authorize a corrected composition. Accepted inputs remain immutable.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.data_config import default_project_root
from ..core.persistence import atomic_json
from .composition import EvidencePin, payload_sha256, verify_saved_pages
from .document_evidence import EvidenceIdentity


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PDFTextReview(FinancialModel):
    reviewer: str = Field(min_length=1)
    method: Literal["controlled_original_pdf_visual_read"]
    review_reference: str = Field(min_length=1)
    observed_text: str = Field(min_length=1)


class DocumentCorrection(FinancialModel):
    original: EvidenceIdentity
    source_composition_sha256: str
    original_evidence_digest: str
    page: int = Field(ge=1)
    source_selector: str
    pdf_source_reference: str
    source_image_digest: str
    original_text: str = Field(min_length=1)
    corrected_text: str = Field(min_length=1)
    correction_type: Literal["material_transcription", "minor_transcription"]
    reason: str = Field(min_length=1)
    review_provenance: PDFTextReview
    validation_status: Literal["PROPOSED", "VALIDATED"] = "PROPOSED"
    correction_version: str = Field(min_length=1)
    created_at: datetime

    @property
    def digest(self):
        return payload_sha256(self.model_dump(mode="json"))


class CorrectedEvidencePin(EvidencePin):
    text_sha256: str
    source_selector: str


class CorrectionRelease(FinancialModel):
    correction_sha256: str
    snapshot_id: str
    composition_id: str
    composition_sha256: str
    evidence: list[CorrectedEvidencePin]

    @property
    def digest(self):
        return payload_sha256(self.model_dump(mode="json"))


class CorrectionApproval(FinancialModel):
    authority: Literal["Tech Lead"]
    purpose: Literal["document_correction_release"]
    release_sha256: str
    decision_reference: str = Field(min_length=1)


class DocumentSourcePolicy(FinancialModel):
    version: Literal["document_source_policy_v1"] = "document_source_policy_v1"
    corrections: list[DocumentCorrection] = Field(default_factory=list)
    releases: list[CorrectionRelease] = Field(default_factory=list)
    approvals: list[CorrectionApproval] = Field(default_factory=list)


def policy_path():
    root = Path(os.environ.get("DOCUMENT_SOURCE_POLICY_ROOT", "artifacts/source-quality"))
    root = (root if root.is_absolute() else default_project_root() / root).resolve()
    path = root / "document-source-policy.json"
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("source_policy_storage_mismatch")
    return path


def load_source_policy():
    path = policy_path()
    expected = os.environ.get("DOCUMENT_SOURCE_POLICY_SHA256", "").strip()
    if not path.exists():
        if "DOCUMENT_SOURCE_POLICY_ROOT" in os.environ or expected:
            raise ValueError("source_policy_required")
        return DocumentSourcePolicy()
    policy = DocumentSourcePolicy.model_validate_json(path.read_bytes())
    if expected and payload_sha256(policy.model_dump(mode="json")) != expected:
        raise ValueError("source_policy_fingerprint_mismatch")
    return policy


class CorrectionPromotionCheck(FinancialModel):
    release_sha256: str
    status: Literal["ready", "pending_approval", "blocked"]
    checks: dict[str, bool]
    reasons: list[str]


def check_correction_promotion(
    release, manifest, repository, pdf, saved_page, *, expected_release_sha256
):
    """Read-only preflight of the actual release. Never grants approval or activates it."""
    from .composition import load_composition

    policy = load_source_policy()
    checks = {
        "release_digest": release.digest == expected_release_sha256,
        "registered_release": release in policy.releases,
        "composition": (release.composition_id, release.composition_sha256)
        == (manifest.composition_id, payload_sha256(manifest.model_dump(mode="json"))),
    }
    records = [
        c
        for c in policy.corrections
        if c.digest == release.correction_sha256 and c.validation_status == "VALIDATED"
    ]
    checks["validated_correction"] = len(records) == 1
    if all(checks.values()):
        correction = records[0]
        try:
            bindings = verify_saved_pages(Path(pdf), [saved_page])
            checks["pdf_provenance"] = len(bindings) == 1 and (
                bindings[0].page,
                bindings[0].image_sha256,
                bindings[0].source_ref,
            ) == (correction.page, correction.source_image_digest, correction.pdf_source_reference)
            catalog = load_composition(
                manifest,
                repository,
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
            )
            rows = {r.evidence_identity().model_dump_json(): r for r in catalog.evidence}
            checks["content_and_selectors"] = bool(release.evidence) and all(
                (row := rows.get(pin.identity.model_dump_json())) is not None
                and row.kind == "text"
                and row.snapshot_id == release.snapshot_id
                and row.snapshot_id == "correction:" + correction.digest
                and payload_sha256(row.model_dump(mode="json")) == pin.payload_sha256
                and text_digest(row.raw_text or "") == pin.text_sha256
                and row.raw_text == correction.corrected_text
                and pin.source_selector == correction.source_selector
                and all(
                    a.reference is not None
                    and a.reference.source_pointer == pin.source_selector
                    and (
                        a.reference.anchor.page.page,
                        a.reference.anchor.page.image,
                        a.reference.anchor.page.source_ref,
                    )
                    == (
                        correction.page,
                        "sha256:" + correction.source_image_digest,
                        correction.pdf_source_reference,
                    )
                    for a in row.sources
                )
                and not any(issue.startswith("pdf_review:") for issue in row.resolution_issues)
                and not any(
                    c.original == pin.identity
                    and (
                        c.validation_status == "PROPOSED"
                        or c.correction_type == "material_transcription"
                    )
                    for c in policy.corrections
                )
                for pin in release.evidence
            )
        except (ValueError, OSError):
            checks["pdf_and_materialization"] = False
    checks["approval"] = any(a.release_sha256 == release.digest for a in policy.approvals)
    reasons = [key for key, valid in checks.items() if not valid]
    return CorrectionPromotionCheck(
        release_sha256=release.digest,
        checks=checks,
        reasons=reasons,
        status="ready"
        if not reasons
        else "pending_approval"
        if reasons == ["approval"]
        else "blocked",
    )


def save_source_policy(policy):
    """Explicit operator action; no auto-approval or writes to evidence repositories."""
    policy = DocumentSourcePolicy.model_validate_json(policy.model_dump_json())
    path = policy_path()
    if path.exists():
        existing = load_source_policy()
        if any(
            c.validation_status == "VALIDATED" and c not in policy.corrections
            for c in existing.corrections
        ):
            raise ValueError("validated_source_review_is_immutable")
        if any(r not in policy.releases for r in existing.releases):
            raise ValueError("correction_release_history_is_immutable")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, policy.model_dump(mode="json"))


def validate_correction(proposal, original, manifest, pdf, saved_page):
    """Check exact saved/rendered PDF binding and a separately recorded visual read.

    This does not claim deterministic semantic OCR detection or human acceptance.
    """
    if (
        proposal.validation_status != "PROPOSED"
        or proposal.original != original.evidence_identity()
        or proposal.original_evidence_digest != payload_sha256(original.model_dump(mode="json"))
        or proposal.source_composition_sha256 != payload_sha256(manifest.model_dump(mode="json"))
        or proposal.original_text != original.raw_text
        or proposal.original_text == proposal.corrected_text
        or proposal.review_provenance.observed_text != proposal.corrected_text
    ):
        raise ValueError("correction_original_or_review_mismatch")
    bindings = verify_saved_pages(Path(pdf), [saved_page])
    if len(bindings) != 1 or (
        bindings[0].page,
        bindings[0].source_ref,
        bindings[0].image_sha256,
    ) != (proposal.page, proposal.pdf_source_reference, proposal.source_image_digest):
        raise ValueError("correction_pdf_binding_mismatch")
    pins = {
        p.identity.model_dump_json(): p.payload_sha256
        for s in manifest.sources
        if s.status == "verified"
        for p in s.evidence
    }
    if pins.get(
        proposal.original.model_dump_json()
    ) != proposal.original_evidence_digest or not any(
        a.reference is not None
        and a.reference.source_pointer == proposal.source_selector
        and a.reference.anchor.page.page == proposal.page
        and a.reference.anchor.page.image == "sha256:" + proposal.source_image_digest
        and a.reference.anchor.page.source_ref == proposal.pdf_source_reference
        for a in original.sources
    ):
        raise ValueError("correction_selector_or_pin_mismatch")
    return proposal.model_copy(update={"validation_status": "VALIDATED"})


def build_correction_version(correction, manifest, repository):
    """Version only the reviewed text selector; preserve all other source identities."""
    from .composition import load_composition

    if (
        correction.validation_status != "VALIDATED"
        or correction.source_composition_sha256 != payload_sha256(manifest.model_dump(mode="json"))
    ):
        raise ValueError("validated_correction_required")
    catalog = load_composition(
        manifest,
        repository,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    sources = [
        s for s in manifest.sources if any(p.identity == correction.original for p in s.evidence)
    ]
    if (
        len(sources) != 1
        or len(sources[0].pages) != 1
        or sources[0].pages[0].page != correction.page
    ):
        raise ValueError("correction_single_page_source_required")
    source = sources[0]
    original_rows = {e.evidence_identity().model_dump_json(): e for e in catalog.evidence}
    original = original_rows[correction.original.model_dump_json()]
    if (
        payload_sha256(original.model_dump(mode="json")) != correction.original_evidence_digest
        or original.raw_text != correction.original_text
    ):
        raise ValueError("correction_original_changed")
    new_snapshot = "correction:" + correction.digest
    row = original.model_copy(deep=True)
    if row.kind != "text":
        raise ValueError("correction_text_required")
    row.snapshot_id = new_snapshot
    for anchor in row.sources:
        anchor.snapshot_id = new_snapshot
    row.source_metadata["correction_sha256"] = correction.digest
    row.source_metadata["original_evidence"] = correction.original.model_dump(mode="json")
    row.raw_text = correction.corrected_text
    rows = [row]
    new_source = source.model_copy(deep=True)
    new_source.descriptor.snapshot_id = new_snapshot
    new_source.descriptor.parent_snapshot_id = source.descriptor.snapshot_id
    new_source.descriptor.origin = "recovery"
    new_source.original_source = "correction:" + correction.digest
    new_source.artifact_sha256 = correction.digest
    new_source.evidence = [
        EvidencePin(
            identity=r.evidence_identity(), payload_sha256=payload_sha256(r.model_dump(mode="json"))
        )
        for r in rows
    ]
    updated = manifest.model_copy(deep=True)
    updated.composition_id += ":correction:" + correction.digest
    for old_source in updated.sources:
        if old_source == source:
            old_source.evidence = [
                p for p in old_source.evidence if p.identity != correction.original
            ]
    updated.sources.append(new_source)
    release = CorrectionRelease(
        correction_sha256=correction.digest,
        snapshot_id=new_snapshot,
        composition_id=updated.composition_id,
        composition_sha256=payload_sha256(updated.model_dump(mode="json")),
        evidence=[
            CorrectedEvidencePin(
                identity=r.evidence_identity(),
                payload_sha256=payload_sha256(r.model_dump(mode="json")),
                text_sha256=text_digest(r.raw_text or ""),
                source_selector=r.sources[0].reference.source_pointer,
            )
            for r in rows
        ],
    )
    return rows, updated, release


def document_source_issues(claim, contexts):
    """Current trust, rechecked even for old proofs/cached ledger payloads."""
    try:
        policy = load_source_policy()
    except (ValueError, OSError):
        return ["source_policy_unavailable"]
    issues = set()
    for ref, context in zip(claim.references, contexts, strict=False):
        identity = ref.evidence
        if identity is None:
            continue
        if any(
            c.validation_status == "PROPOSED" and c.original == identity for c in policy.corrections
        ):
            issues.add("source_review_required")
        if any(
            c.validation_status == "VALIDATED"
            and c.correction_type == "material_transcription"
            and c.original == identity
            for c in policy.corrections
        ):
            issues.add("confirmed_source_discrepancy")
        if not identity.snapshot_id.startswith("correction:"):
            continue
        releases = [
            r
            for r in policy.releases
            if (r.snapshot_id, r.composition_id, r.composition_sha256)
            == (identity.snapshot_id, claim.composition_id, claim.composition_sha256)
        ]
        if len(releases) != 1:
            issues.add("correction_release_mismatch")
            continue
        release = releases[0]
        records = [
            c
            for c in policy.corrections
            if c.digest == release.correction_sha256 and c.validation_status == "VALIDATED"
        ]
        pins = [p for p in release.evidence if p.identity == identity]
        if len(records) != 1 or len(pins) != 1:
            issues.add("correction_source_mismatch")
            continue
        correction, pin = records[0], pins[0]
        if not any(a.release_sha256 == release.digest for a in policy.approvals):
            issues.add("correction_pending_approval")
        if (
            context.content.get("evidence_payload_sha256") != pin.payload_sha256
            or text_digest(context.content.get("text", "")) != pin.text_sha256
        ):
            issues.add("correction_content_mismatch")
        if not context.citations or any(
            c.source.reference is None
            or c.source.reference.source_pointer != pin.source_selector
            or (
                c.pdf_page,
                c.source.reference.anchor.page.image,
                c.source.reference.anchor.page.source_ref,
            )
            != (
                correction.page,
                "sha256:" + correction.source_image_digest,
                correction.pdf_source_reference,
            )
            for c in context.citations
        ):
            issues.add("correction_pdf_selector_mismatch")
    return sorted(issues)
