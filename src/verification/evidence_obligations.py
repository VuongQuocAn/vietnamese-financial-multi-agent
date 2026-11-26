"""M6 replay of existing M5 selection/join records and scoped feedback."""

import re
from collections import Counter
from datetime import date
from itertools import permutations
from typing import get_args

from ..agents.evidence_coordination import (
    SelectionDemand,
    content_digest,
    join_observations,
    observation,
    select_observations,
)
from ..agents.integration_workspace import (
    QuestionRequirement,
    bind_need_results,
    expected_answers_for_verification,
)
from ..agents.lite_orchestrator import inventory
from ..agents.planner_contracts import PlannerContext
from ..evidence.composition import payload_sha256
from ..tools.financial_calculator import DynamicOperation
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
from ..tools.question_understanding import EXTRA_ALIASES, ITEM_RULES, normalize

_ACCOUNTING_ALIASES = [
    (normalize(alias), item)
    for item, rule in ITEM_RULES.items()
    for alias in (*rule.aliases, *EXTRA_ALIASES.get(item, ()))
]
_ACCOUNTING_ALIASES.append(
    (normalize("Lợi nhuận kế toán sau thuế thu nhập doanh nghiệp"), "b02.profit_after_tax")
)


def goal_context(context, claim):
    if not context.get("requirements"):
        return None
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
    if claim.python_execution:
        keys = list(dict.fromkeys(k for tid in owners for k in tasks[tid]["requirement_ids"]))
    return dict(
        proposed_requirement_ids=keys,
        local_requirements=context.get("requirements", []),
        owner_task_ids=owners,
        task_results=closure,
        **(
            {k: context.get(k) for k in ("expected_answers", "source_reporting_scope")}
            if "expected_answers" in context
            else {}
        ),
        **(
            {"question_understanding": context["question_understanding"]}
            if context.get("question_understanding")
            else {}
        ),
        **(
            dict(
                candidate_need_refs=context["candidate_need_refs"].get(claim.candidate_id, []),
                task_need_refs={tid: tasks[tid].get("need_refs", []) for tid in closure},
            )
            if "candidate_need_refs" in context
            else {}
        ),
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
            if "need_refs" in record:
                valid_needs = {
                    f"{r['requirement_id']}.need[{i}]"
                    for r in context["local_requirements"]
                    for i in range(len(r.get("evidence_needs", [])))
                }
                assigned = record["need_refs"]
                if (
                    not set(assigned) <= valid_needs
                    or assigned != context["task_need_refs"][tid]
                    or set(record.get("missing_need_inputs", {})) - set(assigned)
                ):
                    raise ValueError("need_reference_unknown")
                owned = {r["evidence_id"] for r in record.get("selected_observations", [])}
                owned.update(r["handle"] for r in record.get("source_context", []))
                receipt_refs = {ref for r in record["tool_results"] for ref in r["evidence_refs"]}
                retained = record.get("retained_observations", [])
                if any(
                    r["evidence_id"] not in receipt_refs & set(record.get("tool_evidence_ids", []))
                    for r in retained
                ):
                    raise ValueError("need_binding_source_not_owned")
                owned.update(r["evidence_id"] for r in retained)
                for receipt in record["tool_results"]:
                    if not set(receipt["need_refs"]) <= set(assigned):
                        raise ValueError("need_reference_unknown")
                    if not set(receipt["evidence_refs"]) <= owned:
                        raise ValueError("need_binding_source_not_owned")
                if record["need_bindings"] != bind_need_results(
                    assigned,
                    record["tool_results"],
                    record["missing_inputs"],
                    record.get("missing_need_inputs", {}),
                    owned_refs=owned,
                ):
                    raise ValueError("need_binding_result_mismatch")
            coordination = record.get("coordination", {})
            rows = list(record.get("selected_observations", []))
            rows.extend(record.get("retained_observations", []))
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
    if "candidate_need_refs" in context:
        assigned = {
            ref for tid in context["owner_task_ids"] for ref in context["task_need_refs"][tid]
        }
        expected = {
            ref
            for record in results.values()
            for ref, binding in record.get("need_bindings", {}).items()
            if ref in assigned
            and set(binding["evidence_refs"]) & {s.evidence_id for s in claim.supporting_evidence}
        }
        if set(context["candidate_need_refs"]) != expected:
            checks.append(("source", "fail", "candidate_need_binding_mismatch", None))
    if permitted and any(
        not any(s.reference.model_dump(mode="json") == row["reference"] for row in permitted)
        for s in claim.supporting_evidence
        if s.kind == "fact"
    ):
        checks.append(("selection", "fail", "operand_outside_selected_closure", None))
    return checks


def goal_output_type(requirement):
    """Read declared contract fields only; missing/contradictory metadata stays unknown."""
    kind = requirement.get("kind")
    if kind == "question":
        return "question"
    if requirement.get("answer_goal") == "synthesis" and kind in {"document", "explanation"}:
        return "synthesis"
    if kind == "explanation":
        return "explanation"
    if (
        requirement.get("aspect", "value") != "value"
        or requirement.get("interpretation")
        or requirement.get("answer_goal", "value") != "value"
    ):
        return None
    if kind == "fact" and not requirement.get("reasoning_operations"):
        return "value"
    if kind == "metric":
        operations = requirement.get("reasoning_operations", [])
        return (
            "comparison"
            if operations and operations[-1] in {"equal", "greater", "less"}
            else "calculation"
        )
    return None


def candidate_output(claim):
    """Describe the actual claim/proof output, never the raw model's desired statement."""
    calculation = claim.reasoning.calculation if claim.reasoning else None
    if calculation and claim.reasoning.claim_type == "derived_fact":
        unit = calculation.steps[-1].unit
        return dict(type="comparison" if unit == "boolean" else "calculation", units=[unit])
    if claim.kind == "fact":
        return dict(
            type="value", units=list(dict.fromkeys(s.unit for s in claim.supporting_evidence))
        )
    if claim.kind == "derived_metric" and any(s.calculation for s in claim.supporting_evidence):
        return dict(
            type="calculation",
            units=list(
                dict.fromkeys(
                    s.calculation.output_unit for s in claim.supporting_evidence if s.calculation
                )
            ),
        )
    if claim.kind == "supported_interpretation":
        return dict(type="explanation", units=[])
    return dict(type=None, units=[])


_OPERATOR_CODES = frozenset(get_args(DynamicOperation.model_fields["operator"].annotation))
_DIRECTED_OPERATORS = {
    "subtract",
    "divide",
    "ratio",
    "relative_difference",
    "percentage_change",
    "percentage_of",
    "greater",
    "less",
}


def _observation_key(identity):
    return (identity["document_id"], identity["snapshot_id"], identity["local_id"])


def _operand_order_mismatch(proof, requirement, calculation, intent):
    """Find a contradiction in a comparable directed graph using replayed EO receipts."""
    steps = intent["steps"]
    if not steps or any(s["operator"] not in _DIRECTED_OPERATORS for s in steps):
        return False
    declared = {s["operation_id"]: s for s in steps}
    actual = {s.operation.operation_id: s.operation for s in calculation.steps}
    pending = [(steps[-1]["operation_id"], calculation.steps[-1].operation.operation_id)]
    seen, leaves = set(), []
    while pending:
        expected_ref, actual_ref = pair = pending.pop()
        if pair in seen:
            continue
        seen.add(pair)
        if expected_ref not in declared:
            operand = calculation.operands.get(actual_ref)
            if not operand or not operand.reference.observation:
                return False
            leaves.append((expected_ref, operand.reference.observation))
            continue
        wanted, used = declared[expected_ref], actual.get(actual_ref)
        if not used or (wanted["operator"], wanted["period_relation"], len(wanted["inputs"])) != (
            used.operator,
            used.period_relation,
            len(used.inputs),
        ):
            return False
        pending.extend(zip(wanted["inputs"], used.inputs, strict=True))

    replayed_tasks = {
        c.expected.get("task_id")
        for c in proof.validation.claims[0].checks
        if c.status == "pass" and c.reason_code == "coordination_sources_replayed"
    }
    scoped_sources = {}
    for tid, result in proof.goal_context["task_results"].items():
        if tid not in replayed_tasks:
            continue
        rows = {
            row["evidence_id"]: row
            for key in ("selected_observations", "retained_observations")
            for row in result.get(key, [])
        }
        for i, scope in enumerate(intent["operand_constraints"]):
            ref = f"{requirement['requirement_id']}.need[{i}]"
            binding = result.get("need_bindings", {}).get(ref)
            if not binding or binding["missing_inputs"]:
                continue
            sources = scoped_sources.setdefault(f"N{i}", set())
            for eid in binding["evidence_refs"]:
                row = rows.get(eid)
                if (
                    row
                    and ("period" not in scope or scope["period"] == row["context"].get("period"))
                    and ("unit" not in scope or scope["unit"] == row["unit"])
                    and (identity := row["reference"].get("observation"))
                ):
                    sources.add(_observation_key(identity))
    return any(
        (sources := scoped_sources.get(ref))
        and _observation_key(identity.model_dump(mode="json")) not in sources
        for ref, identity in leaves
    )


def _calculation_operators(calculation):
    """Compare the proof without unused copies of steps in the final derivation."""
    operations = [step.operation for step in calculation.steps]
    used = {operations[-1].operation_id}
    signatures = {
        op.operation_id: (op.operator, tuple(op.inputs), op.period_relation) for op in operations
    }
    for op in reversed(operations):
        if op.operation_id in used:
            used.update(op.inputs)
    derived = {signatures[key] for key in used & signatures.keys()}
    return [
        op.operator
        for op in operations
        if op.operation_id in used or signatures[op.operation_id] not in derived
    ]


def _question_items(question, span):
    """Validate a model-selected span against the accounting lexicon."""
    text = " " + normalize(question) + " "
    term = " " + normalize(span) + " "
    spans = [(m.start(), m.end()) for m in re.finditer(re.escape(term), text)]
    matches = [
        (len(alias.split()), item)
        for alias, item in _ACCOUNTING_ALIASES
        for match in re.finditer(r"(?<= )" + re.escape(alias) + r"(?= )", text)
        if any(match.start() < end - 1 and start + 1 < match.end() for start, end in spans)
    ]
    longest = max((length for length, _ in matches), default=0)
    return {item for length, item in matches if length == longest}


def _question_dates(question):
    dates = set(re.findall(r"\b(?:19|20|21)\d{2}-\d{2}-\d{2}\b", question))
    try:
        dates.update(
            date(int(y), int(m), int(d)).isoformat()
            for d, m, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/((?:19|20|21)\d{2})\b", question)
        )
    except ValueError:
        return None
    return dates


def question_indicator_issue(question_span, label, canonical_item_id=None):
    """Compare the requested indicator with the selected source label."""
    expected = _question_items(question_span, question_span)
    actual = {canonical_item_id} if canonical_item_id else _question_items(label, label)
    if expected or actual:
        if expected != actual:
            return "question_indicator_mismatch"
    elif normalize(question_span) != normalize(label):
        return "question_indicator_unresolved"
    return None


def expected_indicator_matches(indicator, label, canonical_item_id=None):
    """Match accounting aliases or a source label with additional qualifiers."""
    expected = _question_items(indicator, indicator)
    actual = {canonical_item_id} if canonical_item_id else _question_items(label, label)
    if expected:
        return expected == actual
    term = normalize(indicator)
    return bool(term and f" {term} " in f" {normalize(label)} ")


def expected_period_matches(required, source):
    return required == source or len(required) == 4 and source.startswith(required + "-")


def numeric_proof_derivation(proof):
    """Read the method from verified source or Calculator evidence."""
    claim = proof.batch.claims[0]
    passed = {
        check.check_id for check in proof.validation.claims[0].checks if check.status == "pass"
    }
    if claim.reasoning and claim.reasoning.calculation:
        return "calculated" if "dynamic_calculation" in passed else None
    if "source" in passed and claim.supporting_evidence:
        return "direct" if claim.kind == "fact" else "evidence_based"
    return None


def independent_candidate_output(proof, output=None):
    output = output or candidate_output(proof.batch.claims[0])
    return dict(
        answer_type="numeric" if output["type"] in {"value", "calculation"} else output["type"],
        derivation=numeric_proof_derivation(proof),
        units=output["units"],
    )


def operand_binding_issue(need, source):
    """Compare the planned role with the period and indicator of the bound source."""
    label = normalize(need["label"])
    period = need["period"]
    dates = _question_dates(need["label"])
    if (period and not expected_period_matches(period, source.period)) or (
        dates is None or dates - {source.period}
    ):
        return "question_operand_period_mismatch"
    if boundary := re.search(r" (dau|cuoi) (?:nam|ky)(?: (\d{4}))?$", label):
        year = boundary[2] or source.period[:4]
        day = "-01-01" if boundary[1] == "dau" else "-12-31"
        if source.period != year + day:
            return "question_operand_period_mismatch"
        label = label[: boundary.start()]
    if dates:
        label = re.sub(r" (?:tai ngay |ngay )?\d{1,4} \d{1,2} \d{1,4}$", "", label)
    label = re.sub(rf" (?:nam )?{source.period[:4]}$", "", label)
    if not expected_indicator_matches(label, source.label, source.canonical_item_id):
        return "question_operand_indicator_mismatch"
    return None


def independent_numeric_issue(proof, requirement, expected):
    if expected["reporting_scope"] and (
        proof.goal_context.get("source_reporting_scope") != expected["reporting_scope"]
    ):
        return "question_reporting_scope_unverified"
    claim = proof.batch.claims[0]
    output = candidate_output(claim)
    actual = output["type"]
    sources = claim.supporting_evidence
    kind = requirement.get("answer_type")
    if kind is None:
        kind = requirement["output_type"]
        compatible = actual == kind or (actual == "explanation" and kind in {"entity", "date"})
    else:
        # Numeric covers either source values or scalar results of replayed arithmetic.
        actual_output = independent_candidate_output(proof, output)
        answer_type = actual_output["answer_type"]
        compatible = answer_type == kind or (
            answer_type == "explanation" and kind in {"entity", "date"}
        )
        if not actual_output["derivation"]:
            return "question_derivation_unverified"
        scope = proof.batch.context
        if any(
            getattr(item, field) != getattr(scope, field)
            for item in (claim, *sources)
            for field in ("company_id", "document_id", "snapshot_id")
        ):
            return "question_requirement_mismatch"
        if (unit := requirement.get("unit")) and unit.casefold() not in {
            value.casefold() for value in output["units"]
        }:
            return "question_output_unit_mismatch"
    if not compatible:
        return "question_output_type_mismatch"
    if any(
        not any(expected_period_matches(period, source.period) for source in sources)
        for period in requirement["periods"]
    ):
        return "question_period_mismatch"
    if actual == "value":
        if len(sources) != 1 or not expected_indicator_matches(
            requirement["indicator"], sources[0].label, sources[0].canonical_item_id
        ):
            return "question_indicator_mismatch"
        return question_period_issue(proof.batch.question, sources[0].period)
    if actual in {"calculation", "comparison"}:
        calculation = claim.reasoning.calculation if claim.reasoning else None
        if not calculation:
            return "question_terminal_proof_missing"
        terminal = calculation.steps[-1].operation
        planned = requirement["operator"]
        if (
            planned
            and planned != terminal.operator
            and {planned, terminal.operator}
            != {
                "divide",
                "ratio",
            }
        ):
            return "question_operation_mismatch"
        operations = {
            step.operation.operation_id: step.operation.inputs for step in calculation.steps
        }

        def leaves(key):
            if key not in operations:
                return [key]
            return [leaf for child in operations[key] for leaf in leaves(child)]

        by_id = {e.evidence_id: e for e in sources}
        operands = [by_id.get(key) for key in leaves(terminal.operation_id)]
        required = requirement["operands"]
        if "answer_type" in requirement:
            dates = _question_dates(proof.batch.question)
            if dates is None or dates - {s.period for s in sources}:
                return "question_operand_period_mismatch"
        if len(required) < 2 or len(required) != len(operands) or any(o is None for o in operands):
            return "question_operands_not_covered"
        if any("role" in need for need in required):
            if terminal.operator in _DIRECTED_OPERATORS:
                by_role = {need["role"]: need for need in required}
                if len(required) != 2 or set(by_role) != {"first", "second"}:
                    return "operand_role_conflict"
                required = [by_role["first"], by_role["second"]]
            else:
                allowed = [
                    {
                        i
                        for i, source in enumerate(operands)
                        if not operand_binding_issue(need, source)
                    }
                    for need in required
                ]
                if not any(
                    all(i in options for i, options in zip(order, allowed, strict=True))
                    for order in permutations(range(len(operands)))
                ):
                    return "operand_role_conflict"
                return None
        for need, source in zip(required, operands, strict=True):
            if issue := operand_binding_issue(need, source):
                return issue
    return None


def question_period_issue(question, period):
    dates = _question_dates(question)
    if dates is None:
        return "question_period_unresolved"
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", question))
    if (len(years) == 1 and period[:4] not in years) or (dates and period not in dates):
        return "question_period_mismatch"
    return None


def _question_fact_issue(proof, claim, slot):
    checks = getattr(proof.semantic, "question_operands", None) or []
    if len(checks) != 1 or len(claim.supporting_evidence) != 1 or checks[0].evidence_id != "E1":
        return "question_fact_binding_missing"
    check = checks[0]
    source = claim.supporting_evidence[0]
    term = normalize(check.question_span)
    span = normalize(slot["text"])
    if not term or f" {term} " not in f" {span} ":
        return "question_fact_span_unbound"
    if issue := question_indicator_issue(
        check.question_span, source.label, source.canonical_item_id
    ):
        return issue
    if not check.period or check.period != source.period:
        return "question_period_mismatch"
    return question_period_issue(proof.batch.question, source.period)


def question_operand_issue(proof, claim, slots):
    """Bind semantic operand roles to replayed leaves, periods and answer fragments."""
    calculation = claim.reasoning.calculation if claim.reasoning else None
    if not calculation:
        return None
    checks = getattr(proof.semantic, "question_operands", None)
    if not checks or any(not normalize(c.question_span) or not c.period for c in checks):
        return "question_operand_check_missing"
    terminal_leaves = {calculation.steps[-1].operation.operation_id}
    for step in reversed(calculation.steps):
        op = step.operation
        if op.operation_id in terminal_leaves:
            terminal_leaves.remove(op.operation_id)
            terminal_leaves.update(op.inputs)
    aliases = {
        f"E{i}": evidence
        for i, evidence in enumerate(claim.supporting_evidence, 1)
        if evidence.evidence_id in terminal_leaves
    }
    if not aliases or {c.evidence_id for c in checks} != aliases.keys():
        return "question_operands_not_covered"
    dates = _question_dates(proof.batch.question)
    if dates is None or (len(dates) > 1 and dates - {e.period for e in aliases.values()}):
        return "question_operand_period_mismatch"
    span_counts = Counter(normalize(check.question_span) for check in checks)
    for check in checks:
        source = aliases[check.evidence_id]
        if check.period and check.period != source.period:
            return "question_operand_period_mismatch"
        span = normalize(check.question_span)
        items = _question_items(check.question_span, check.question_span)
        if span_counts[span] == 1 and len(items) == 1 and source.canonical_item_id not in items:
            return "question_operand_indicator_mismatch"

    from .lite_contracts import question_parts

    parts = {
        key: f" {normalize(text)} " for key, text in question_parts(proof.batch.question).items()
    }
    answer_parts = {slot["part"] for slot in slots}
    anchors = [
        {part for part, text in parts.items() if f" {span} " in text} for span in span_counts
    ]
    if all(anchors) and not answer_parts.intersection(set().union(*anchors)):
        return "question_operands_only_premise"
    return None


def goal_binding_issue(proof, requirement, *, slot_id=None):
    """Check declared dimensions; semantic M6 owns indicator/period/formula meaning."""
    if not requirement:
        return "goal_context_missing"
    claim = proof.batch.claims[0]
    expected, actual = goal_output_type(requirement), candidate_output(claim)
    if expected == "question":
        if not QuestionRequirement.matches_request(
            requirement, proof.batch.question, proof.batch.context
        ):
            return "question_requirement_mismatch"
        if not actual["type"]:
            return "goal_output_type_unknown"
        coverage = getattr(proof, "goal_context", {}).get("question_coverage", {})
        expected_answers = proof.goal_context.get("expected_answers")
        revision = (
            expected_answers["revision"]
            if expected_answers is not None
            else payload_sha256(requirement)
        )
        if coverage.get("requirement_sha256") != revision:
            return "question_binding_revision_missing"
        slots = [
            slot
            for slot in coverage["slots"]
            if claim.candidate_id in slot["candidate_ids"]
            and (slot_id is None or slot["slot_id"] == slot_id)
        ]
        if expected_answers is not None:
            by_id = {r["requirement_id"]: r for r in expected_answers["requirements"]}
            issues = [
                independent_numeric_issue(proof, by_id[s["slot_id"]], expected_answers)
                for s in slots
            ]
        else:
            issues = [_numeric_slot_issue(proof, claim, actual["type"], slot) for slot in slots]
        return (None if None in issues else issues[0]) if issues else "question_claim_slot_unbound"
    if expected is None or actual["type"] is None:
        return "goal_output_type_unknown"
    if actual["type"] == "comparison" and expected != "comparison":
        return "goal_output_type_mismatch"
    if expected == "value" and (actual["type"] == "explanation" or "boolean" in actual["units"]):
        return "goal_output_type_mismatch"
    # A reported-value goal does not declare a calculation's output dimension.
    # Do not borrow a unit from its operands or let a semantic proposal supply it.
    if (
        expected == "value"
        and actual["type"] == "calculation"
        and not requirement.get("requested_unit")
    ):
        return "goal_numeric_output_unbound"
    calculation = claim.reasoning.calculation if claim.reasoning else None
    unit = requirement.get("requested_unit")
    if unit and unit not in actual["units"]:
        return "goal_unit_mismatch"
    intent = requirement.get("calculation_intent")
    if calculation:
        operations = [op.strip() for op in requirement.get("reasoning_operations", [])]
        if intent:
            operations = [step["operator"] for step in intent["steps"]]
        if expected in {"calculation", "comparison"} and not any(operations):
            return "goal_calculation_intent_missing"
        # A's prose describes intent, not operator IDs. The independent semantic
        # verdict must resolve that wording against the question and replayed proof.
        if _OPERATOR_CODES.intersection(operations) and operations != _calculation_operators(
            calculation
        ):
            return "goal_operations_mismatch"
    if requirement.get("period") and any(
        s.period != requirement["period"] for s in claim.supporting_evidence
    ):
        return "goal_period_mismatch"
    if periods := requirement.get("reasoning_periods"):
        if set(periods) != {s.period for s in claim.supporting_evidence}:
            return "goal_periods_mismatch"
    if (
        intent
        and calculation
        and expected in {"calculation", "comparison"}
        and actual["type"] in {"calculation", "comparison"}
        and _operand_order_mismatch(proof, requirement, calculation, intent)
    ):
        return "goal_operand_order_mismatch"
    return None


def _numeric_slot_issue(proof, claim, output_type, slot):
    if slot["role"] != "answer":
        return "question_role_conflict" if slot["role"] == "unresolved" else "question_premise_only"
    compatible = {
        "value": {"value"},
        "calculation": {"calculation", "value"},
        "comparison": {"comparison"},
        "explanation": {"entity", "explanation"},
    }
    if slot.get("kind") not in compatible.get(output_type, ()):
        return "question_output_type_mismatch"
    if output_type == "value":
        return _question_fact_issue(proof, claim, slot)
    if output_type == "calculation" and slot["kind"] == "value":
        # A bare operand span cannot license a calculated result.
        span = normalize(slot["text"])
        checks = getattr(proof.semantic, "question_operands", None) or ()
        if any(f" {span} " in f" {normalize(c.question_span)} " for c in checks):
            return "question_operand_only"
    return question_operand_issue(proof, claim, [slot])


def numeric_question_binding(proof, decision):
    from .lite_contracts import resolve_question_slots

    coverage = getattr(proof, "goal_context", {}).get("question_coverage", {})
    if not coverage:
        return {}
    claim = proof.batch.claims[0]
    requirement = next(
        (r for r in proof.goal_context["local_requirements"] if r.get("kind") == "question"), None
    )
    if not requirement:
        return {}
    expected = proof.goal_context.get("expected_answers") or {}
    method = (
        numeric_proof_derivation(proof)
        if any("answer_type" in row for row in expected.get("requirements", []))
        else None
    )
    return resolve_question_slots(
        coverage,
        claim,
        proof.semantic_input_sha256,
        lambda slot: (
            goal_binding_issue(proof, requirement, slot_id=slot["slot_id"])
            if decision.decision == "ACCEPT"
            and proof.semantic
            and proof.semantic.verdict == "SUPPORTED"
            else "question_truth_unverified"
        ),
        derivation=(lambda _: method) if method is not None else None,
    )


def question_grants(binding):
    return [grant for slot in binding.get("slots", ()) for grant in slot.get("bindings", ())]


def current_question_binding(entry, question, requirements, expected_answers=None):
    """Read a resolved Q1 grant from either ledger history under the same request revision."""
    proof = getattr(entry.history, "proof", entry.history)
    context = getattr(proof, "goal_context", {})
    saved = next(
        (r for r in context.get("local_requirements", []) if r.get("kind") == "question"), None
    )
    if (
        not saved
        or saved["text"] != question
        or saved not in requirements
        or entry.decision.decision != "ACCEPT"
    ):
        return {}
    binding = (
        context.get("verified_question", {})
        if hasattr(entry.history, "proof")
        else proof.goal_completion.get("Q1", {})
    )
    expected_answers = expected_answers_for_verification(expected_answers)
    if expected_answers != context.get("expected_answers"):
        return {}
    revision = (
        expected_answers["revision"] if expected_answers is not None else payload_sha256(saved)
    )
    if binding.get("requirement_sha256") != revision or not proof.semantic_input_sha256:
        return {}
    if any(
        grant["candidate_id"] != entry.identity.accepted_candidate_id
        or grant["proof_sha256"] != proof.semantic_input_sha256
        or grant["requirement_sha256"] != revision
        or grant["slot_id"] != slot["slot_id"]
        or slot["role"] != "answer"
        or grant["role"] != "answer"
        or grant["status"] != "verified"
        for slot in binding["slots"]
        for grant in slot["bindings"]
    ):
        return {}
    return binding


def _calculation_nodes(calculation):
    """Identify the root and its strict ancestors independently of local step IDs."""
    nodes = {
        eid: (content_digest(operand), set()) for eid, operand in calculation["operands"].items()
    }
    for step in calculation["steps"]:
        op = step["operation"]
        children = [nodes[ref] for ref in op["inputs"]]
        root = content_digest([op["operator"], op["period_relation"], [key for key, _ in children]])
        ancestors = set().union(*({key} | prior for key, prior in children))
        nodes[op["operation_id"]] = (root, ancestors)
    return nodes[calculation["steps"][-1]["operation"]["operation_id"]]


def _terminal_completion_issue(proofs, requirement, context):
    tasks = context.get("tasks", {})
    results = context.get("task_results", {})
    reasoners = {
        tid
        for tid, task in tasks.items()
        if task.get("role") == "reasoning"
        and requirement["requirement_id"] in task.get("requirement_ids", ())
        and not results.get(tid, {}).get("request_work")
    }
    if len(reasoners) < 2:
        return None
    dependencies = {}
    for tid in reasoners:
        pending = list(tasks[tid].get("depends_on", ()))
        seen = set()
        while pending:
            parent = pending.pop()
            if parent == tid or parent not in tasks:
                return "goal_terminal_graph_unresolved"
            if parent not in seen:
                seen.add(parent)
                pending.extend(tasks[parent].get("depends_on", ()))
        dependencies[tid] = seen & reasoners

    intermediate = set().union(*dependencies.values())
    if not intermediate:
        return None
    numeric = goal_output_type(requirement) in {"calculation", "comparison"}
    for tid in sorted(reasoners - intermediate):
        terminal = [p for p in proofs if tid in p.goal_context.get("owner_task_ids", ())]
        if not terminal:
            return "goal_terminal_result_missing"
        if not numeric:
            continue
        calculations = [
            p.batch.claims[0].reasoning.calculation
            for p in terminal
            if p.batch.claims[0].reasoning and p.batch.claims[0].reasoning.calculation
        ]
        if not calculations:
            return "goal_terminal_proof_missing"
        try:
            used = set().union(
                *(_calculation_nodes(calc.model_dump(mode="json"))[1] for calc in calculations)
            )
            for parent in dependencies[tid]:
                if not any(
                    _calculation_nodes(calc)[0] in used
                    for candidate in results.get(parent, {}).get("candidates", ())
                    if (calc := (candidate.get("reasoning") or {}).get("calculation"))
                ):
                    return "goal_terminal_dependency_not_used"
        except (KeyError, ValueError, IndexError, TypeError):
            return "goal_terminal_dependency_unresolved"
    return None


def goal_completion_issue(proofs, requirement, context=None):
    """Check the proposed group after truth/relevance; related premises alone are insufficient."""
    if not proofs or any(goal_binding_issue(p, requirement) for p in proofs):
        return "goal_output_not_aligned"
    expected = goal_output_type(requirement)
    types = {candidate_output(p.batch.claims[0])["type"] for p in proofs}
    if expected in {"calculation", "comparison", "explanation"} and expected not in types:
        return "goal_result_missing"
    if expected == "synthesis" and "explanation" not in types:
        return "goal_result_missing"
    if context and (issue := _terminal_completion_issue(proofs, requirement, context)):
        return issue
    needs = {
        f"{requirement['requirement_id']}.need[{i}]"
        for i in range(len(requirement.get("evidence_needs", [])))
    }
    covered = {ref for p in proofs for ref in p.goal_context.get("candidate_need_refs", [])}
    if needs - covered:
        return "goal_evidence_needs_incomplete"
    indicators = {
        s.canonical_item_id for p in proofs for s in p.batch.claims[0].supporting_evidence
    }
    if set(requirement.get("required_indicators", [])) - indicators:
        return "goal_indicators_incomplete"
    if any(p.batch.claims[0].missing_information for p in proofs):
        return "goal_candidate_incomplete"
    return None


def supported_goals(proof, decision):
    from .lite_runtime import direct_fact_goals, payload_digest, semantic_payload

    if decision.decision != "ACCEPT" or not getattr(proof, "goal_context", None):
        return []
    if goals := direct_fact_goals(proof):
        return goals
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
    requirements = {r["requirement_id"]: r for r in proof.goal_context["local_requirements"]}
    if "expected_answers" in proof.goal_context:
        return ["Q1"] if question_grants(proof.goal_context.get("verified_question", {})) else []
    return list(
        dict.fromkeys(
            r
            for r in semantic.supported_requirement_ids
            if r in requirements
            and (
                question_grants(proof.goal_context.get("verified_question", {}))
                if requirements[r].get("kind") == "question"
                else not goal_binding_issue(proof, requirements[r])
            )
        )
    )


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
    requirements = {r["requirement_id"]: r for r in context["local_requirements"]}
    for rid in missing:
        issue = goal_binding_issue(proof, requirements.get(rid))
        checks.append(("goal_support", issue or "goal_not_supported", refs))
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
            **(dict(request_work=result["request_work"]) if "request_work" in result else {}),
            **(
                {
                    key: result[key]
                    for key in (
                        "handle",
                        "input_results",
                        "need_refs",
                        "need_bindings",
                        "tool_results",
                    )
                }
                if "need_bindings" in result
                else {}
            ),
        )
    return dict(
        local_requirements=context["local_requirements"],
        proposed_requirement_ids=context["proposed_requirement_ids"],
        **(
            {k: context.get(k) for k in ("expected_answers", "source_reporting_scope")}
            if "expected_answers" in context
            else {}
        ),
        evidence_obligations=tasks,
        observations=observations,
        **(
            {"question_understanding": context["question_understanding"]}
            if context.get("question_understanding")
            else {}
        ),
        **(
            dict(
                candidate_need_refs=context["candidate_need_refs"],
                task_need_refs=context["task_need_refs"],
            )
            if "candidate_need_refs" in context
            else {}
        ),
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
