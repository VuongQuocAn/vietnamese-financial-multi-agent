"""M7-05 release contracts. Only the final decision grants display permission."""

from typing import Literal

from pydantic import Field, model_validator

from ..accounting.contracts import FinancialModel
from .citation_contracts import CitationBinding, CitationReference
from .qa_contracts import QAValidationResult

FirewallVerdict = Literal["ALLOW", "ALLOW_WITH_CAVEAT", "BLOCK", "CLARIFICATION_REQUIRED"]


class FirewallCheckResult(FinancialModel):
    check_id: str
    status: Literal["pass", "fail", "warning", "not_applicable"]
    severity: Literal["info", "warning", "critical"]
    reason_code: str
    reasons: list[str] = Field(default_factory=list)
    affected_verified_claim_ids: list[str] = Field(default_factory=list)
    affected_segment_ids: list[str] = Field(default_factory=list)
    affected_citation_ids: list[str] = Field(default_factory=list)


class ValidatedOutput(FinancialModel):
    status: str
    message_vi: str
    rendered_text: str | None = None
    references: list[CitationReference] = Field(default_factory=list)
    citation_bindings: list[CitationBinding] = Field(default_factory=list)
    verified_claim_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FirewallDecision(FinancialModel):
    version: Literal["information_firewall_v1"] = "information_firewall_v1"
    output_type: Literal["qa", "report"]
    decision: FirewallVerdict
    original_status: str
    release_status: Literal["released", "blocked", "clarification_required"]
    validated_verified_claim_ids: list[str] = Field(default_factory=list)
    validated_citation_ids: list[str] = Field(default_factory=list)
    checks: list[FirewallCheckResult]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source_fingerprint: str | None = None
    output_fingerprint: str | None = None
    validated_output: ValidatedOutput
    validation_result: QAValidationResult
    ledger_queries: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def safe_release(self):
        release = self.decision in ("ALLOW", "ALLOW_WITH_CAVEAT")
        expected = (
            "released"
            if release
            else ("blocked" if self.decision == "BLOCK" else "clarification_required")
        )
        if self.release_status != expected:
            raise ValueError("release_status_decision_mismatch")
        if release:
            if not self.validation_result.valid or self.blockers:
                raise ValueError("release_requires_valid_checks")
            if self.validated_output.rendered_text is None:
                raise ValueError("released_view_required")
        elif (
            self.validated_output.rendered_text is not None
            or self.validated_output.references
            or self.validated_output.citation_bindings
            or self.validated_output.verified_claim_ids
            or self.validated_output.caveats
            or self.validated_output.limitations
            or self.validated_verified_claim_ids
            or self.validated_citation_ids
        ):
            raise ValueError("unreleased_view_must_not_contain_financial_body")
        return self
