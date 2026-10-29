"""Canonical observations và nguồn; không ingest, gộp hoặc xác minh số liệu."""

from typing import Annotated, Literal

from pydantic import Field
from vietnamese_financial_multi_agent.accounting.contracts import (
    FinancialContext,
    FinancialModel,
    FinancialSourceReference,
    FinancialValue,
)
from vietnamese_financial_multi_agent.accounting.quality import (
    QualityIssue,
    TaskType,
    UsageDecision,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    UnderstandingIssue,
)

Identity = Annotated[str, Field(min_length=1, pattern=r"\S")]


class ObservationIdentity(FinancialModel):
    """local_id chỉ unique trong (document_id, snapshot_id), không phải global ID."""

    model_config = {**FinancialModel.model_config, "frozen": True}
    document_id: Identity
    snapshot_id: Identity
    local_id: Identity


class SemanticFactKey(FinancialModel):
    """Khóa ngữ nghĩa đầy đủ; bằng nhau không cho phép deduplicate nguồn."""

    model_config = {**FinancialModel.model_config, "frozen": True}
    company_id: Identity
    canonical_item_id: Identity
    context: FinancialContext
    unit: Identity


class EvidenceAnchor(FinancialModel):
    # IDs do caller bind với tài liệu và extraction attempt/snapshot thực tế.
    document_id: Identity | None = None
    snapshot_id: Identity | None = None
    reference: FinancialSourceReference | None = None

    def source_key(self) -> tuple | None:
        """Selector được scope bởi document/snapshot/page; không suy từ row/column."""
        if not self.document_id or not self.snapshot_id or self.reference is None:
            return None
        r = self.reference
        a = r.anchor
        p = a.page
        return (
            self.document_id,
            self.snapshot_id,
            p.page,
            p.image,
            p.source_ref,
            a.element_id,
            a.table_id,
            a.cell_id,
            a.line_id,
            tuple(a.observed_bbox) if a.observed_bbox is not None else None,
            r.source_pointer,
        )


class TaskQualityContext(FinancialModel):
    """Annotation M2 có nguồn; không aggregate hoặc propagate decisions."""

    task_type: TaskType
    decision: UsageDecision
    evidence_ids: list[Identity]
    issues: list[QualityIssue] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class CanonicalFinancialFact(FinancialModel):
    # None giữ missing identity; không lấy year của RawPageIdentity làm kỳ tài chính.
    document_id: Identity | None = None
    snapshot_id: Identity | None = None
    local_observation_id: Identity | None = None
    company_id: Identity | None = None
    canonical_item_id: Identity | None = None
    source_item_code: str | None = None
    semantic_role: Identity | None = None
    value: FinancialValue
    context: FinancialContext
    sources: list[EvidenceAnchor] = Field(default_factory=list)
    resolution_issues: list[QualityIssue] = Field(default_factory=list)
    quality_context: list[TaskQualityContext] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False

    def observation_identity(self) -> ObservationIdentity | None:
        if not all((self.document_id, self.snapshot_id, self.local_observation_id)):
            return None
        return ObservationIdentity(
            document_id=self.document_id,
            snapshot_id=self.snapshot_id,
            local_id=self.local_observation_id,
        )

    def semantic_key(self) -> SemanticFactKey | None:
        c = self.context
        if (
            not all(
                (
                    self.company_id,
                    self.canonical_item_id,
                    c.statement_type,
                    c.period,
                    c.period_type,
                    c.reporting_scope,
                    c.currency,
                    self.value.unit,
                )
            )
            or c.scale is None
        ):
            return None
        # Raw label/code không thuộc khóa canonical. Không đổi context gốc.
        return SemanticFactKey(
            company_id=self.company_id,
            canonical_item_id=self.canonical_item_id,
            context=c.model_copy(update={"raw_item_label": None, "mapped_item_code": None}),
            unit=self.value.unit,
        )


# SourceFact và canonical fact là cùng một representation; mapping có thể thiếu.
SourceFact = CanonicalFinancialFact


class FactConsistencyAssessment(FinancialModel):
    status: Literal["consistent", "unresolved", "inconsistent"]
    issues: list[UnderstandingIssue]
    financial_fact_verified: Literal[False] = False


def assess_fact_consistency(fact: CanonicalFinancialFact) -> FactConsistencyAssessment:
    """Metadata checks thuần; không mở PDF, không sửa payload hay certify nguồn."""
    issues = []
    inconsistent = False

    def issue(code: str, path: list[str | int], *, conflict: bool = False) -> None:
        nonlocal inconsistent
        inconsistent |= conflict
        issues.append(UnderstandingIssue(code=code, path=path, message=code))

    if fact.observation_identity() is None:
        issue("missing_observation_identity", [])
    if fact.semantic_key() is None:
        issue("unresolved_semantic_context", ["context"])
    if fact.resolution_issues:
        issue("unresolved_operand_context", ["resolution_issues"])
    if not fact.sources:
        issue("missing_provenance", ["sources"])
    for i, source in enumerate(fact.sources):
        path = ["sources", i]
        for field in ("document_id", "snapshot_id"):
            actual, expected = getattr(source, field), getattr(fact, field)
            if not actual or not expected:
                issue("missing_source_identity", [*path, field])
            elif actual != expected:
                issue("source_identity_mismatch", [*path, field], conflict=True)
        if source.reference is None:
            issue("unresolved_source_reference", path)
            continue
        r = source.reference
        a = r.anchor
        if a.page.page < 1 or not a.page.image.strip():
            issue("invalid_page_reference", path, conflict=True)
        if a.status != "resolved":
            issue("source_reference_uncertain", path)
        if r.provenance_level == "cell" and not (a.cell_id and a.table_id):
            issue("unsupported_cell_provenance", path, conflict=True)
        if r.provenance_level == "element" and not (a.element_id or a.table_id or a.line_id):
            issue("unsupported_element_provenance", path, conflict=True)
    return FactConsistencyAssessment(
        status="inconsistent" if inconsistent else "unresolved" if issues else "consistent",
        issues=issues,
    )
