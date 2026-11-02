"""BBS specialist evaluation: independent M4 references, mock/live/replay separated."""

import argparse
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

from evaluate_d04_closure import save
from evaluate_m4_05_qa import setup
from evaluate_m5_02_planner import protected as previous_protected
from evaluate_m5_04_profitability import regressions as profitability_regressions
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    EvidenceAwareQueryPlanner,
    LiquidityLeverageSpecialist,
    PlannerContext,
    RiskAwareSupervisor,
    SpecialistResult,
    SupervisorResult,
)
from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import PROMPT_VERSION
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
)
from vietnamese_financial_multi_agent.tools.question_understanding import normalize


def protected(root):
    hashes = previous_protected(root)
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-05"):
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
            and f.context.period == f"{case['year']}-12-31"
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


def interpretation_valid(content, value):
    """Independent arithmetic relation check, never specialist rendering as gold."""
    prose = normalize(content)
    amount = normalize(value)
    return bool(
        re.fullmatch(
            r"(?:(?:cu|voi moi|tren moi) 100 dong tong tai san (?:tai thoi diem bao cao )?tuong ung (?:khoang )?"
            + re.escape(amount)
            + r" dong no phai tra(?: tai thoi diem bao cao)?|"
            + r"no phai tra tuong ung (?:khoang )?"
            + re.escape(amount)
            + r" dong tren (?:moi )?100 dong tong tai san tai thoi diem bao cao)",
            prose,
        )
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
                == next(o.context.period for o in original.trace.operands if o.role == "assets")
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
                original.formula_id == "debt_to_assets"
                and candidate.kind == "supported_interpretation"
            ):
                allowed.add("100")
        else:
            expected_value = display(original.value.normalized_value)
            allowed = {expected_value, original.context.period, str(original.context.scale)}
        numeric_text = candidate.content
        periods = (
            [o.context.period for o in original.trace.operands]
            if candidate.calculation
            else [original.context.period]
        )
        for period in periods:
            numeric_text = numeric_text.replace(period, "")
        mentioned = set(re.findall(r"(?<!\w)-?\d+(?:[.,]\d+)*(?!\w)", numeric_text))
        numeric = numeric and expected_value in candidate.content and mentioned <= allowed
        interpretation = None
        if candidate.kind == "supported_interpretation":
            interpretation = interpretation_valid(candidate.content, expected_value)
        grounded = (
            numeric
            and citations
            and binding
            and formula is not False
            and interpretation is not False
        )
        assert candidate.status == "candidate" and not candidate.financial_fact_verified
        checks.append(
            dict(
                id=candidate.candidate_id,
                grounded=grounded,
                numeric=numeric,
                citations=citations,
                formula=formula,
                context=binding,
                interpretation=interpretation,
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
            claims.append(
                dict(
                    evidence_id=evidence["evidence_id"],
                    kind="supported_interpretation",
                    meaning="liabilities_per_100_assets",
                    period=evidence["period"],
                    statement="Cứ 100 đồng tổng tài sản tại thời điểm báo cáo tương ứng khoảng {value} đồng nợ phải trả.",
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
    result = profitability_regressions(
        root, data, scopes, recovery, accepted, output, catalog, documents
    )

    # Compare before/after outputs, ignoring only random IDs, correlation and timing.
    def stable(value):
        if isinstance(value, dict):
            return {
                k: stable(v)
                for k, v in value.items()
                if k not in {"candidate_id", "request_id", "correlation", "latency_ms"}
            }
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value

    before = root / "artifacts/evidence/M5-04-M5-05-before"
    after = root / "artifacts/evidence/M5-04-M5-05-after"
    paths = sorted(before.glob("result-*.json"))
    assert len(paths) == 13
    for path in paths:
        assert stable(load(path)) == stable(load(after / path.name)), path.name
    result["m5_04_before_after_exact"] = len(paths)
    result["m5_04_accepted_baseline"] = (
        "offline13/13; initial2/6; targeted4/4 preserved; zero new live calls"
    )
    # The M5-04 helper already wrote regression-summary.json. Its append-only
    # writer deliberately refuses an overwrite with the extra compatibility keys.
    save(output / "compatibility-summary.json", result)
    return result


def inject(upstream, case):
    """Copies only: synthetic runtime failure controls over real BBS evidence."""
    bundle = upstream.evidence_bundle
    mode = case.get("injection")
    if not mode:
        return
    upstream.status = "partial"
    bundle.missing_requirement_ids.append("injected_" + mode)
    item = "b01.total_assets" if mode == "missing_assets" else "b01.total_liabilities"
    if mode.startswith("missing_"):
        bundle.facts = [f for f in bundle.facts if f.record.canonical_item_id != item]
    elif mode == "approval":
        bundle.calculations[0].evidence.closure.readiness["formula_policy"][
            "execution_approved"
        ] = False
    else:
        fact = next(f for f in bundle.facts if f.record.canonical_item_id == item)
        if mode == "citation":
            fact.citations[0].pdf_page = 999
        elif mode == "conflict":
            conflict = fact.model_copy(deep=True)
            conflict.record.value.normalized_value += 1
            bundle.facts.append(conflict)
        else:
            raise ValueError("unknown_failure_control")


def evaluate(
    root,
    output,
    *,
    live=False,
    case_ids=None,
    replay_from=None,
    run_regressions=False,
    upstream_from=None,
    retest_of=None,
):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M5-05"
    ):
        raise ValueError("output_must_be_new_M5-05_evidence_directory")
    if live and replay_from:
        raise ValueError("live_replay_mutually_exclusive")
    for source in (upstream_from, retest_of, replay_from):
        if source and not source.is_relative_to(root / "artifacts/evidence"):
            raise ValueError("input_must_stay_under_evidence_directory")
    cases = load(root / "evaluation/m5-05-scenarios.json")
    if live:
        cases = [c for c in cases if c.get("live")]
    if case_ids:
        assert set(case_ids) <= {c["id"] for c in cases}
        cases = [c for c in cases if c["id"] in case_ids]
    assert not live or 1 <= len(cases) <= (4 if retest_of else 6)
    if retest_of:
        initial = load(retest_of / "summary.json")
        assert live and initial["mode"] == "live_Gemini" and initial["calls"] <= 6
        assert initial["calls"] + len(cases) <= 10
    output.mkdir(parents=True, exist_ok=False)
    hashes = protected(root)
    save(output / "hashes-before.json", hashes)
    save(
        output / "implementation.json",
        dict(
            specialist_sha256=digest(root / "src/agents/liquidity_leverage_specialist.py"),
            evaluator_sha256=digest(Path(__file__)),
            common_sha256=digest(root / "src/agents/specialist_common.py"),
            prompt_version=PROMPT_VERSION,
            manifest_sha256=digest(root / "evaluation/m5-05-scenarios.json"),
            phase="targeted" if retest_of else "initial",
            retest_of=retest_of.relative_to(root).as_posix() if retest_of else None,
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
    # Preflight references prove each selected scenario has real persisted support.
    all_cases = {c["id"]: c for c in load(root / "evaluation/m5-05-scenarios.json")}
    planner = EvidenceAwareQueryPlanner(catalog, documents)
    supervisor = RiskAwareSupervisor(catalog)
    upstream_cache = {}
    reused_upstreams = set()

    def get_upstream(case):
        if upstream_from:
            path = upstream_from / f"upstream-{case['id']}.json"
            if path.is_file():
                saved = SupervisorResult.model_validate_json(path.read_text(encoding="utf-8"))
                targets = saved.final_plan_state.query.required_indicators
                if set(case["items"]) <= set(targets):
                    reused_upstreams.add(case["id"])
                    return saved
        if case.get("base"):
            return get_upstream(all_cases[case["base"]]).model_copy(deep=True)
        if case["id"] in upstream_cache:
            return upstream_cache[case["id"]].model_copy(deep=True)
        if case.get("new_supervisor"):
            snapshot = (
                recovery.snapshot_id
                if case.get("snapshot") == "recovery"
                else scopes[case["year"]]["snapshot_id"]
            )
            proposed = planner.plan(
                case["question"], PlannerContext(mode="deterministic", snapshot_id=snapshot)
            )
            assert proposed.plan is not None, (case["id"], proposed.reasons)
            upstream = supervisor.execute(proposed.plan)
            assert upstream.status == "completed", (case["id"], upstream.model_dump())
        else:
            path = root / f"artifacts/evidence/M5-03-verified/execution-{case['trace']}.json"
            upstream = SupervisorResult.model_validate_json(path.read_text(encoding="utf-8"))
        upstream_cache[case["id"]] = upstream
        return upstream.model_copy(deep=True)

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
            upstream = get_upstream(case)
            origin = dict(
                mode="saved_BBS_upstream"
                if case["id"] in reused_upstreams
                else "new_deterministic_supervisor"
                if case.get("new_supervisor") or case.get("base")
                else "persisted_M5_03_trace",
                trace=case.get("trace"),
                base=case.get("base"),
                evidence="real_persisted_BBS",
                failure_control=case.get("injection"),
            )
            if case["id"] in reused_upstreams:
                path = upstream_from / f"upstream-{case['id']}.json"
                origin.update(path=path.relative_to(root).as_posix(), sha256=digest(path))
            else:
                inject(upstream, case)
            save(output / f"upstream-{case['id']}.json", upstream.model_dump(mode="json"))

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

            result = LiquidityLeverageSpecialist(SharedLLMGateway({"gemini": transport})).analyze(
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
    except Exception as error:
        # Keep an interrupted scorer/provider run reviewable without saving secrets
        # from exception text; raw requests/responses were already persisted.
        save(
            output / "run-error.json",
            dict(
                error_type=type(error).__name__,
                completed_cases=[r["id"] for r in rows],
                recorded_attempts=len(attempts),
            ),
        )
        raise
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
    interpretation_claims = [c for c in claims if c["interpretation"] is not None]
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
        supported_interpretation_validity=fraction(
            sum(c["interpretation"] for c in interpretation_claims), len(interpretation_claims)
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
    parser.add_argument("--upstream-from", type=Path)
    parser.add_argument("--retest-of", type=Path)
    args = parser.parse_args()
    evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        live=args.allow_live,
        case_ids=args.cases,
        replay_from=args.replay_from.resolve() if args.replay_from else None,
        run_regressions=args.regressions,
        upstream_from=args.upstream_from.resolve() if args.upstream_from else None,
        retest_of=args.retest_of.resolve() if args.retest_of else None,
    )
