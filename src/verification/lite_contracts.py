"""Honest Lite proofs: deterministic checks and optional semantic verdict only."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.planner_contracts import PlannerLLMMetadata
from .contracts import VerificationInput
from .decision_contracts import VerificationLoopResult
from .validation_contracts import ValidationResult


class SemanticVerdict(FinancialModel):
    claim_id: str
    verdict: Literal["SUPPORTED", "INSUFFICIENT", "UNSUPPORTED"]
    reason: str = Field(min_length=1, max_length=1500)


class SemanticVerdicts(FinancialModel):
    verdicts: list[SemanticVerdict] = Field(max_length=32)


class LiteProof(FinancialModel):
    batch: VerificationInput
    validation: ValidationResult
    semantic: SemanticVerdict | None = None
    semantic_input_sha256: str | None = None
    metadata: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    semantic_error: str | None = None


class LiteVerificationHistory(FinancialModel):
    version: Literal["lite_verification_history_v1"] = "lite_verification_history_v1"
    proof: LiteProof
    outcome: VerificationLoopResult
