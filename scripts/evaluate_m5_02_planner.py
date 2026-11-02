"""BBS Planner evaluation: independent references, bounded live calls, no execution."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median

from evaluate_d04_closure import save
from evaluate_m4_05_qa import setup
from evaluate_m5_01_contracts import protected as previous_protected
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    EvidenceAwareQueryPlanner,
    PlannerContext,
    PlannerResult,
)
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.question_understanding import ITEM_RULES


def protected(root):
    hashes = previous_protected(root)
    for folder in ("M5-01-scope-final",):
        hashes.update(
            (p.relative_to(root).as_posix(), digest(p))
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return dict(sorted(hashes.items()))


def reference_for(case, data, scopes, recovery):
    """Không gọi Planner/parser/validate_plan để tạo reference.

    Human manifest chốt targets/intent/status; operands/periods từ persisted
    approved policies + metric bindings, không từ generated proposal/plan.
    """
    reference = dict(
        status=case["status"],
        intents=case.get("intents", [case["intent"]]),
        evidence=[],
        optional_evidence=[],
        tools=[],
        optional_tools=[],
        facts=[],
        formulas=case.get("formulas", []),
    )
    materialized = case["status"] == "planned" or case.get("materialized", False)
    if not materialized:
        return reference
    scope = dict(scopes[case["year"]])
    if case.get("snapshot") == "recovery":
        scope["snapshot_id"] = recovery.snapshot_id
    reference.update(scope)
    signatures, tools, optional = set(), set(), set()
    facts = set()
    for item in case.get("items", []):
        rule = ITEM_RULES[item]
        period = f"{case['year']}-12-31" if rule.statement_type == "B01" else str(case["year"])
        facts.add((item, period))
        signatures.add(("citations", item, period))
        tools |= {"find_financial_facts", "get_evidence_sources"}
    for formula in case.get("formulas", []):
        policies = [p for p in data["formula_policies"] if p.formula_id == formula]
        assert len(policies) == 1
        metrics = [
            m
            for m in data["metrics"]
            if m.definition.name == formula
            and m.request.document_id == scope["document_id"]
            and m.request.snapshot_id == scope["snapshot_id"]
        ]
        assert len(metrics) == 1
        metric = metrics[0]
        for operand in policies[0].operands:
            facts.add((operand.canonical_item_id, metric.request.operand_periods[operand.role]))
            optional.add(
                (
                    "citations",
                    operand.canonical_item_id,
                    metric.request.operand_periods[operand.role],
                )
            )
        for kind in ("formula", "compatibility", "metric", "lineage", "citations"):
            signatures.add((kind, formula, ""))
        tools |= {
            "find_financial_facts",
            "calculate_financial_metric",
            "get_metric_evidence_lineage",
        }
    for item, period in facts:
        rows = [
            f
            for f in data["facts"]
            if f.document_id == scope["document_id"]
            and f.snapshot_id == scope["snapshot_id"]
            and f.canonical_item_id == item
            and f.context.period == period
        ]
        assert len(rows) == 1, (case["id"], item, period)
        signatures.add(("fact", item, period))
    if case["intent"] == "multi_step_analysis":
        signatures.add(("analysis_bundle", "", ""))
    reference.update(
        evidence=sorted(signatures),
        tools=sorted(tools),
        facts=sorted(facts),
        optional_evidence=sorted(optional),
        optional_tools=["get_evidence_sources"] if case.get("formulas") else [],
    )
    return reference


def evidence_signatures(plan):
    requirements = {r.requirement_id: r for r in plan.requirements}

    def target(req):
        if req.formula_id:
            return req.formula_id, ""
        if req.evidence_type == "fact":
            return req.canonical_item_id, req.selector.period
        if req.evidence_type in {"lineage", "citations"} and len(req.dependencies) == 1:
            return target(requirements[req.dependencies[0]])
        return "", ""

    return {
        (r.evidence_type, *target(r)) for r in plan.requirements if r.evidence_type != "snapshot"
    }


def assess(result, reference):
    expected = {tuple(s) for s in reference["evidence"]}
    acceptable = expected | {tuple(s) for s in reference.get("optional_evidence", [])}
    actual = evidence_signatures(result.plan) if result.plan else set()
    eligible = result.validation.execution_eligible if result.validation else False
    dependency_valid = False
    constraints = not result.plan
    if result.plan:
        plan = result.plan
        producers = {e: s for s in plan.steps for e in s.output_evidence_ids}
        dependency_valid = all(
            producers[r].step_id in s.prerequisite_step_ids
            for s in plan.steps
            for r in s.required_evidence_ids
            if r in producers
        )
        # Calculation phải qua gate, gate cần tất cả operand facts; sources/lineage
        # dùng đúng typed binding. Structural validity một mình chưa là semantic score.
        dependency_valid &= all(
            any(
                t.step_type == "check_compatibility" and t.step_id in s.prerequisite_step_ids
                for t in plan.steps
            )
            for s in plan.steps
            if s.tool == "calculate_financial_metric"
        )
        constraints = all(
            s.selector.document_id == reference.get("document_id")
            and s.selector.snapshot_id == reference.get("snapshot_id")
            for s in plan.steps
        )
        constraints &= {
            (r.canonical_item_id, r.selector.period)
            for r in plan.requirements
            if r.evidence_type == "fact"
        } == {tuple(f) for f in reference["facts"]}
    intent = result.query.intent in reference["intents"]
    tools = sorted({s.tool for s in result.plan.steps if s.tool}) if result.plan else []
    tool_correct = (
        set(reference["tools"])
        <= set(tools)
        <= set(reference["tools"]) | set(reference.get("optional_tools", []))
    )
    disposition = result.status == reference["status"]
    evidence_correct = expected <= actual <= acceptable
    return dict(
        intent_correct=intent,
        proposal_intent_correct=result.proposal.intent in reference["intents"]
        if result.proposal
        else False,
        tools_correct=tool_correct,
        disposition_correct=disposition,
        evidence_tp=len(actual & acceptable),
        evidence_required_tp=len(actual & expected),
        evidence_fp=len(actual - acceptable),
        evidence_fn=len(expected - actual),
        evidence_exact=actual == expected,
        evidence_correct=evidence_correct,
        minimal_tools_exact=tools == reference["tools"],
        dependency_valid=bool(dependency_valid),
        structurally_valid=result.validation.structurally_valid if result.validation else None,
        execution_eligible=eligible,
        constraints_correct=bool(constraints),
        correct=bool(
            intent
            and tool_correct
            and disposition
            and evidence_correct
            and constraints
            and (not expected or dependency_valid)
        ),
    )


def evaluate(root, output, *, live=False, case_ids=None, manifest=None, replay_from=None):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = protected(root)
    save(output / "hashes-before.json", hashes)
    data, scopes, recovery, documents = setup(root)
    before = [r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]]
    questions = load(
        manifest
        or root
        / ("evaluation/m5-02-live-questions.json" if live else "evaluation/m5-02-questions.json")
    )
    if case_ids:
        assert set(case_ids) <= {c["id"] for c in questions}
        questions = [c for c in questions if c["id"] in case_ids]
    assert not live or 1 <= len(questions) <= 8
    references = {c["id"]: reference_for(c, data, scopes, recovery) for c in questions}
    save(output / "references.json", references)
    adapter, calls, rows = None, [], []
    recorded = load(replay_from / "gateway-responses.json") if replay_from else []
    if replay_from:
        assert not live and len(recorded) == len(questions)
    if live:
        adapter, credential = create_qa_adapter(root)
        save(
            output / "credential-metadata.json",
            dict(
                source=credential.source,
                key_count=credential.key_count,
                key_index=credential.key_index,
            ),
        )

    def transport(request):
        if len(calls) >= len(questions):
            raise RuntimeError("live_request_budget_exhausted")
        attempt = dict(request_id=request.request_id, outcome="started")
        calls.append(attempt)
        save(output / f"attempt-{len(calls):02d}.json", attempt)
        if replay_from:
            payload = dict(recorded[len(calls) - 1]["response"])
            attempt["original_request_id"] = payload["request_id"]
            payload.update(request_id=request.request_id, correlation=None)
            response = LLMResponse.model_validate(payload)
        else:
            response = adapter(request)
        attempt.update(outcome="returned", response=response.export())
        save(output / f"gateway-{len(calls):02d}.json", attempt)
        return response

    api = EvidenceAwareQueryPlanner(
        SnapshotCatalog(**data),
        documents,
        SharedLLMGateway({"gemini": transport}) if live or replay_from else None,
    )
    try:
        for case in questions:
            result = api.plan(
                case["question"],
                PlannerContext(mode="gemini" if live or replay_from else "deterministic"),
            )
            assert PlannerResult.model_validate_json(result.model_dump_json()) == result
            row = dict(
                id=case["id"],
                group=case["group"],
                question=case["question"],
                status=result.status,
                **assess(result, references[case["id"]]),
                latency_ms=result.latency_ms,
                llm=result.llm.model_dump(mode="json"),
            )
            rows.append(row)
            save(output / f"response-{case['id']}.json", result.model_dump(mode="json"))
            save(output / f"score-{case['id']}.json", row)
            print(
                json.dumps(
                    {
                        k: row[k]
                        for k in (
                            "id",
                            "status",
                            "correct",
                            "intent_correct",
                            "tools_correct",
                            "evidence_exact",
                            "dependency_valid",
                        )
                    }
                ),
                flush=True,
            )
            if result.llm.error:
                break
    finally:
        if adapter:
            adapter.close()
        save(output / "scores.json", rows)
        save(output / "gateway-responses.json", calls)
        after = {p: digest(root / p) for p in hashes}
        save(output / "hashes-after.json", after)
        assert hashes == after
        assert before == [
            r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]
        ]
    plans = [r for r in rows if r["structurally_valid"] is not None]
    expected_plans = sum(bool(references[r["id"]]["evidence"]) for r in rows)
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("evidence_tp", "evidence_fp", "evidence_fn"))
    required_tp = sum(r["evidence_required_tp"] for r in rows)
    negatives = [r for r in rows if references[r["id"]]["status"] != "planned"]

    def fraction(n, d):
        return dict(numerator=n, denominator=d, value=n / d if d else None)

    summary = dict(
        mode="live_Gemini"
        if live
        else "offline_saved_Gemini_replay"
        if replay_from
        else "offline_catalog_alias_rules",
        total=len(rows),
        groups=dict(Counter(r["group"] for r in rows)),
        statuses=dict(Counter(r["status"] for r in rows)),
        correct=fraction(sum(r["correct"] for r in rows), len(rows)),
        intent_accuracy=fraction(sum(r["intent_correct"] for r in rows), len(rows)),
        proposal_intent_accuracy=fraction(
            sum(r["proposal_intent_correct"] for r in rows), len(rows)
        ),
        evidence_precision=fraction(tp, tp + fp),
        evidence_recall=fraction(required_tp, required_tp + fn),
        tool_accuracy=fraction(sum(r["tools_correct"] for r in rows), len(rows)),
        dependency_validity=fraction(sum(r["dependency_valid"] for r in rows), expected_plans),
        structural_validity=fraction(
            sum(r["structurally_valid"] is True for r in rows), expected_plans
        ),
        materialized_plans=len(plans),
        no_plan=len(rows) - len(plans),
        execution_eligibility=fraction(sum(r["execution_eligible"] for r in rows), expected_plans),
        correct_negative=fraction(sum(r["disposition_correct"] for r in negatives), len(negatives)),
        constraint_accuracy=fraction(sum(r["constraints_correct"] for r in rows), len(rows)),
        calls=len(calls) if live else 0,
        replayed_responses=len(calls) if replay_from else 0,
        tokens={
            k: sum(r["llm"]["usage"][k] for r in rows)
            if live
            and rows
            and all(r["llm"]["usage"] and r["llm"]["usage"][k] is not None for r in rows)
            else None
            for k in ("input_tokens", "output_tokens", "total_tokens")
        },
        latency_ms=dict(
            median=median(r["latency_ms"] for r in rows), max=max(r["latency_ms"] for r in rows)
        ),
        failed_ids=[r["id"] for r in rows if not r["correct"]],
        not_run=[c["id"] for c in questions[len(rows) :]],
        protected_input_hashes=len(hashes),
        hashes_unchanged=True,
        json_roundtrip_exact=True,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--replay-from", type=Path, help="Saved responses; zero live API calls")
    args = parser.parse_args()
    evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        live=args.allow_live,
        case_ids=args.cases,
        manifest=args.manifest,
        replay_from=args.replay_from,
    )
