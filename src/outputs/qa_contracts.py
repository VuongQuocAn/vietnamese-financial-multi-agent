"""M7-01: source-bound QA wire contracts; no verification authority."""

from typing import Literal

from pydantic import Field, field_validator

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import Cost, GatewayError, ModelIdentity, ResponseProvenance, Usage
from ..evidence.retrieval import EvidenceCitation
from ..tools.financial_calculator import CalculationOperand

QAStatus = Literal["answered", "partial", "clarification_required", "abstained", "unsupported"]


class VietnameseQARequest(FinancialModel):
    question: str = Field(min_length=1, max_length=4000)
    company_id: str | None = None
    document_id: str | None = None
    snapshot_id: str | None = None
    period: str | None = None
    composition_id: str | None = None
    composition_sha256: str | None = None
    # Approved original document snapshots for a mixed request, not renamed IDs.
    document_snapshots: list[str] = Field(default_factory=list)
    reporting_scope: Literal["separate", "consolidated"] | None = None
    allow_gateway: bool = False
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("question_must_not_be_blank")
        return value


class QARequirement(FinancialModel):
    requirement_id: str
    text: str
    kind: Literal[
        "fact",
        "metric",
        "explanation",
        "limitations",
        "unsupported",
        "ambiguous",
        "document",
        "source_context",
    ]
    target_id: str | None = None
    interpretation: bool = False
    aspect: Literal["value", "formula", "operands"] = "value"
    depends_on: list[str] = Field(default_factory=list)
    interpretation_topic: Literal["metric_meaning", "earnings_quality", "unbounded"] | None = None
    verified_claim_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class GroundedAnswerPlan(FinancialModel):
    requirements: list[QARequirement] = Field(default_factory=list)
    selected_verified_claim_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class QAClaimContext(FinancialModel):
    company_id: str
    document_id: str
    snapshot_id: str
    period: str | None
    reporting_scope: Literal["separate", "consolidated"] | None = None


class QAExplanationOperand(FinancialModel):
    label: str
    operand: CalculationOperand
    citations: list[EvidenceCitation] = Field(min_length=1)


class QAMetricExplanation(FinancialModel):
    """Display projection of an ACCEPT calculation, never an independent fact."""

    metric_id: str
    formula_id: str
    formula_version: str
    formula_digest: str
    result: str
    output_unit: str
    formula: str | None = None
    operands: list[QAExplanationOperand] = Field(default_factory=list)


class GroundedSegment(FinancialModel):
    segment_id: str
    content: str
    verified_claim_ids: list[str] = Field(min_length=1)
    citations: list[EvidenceCitation] = Field(min_length=1)
    context: QAClaimContext
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    explanation: QAMetricExplanation | None = None


class QACompositionProposal(FinancialModel):
    """Only protected-slot ordering and a finite introduction; never free prose."""

    claim_order: list[str] = Field(min_length=1, max_length=12)
    introduction: Literal["verified", "by_requirement"]


class QACompositionMetadata(FinancialModel):
    calls: int = 0
    status: Literal["not_called", "accepted", "fallback"] = "not_called"
    reason: str | None = None
    model: ModelIdentity | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    provenance: ResponseProvenance | None = None
    error: GatewayError | None = None


class QAValidationResult(FinancialModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class VietnameseQAResponse(FinancialModel):
    version: Literal["vietnamese_qa_v1"] = "vietnamese_qa_v1"
    question: str
    status: QAStatus
    answer_vi: str
    answered_requirements: list[QARequirement] = Field(default_factory=list)
    unanswered_requirements: list[QARequirement] = Field(default_factory=list)
    used_verified_claim_ids: list[str] = Field(default_factory=list)
    grounded_segments: list[GroundedSegment] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    plan: GroundedAnswerPlan
    introduction: Literal["verified", "by_requirement"] = "verified"
    llm_metadata: QACompositionMetadata = Field(default_factory=QACompositionMetadata)
    validation_result: QAValidationResult = Field(
        default_factory=lambda: QAValidationResult(valid=False)
    )
