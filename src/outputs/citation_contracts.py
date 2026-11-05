"""M7-04: presentation contracts; source location grants no financial authority."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..document_processing.contracts.raw_ocr import OCRBoundingBox
from ..evidence.retrieval import EvidenceCitation
from .qa_contracts import QAClaimContext, QAValidationResult


class CitationLocator(FinancialModel):
    document_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    pdf_page: int | None = Field(default=None, ge=1)
    source_ref: str | None = None
    source_pointer: str | None = None
    image_reference: str | None = None
    element_id: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    line_id: str | None = None
    observed_bbox: OCRBoundingBox | None = None
    provenance_level: Literal["page", "element", "cell"] | None = None
    resolution_status: Literal["resolved", "unresolved", "location_unavailable"]
    # No resource mapping is inferred from image/source_ref or a local path.
    resource_mapping_status: Literal["not_provided"] = "not_provided"


class CitationReference(FinancialModel):
    citation_id: str = Field(min_length=1)
    display_number: int = Field(ge=1)
    display_label: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    pdf_page: int | None = Field(default=None, ge=1)
    provenance_level: Literal["page", "element", "cell"] | None
    anchor_id: str | None
    source_locator: CitationLocator
    # Keep every upstream citation variant (including its caveats) verbatim.
    source_citations: list[EvidenceCitation] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    bound_verified_claim_ids: list[str] = Field(min_length=1)
    bound_output_segment_ids: list[str] = Field(min_length=1)


class CitationBinding(FinancialModel):
    output_segment_id: str = Field(min_length=1)
    verified_claim_ids: list[str] = Field(min_length=1)
    citation_ids: list[str] = Field(min_length=1)
    display_numbers: list[int] = Field(min_length=1)
    source_slot_ids: list[str] = Field(default_factory=list)
    contexts: list[QAClaimContext] = Field(min_length=1)


class RenderedCitationOutput(FinancialModel):
    version: Literal["rendered_citations_v1"] = "rendered_citations_v1"
    source_output_type: Literal["qa", "report"]
    source_fingerprint: str
    status: Literal["rendered", "location_limited"]
    original_status: str
    rendered_text: str
    references: list[CitationReference] = Field(default_factory=list)
    citation_bindings: list[CitationBinding] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validation_result: QAValidationResult
