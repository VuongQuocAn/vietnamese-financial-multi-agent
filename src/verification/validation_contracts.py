"""Check outcomes only; these contracts cannot accept claims or write a ledger."""

from typing import Literal

from pydantic import Field, JsonValue

from ..accounting.contracts import FinancialModel
from ..agents.orchestration_contracts import CandidateConflict
from ..evidence.retrieval import EvidenceCitation
from .contracts import VerificationFinding

CheckStatus = Literal["pass", "fail", "undetermined", "not_applicable"]


class ValidationCheck(VerificationFinding):
    check_id: str
    status: CheckStatus
    reason_code: str
    expected: dict[str, JsonValue] = Field(default_factory=dict)
    observed: dict[str, JsonValue] = Field(default_factory=dict)
    citations: list[EvidenceCitation] = Field(default_factory=list)


class ClaimValidationResult(FinancialModel):
    candidate_id: str
    claim_kind: Literal["fact", "approved_metric", "supported_interpretation"]
    checks: list[ValidationCheck] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    # Scope uncertainty remains visible per check; there is deliberately no
    # aggregate verdict that could mistake partial coverage for verification.
    financial_fact_verified: Literal[False] = False


class ValidationResult(FinancialModel):
    version: Literal["deterministic_financial_validation_v1"] = (
        "deterministic_financial_validation_v1"
    )
    source_result_sha256: str
    claims: list[ClaimValidationResult] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False
