"""M2 → M3 thuần dữ liệu; không extraction, mapping hoặc quality assessment mới."""

import json
from collections.abc import Sequence
from copy import deepcopy

from ..accounting.quality import AssessableEvidence, QualityAssessment, QualityIssue
from .contracts import CanonicalFinancialFact, EvidenceAnchor, TaskQualityContext


def fact_from_m2(
    evidence: AssessableEvidence,
    *,
    document_id: str | None,
    snapshot_id: str | None,
    company_id: str | None = None,
    quality_context: Sequence[TaskQualityContext] = (),
) -> CanonicalFinancialFact:
    """IDs document/attempt do caller bind, local ID giữ nguyên evidence_id M2."""
    result = evidence.extraction
    identifiers = dict(
        document_id=document_id,
        snapshot_id=snapshot_id,
        local_observation_id=evidence.evidence_id,
        company_id=company_id,
    )
    # Blank là missing, không tạo ID thay thế từ source/filename/hash.
    identifiers = {k: v if v and v.strip() else None for k, v in identifiers.items()}
    issues = [
        QualityIssue(code="m2_extraction_issue", detail=i) for i in evidence.extraction_issues
    ]
    missing = {
        **identifiers,
        "canonical_mapping": evidence.canonical_item_id,
        "period": result.context.period,
        "period_type": result.context.period_type,
        "reporting_scope": result.context.reporting_scope,
    }
    issues.extend(
        QualityIssue(
            code=f"missing_{field}", detail="Not supplied by M2/caller; retained unresolved"
        )
        for field, value in missing.items()
        if not value
    )
    return CanonicalFinancialFact(
        **identifiers,
        canonical_item_id=evidence.canonical_item_id,
        source_item_code=evidence.source_item_code,
        raw_header=evidence.raw_header,
        source_metadata=deepcopy(evidence.source_metadata),
        value=result.value.model_copy(deep=True),
        context=result.context.model_copy(deep=True),
        sources=[
            EvidenceAnchor(
                document_id=identifiers["document_id"],
                snapshot_id=identifiers["snapshot_id"],
                reference=ref.model_copy(deep=True),
            )
            for ref in result.provenance
        ],
        resolution_issues=issues,
        quality_context=[q.model_copy(deep=True) for q in quality_context],
    )


def facts_from_persisted_result(
    result: dict, *, company_id: str | None = None
) -> list[CanonicalFinancialFact]:
    """Đọc projection quality đầy đủ của result.json W-04, không replay records.

    Chỉ copy item decisions đã có; aggregate task decision vẫn thuộc snapshot M2.
    Không suy company từ metadata symbol/name và không dùng projection items rút gọn.
    """
    if result.get("quality") is None:
        if result.get("items") or result.get("records"):
            raise ValueError("M2 quality evidence unavailable; explicit conversion required")
        return []
    quality = QualityAssessment.model_validate_json(json.dumps(result["quality"]))
    return [
        fact_from_m2(
            item.evidence,
            document_id=result.get("document_id"),
            snapshot_id=result.get("attempt_id"),
            company_id=company_id,
            quality_context=[
                TaskQualityContext(
                    task_type=quality.task_type,
                    decision=item.decision,
                    evidence_ids=[item.evidence.evidence_id]
                    if item.evidence.evidence_id.strip()
                    else [],
                    issues=item.issues,
                    caveats=item.caveats,
                )
            ],
        )
        for item in quality.items
    ]
