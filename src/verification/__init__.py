"""M6 candidate contracts and deterministic M5 handoff; verification is pending."""

from .adapter import to_verification_input
from .contracts import (
    CandidateClaim,
    ClaimProvenance,
    ConversionIssue,
    FindingKind,
    VerificationDecision,
    VerificationEvidence,
    VerificationFinding,
    VerificationInput,
)
from .evidence_contracts import (
    ClaimEvidenceAssessment,
    EvidenceContext,
    EvidenceCriticError,
    EvidenceCriticResult,
    EvidenceCriticTrace,
    EvidenceSupportFinding,
    SemanticEvidenceAssessment,
    SupportStatus,
)
from .evidence_critic import EvidenceCritic
from .validation_contracts import (
    CheckStatus,
    ClaimValidationResult,
    ValidationCheck,
    ValidationResult,
)
from .validators import DeterministicFinancialValidator

__all__ = [
    "CandidateClaim",
    "ClaimEvidenceAssessment",
    "EvidenceContext",
    "EvidenceCritic",
    "EvidenceCriticError",
    "EvidenceCriticResult",
    "EvidenceCriticTrace",
    "EvidenceSupportFinding",
    "SemanticEvidenceAssessment",
    "SupportStatus",
    "CheckStatus",
    "ClaimValidationResult",
    "ClaimProvenance",
    "ConversionIssue",
    "DeterministicFinancialValidator",
    "FindingKind",
    "VerificationDecision",
    "VerificationEvidence",
    "VerificationFinding",
    "VerificationInput",
    "ValidationCheck",
    "ValidationResult",
    "to_verification_input",
]
