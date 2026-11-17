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


class SemanticIssue(FinancialModel):
    check: Literal[
        "source",
        "period",
        "selection",
        "entity_join",
        "formula",
        "goal_support",
        "semantic_conclusion",
    ]
    reason_code: str = Field(min_length=1, max_length=100)
    input_refs: list[str] = Field(default_factory=list, max_length=32)


class GoalSemanticVerdict(SemanticVerdict):
    supported_requirement_ids: list[str] = Field(max_length=16)
    issues: list[SemanticIssue] = Field(default_factory=list, max_length=16)


class LiteProofV2(LiteProof):
    goal_context: dict = Field(default_factory=dict)
    semantic: GoalSemanticVerdict | None = None


class LiteVerificationHistoryV2(LiteVerificationHistory):
    version: Literal["lite_verification_history_v2"] = "lite_verification_history_v2"
    proof: LiteProofV2
