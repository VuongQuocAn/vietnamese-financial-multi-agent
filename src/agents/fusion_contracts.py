"""QA-01b: bounded multi-lane requirements; no financial or causal authority."""

import re
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..tools.question_understanding import normalize
from .document_qa_contracts import DocumentRequirement, document_intent


class FusionRequirement(FinancialModel):
    requirement_id: str
    original_span: str
    execution_question: str | None = None
    target: str | None = None
    lane: Literal["financial", "document", "relation", "unsupported"]
    kind: str
    dependencies: list[str] = Field(default_factory=list)
    evidence_needs: list[str] = Field(default_factory=list)
    verification_requirements: list[str] = Field(default_factory=list)
    support_status: Literal["pending", "accepted", "missing", "unsupported"] = "pending"
    missing_information: list[str] = Field(default_factory=list)
    reason: str | None = None
    document_requirement: DocumentRequirement | None = None


class FusionPlan(FinancialModel):
    question: str
    requirements: list[FusionRequirement]


class EvidenceFusionBundle(FinancialModel):
    context: dict
    plan: FusionPlan
    lane_results: list[dict] = Field(default_factory=list)
    graph_paths: list[dict] = Field(default_factory=list)
    original_citations: list[dict] = Field(default_factory=list)
    source_quality: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    relation_policy: Literal["independent_verified_components_only"] = (
        "independent_verified_components_only"
    )


def decompose(question):
    # Lazy import: catalog matching belongs to existing M7 contracts, not a second catalog.
    from ..outputs.qa_composer import understand_requirements

    result = []
    for span in re.split(r"[.?;!\n]+|\s+(?:và|đồng thời|kèm theo)\s+", question, flags=re.I):
        if not span.strip():
            continue
        text = normalize(span)
        execution = span
        if re.search(r"\bdoanh thu\b.*\b(tang hay giam|tang hoac giam)\b.*\bnam truoc\b", text):
            execution = "Tăng trưởng doanh thu"
        elif re.search(r"\bno phai tra\b.*\bchiem\b.*\bphan tram\b.*\btong tai san\b", text):
            execution = "Tỷ lệ nợ phải trả trên tổng tài sản"
        intent, specs = document_intent(span)
        causal = bool(
            re.search(
                r"\b(nguyen nhan|vi sao|tai sao|do dau|la do|dan den|chung to|"
                r"co phai(?: \w+){0,8} do|giai thich(?: \w+){0,6} bien dong)\b",
                text,
            )
        )
        if causal:
            # Asking whether a policy explains a movement is a relation request,
            # even when the same span also contains a searchable document topic.
            parts = [("relation", "causal_explanation", None, None, "unsupported_causal_inference")]
        elif specs and intent == "document":
            parts = [("document", "document_evidence", s.target, s, None) for s in specs]
        elif re.search(r"\b(thuyet minh|chinh sach|noi dung b09)\b", text) and not causal:
            # Topic is retained verbatim from the user; no inferred semantic relation.
            topic = re.split(r"\bvề\s+", span, flags=re.I)[-1].strip(" .?")
            topic = re.sub(r"^(?:các\s+)?khoản\s+", "", topic, flags=re.I)
            topic = re.sub(r"\s+(?:không|như thế nào|thế nào|ra sao).*$", "", topic, flags=re.I)
            if topic == span.strip(" .?"):
                topic = re.sub(r"^.*?chính sách\s+", "", topic, flags=re.I)
                topic = re.sub(r"\s+được thuyết minh.*$", "", topic, flags=re.I)
            spec = DocumentRequirement(
                target=normalize(topic), label=topic, query=topic, kind="source_excerpt"
            )
            parts = [("document", "document_summary", spec.target, spec, None)]
        elif re.search(r"\b(nguon goc|dan nguon|quan he bang chung)\b", text):
            parts = [("relation", "source_context", None, None, None)]
        else:
            parts = [
                (
                    "financial"
                    if r.kind in {"fact", "metric", "explanation", "limitations"}
                    else "unsupported",
                    r.kind,
                    r.target_id,
                    None,
                    r.reason,
                )
                for r in understand_requirements(execution)
            ]
        for lane, kind, target, spec, reason in parts:
            result.append(
                FusionRequirement(
                    requirement_id=f"U{len(result) + 1}",
                    original_span=span.strip(),
                    target=target,
                    execution_question=execution.strip(),
                    lane=lane,
                    kind=kind,
                    document_requirement=spec,
                    reason=reason,
                    support_status="unsupported"
                    if lane == "unsupported" or kind == "causal_explanation"
                    else "pending",
                    evidence_needs=["exact_source", "original_citations"],
                    verification_requirements=["M6_ACCEPT", "same_approved_filing"],
                )
            )
    for requirement in result:
        if requirement.lane == "relation":
            requirement.dependencies = [r.requirement_id for r in result if r.lane != "relation"]
    return FusionPlan(question=question, requirements=result)


def is_mixed(question):
    requirements = decompose(question).requirements
    lanes = {r.lane for r in requirements}
    unsupported_financial = any(
        r.reason in {"unsupported_formula", "unsupported_question_or_formula"} for r in requirements
    )
    return (
        "financial" in lanes
        and ("document" in lanes or "relation" in lanes)
        or "document" in lanes
        and unsupported_financial
    )
