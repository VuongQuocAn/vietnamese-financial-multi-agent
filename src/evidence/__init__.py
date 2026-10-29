"""Canonical facts, adapter M2 và local persistence; chưa có graph engine."""

from .adapter import fact_from_m2, facts_from_persisted_result
from .compatibility import (
    CompatibilityAssessment,
    CompatibilityReason,
    FinancialOperand,
    OperandReference,
    OperandRequirement,
    OperationCompatibilitySpec,
    PeriodPair,
    assess_compatibility,
)
from .contracts import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    FactConsistencyAssessment,
    ObservationIdentity,
    SemanticFactKey,
    SourceFact,
    TaskQualityContext,
    assess_fact_consistency,
)
from .repository import CanonicalFactRepository, ObservationConflict

__all__ = [
    "CanonicalFactRepository",
    "CanonicalFinancialFact",
    "CompatibilityAssessment",
    "CompatibilityReason",
    "EvidenceAnchor",
    "FactConsistencyAssessment",
    "FinancialOperand",
    "ObservationIdentity",
    "ObservationConflict",
    "OperandReference",
    "OperandRequirement",
    "OperationCompatibilitySpec",
    "PeriodPair",
    "SemanticFactKey",
    "SourceFact",
    "TaskQualityContext",
    "assess_compatibility",
    "assess_fact_consistency",
    "fact_from_m2",
    "facts_from_persisted_result",
]
