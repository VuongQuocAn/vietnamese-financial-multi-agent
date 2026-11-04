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
from .financial_logic_critic import FinancialLogicCritic
from .logic_contracts import (
    ClaimLogicAssessment,
    FinancialLogicCriticResult,
    FinancialLogicError,
    FinancialLogicTrace,
    LogicFinding,
    LogicStatus,
    SemanticLogicAssessment,
)
from .validation_contracts import (
    CheckStatus,
    ClaimValidationResult,
    ValidationCheck,
    ValidationResult,
)
from .validators import DeterministicFinancialValidator

__all__ = [
    "ClaimLogicAssessment",
    "FinancialLogicCritic",
    "FinancialLogicCriticResult",
    "FinancialLogicError",
    "FinancialLogicTrace",
    "LogicFinding",
    "LogicStatus",
    "SemanticLogicAssessment",
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
