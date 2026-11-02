"""BBS specialist evaluation: independent M4 references, mock/live/replay separated."""

import argparse
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

from evaluate_d04_closure import save
from evaluate_m4_05_qa import bounded_regressions, context_for, setup
from evaluate_m5_02_planner import protected as previous_protected
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    EvidenceAwareQueryPlanner,
    PlannerContext,
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
    SpecialistResult,
    SupervisorResult,
    validate_plan,
)
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    LLMResponse,
    ResponseProvenance,
    Usage,
    parse_json_output,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    FinancialCalculationResponse,
    FinancialQABaseline,
    QAResponse,
)


def protected(root):
    hashes = previous_protected(root)
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-04"):
            hashes.update(
                (p.relative_to(root).as_posix(), digest(p))
                for p in folder.rglob("*")
                if p.is_file() and p.suffix != ".log"
            )
    hashes["web/next-env.d.ts"] = digest(root / "web/next-env.d.ts")
    return dict(sorted(hashes.items()))


def reference_for(case, data, scopes, recovery, accepted):
    """Human targets + persisted canonical facts + accepted M4, never model output."""
    scope = dict(scopes[case["year"]])
    if case.get("snapshot") == "recovery":
        scope["snapshot_id"] = recovery.snapshot_id
    facts = []
    for item in case["items"]:
        matches = [
            f
            for f in data["facts"]
            if f.document_id == scope["document_id"]
            and f.snapshot_id == scope["snapshot_id"]
            and f.canonical_item_id == item
            and f.context.period == str(case["year"])
        ]
        assert len(matches) == 1
        facts.append(matches[0])
    calculations = [
        c
        for c in accepted
        if c.document_id == scope["document_id"]
        and c.snapshot_id == scope["snapshot_id"]
        and c.formula_id == case.get("formula")
    ]
    assert len(calculations) == (1 if case.get("formula") else 0)
    return dict(
        **scope,
        facts=[f.model_dump(mode="json") for f in facts],
        calculations=[c.model_dump(mode="json") for c in calculations],
        expected_targets=len(facts) + len(calculations) + int(case.get("interpretation", False)),
    )


def assess(case, result, reference, data, accepted):
    # Inspect final claims against independent persisted records, not the specialist
    # digest. Full citation selector/page/period/unit/scale and trace equality count.
    facts = {f.observation_identity(): f for f in data["facts"]}
    metrics = {c.metric_id: c for c in accepted}
    checks = []
    covered = set()
    targets = {f["canonical_item_id"] for f in reference["facts"]}
    for candidate in result.candidates:
        if candidate.calculation:
            original = metrics[candidate.metric_ids[0]]
            numeric = candidate.calculation == original
            sources = original.evidence.citations
            binding = (
                candidate.document_id == original.document_id
                and candidate.snapshot_id == original.snapshot_id
                and {r.observation for r in candidate.fact_references}
                == {o.observation for o in original.trace.operands}
                and candidate.company_id == original.trace.operands[0].company_id
                and candidate.period
                == next(
                    o.context.period
                    for o in original.trace.operands
                    if o.role in {"revenue", "current_revenue"}
                )
            )
            formula = candidate.calculation.trace == original.trace
            if candidate.metric_ids == [c["metric_id"] for c in reference["calculations"]]:
                covered.add(candidate.kind)
        else:
            original = facts[candidate.fact_references[0].observation]
            numeric = all(
                str(original.value.normalized_value) == e.value
                for e in result.supporting_evidence
                if e.evidence_id in candidate.supporting_evidence_ids
            )
            sources = next(f.citations for f in _independent_fact_matches(data, original))
            binding = (
                candidate.document_id == original.document_id
                and candidate.snapshot_id == original.snapshot_id
                and candidate.period == original.context.period
                and candidate.company_id == original.company_id
            )
            formula = None
            if original.canonical_item_id in targets:
                covered.add(original.canonical_item_id)
        citations = candidate.citations == sources and bool(sources)

        # Also inspect numbers actually rendered into the claim. Accepted M4
        # supplies the whitelist; no Gemini/digest numeric text is ground truth.
        def display(value):
            return format(Decimal(value), ",f").translate(str.maketrans({",": ".", ".": ","}))

        if candidate.calculation:
            expected_value = (
                display(abs(Decimal(original.result)))
                if original.formula_id == "revenue_yoy"
                and candidate.kind == "supported_interpretation"
                else display(original.result)
            )
            allowed = {expected_value, *[o.context.period for o in original.trace.operands]}
            if (
                original.formula_id == "gross_margin"
                and candidate.kind == "supported_interpretation"
            ):
                allowed.add("100")
        else:
            expected_value = display(original.value.normalized_value)
            allowed = {expected_value, original.context.period, str(original.context.scale)}
        mentioned = set(re.findall(r"(?<!\w)-?\d+(?:[.,]\d+)*(?!\w)", candidate.content))
        numeric = numeric and expected_value in candidate.content and mentioned <= allowed
        grounded = numeric and citations and binding and formula is not False
        assert candidate.status == "candidate" and not candidate.financial_fact_verified
        checks.append(
            dict(
                id=candidate.candidate_id,
                grounded=grounded,
                numeric=numeric,
                citations=citations,
                formula=formula,
                context=binding,
            )
        )
    # Extra fact claims grounded in the bundle are allowed, but cannot inflate target coverage.
    if not case.get("formula"):
        covered = covered & targets
    else:
        covered &= (
            {"approved_metric", "supported_interpretation"}
            if case.get("interpretation")
            else {"approved_metric"}
        )
    appropriate = (
        (not result.candidates and result.status == "abstained") if case.get("abstain") else None
    )
    correct = (
        all(c["grounded"] for c in checks)
        and len(covered) == reference["expected_targets"]
        and (appropriate is not False)
        and (not case.get("partial") or result.status == "partial")
    )
    if case.get("missing_items"):
        correct &= not any(
            facts[r.observation].canonical_item_id in case["missing_items"]
            for c in result.candidates
            for r in c.fact_references
        )
    return dict(
        correct=bool(correct),
        candidates=checks,
        covered=len(covered),
        expected=reference["expected_targets"],
        appropriate_abstention=appropriate,
    )


def _independent_fact_matches(data, original):
    # Reconstruct source citations from canonical sources with the production
    # constructor, rather than treating a model's citation list as authoritative.
    from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceRetrieval

    api = EvidenceRetrieval([original], graph=data["graph"])
    return api.get_fact(original.observation_identity()).matches


def mock_response(request, case):
    """Clearly labeled mock on REAL BBS inputs; not a Gemini accuracy measurement."""
    prompt = json.loads(request.messages[0].content)
    claims = []
    for evidence in prompt["evidence"]:
        if evidence["kind"] == "fact" and evidence["canonical_item_id"] not in case["items"]:
            continue
        if evidence["kind"] == "metric" and evidence["formula_id"] != case.get("formula"):
            continue
        metric = evidence["kind"] == "metric"
        claims.append(
            dict(
                evidence_id=evidence["evidence_id"],
                kind="approved_metric" if metric else "fact",
                meaning="metric_value" if metric else "fact_value",
                period=evidence["period"],
                statement=None,
            )
        )
        if metric and case.get("interpretation"):
            gross = evidence["formula_id"] == "gross_margin"
            claims.append(
                dict(
                    evidence_id=evidence["evidence_id"],
                    kind="supported_interpretation",
                    meaning="gross_profit_per_100_revenue" if gross else "revenue_change",
                    period=evidence["period"],
                    statement="Trong kỳ {period}, cứ 100 đồng doanh thu thuần tương ứng khoảng {value} đồng lợi nhuận gộp."
                    if gross
                    else "Trong cùng báo cáo, doanh thu thuần kỳ {period} {direction} {value}% so với kỳ {prior_period}.",
                )
            )
    return LLMResponse(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        status="success",
        finish_reason="stop",
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
        output=parse_json_output(
            json.dumps(dict(claims=claims, missing_information=[]), ensure_ascii=False)
        ),
    )


def regressions(root, data, scopes, recovery, accepted, output, catalog, documents):
    result = bounded_regressions(root, data, scopes, recovery, accepted, output)
    qa = FinancialQABaseline(catalog, documents)
    qa_cases = load(root / "evaluation/m4-05-questions.json")
    for case, old in zip(
        qa_cases, load(root / "artifacts/evidence/M4-05-final/responses.json"), strict=True
    ):
        assert qa.answer(
            case["question"], context_for(case, scopes, recovery)
        ) == QAResponse.model_validate_json(json.dumps(old["response"]))
    cases = load(root / "artifacts/evidence/M5-01-scope-final/cases.json")
    for case in cases:
        name = (
            "invalid-period-binding"
            if case["case_id"] == "invalid_period_binding"
            else case["case_id"]
        )
        old = load(root / f"artifacts/evidence/M5-01-scope-final/{name}.json")
        assert (
            validate_plan(old["plan"], catalog=catalog).model_dump(mode="json") == old["validation"]
        )
    # Reuse accepted execution traces; no unnecessary new Supervisor/Gemini runs.
    traces = [
        load(p)
        for p in sorted((root / "artifacts/evidence/M5-03-verified").glob("execution-*.json"))
    ]
    assert len(traces) == 19 and Counter(t["status"] for t in traces) == {
        "completed": 13,
        "partial": 3,
        "blocked": 3,
    }
    result.update(
        qa_exact=len(qa_cases),
        m5_01_exact=len(cases),
        m5_03_preserved_traces=len(traces),
        m5_02_baseline="offline18/18;fresh4/6;raw5/6;replay6/6 preserved, not rerun",
    )
    save(output / "regression-summary.json", result)
    return result


def evaluate(root, output, *, live=False, case_ids=None, replay_from=None, run_regressions=False):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M5-04"
    ):
        raise ValueError("output_must_be_new_M5-04_evidence_directory")
    if live and replay_from:
        raise ValueError("live_replay_mutually_exclusive")
    cases = load(root / "evaluation/m5-04-scenarios.json")
    if live:
        cases = [c for c in cases if c.get("live")]
    if case_ids:
        assert set(case_ids) <= {c["id"] for c in cases}
        cases = [c for c in cases if c["id"] in case_ids]
    assert not live or 1 <= len(cases) <= 6
    output.mkdir(parents=True, exist_ok=False)
    hashes = protected(root)
    save(output / "hashes-before.json", hashes)
    save(
        output / "implementation.json",
        dict(
            specialist_sha256=digest(root / "src/agents/profitability_specialist.py"),
            evaluator_sha256=digest(Path(__file__)),
        ),
    )
    data, scopes, recovery, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(c))
        for c in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]
    references = {c["id"]: reference_for(c, data, scopes, recovery, accepted) for c in cases}
    save(output / "references.json", references)
    adapter, rows, attempts = None, [], []
    if live:
        adapter, credential = create_qa_adapter(root)
        save(
            output / "credential-metadata.json",
            dict(
                source=credential.source,
                key_index=credential.key_index,
                key_count=credential.key_count,
            ),
        )
    replayed = load(replay_from / "gateway-responses.json") if replay_from else []
    try:
        for case in cases:
            if case.get("new_supervisor"):
                plan = (
                    EvidenceAwareQueryPlanner(catalog, documents)
                    .plan(case["question"], PlannerContext(mode="deterministic"))
                    .plan
                )
                assert plan is not None
                upstream = RiskAwareSupervisor(catalog).execute(plan)
                save(output / f"upstream-{case['id']}.json", upstream.model_dump(mode="json"))
                origin = dict(mode="new_deterministic_supervisor", gateway_calls=0)
            else:
                path = root / f"artifacts/evidence/M5-03-verified/execution-{case['trace']}.json"
                upstream = SupervisorResult.model_validate_json(path.read_text(encoding="utf-8"))
                origin = dict(path=path.relative_to(root).as_posix(), sha256=digest(path))

            def transport(request, case=case):
                assert len(attempts) < len(cases)
                attempt = dict(case=case["id"], outcome="started", request_id=request.request_id)
                attempts.append(attempt)
                save(output / f"attempt-{case['id']}.json", attempt)
                save(output / f"request-{case['id']}.json", request.model_dump(mode="json"))
                if replay_from:
                    original = next(a for a in replayed if a["case"] == case["id"])
                    payload = dict(original["response"])
                    payload.update(request_id=request.request_id, correlation=None)
                    response = LLMResponse.model_validate(payload)
                elif live:
                    response = adapter(request)
                else:
                    response = mock_response(request, case)
                attempt.update(outcome="returned", response=response.export())
                save(output / f"gateway-{case['id']}.json", attempt)
                return response

            result = ProfitabilitySpecialist(SharedLLMGateway({"gemini": transport})).analyze(
                question=case["question"], supervisor_result=upstream
            )
            save(output / f"result-{case['id']}.json", result.model_dump(mode="json"))
            assert SpecialistResult.model_validate_json(result.model_dump_json()) == result
            score = assess(case, result, references[case["id"]], data, accepted)
            row = dict(
                id=case["id"],
                status=result.status,
                upstream_status=upstream.status,
                origin=origin,
                **score,
                latency_ms=result.latency_ms,
                llm=result.llm.model_dump(mode="json"),
                exclusions=[t.model_dump() for t in result.trace if t.outcome == "excluded"],
            )
            rows.append(row)
            save(output / f"score-{case['id']}.json", row)
            print(
                f"{case['id']}: {result.status}, candidates={len(result.candidates)}, coverage={score['covered']}/{score['expected']}, correct={score['correct']}",
                flush=True,
            )
            if result.llm.error:
                break
        if run_regressions:
            regressions(root, data, scopes, recovery, accepted, output, catalog, documents)
    finally:
        if adapter:
            adapter.close()
        save(output / "scores.json", rows)
        save(output / "gateway-responses.json", attempts)
        after = {p: digest(root / p) for p in hashes}
        save(output / "hashes-after.json", after)
        assert hashes == after
    claims = [c for row in rows for c in row["candidates"]]

    def fraction(n, d):
        return dict(numerator=n, denominator=d, value=n / d if d else None)

    negatives = [r for r in rows if r["appropriate_abstention"] is not None]
    formula_claims = [c for c in claims if c["formula"] is not None]
    summary = dict(
        mode="live_Gemini"
        if live
        else "offline_saved_Gemini_replay"
        if replay_from
        else "real_BBS_mock_Gemini",
        total=len(rows),
        correct=sum(r["correct"] for r in rows),
        failed_ids=[r["id"] for r in rows if not r["correct"]],
        not_run=[c["id"] for c in cases[len(rows) :]],
        statuses=dict(Counter(r["status"] for r in rows)),
        grounding=fraction(sum(c["grounded"] for c in claims), len(claims)),
        numeric_accuracy=fraction(sum(c["numeric"] for c in claims), len(claims)),
        citation_correctness=fraction(sum(c["citations"] for c in claims), len(claims)),
        formula_operand_correctness=fraction(
            sum(c["formula"] for c in formula_claims), len(formula_claims)
        ),
        unsupported_claim_rate=fraction(sum(not c["grounded"] for c in claims), len(claims)),
        appropriate_abstention=fraction(
            sum(r["appropriate_abstention"] for r in negatives), len(negatives)
        ),
        claim_coverage=fraction(sum(r["covered"] for r in rows), sum(r["expected"] for r in rows)),
        calls=len(attempts) if live else 0,
        mocked_calls=len(attempts) if not live and not replay_from else 0,
        replayed_calls=len(attempts) if replay_from else 0,
        tokens={
            k: sum(r["llm"]["usage"][k] for r in rows)
            if live
            and rows
            and all(r["llm"]["usage"] and r["llm"]["usage"][k] is not None for r in rows)
            else None
            for k in ("input_tokens", "output_tokens", "total_tokens")
        },
        latency_ms=dict(
            median=median(r["latency_ms"] for r in rows), maximum=max(r["latency_ms"] for r in rows)
        ),
        protected_hashes=len(hashes),
        hashes_unchanged=True,
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
    parser.add_argument("--replay-from", type=Path)
    parser.add_argument("--regressions", action="store_true")
    args = parser.parse_args()
    evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        live=args.allow_live,
        case_ids=args.cases,
        replay_from=args.replay_from.resolve() if args.replay_from else None,
        run_regressions=args.regressions,
    )
