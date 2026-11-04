"""M6 pending candidates, Critics and source-bound deterministic verification decisions."""

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
from .decision_contracts import (
    DecisionError,
    InvestigationRequirement,
    RevisionInput,
    RevisionProposal,
    VerificationDecisionRecord,
    VerificationDecisionResult,
    VerificationDecisionTrace,
    VerificationLoopResult,
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
from .judge import VerificationJudge
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
from .verification_loop import BoundedVerificationLoop

__all__ = [
    "BoundedVerificationLoop",
    "DecisionError",
    "InvestigationRequirement",
    "RevisionInput",
    "RevisionProposal",
    "VerificationDecisionRecord",
    "VerificationDecisionResult",
    "VerificationDecisionTrace",
    "VerificationJudge",
    "VerificationLoopResult",
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
