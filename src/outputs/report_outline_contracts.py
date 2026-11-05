"""M7-02 outline IR: source-bound protected slots for the later report writer."""

from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from ..accounting.contracts import FinancialModel
from ..agents.specialist_common import ClaimKind
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import ModelIdentity
from ..evidence.retrieval import EvidenceCitation
from .qa_contracts import QAClaimContext, QACompositionMetadata, QAValidationResult

ReportType = Literal[
    "general_financial_analysis",
    "profitability",
    "liquidity_and_leverage",
    "cash_flow_and_earnings_quality",
    "focused_analysis",
]
SectionType = Literal[
    "scope",
    "overview",
    "profitability",
    "financial_position",
    "cash_flow",
    "verified_unclassified",
    "limitations",
]
OutlineStatus = Literal["ready", "partial", "clarification_required", "abstained", "unsupported"]


class ReportOutlineRequest(FinancialModel):
    report_type: ReportType = "general_financial_analysis"
    # User label only. Output titles/objectives always come from the neutral catalog.
    title: str | None = Field(default=None, min_length=1, max_length=2000)
    company_id: str | None = None
    document_id: str | None = None
    snapshot_id: str | None = None
    period: str | None = None
    period_context: "ReportPeriodContext | None" = None
    reporting_scope: Literal["separate", "consolidated"] | None = None
    requested_sections: list[SectionType] = Field(default_factory=list, max_length=7)
    language: str = "vi"
    allow_gateway: bool = False
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )

    @field_validator("title", "company_id", "document_id", "snapshot_id", "period")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("blank_report_field")
        return value

    @field_validator("requested_sections")
    @classmethod
    def unique_sections(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("duplicate_requested_sections")
        return value


class ReportPeriodContext(FinancialModel):
    """Explicit caller binding, never inferred from the year or document name."""

    period_type: Literal["fiscal_year"] = "fiscal_year"
    period_end: str

    @field_validator("period_end")
    @classmethod
    def iso_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("canonical_period_end_required")
        return value


class ReportOutlineScope(FinancialModel):
    company_id: str | None
    document_id: str | None
    snapshot_id: str | None
    period: str | None
    period_context: ReportPeriodContext | None = None
    included_periods: list[str] = Field(default_factory=list)
    requested_reporting_scope: Literal["separate", "consolidated"] | None = None
    reporting_scope: Literal["separate", "consolidated"] | None = None


class ReportClaimSlot(FinancialModel):
    slot_id: str
    verified_claim_ids: list[str] = Field(min_length=1)
    accepted_content: str
    claim_kind: ClaimKind
    claim_context: QAClaimContext
    period_role: Literal["exact_period", "closing_balance"] = "exact_period"
    citations: list[EvidenceCitation] = Field(min_length=1)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    suggested_role: Literal[
        "key_fact", "approved_metric", "verified_interpretation", "supporting_context"
    ]


class ReportOutlineSection(FinancialModel):
    section_id: SectionType
    section_type: SectionType
    title_vi: str
    purpose: str
    order: int = Field(ge=1)
    status: Literal["supported", "insufficient_evidence", "context"]
    claim_slots: list[ReportClaimSlot] = Field(default_factory=list)
    linked_section_ids: list[SectionType] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class OutlineSectionOrder(FinancialModel):
    section_index: int = Field(ge=0)
    slot_order: list[int]


class ReportOutlineProposal(FinancialModel):
    """Complete permutations only; titles and every evidence field are protected."""

    sections: list[OutlineSectionOrder] = Field(min_length=2, max_length=7)


class GroundedReportOutline(FinancialModel):
    version: Literal["grounded_report_outline_v1"] = "grounded_report_outline_v1"
    report_type: ReportType
    report_title: str
    status: OutlineStatus
    scope: ReportOutlineScope
    sections: list[ReportOutlineSection] = Field(default_factory=list)
    used_verified_claim_ids: list[str] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    omitted_sections: list[SectionType] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    llm_metadata: QACompositionMetadata = Field(default_factory=QACompositionMetadata)
    validation_result: QAValidationResult = Field(
        default_factory=lambda: QAValidationResult(valid=False)
    )
