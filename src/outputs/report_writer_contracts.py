"""M7-03: protected narrative paragraphs, with source bindings kept on the wire."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.specialist_common import ClaimKind
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import ModelIdentity
from ..evidence.retrieval import EvidenceCitation
from .qa_contracts import QAClaimContext, QACompositionMetadata, QAValidationResult
from .report_outline_contracts import (
    GroundedReportOutline,
    ReportOutlineRequest,
    ReportOutlineScope,
    SectionType,
)

Transition = Literal["evidence", "also", "interpretation"]


class GroundedReportRequest(FinancialModel):
    outline: GroundedReportOutline
    outline_request: ReportOutlineRequest
    allow_gateway: bool = False
    language: str = "vi"
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )


class ReportParagraphContext(FinancialModel):
    source_slot_id: str
    claim_context: QAClaimContext
    period_role: Literal["exact_period", "closing_balance"]
    claim_kind: ClaimKind


class ReportParagraph(FinancialModel):
    paragraph_id: str
    paragraph_type: Literal[
        "scope_description",
        "section_introduction",
        "grounded_analysis",
        "verified_interpretation",
        "evidence_limitation",
        "summary",
    ]
    text_vi: str
    source_slot_ids: list[str] = Field(default_factory=list)
    verified_claim_ids: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    context: list[ReportParagraphContext] = Field(default_factory=list)
    transition: Transition = "evidence"


class ReportSection(FinancialModel):
    section_id: SectionType
    title_vi: str
    order: int = Field(ge=1)
    status: Literal["supported", "insufficient_evidence", "context"]
    paragraphs: list[ReportParagraph]
    used_claim_slots: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class NarrativeGroup(FinancialModel):
    slot_indexes: list[int] = Field(min_length=1)
    transition: Transition


class SectionNarrativePlan(FinancialModel):
    section_index: int = Field(ge=0)
    paragraphs: list[NarrativeGroup]


class ReportNarrativeProposal(FinancialModel):
    sections: list[SectionNarrativePlan] = Field(max_length=7)


class GroundedFinancialReport(FinancialModel):
    version: Literal["grounded_financial_report_v1"] = "grounded_financial_report_v1"
    report_title: str
    status: Literal["generated", "partial", "clarification_required", "abstained", "unsupported"]
    scope: ReportOutlineScope
    sections: list[ReportSection] = Field(default_factory=list)
    body_vi: str
    used_verified_claim_ids: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    llm_metadata: QACompositionMetadata = Field(default_factory=QACompositionMetadata)
    validation_result: QAValidationResult = Field(
        default_factory=lambda: QAValidationResult(valid=False)
    )
