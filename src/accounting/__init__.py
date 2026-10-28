"""Contracts và resolver context tài chính có provenance."""

from .automated_extraction import (
    extract_financial_page,
    parse_vietnamese_number,
    run_automated_pdf,
    validate_automated_extraction,
)
from .context_resolution import (
    ContextCandidate,
    ContextEvidence,
    ContextFieldResolution,
    ContextResolution,
    evidence_from_unified_page,
    resolve_financial_context,
)
from .contracts import (
    FINANCIAL_NORMALIZATION_CONTRACT_VERSION,
    FinancialContext,
    FinancialNormalizationResult,
    FinancialSourceReference,
    FinancialValue,
    financial_normalization_json_schema,
)
from .item_mapping import (
    ITEM_CATALOG,
    ItemCandidate,
    ItemMapping,
    map_financial_items,
    map_item_label,
)
from .statement_resolution import (
    DocumentStatementTypes,
    StatementCandidate,
    StatementTypeResolution,
    recognize_document_statements,
    resolve_statement_type,
)
from .table_recovery import (
    LinkDecision,
    ManualReview,
    ReviewedCell,
    link_reviewed_candidate,
    recover_table_structure,
)
from .validation import validate_financial_quality

__all__ = [
    "extract_financial_page",
    "parse_vietnamese_number",
    "run_automated_pdf",
    "validate_automated_extraction",
    "LinkDecision",
    "ManualReview",
    "ReviewedCell",
    "link_reviewed_candidate",
    "recover_table_structure",
    "ITEM_CATALOG",
    "ItemCandidate",
    "ItemMapping",
    "map_financial_items",
    "map_item_label",
    "ContextCandidate",
    "ContextEvidence",
    "ContextFieldResolution",
    "ContextResolution",
    "FINANCIAL_NORMALIZATION_CONTRACT_VERSION",
    "FinancialContext",
    "FinancialNormalizationResult",
    "FinancialSourceReference",
    "FinancialValue",
    "DocumentStatementTypes",
    "StatementCandidate",
    "StatementTypeResolution",
    "evidence_from_unified_page",
    "financial_normalization_json_schema",
    "resolve_financial_context",
    "recognize_document_statements",
    "resolve_statement_type",
    "validate_financial_quality",
]
