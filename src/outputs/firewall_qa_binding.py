"""Request inventory checks, complementing M7-01's protected-slot validator.

No answer generation: derive only requirement selection/status from the original
request using the accepted catalog, ambiguity, scope and D03-B10 policies.
"""

import re

from ..agents.document_qa_contracts import document_intent
from ..evidence.document_claim_support import complete_declared_list
from ..tools.question_understanding import normalize, understand
from .qa_composer import (
    _assertion_signature,
    _matches_target,
    _unique,
    claim_scope,
    understand_requirements,
)
from .qa_contracts import GroundedAnswerPlan, QARequirement
from .qa_explanation import metric_explanation


def _document_inventory(request, entries, intent, specs):
    plan = GroundedAnswerPlan(
        requirements=[
            QARequirement(
                requirement_id=f"R{i}", kind="document", text=spec.label, target_id=spec.target
            )
            for i, spec in enumerate(specs, 1)
        ]
    )
    if intent == "mixed":
        plan.reasons.append("mixed_financial_document_unsupported")
        return plan, "unsupported"
    if not all(
        (
            request.document_id,
            request.company_id,
            request.composition_id,
            request.composition_sha256,
        )
    ):
        plan.missing_information.append("approved_document_composition_required")
        return plan, "clarification_required"
    parsed, issues = understand(request.question)
    if (
        request.period
        or parsed.period
        or request.reporting_scope
        or parsed.reporting_scope
        or set(issues)
        & {
            "invalid_period",
            "multiple_periods_unsupported",
            "non_annual_period_unsupported",
            "cross_document_comparison_blocked_D03_B10",
            "semantic_intent_requires_gateway",
        }
    ):
        plan.missing_information.append("document_reporting_context_unconfirmed")
        return plan, "clarification_required"
    for requirement in plan.requirements:
        matching = [
            e
            for e in entries
            if e.identity.kind == "document"
            and e.identity.document_id == request.document_id
            and e.identity.company_id == request.company_id
            and e.identity.composition_id == request.composition_id
            and e.identity.composition_sha256 == request.composition_sha256
            and (request.snapshot_id is None or e.identity.snapshot_id == request.snapshot_id)
            and e.accepted_claim.requirement in specs
            and (
                e.accepted_claim.claim_type != "source_excerpt"
                or complete_declared_list(e.accepted_claim.quotations)
            )
            and _matches_target(e, requirement)
        ]
        if not matching:
            requirement.reason = "no_verified_document_claim"
        elif len({_assertion_signature(e) for e in matching}) > 1 and not any(
            s.target == requirement.target_id and s.kind == "source_excerpt" for s in specs
        ):
            requirement.reason = "ambiguous_verified_claims"
        else:
            requirement.verified_claim_ids = sorted(e.identity.verified_claim_id for e in matching)[
                :3
            ]
    plan.selected_verified_claim_ids = [
        key for r in plan.requirements for key in r.verified_claim_ids
    ]
    if not plan.selected_verified_claim_ids:
        return plan, "abstained"
    return plan, "partial" if any(
        not r.verified_claim_ids for r in plan.requirements
    ) else "answered"


def request_inventory(request, entries):
    from ..agents.fusion_contracts import is_mixed

    if is_mixed(request.question) or request.adaptive_fusion_plan:
        return _fusion_inventory(request, entries)
    intent, specs = document_intent(request.question)
    if intent != "other":
        return _document_inventory(request, entries, intent, specs)
    if request.composition_id is not None or request.composition_sha256 is not None:
        return GroundedAnswerPlan(reasons=["composition_requires_document_question"]), "unsupported"
    parsed, issues = understand(request.question)
    plan = GroundedAnswerPlan(
        requirements=[
            r.model_copy(deep=True, update={"verified_claim_ids": [], "reason": None})
            for r in request.answer_requirements
        ]
        if request.answer_requirements
        else understand_requirements(request.question)
    )
    if "cross_document_comparison_blocked_D03_B10" in issues and not request.answer_requirements:
        plan.reasons.append("cross_document_comparison_blocked_D03_B10")
        return plan, "unsupported"
    if "ambiguous_reporting_scope" in issues:
        plan.reasons.append("ambiguous_reporting_scope")
        return plan, "clarification_required"
    if (
        parsed.period
        and request.period
        and parsed.period != request.period
        or parsed.reporting_year
        and request.period
        and request.period[:4] != str(parsed.reporting_year)
    ):
        plan.missing_information.append("period")
        return plan, "clarification_required"
    if (
        parsed.reporting_scope
        and request.reporting_scope
        and parsed.reporting_scope != request.reporting_scope
    ):
        plan.missing_information.append("reporting_scope")
        return plan, "clarification_required"
    if not any(r.kind in ("fact", "metric", "limitations") for r in plan.requirements):
        status = (
            "clarification_required"
            if any(r.kind == "ambiguous" for r in plan.requirements)
            else "unsupported"
        )
        return plan, status
    if any(
        r.kind == "ambiguous" and r.reason == "specify_catalog_target" for r in plan.requirements
    ):
        return plan, "clarification_required"
    if not request.snapshot_id or not (request.document_id or request.company_id):
        plan.missing_information = [
            k
            for k, v in (
                ("snapshot_id", request.snapshot_id),
                ("company_id_or_document_id", request.company_id or request.document_id),
            )
            if not v
        ]
        return plan, "clarification_required"
    if re.search(
        r"\bsnapshot\b|\brecovery\b|\bban goc\b|\boriginal\b", normalize(request.question)
    ):
        plan.missing_information.append("snapshot_origin_binding")
        return plan, "clarification_required"
    if (
        len(
            {
                (e.identity.company_id, e.identity.document_id, e.identity.snapshot_id)
                for e in entries
            }
        )
        > 1
    ):
        plan.missing_information.append("document_id")
        return plan, "clarification_required"
    scope = request.reporting_scope or parsed.reporting_scope
    for requirement in plan.requirements:
        if requirement.kind not in ("fact", "metric"):
            continue
        candidates = [
            e
            for e in entries
            if _matches_target(e, requirement)
            and (
                parsed.reporting_year is None or e.identity.period[:4] == str(parsed.reporting_year)
            )
            and (scope is None or claim_scope(e) == scope)
        ]
        if len({_assertion_signature(e) for e in candidates}) > 1:
            requirement.reason = "ambiguous_verified_claims"
        elif candidates:
            requirement.verified_claim_ids = sorted(
                e.identity.verified_claim_id for e in candidates
            )
        else:
            requirement.reason = (
                "no_supported_interpretation"
                if requirement.interpretation
                else "requested_scope_unconfirmed"
                if scope
                else "no_verified_claim"
            )
    # Explanation is authorized only by the selected value requirement, never
    # by arbitrary operands or another admitted calculation with a nearby label.
    for requirement in plan.requirements:
        if requirement.kind != "explanation":
            continue
        parent_ids = {
            key
            for parent in plan.requirements
            if parent.requirement_id in requirement.depends_on
            for key in parent.verified_claim_ids
        }
        candidates = [
            e
            for e in entries
            if e.identity.verified_claim_id in parent_ids and _matches_target(e, requirement)
        ]
        signatures = {
            metric_explanation(e, [requirement.aspect]).model_dump_json() for e in candidates
        }
        if len(signatures) == 1:
            requirement.verified_claim_ids = sorted(
                e.identity.verified_claim_id for e in candidates
            )
        else:
            requirement.reason = (
                "ambiguous_calculation_metadata"
                if signatures
                else "insufficient_admitted_calculation_metadata"
            )
    ids = _unique(k for r in plan.requirements for k in r.verified_claim_ids)
    years = {e.identity.period[:4] for e in entries if e.identity.verified_claim_id in ids}
    if len(years) > 1 or len(ids) > 12:
        for requirement in plan.requirements:
            requirement.verified_claim_ids = []
        plan.missing_information.append("period" if len(years) > 1 else "narrower_question")
        return plan, "clarification_required"
    for requirement in plan.requirements:
        if requirement.kind == "limitations":
            requirement.verified_claim_ids = ids.copy()
            if not ids:
                requirement.reason = "select_claims_for_limitations"
    plan.selected_verified_claim_ids = ids
    status = (
        ("partial" if any(not r.verified_claim_ids for r in plan.requirements) else "answered")
        if ids
        else "clarification_required"
        if any(r.reason == "ambiguous_verified_claims" for r in plan.requirements)
        else "abstained"
    )
    return plan, status


def _fusion_inventory(request, entries):
    from ..agents.fusion_contracts import decompose

    parsed, issues = understand(request.question)
    plan = GroundedAnswerPlan()
    if "cross_document_comparison_blocked_D03_B10" in issues:
        return GroundedAnswerPlan(
            reasons=["cross_document_comparison_blocked_D03_B10"]
        ), "unsupported"
    if not all(
        (
            request.document_id,
            request.company_id,
            request.snapshot_id,
            request.composition_id,
            request.composition_sha256,
            request.document_snapshots,
        )
    ):
        return GroundedAnswerPlan(
            missing_information=["approved_fusion_context_required"]
        ), "clarification_required"
    fusion = request.adaptive_fusion_plan or decompose(request.question)
    if fusion.question != request.question or len(fusion.requirements) > 12:
        return GroundedAnswerPlan(reasons=["fusion_plan_question_binding_invalid"]), "unsupported"
    for part in fusion.requirements:
        if part.lane == "financial":
            financial_question = part.execution_question or part.original_span
            if parsed.reporting_year:
                financial_question += f" năm {parsed.reporting_year}"
            sub = request.model_copy(
                update={
                    "question": financial_question,
                    "composition_id": None,
                    "composition_sha256": None,
                    "document_snapshots": [],
                    "adaptive_fusion_plan": None,
                    "fusion_answer_requirements": {},
                    "answer_requirements": request.fusion_answer_requirements.get(
                        part.requirement_id, []
                    ),
                }
            )
            child, _ = request_inventory(sub, [e for e in entries if e.identity.kind != "document"])
        elif part.lane == "document":
            sub = request.model_copy(
                update={
                    "question": part.original_span,
                    "snapshot_id": None,
                    "period": None,
                    "reporting_scope": None,
                }
            )
            child, _ = _document_inventory(
                sub,
                [
                    e
                    for e in entries
                    if e.identity.kind == "document"
                    and e.identity.snapshot_id in request.document_snapshots
                ],
                "document",
                [part.document_requirement],
            )
        elif part.kind == "source_context":
            child = GroundedAnswerPlan(
                requirements=[
                    QARequirement(
                        requirement_id=part.requirement_id,
                        kind="source_context",
                        text=part.original_span,
                        verified_claim_ids=plan.selected_verified_claim_ids.copy(),
                    )
                ]
            )
        else:
            child = GroundedAnswerPlan(
                requirements=[
                    QARequirement(
                        requirement_id=part.requirement_id,
                        kind="unsupported",
                        text=part.original_span,
                        reason=part.reason or "unsupported_inference",
                    )
                ]
            )
        for requirement in child.requirements:
            requirement.requirement_id = f"{part.requirement_id}:{requirement.requirement_id}"
            plan.requirements.append(requirement)
        plan.reasons.extend(child.reasons)
        plan.missing_information.extend(child.missing_information)
        plan.selected_verified_claim_ids = _unique(
            k for r in plan.requirements for k in r.verified_claim_ids
        )
    for requirement in plan.requirements:
        if requirement.kind == "source_context":
            requirement.verified_claim_ids = plan.selected_verified_claim_ids.copy()
            requirement.reason = (
                None if requirement.verified_claim_ids else "no_verified_source_context"
            )
    plan.selected_verified_claim_ids = _unique(
        k for r in plan.requirements for k in r.verified_claim_ids
    )
    return plan, (
        "partial" if any(not r.verified_claim_ids for r in plan.requirements) else "answered"
    ) if plan.selected_verified_claim_ids else "abstained"


def validate_qa_request_binding(request, response, entries):
    plan, status = request_inventory(request, entries)
    errors = []
    if request.question != response.question:
        errors.append("original_question_mismatch")
    if response.plan != plan:
        errors.append("original_request_requirement_inventory_mismatch")
    if response.status != status:
        errors.append("request_status_coverage_mismatch")
    reasons = _unique(
        plan.reasons
        + [r.reason for r in plan.requirements if not r.verified_claim_ids and r.reason]
    )
    if response.reasons != reasons or response.missing_information != plan.missing_information:
        errors.append("request_reasons_or_missing_information_mismatch")
    return errors
