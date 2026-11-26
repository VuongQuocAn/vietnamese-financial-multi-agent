"""M6 document checks, critic decisions and replayable proof."""

import json
import re
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.document_qa_contracts import DocumentCandidate
from ..agents.planner_contracts import PlannerLLMMetadata
from ..core.llm_contracts import (
    GenerationParameters,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..evidence.composition import payload_sha256
from ..evidence.contracts import is_json_reference
from ..evidence.document_claim_support import consecutive, source_assertion
from .evidence_context import EvidenceContextBuilder
from .evidence_contracts import EvidenceContext
from .lite_contracts import (
    INDEPENDENT_VERIFIER_INSTRUCTION,
    QUESTION_COVERAGE_INSTRUCTION,
    VERIFIER_INSTRUCTION,
    GoalSemanticVerdict,
    bind_question_slots,
    independent_question_coverage,
    independent_verifier_schema,
    question_completion,
    question_parts,
    resolve_question_slots,
    semantic_output,
    verified_completion_refs,
    verifier_citations,
    verifier_output_schema,
)


class DocumentDecision(FinancialModel):
    policy_version: Literal["document_verification_v1"] = "document_verification_v1"
    original_claim: DocumentCandidate
    decision: Literal["ACCEPT", "INVESTIGATE", "ABSTAIN"]
    checks: dict[str, bool]
    evidence: list[EvidenceContext]
    reasons: list[str]
    caveats: list[str] = Field(default_factory=list)

    @property
    def supporting_references(self):
        return self.original_claim.references

    @property
    def supporting_citations(self):
        return self.original_claim.citations if self.decision == "ACCEPT" else []


class DocumentVerificationHistory(FinancialModel):
    version: Literal["document_verification_history_v1"] = "document_verification_history_v1"
    final: DocumentDecision
    goal_context: dict = Field(default_factory=dict)
    goal_completion: dict = Field(default_factory=dict)
    semantic: GoalSemanticVerdict | None = None
    semantic_input_sha256: str | None = None
    metadata: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)


def judge_document(claim, contexts):
    """Replay source, evidence fidelity and relation checks over resolved M4 proof."""
    refs = claim.references
    identity = (claim.source_document_id, claim.snapshot_id)
    source_ok = (
        len(contexts) == len(refs)
        and len({ref.model_dump_json() for ref in refs}) == len(refs)
        and all(
            ref.evidence is not None
            and (ref.evidence.document_id, ref.evidence.snapshot_id) == identity
            and ctx.reference == ref
            and ctx.available
            and (ctx.document_id, ctx.snapshot_id) == identity
            and bool(ctx.citations)
            and all(
                (c.document_id, c.snapshot_id) == identity
                and (c.source.document_id, c.source.snapshot_id) == identity
                and c.source.reference is not None
                and (
                    c.pdf_page == c.source.reference.anchor.page.page
                    or c.pdf_page is None
                    and is_json_reference(c.source.reference)
                )
                for c in ctx.citations
            )
            for ref, ctx in zip(refs, contexts, strict=True)
        )
    )
    citations_ok = source_ok and claim.citations == [c for ctx in contexts for c in ctx.citations]
    layout_ok = (
        source_ok
        and len({ctx.content.get("request_id") for ctx in contexts}) == 1
        and consecutive([ctx.citations for ctx in contexts])
    )
    assertion = (
        source_assertion(claim.requirement, [ctx.content for ctx in contexts])
        if layout_ok
        else None
    )
    relationship_ok = claim.claim_type != "entity_role" or bool(assertion and assertion[2])
    content_ok = (
        assertion is not None
        and assertion == (claim.quotations, claim.content, claim.person)
        and claim.claim_type == claim.requirement.kind
    )
    source_caveats = {c for ctx in contexts for c in ctx.caveats}
    checks = {
        "source_identity": source_ok,
        "original_citations": citations_ok,
        "source_continuity": layout_ok,
        "content_fidelity": content_ok,
        "relationship_support": relationship_ok,
        "source_caveats": set(claim.caveats) <= source_caveats,
    }
    # Matching saved OCR is insufficient when PDF review has identified a defect.
    # Reviews currently flag whole-page projections; fail closed for those records.
    # Leave clean v1 proofs unchanged so existing valid ledger entries still replay.
    if any(caveat.startswith("pdf_review:") for caveat in source_caveats):
        checks["source_quality"] = False
    from ..evidence.document_corrections import document_source_issues

    current_issues = document_source_issues(claim, contexts)
    if current_issues:
        checks["source_quality"] = False
        source_caveats.update(current_issues)
    reasons = [key for key, passed in checks.items() if not passed]
    return DocumentDecision(
        original_claim=claim,
        decision="ACCEPT" if not reasons else "INVESTIGATE" if citations_ok else "ABSTAIN",
        checks=checks,
        evidence=contexts,
        reasons=reasons or ["exact_source_support"],
        caveats=sorted(source_caveats),
    )


def verify_document_claim(
    claim,
    builder: EvidenceContextBuilder,
    manifest,
    company_id,
    snapshot_id,
    *,
    gateway=None,
    model=None,
    goal_context=None,
    related_claims=(),
):
    pinned = {
        pin.identity.model_dump_json()
        for source in manifest.sources
        if source.status == "verified"
        for pin in source.evidence
    }
    digest = payload_sha256(manifest.model_dump(mode="json"))
    if (
        (claim.document_id, claim.composition_id, claim.composition_sha256, claim.company_id)
        != (manifest.logical_document_id, manifest.composition_id, digest, company_id)
        or (snapshot_id is not None and claim.snapshot_id != snapshot_id)
        or any(
            ref.evidence is None or ref.evidence.model_dump_json() not in pinned
            for ref in claim.references
        )
    ):
        return DocumentVerificationHistory(final=judge_document(claim, []))
    history = DocumentVerificationHistory(
        final=judge_document(claim, builder.build_document(claim)), goal_context=goal_context or {}
    )
    if history.final.decision != "ACCEPT" or not history.goal_context:
        return history
    if gateway is None:
        history.final.decision = "INVESTIGATE"
        history.final.reasons = ["semantic_verification_required"]
        return history
    requirements = history.goal_context.get("local_requirements", [])
    if "proposed_requirement_ids" in history.goal_context:
        requirements = [
            r
            for r in requirements
            if r["requirement_id"] in history.goal_context["proposed_requirement_ids"]
        ]
    related = {
        row["candidate_id"]: row
        for row in related_claims
        if row["candidate_id"] != claim.candidate_id and row.get("truth_verified") is True
    }
    wire_ids = {"C1": claim.candidate_id} | {f"C{i}": key for i, key in enumerate(related, 2)}
    verified_related = {
        handle: goals
        for handle, cid in wire_ids.items()
        if handle != "C1"
        and (
            goals := [
                rid
                for rid in related[cid].get("supported_requirement_ids", [])
                if any(r["requirement_id"] == rid for r in requirements)
            ]
        )
    }
    question = next((r for r in requirements if r.get("kind") == "question"), None)
    expected = history.goal_context.get("expected_answers") if question else None
    parts = question_parts(question["text"]) if question and expected is None else {}
    schema = (
        independent_verifier_schema(["C1"], expected)
        if expected is not None
        else verifier_output_schema(
            ["C1"],
            [r["requirement_id"] for r in requirements],
            verified_related,
            question_level=bool(parts),
            part_ids=parts,
        )
    )
    if verified_related:
        history.goal_context = dict(
            history.goal_context,
            verified_related_claims={
                wire_ids[handle]: goals for handle, goals in verified_related.items()
            },
        )
    # Hash the original proof for replay of both saved and new ledger entries.
    history.semantic_input_sha256 = payload_sha256(
        dict(
            claim=claim.model_dump(mode="json"),
            evidence=[e.model_dump(mode="json") for e in history.final.evidence],
            **history.goal_context,
        )
    )
    scope = dict(
        company_id=claim.company_id, document_id=claim.document_id, snapshot_id=claim.snapshot_id
    )
    statement, evidence = claim.content, []
    for i, ctx in enumerate(history.final.evidence, 1):
        handle = f"E{i}"
        if text := ctx.content.get("text"):
            statement = statement.replace(text, f"[{handle}]")
        evidence.append(
            dict(
                evidence_id=handle,
                content=ctx.content,
                sources=verifier_citations(ctx.citations, scope),
            )
        )
    payload = dict(
        claim_id="C1",
        statement=statement,
        question=history.goal_context["question"],
        **({"question_parts": parts} if parts else {}),
        **(
            {"question_understanding": history.goal_context["question_understanding"]}
            if history.goal_context.get("question_understanding")
            else {}
        ),
        local_requirements=[
            {
                k: v
                for k, v in r.items()
                if k
                in {
                    "requirement_id",
                    "text",
                    "kind",
                    "period",
                    "requested_unit",
                    "source_scope",
                    "target_id",
                    "required_indicators",
                    "reasoning_operations",
                    "aspect",
                    "answer_goal",
                }
                and v not in (None, [], {})
            }
            for r in requirements
        ],
        scope=scope,
        evidence=evidence,
        limitations=history.final.caveats,
        related_claims=[
            dict(
                claim_id=handle,
                statement=related[cid]["statement"],
                truth_verified=True,
                supported_requirement_ids=verified_related.get(handle, []),
                **({"role": "premise"} if handle not in verified_related else {}),
                **(
                    {"question_slots": related[cid]["question_slots"]}
                    if related[cid].get("question_slots")
                    else {}
                ),
            )
            for handle, cid in wire_ids.items()
            if handle != "C1"
        ],
    )
    if expected is not None:
        payload["local_requirements"] = expected["requirements"]
        payload["requirement_revision"] = expected["revision"]
        payload.pop("question_understanding", None)
        for related_row in payload["related_claims"]:
            related_row["verified_requirement_ids"] = [
                slot["requirement_id"]
                for slot in related_row.pop("question_slots", [])
                if "requirement_id" in slot
            ]
            related_row.pop("supported_requirement_ids")
    response = gateway.generate(
        LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m6-document-" + uuid4().hex,
            model=model,
            messages=[
                Message(
                    role="system",
                    content=INDEPENDENT_VERIFIER_INSTRUCTION
                    if expected is not None
                    else (
                        VERIFIER_INSTRUCTION
                        + (QUESTION_COVERAGE_INSTRUCTION if parts else "")
                        + (
                            " Với hàng thuyết minh, ghép tên đối tượng với đúng giao dịch và đúng "
                            "cột thời điểm của cùng đối tượng. Số tăng, số giảm và số dư là vai trò "
                            "khác nhau. Giữ dấu gạch theo quy ước của bảng. Chỉ cấp binding cho vế "
                            "có đủ quan hệ từ nguồn. Với giá trị báo cáo trong bảng, chỉ cấp role "
                            "answer khi nhãn hàng đã trích và cột kỳ trực tiếp chứa chỉ tiêu cần hỏi."
                            if any(r.get("kind") == "question" for r in requirements)
                            else ""
                        )
                        + (
                            " question_understanding là phân tích sơ bộ. Câu hỏi nguyên văn quyết định "
                            "điều kiện định tính và mức đầy đủ nếu bản phân tích sai hoặc thiếu."
                            if history.goal_context.get("question_understanding")
                            else ""
                        )
                    ),
                ),
                Message(role="user", content=json.dumps(payload, ensure_ascii=False)),
            ],
            generation=GenerationParameters(temperature=0, max_output_tokens=1800),
            output_spec=OutputSpec(format="json", json_schema=schema),
            constraints=RequestConstraints(timeout_seconds=45),
        )
    )
    history.metadata = PlannerLLMMetadata(
        calls=1,
        status=response.status,
        model=model,
        usage=response.usage,
        cost=response.cost,
        error=response.error,
        provenance=response.provenance,
    )
    items = semantic_output(response)
    if len(items) == 1:
        try:
            item = items[0]
            if expected is not None:
                item = dict(item, supported_requirement_ids=[])
            verdict = GoalSemanticVerdict.model_validate(item)
            allowed = {r["requirement_id"] for r in requirements}
            if verdict.claim_id == "C1" and set(verdict.supported_requirement_ids) <= allowed:
                history.semantic = verdict.model_copy(update={"claim_id": claim.candidate_id})
        except ValueError:
            pass
    if history.semantic is None:
        history.final.decision = "INVESTIGATE"
        history.final.reasons = [
            "semantic_output_truncated"
            if response.finish_reason == "length"
            else "semantic_verdict_missing_or_invalid"
            if response.status in {"success", "malformed"}
            else "semantic_provider_failure"
        ]
    elif history.semantic.verdict != "SUPPORTED":
        history.final.decision = (
            "ABSTAIN" if history.semantic.verdict == "UNSUPPORTED" else "INVESTIGATE"
        )
        history.final.reasons = ["semantic_" + history.semantic.verdict.lower()]
    if expected is not None:
        coverage = independent_question_coverage(
            expected, response=response, schema=schema, wire_ids={"C1": claim.candidate_id}
        )
        history.goal_completion["Q1"] = question_completion(
            resolve_question_slots(
                coverage,
                claim,
                history.semantic_input_sha256,
                lambda slot: document_slot_issue(history, question, slot),
                derivation=(
                    lambda slot: "direct" if slot["kind"] == "numeric" else "evidence_based"
                )
                if any("answer_type" in row for row in expected["requirements"])
                else None,
            )
        )
        return history
    completion = verified_completion_refs(response, schema, verified_related)
    history.goal_completion = {
        r["requirement_id"]: dict(
            status="satisfied" if completion[r["requirement_id"]] else "unverified",
            candidate_ids=list(
                dict.fromkeys(wire_ids[ref] for ref in completion[r["requirement_id"]])
            ),
        )
        for r in requirements
        if response.status == "success"
        and response.finish_reason != "length"
        and isinstance(completion, dict)
        and isinstance(completion.get(r["requirement_id"]), list)
        and all(isinstance(ref, str) and ref in wire_ids for ref in completion[r["requirement_id"]])
    }
    if parts and (coverage := bind_question_slots(response, schema, parts, wire_ids, question)):
        history.goal_completion["Q1"] = question_completion(
            resolve_question_slots(
                coverage,
                claim,
                history.semantic_input_sha256,
                lambda slot: document_slot_issue(history, question, slot),
            )
        )
    return history


def document_slot_issue(history, requirement, slot):
    """Check Q1 against the selected quotation, independently of the retrieval query."""
    from ..accounting.automated_extraction import parse_vietnamese_number
    from .evidence_obligations import (
        expected_indicator_matches,
        expected_period_matches,
        question_indicator_issue,
        question_period_issue,
    )

    claim = history.final.original_claim
    scope = requirement["source_scope"]
    if (
        history.final.decision != "ACCEPT"
        or not history.semantic
        or history.semantic.verdict != "SUPPORTED"
    ):
        return "question_truth_unverified"
    if requirement["text"] != history.goal_context["question"] or any(
        scope[key] != getattr(claim, key) for key in ("company_id", "document_id", "snapshot_id")
    ):
        return "question_requirement_mismatch"
    expected = history.goal_context.get("expected_answers")
    answer = (
        next((r for r in expected["requirements"] if r["requirement_id"] == slot["slot_id"]), None)
        if expected is not None
        else None
    )
    reporting_scope = (
        expected["reporting_scope"] if expected is not None else scope["reporting_scope"]
    )
    if reporting_scope and history.goal_context.get("source_reporting_scope") != reporting_scope:
        return "question_reporting_scope_unverified"
    if slot["kind"] == "calculation" or (answer is not None and slot["kind"] == "comparison"):
        return "question_output_type_mismatch"
    if slot["kind"] not in {"value", "numeric"}:
        return None
    table = (
        history.final.evidence[0].content.get("literal_table")
        if len(history.final.evidence) == 1
        else None
    )
    if not table:
        return "question_document_value_cell_unbound"
    row = next((row for row in table["rows"] if " | ".join(row) == claim.quotations[-1]), None)
    if row is None or len(row) != len(table["columns"]):
        return "question_document_value_cell_unbound"
    if answer is not None:
        if not expected_indicator_matches(answer["indicator"], row[0]):
            return "question_indicator_mismatch"
    elif issue := question_indicator_issue(slot["text"], row[0]):
        return issue
    unit = answer.get("unit", "").casefold() if answer is not None else ""
    unit_marker = {"percent": "%", "ratio": "lần"}.get(unit, unit)
    periods = [
        period
        for header, cell in zip(table["columns"][1:], row[1:], strict=True)
        if parse_vietnamese_number(cell) is not None
        and (
            not unit_marker or unit_marker in f"{table.get('title', '')} {header} {cell}".casefold()
        )
        for period in re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?:-\d{2}-\d{2})?(?!\d)", header)
    ]
    if answer is not None and any(
        not any(expected_period_matches(wanted, source) for source in periods)
        for wanted in answer["periods"]
    ):
        return "question_period_mismatch"
    if not any(
        (scope["period"] is None or expected_period_matches(scope["period"], period))
        and question_period_issue(requirement["text"], period) is None
        for period in periods
    ):
        return "question_period_mismatch"
    return None


def document_supported_goals(history):
    from .evidence_obligations import question_grants

    if not history.semantic or history.semantic.verdict != "SUPPORTED":
        return []
    if "expected_answers" in history.goal_context:
        return ["Q1"] if question_grants(history.goal_completion.get("Q1", {})) else []
    return [
        rid
        for rid in history.semantic.supported_requirement_ids
        if rid != "Q1" or question_grants(history.goal_completion.get("Q1", {}))
    ]
