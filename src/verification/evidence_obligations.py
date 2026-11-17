"""M6 replay of existing M5 selection/join records and scoped feedback."""

from ..agents.evidence_coordination import (
    SelectionDemand,
    content_digest,
    join_observations,
    observation,
    select_observations,
)
from ..agents.lite_orchestrator import inventory
from ..agents.planner_contracts import PlannerContext
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest


def goal_context(context, claim):
    tasks, results = context.get("tasks", {}), context.get("task_results", {})
    owners = [o.execution_id for o in claim.provenance.origins if o.execution_id in tasks]
    pending, closure = list(owners), {}
    while pending:
        tid = pending.pop(0)
        if tid in closure:
            continue
        closure[tid] = results.get(tid, {})
        pending.extend(tasks.get(tid, {}).get("depends_on", []))
    keys = context.get("candidate_requirements", {}).get(claim.candidate_id, [])
    return dict(
        proposed_requirement_ids=keys,
        local_requirements=[
            r for r in context.get("requirements", []) if r["requirement_id"] in keys
        ],
        owner_task_ids=owners,
        task_results=closure,
    )


def replay_obligations(catalog, batch, context):
    """Return checks using catalog values, never trusting M5's numeric records."""
    claim = batch.claims[0]
    results = context.get("task_results", {})
    if not results:
        return []
    tools = FinancialRetrievalTools(catalog)
    sources = inventory(
        catalog,
        PlannerContext(
            company_id=claim.company_id,
            document_id=claim.document_id,
            snapshot_id=claim.snapshot_id,
        ),
    )
    checks = []
    for tid, record in results.items():
        try:
            if not record or record["digest"] != content_digest(
                {k: v for k, v in record.items() if k != "digest"}
            ):
                raise ValueError("task_result_digest_mismatch")
            for parent in record["input_results"]:
                expected = results.get(parent["task_id"], {})
                if any(parent[k] != expected.get(k) for k in ("handle", "revision", "digest")):
                    raise ValueError("stale_dependency_result")
            coordination = record.get("coordination", {})
            rows = list(record.get("selected_observations", []))
            selection = coordination.get("selection")
            if selection:
                rows.extend(selection["domain"])
            for join in coordination.get("joins", []):
                rows.extend(join["left"] + join["right"])
            for row in rows:
                identity = row["reference"]["observation"]
                response = tools.get_financial_fact(
                    GetFinancialFactRequest(
                        document_id=claim.document_id,
                        snapshot_id=claim.snapshot_id,
                        local_observation_id=identity["local_id"],
                    )
                )
                if (
                    response.status != "found"
                    or len(response.matches) != 1
                    or observation(response.matches[0]) != row
                ):
                    raise ValueError("selection_source_mismatch")
            checks.append(("source", "pass", "coordination_sources_replayed", tid))
            if selection:
                selected, expected = select_observations(
                    SelectionDemand.model_validate(selection["selection"]),
                    selection["domain"],
                    sources,
                )
                if expected != selection or selected != record["selected_observations"]:
                    raise ValueError("selection_replay_mismatch")
                checks.append(
                    ("selection", "pass", "selection_domain_and_comparator_replayed", tid)
                )
            for join in coordination.get("joins", []):
                parent = next(
                    (
                        r
                        for r in results.values()
                        if r.get("handle") == join["from_result"]["handle"]
                    ),
                    None,
                )
                if (
                    not parent
                    or join_observations(parent, join["right"]) != join
                    or join["status"] != "matched"
                ):
                    raise ValueError("entity_join_replay_mismatch")
                if join["right"] != record["selected_observations"]:
                    raise ValueError("entity_join_selected_rows_mismatch")
                checks.append(("entity_join", "pass", "exact_context_join_replayed", tid))
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            reason = str(error) if isinstance(error, ValueError) else "coordination_input_invalid"
            check = (
                "entity_join"
                if "join" in reason
                else "selection"
                if "selection" in reason
                else "source"
            )
            checks.append((check, "fail", reason, tid))
    permitted = [row for r in results.values() for row in r.get("selected_observations", [])]
    if permitted and any(
        not any(s.reference.model_dump(mode="json") == row["reference"] for row in permitted)
        for s in claim.supporting_evidence
        if s.kind == "fact"
    ):
        checks.append(("selection", "fail", "operand_outside_selected_closure", None))
    return checks


def supported_goals(proof, decision):
    from .lite_runtime import payload_digest, semantic_payload

    if decision.decision != "ACCEPT" or not getattr(proof, "goal_context", None):
        return []
    semantic = proof.semantic
    if (
        not semantic
        or semantic.verdict != "SUPPORTED"
        or proof.metadata.status != "success"
        or proof.metadata.calls != 1
    ):
        return []
    if proof.semantic_input_sha256 != payload_digest(
        semantic_payload(proof.batch, proof.batch.claims[0], proof.goal_context)
    ):
        return []
    allowed = proof.goal_context["proposed_requirement_ids"]
    return list(dict.fromkeys(r for r in semantic.supported_requirement_ids if r in allowed))


def feedback(proof, decision):
    claim = proof.batch.claims[0]
    context = proof.goal_context
    supported = supported_goals(proof, decision)
    issues = []
    refs = [s.evidence_id for s in claim.supporting_evidence]
    checks = [
        (c.check_id, c.reason_code, refs)
        for c in proof.validation.claims[0].checks
        if c.status in {"fail", "undetermined"}
        and c.reason_code != "reporting_scope_unresolved"
        and not (c.check_id == "semantic_conclusion" and decision.decision == "ACCEPT")
    ]
    if proof.semantic:
        checks.extend((i.check, i.reason_code, i.input_refs or refs) for i in proof.semantic.issues)
    if decision.decision != "ACCEPT" and not checks:
        checks.append(("semantic_conclusion", decision.reason_codes[0], refs))
    missing = [r for r in context["proposed_requirement_ids"] if r not in supported]
    if missing:
        checks.append(("goal_support", "goal_not_supported", refs))
    for check, reason, inputs in checks:
        action = (
            "revise_selection"
            if check == "selection"
            else "resolve_entity"
            if check == "entity_join"
            else "revise_binding"
            if check == "goal_support"
            else "revise_formula"
            if check in {"formula", "dynamic_calculation", "numeric"}
            else "retrieve_evidence"
        )
        issues.append(
            dict(
                obligation_id=f"{claim.candidate_id}:{check}",
                check=check,
                reason_code=reason,
                input_refs=inputs,
                requirement_ids=missing
                if check == "goal_support"
                else context["proposed_requirement_ids"],
                action=action,
                repairable=not bool(proof.semantic_error),
            )
        )
    return dict(
        candidate_id=claim.candidate_id,
        candidate_version=1,
        task_ids=context["owner_task_ids"],
        decision=decision.decision,
        supported_requirement_ids=supported,
        issues=issues,
    )


def semantic_goal_context(context):
    """Deduplicate replayed observations; preserve domain, join and source anchors."""
    observations, tasks = {}, {}

    def refs(rows):
        for row in rows:
            key = row["evidence_id"]
            if key not in observations:
                sources = {}
                for citation in row["citations"]:
                    reference = citation["source"]["reference"]
                    page = reference["anchor"]["page"]["page"]
                    source = sources.setdefault(page, dict(page=page, pointers=[], limitations=[]))
                    source["pointers"].append(reference["source_pointer"])
                    source["limitations"] = sorted(
                        set(source["limitations"] + citation["limitations"])
                    )
                observations[key] = {
                    k: row[k]
                    for k in (
                        "source_digest",
                        "item",
                        "label",
                        "header",
                        "raw_value",
                        "value",
                        "unit",
                        "context",
                        "quality",
                        "issues",
                        "parser",
                    )
                }
                observations[key]["sources"] = list(sources.values())
        return [r["evidence_id"] for r in rows]

    for tid, result in context["task_results"].items():
        coordination = result.get("coordination", {})
        selection = coordination.get("selection")
        tasks[tid] = dict(
            revision=result.get("revision"),
            digest=result.get("digest"),
            selected_ids=refs(result.get("selected_observations", [])),
            selection=(
                {k: v for k, v in selection.items() if k != "domain"}
                | dict(domain_ids=refs(selection["domain"]))
            )
            if selection
            else None,
            joins=[
                {k: v for k, v in join.items() if k not in {"left", "right"}}
                | dict(left_ids=refs(join["left"]), right_ids=refs(join["right"]))
                for join in coordination.get("joins", [])
            ],
            retrieval_lineage=coordination.get("retrieval_lineage", []),
        )
    return dict(
        local_requirements=context["local_requirements"],
        proposed_requirement_ids=context["proposed_requirement_ids"],
        evidence_obligations=tasks,
        observations=observations,
    )


def current_goal_support(entry, question, requirements):
    """Historical truth never grants coverage to changed/reordered local goals."""
    from .lite_contracts import LiteVerificationHistoryV2

    if not isinstance(entry.history, LiteVerificationHistoryV2):
        return []
    proof = entry.history.proof
    if proof.batch.question != question:
        return []
    current = {r["requirement_id"]: r for r in requirements}
    saved = {r["requirement_id"]: r for r in proof.goal_context["local_requirements"]}
    return [
        rid
        for rid in supported_goals(proof, entry.decision)
        if saved.get(rid) == current.get(rid) and rid in current
    ]
