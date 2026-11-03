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

__all__ = [
    "CandidateClaim",
    "ClaimProvenance",
    "ConversionIssue",
    "FindingKind",
    "VerificationDecision",
    "VerificationEvidence",
    "VerificationFinding",
    "VerificationInput",
    "to_verification_input",
]
