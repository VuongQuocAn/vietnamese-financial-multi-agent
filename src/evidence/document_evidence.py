"""Text/table representations giữ nguồn M1/M2; không phải verified claims."""

from typing import Annotated, Literal

from pydantic import Field

from ..accounting.automated_extraction import ExtractionTable
from ..accounting.contracts import FinancialModel
from ..document_processing.contracts.document_understanding import UnderstoodTable
from ..document_processing.contracts.unified_document import UnifiedTable
from .contracts import CanonicalFinancialFact, EvidenceAnchor, Identity, ObservationIdentity


class EvidenceIdentity(ObservationIdentity):
    kind: Literal["text", "table"]


class _DocumentEvidence(FinancialModel):
    document_id: Identity | None = None
    snapshot_id: Identity | None = None
    local_evidence_id: Identity | None = None
    sources: list[EvidenceAnchor] = Field(default_factory=list)
    source_metadata: dict = Field(default_factory=dict)
    resolution_issues: list[str] = Field(default_factory=list)

    def evidence_identity(self) -> EvidenceIdentity | None:
        if not all((self.document_id, self.snapshot_id, self.local_evidence_id)):
            return None
        return EvidenceIdentity(
            document_id=self.document_id,
            snapshot_id=self.snapshot_id,
            local_id=self.local_evidence_id,
            kind=self.kind,
        )


class TextEvidence(_DocumentEvidence):
    kind: Literal["text"] = "text"
    raw_text: str | None
    structural_role: str | None = None


class TableEvidence(_DocumentEvidence):
    kind: Literal["table"] = "table"
    original_table_id: str | None = None
    # Wrapper mỏng: không tái dựng hoặc copy schema cells của M1/M2.
    structure: UnderstoodTable | UnifiedTable | ExtractionTable | None = None
    member_sources: list[EvidenceAnchor] = Field(default_factory=list)
    structural_issues: list[str] = Field(default_factory=list)


DocumentEvidence = Annotated[TextEvidence | TableEvidence, Field(discriminator="kind")]


class FactEvidenceAssociation(FinancialModel):
    fact: ObservationIdentity
    evidence: EvidenceIdentity
    matching_sources: list[EvidenceAnchor]


def associate_fact(
    fact: CanonicalFinancialFact, evidence: TextEvidence | TableEvidence
) -> FactEvidenceAssociation | None:
    """Exact source selector association, không suy supporting claim từ cùng trang."""
    fid, eid = fact.observation_identity(), evidence.evidence_identity()
    if fid is None or eid is None:
        return None
    if (fid.document_id, fid.snapshot_id) != (eid.document_id, eid.snapshot_id):
        return None
    request_ids = [s.source_metadata.get("request_id") for s in (fact, evidence)]
    if any(request_ids) and request_ids[0] != request_ids[1]:
        return None
    sources = [*evidence.sources]
    if isinstance(evidence, TableEvidence):
        sources.extend(evidence.member_sources)
    # Một source có binding mâu thuẫn làm association không đủ căn cứ.
    if any(
        (s.document_id, s.snapshot_id) != (fid.document_id, fid.snapshot_id)
        for s in [*fact.sources, *sources]
    ):
        return None
    matches = []
    for source in sources:
        ref = source.reference
        if ref is None:
            continue
        a = ref.anchor
        if a.page.page < 1 or not a.page.image.strip():
            continue
        if not (ref.source_pointer or a.element_id or a.table_id or a.cell_id or a.line_id):
            continue
        if any(
            other.reference is not None
            and a.page == other.reference.anchor.page
            and source.source_key() == other.source_key()
            for other in fact.sources
        ):
            matches.append(source.model_copy(deep=True))
    if not matches:
        return None
    return FactEvidenceAssociation(fact=fid, evidence=eid, matching_sources=matches)
