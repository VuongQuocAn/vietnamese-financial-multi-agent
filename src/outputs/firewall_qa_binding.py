"""Request inventory checks, complementing M7-01's protected-slot validator.

No answer generation: derive only requirement selection/status from the original
request using the accepted catalog, ambiguity, scope and D03-B10 policies.
"""

import re

from ..tools.question_understanding import normalize, understand
from .qa_composer import (
    _assertion_signature,
    _matches_target,
    _unique,
    claim_scope,
    understand_requirements,
)
from .qa_contracts import GroundedAnswerPlan
from .qa_explanation import metric_explanation


def request_inventory(request, entries):
    parsed, issues = understand(request.question)
    plan = GroundedAnswerPlan(requirements=understand_requirements(request.question))
    if "cross_document_comparison_blocked_D03_B10" in issues:
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
