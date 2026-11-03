"""BBS cash-flow evaluation; persisted references, mocks, replays and live calls separated."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import median

from evaluate_d04_closure import save
from evaluate_m4_05_qa import setup
from evaluate_m5_02_planner import protected as previous_protected
from evaluate_m5_04_profitability import regressions as bounded_regressions
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    CashFlowEarningsQualitySpecialist,
    EvidenceAwareQueryPlanner,
    LiquidityLeverageSpecialist,
    PlannerContext,
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
    SpecialistResult,
    SupervisorResult,
)
from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
    PROMPT_VERSION,
    SIGN_TEMPLATE,
    ZERO_TEMPLATE,
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
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceRetrieval
from vietnamese_financial_multi_agent.tools import FinancialCalculationResponse

ITEMS = (
    "b03.operating_cash_flow",
    "b03.investing_cash_flow",
    "b03.financing_cash_flow",
    "b03.net_cash_flow",
    "b03.opening_cash",
    "b03.closing_cash",
    "b02.profit_before_tax",
    "b02.profit_after_tax",
)


def protected(root):
    hashes = previous_protected(root)
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-06"):
            hashes.update(
                (p.relative_to(root).as_posix(), digest(p))
                for p in folder.rglob("*")
                if p.is_file() and p.suffix != ".log"
            )
    hashes["web/next-env.d.ts"] = digest(root / "web/next-env.d.ts")
    return dict(sorted(hashes.items()))


def response_for(request, payload):
    return LLMResponse(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        status="success",
        finish_reason="stop",
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
        output=parse_json_output(json.dumps(payload, ensure_ascii=False)),
    )


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


def compatibility(root, output, before=None):
    """Replay identical saved proposals on real evidence before/after common edits."""
    checks = []
    for folder, cls, ids in (
        ("M5-04-offline-final", ProfitabilitySpecialist, ("R01", "R05", "R08")),
        ("M5-05-offline-complete", LiquidityLeverageSpecialist, ("L01", "L07", "L10")),
    ):
        for case_id in ids:
            source = root / "artifacts/evidence" / folder
            old = load(source / f"result-{case_id}.json")
            path = source / f"upstream-{case_id}.json"
            if not path.exists():
                manifest = load(root / "evaluation/m5-04-scenarios.json")
                trace = next(c["trace"] for c in manifest if c["id"] == case_id)
                path = root / f"artifacts/evidence/M5-03-verified/execution-{trace}.json"
            upstream = SupervisorResult.model_validate_json(path.read_text(encoding="utf-8"))
            payload = old["raw_output"]
            gateway = SharedLLMGateway({"gemini": lambda req, p=payload: response_for(req, p)})
            current = cls(gateway).analyze(question=old["question"], supervisor_result=upstream)
            name = f"compatibility-{case_id}.json"
            actual = stable(current.model_dump(mode="json"))
            save(output / name, actual)
            if before:
                assert actual == load(before / name), case_id
            else:
                assert actual == stable(old), case_id
            checks.append(
                dict(
                    case=case_id,
                    status=current.status,
                    candidates=len(current.candidates),
                    exact=bool(before),
                )
            )
    save(output / "compatibility-summary.json", checks)
    return checks


def audit(root, output):
    data, scopes, recovery, _ = setup(root)
    retrieval = EvidenceRetrieval(data["facts"], graph=data["graph"])
    rows = []
    for year, scope in scopes.items():
        snapshots = [("original", scope["snapshot_id"])]
        if year == 2022:
            snapshots.append(("recovery", recovery.snapshot_id))
        for origin, snapshot in snapshots:
            for item in ITEMS:
                records = [
                    f
                    for f in data["facts"]
                    if f.document_id == scope["document_id"]
                    and f.snapshot_id == snapshot
                    and f.canonical_item_id == item
                ]
                facts = []
                for fact in records:
                    match = retrieval.get_fact(fact.observation_identity()).matches
                    facts.append(
                        dict(
                            record=fact.model_dump(mode="json"),
                            retrieval=[m.model_dump(mode="json") for m in match],
                        )
                    )
                rows.append(
                    dict(
                        year=year,
                        origin=origin,
                        document_id=scope["document_id"],
                        snapshot_id=snapshot,
                        item=item,
                        facts=facts,
                    )
                )
    save(output / "coverage-audit.json", rows)
    for row in rows:
        current = [f for f in row["facts"] if f["record"]["context"]["period"] == str(row["year"])]
        values = [
            (
                f["record"]["value"]["normalized_value"],
                [m["display_status"] for m in f["retrieval"]],
                f["record"]["context"]["period_type"],
            )
            for f in current
        ]
        print(row["year"], row["origin"], row["item"], values, flush=True)
    return rows


def reference_for(case, data, scopes, recovery):
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
        assert len(matches) == 1, (case["id"], item)
        facts.append(matches[0].model_dump(mode="json"))
    return dict(
        **scope, facts=facts, expected_targets=len(facts) + bool(case.get("interpretation"))
    )


def mock_response(request, case):
    """Mock intent on persisted evidence: engineering evaluation, not model accuracy."""
    claims = []
    for evidence in json.loads(request.messages[0].content)["evidence"]:
        item = evidence["canonical_item_id"]
        if item not in case["items"]:
            continue
        claims.append(
            dict(
                evidence_id=evidence["evidence_id"],
                kind="fact",
                meaning="fact_value",
                period=evidence["period"],
                statement=None,
            )
        )
        if item == case.get("interpretation"):
            value = Decimal(evidence["value"])
            claims.append(
                dict(
                    evidence_id=evidence["evidence_id"],
                    kind="supported_interpretation",
                    meaning="cash_flow_sign",
                    period=evidence["period"],
                    sign="positive" if value > 0 else "negative" if value < 0 else "zero",
                    statement=ZERO_TEMPLATE if value == 0 else SIGN_TEMPLATE,
                )
            )
    return response_for(request, dict(claims=claims, missing_information=[]))


def inject(upstream, mode):
    """Synthetic failures on a COPY of real BBS evidence; originals remain read-only."""
    if not mode:
        return
    bundle = upstream.evidence_bundle
    if mode == "missing_profit":
        upstream.status = "partial"
        bundle.missing_requirement_ids.append("synthetic_injected_missing_profit")
        bundle.facts = [
            f for f in bundle.facts if f.record.canonical_item_id != "b02.profit_before_tax"
        ]
        return
    fact = next(f for f in bundle.facts if f.record.canonical_item_id == "b03.operating_cash_flow")
    upstream.status = "partial"
    bundle.missing_requirement_ids.append("synthetic_injected_" + mode)
    if mode == "conflict":
        other = fact.model_copy(deep=True)
        other.record.value.normalized_value += 1
        bundle.facts.append(other)
    elif mode == "period":
        fact.record.context.period = "2024"
    elif mode == "unit":
        fact.record.value.unit = "USD"
    elif mode == "citation":
        fact.citations[0].pdf_page = 999
    else:
        raise ValueError("unknown_injection")


# Human semantic reference independent of the specialist digest/model output.
REFERENCE_NAMES = {
    "b03.operating_cash_flow": "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
    "b03.investing_cash_flow": "Lưu chuyển tiền thuần từ hoạt động đầu tư",
    "b03.financing_cash_flow": "Lưu chuyển tiền thuần từ hoạt động tài chính",
    "b03.closing_cash": "Tiền và tương đương tiền cuối kỳ",
    "b02.profit_before_tax": "Lợi nhuận kế toán trước thuế",
    "b02.profit_after_tax": "Lợi nhuận sau thuế",
}


def assess(case, result, reference, data, retrieval=None):
    records = {f.observation_identity(): f for f in data["facts"]}
    retrieval = retrieval or EvidenceRetrieval(data["facts"], graph=data["graph"])
    covered, checks = set(), []
    targets = set(case["items"])
    for candidate in result.candidates:
        references = candidate.fact_references
        original = records.get(references[0].observation) if len(references) == 1 else None
        context = numeric = citations = semantic = sign_check = False
        if original:
            key = original.canonical_item_id
            amount = original.value.normalized_value
            display = format(amount, ",f").translate(str.maketrans({",": ".", ".": ","}))
            context = (
                candidate.document_id == original.document_id == reference["document_id"]
                and candidate.snapshot_id == original.snapshot_id == reference["snapshot_id"]
                and candidate.period == original.context.period == str(case["year"])
                and candidate.company_id == original.company_id
            )
            selected = [
                e
                for e in result.supporting_evidence
                if e.evidence_id in candidate.supporting_evidence_ids
            ]
            numeric = (
                len(selected) == 1
                and selected[0].value == str(amount)
                and selected[0].unit == original.value.unit
                and selected[0].scale == str(original.context.scale)
                and display in candidate.content
            )
            source = retrieval.get_fact(original.observation_identity()).matches[0]
            citations = (
                candidate.citations == source.citations
                and bool(source.citations)
                and len(candidate.supporting_evidence_ids) == 1
                and selected[0].reference == references[0]
                if selected
                else False
            )
            name = REFERENCE_NAMES.get(key, "unsupported")
            if candidate.kind == "fact":
                expected = (
                    f"{name} của kỳ {original.context.period} là {display} {original.value.unit}."
                )
                semantic = candidate.content == expected
                sign_check = None
                if key in targets:
                    covered.add(key)
            elif candidate.kind == "supported_interpretation":
                # Validate the entire bounded statement using independent canonical
                # amounts and approved accounting meaning, including the minus sign.
                direction = "vào" if amount > 0 else "ra"
                sign = "dương" if amount > 0 else "âm"
                activity = {
                    "b03.operating_cash_flow": "từ hoạt động kinh doanh",
                    "b03.investing_cash_flow": "từ hoạt động đầu tư",
                    "b03.financing_cash_flow": "từ hoạt động tài chính",
                }.get(key)
                prefix = f"{name} trong kỳ {original.context.period} là {display} {original.value.unit}, "
                suffix = (
                    f"mang giá trị {sign}, phản ánh dòng tiền {direction} thuần {activity} "
                    "theo chỉ tiêu được báo cáo."
                    if amount
                    else "phản ánh giá trị dòng tiền thuần bằng không theo chỉ tiêu được báo cáo."
                )
                sign_check = bool(activity) and candidate.content == prefix + suffix
                semantic = sign_check
                if key == case.get("interpretation"):
                    covered.add("interpretation:" + key)
            else:
                sign_check = None
        grounded = bool(
            context
            and numeric
            and citations
            and semantic
            and not candidate.metric_ids
            and candidate.calculation is None
            and candidate.status == "candidate"
            and not candidate.financial_fact_verified
        )
        checks.append(
            dict(
                id=candidate.candidate_id,
                grounded=grounded,
                numeric=bool(numeric),
                citations=bool(citations),
                context=bool(context),
                semantic=bool(semantic),
                sign=sign_check,
            )
        )
    appropriate = (
        (result.status == "abstained" and not result.candidates) if case.get("abstain") else None
    )
    complete = len(covered) == reference["expected_targets"]
    correct = all(c["grounded"] for c in checks) and complete and appropriate is not False
    if case.get("partial"):
        correct &= result.status == "partial" and bool(result.missing_evidence)
    if case.get("missing_items"):
        correct &= not any(
            records[r.observation].canonical_item_id in case["missing_items"]
            for c in result.candidates
            for r in c.fact_references
        )
    return dict(
        correct=bool(correct),
        candidates=checks,
        covered=len(covered),
        expected=reference["expected_targets"],
        multi_fact_complete=complete,
        appropriate_abstention=appropriate,
    )


def evaluate(
    root,
    output,
    *,
    live=False,
    case_ids=None,
    replay_from=None,
    upstream_from=None,
    retest_of=None,
    run_regressions=False,
):
    if live and replay_from:
        raise ValueError("live_replay_mutually_exclusive")
    cases = load(root / "evaluation/m5-06-scenarios.json")
    all_cases = {c["id"]: c for c in cases}
    if live:
        cases = [c for c in cases if c.get("live")]
    if case_ids:
        assert set(case_ids) <= {c["id"] for c in cases}
        cases = [c for c in cases if c["id"] in case_ids]
    assert cases and (not live or len(cases) <= (4 if retest_of else 6))
    phase = "targeted" if retest_of else "initial"
    if live:
        prior = [
            load(p)
            for d in (root / "artifacts/evidence").glob("M5-06*")
            for p in d.glob("attempt-*.json")
        ]
        used = sum(a.get("mode") == "live_Gemini" and a.get("phase") == phase for a in prior)
        assert used + len(cases) <= (4 if retest_of else 6), "live_budget_exceeded"
        if retest_of:
            assert load(retest_of / "summary.json")["mode"] == "live_Gemini"
    save(
        output / "implementation.json",
        dict(
            specialist_sha256=digest(root / "src/agents/cash_flow_earnings_quality_specialist.py"),
            common_sha256=digest(root / "src/agents/specialist_common.py"),
            evaluator_sha256=digest(Path(__file__)),
            prompt_version=PROMPT_VERSION,
            manifest_sha256=digest(root / "evaluation/m5-06-scenarios.json"),
            phase=phase,
            retest_of=retest_of.relative_to(root).as_posix() if retest_of else None,
        ),
    )
    data, scopes, recovery, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    planner, supervisor = (
        EvidenceAwareQueryPlanner(catalog, documents),
        RiskAwareSupervisor(catalog),
    )
    references = {c["id"]: reference_for(c, data, scopes, recovery) for c in cases}
    retrieval = EvidenceRetrieval(data["facts"], graph=data["graph"])
    save(output / "references.json", references)
    cache = {}

    def get_upstream(case):
        if case["id"] in cache:
            return cache[case["id"]].model_copy(deep=True)
        saved = upstream_from / f"upstream-{case['id']}.json" if upstream_from else None
        if saved and saved.exists():
            upstream = SupervisorResult.model_validate_json(saved.read_text(encoding="utf-8"))
        elif case.get("base"):
            upstream = get_upstream(all_cases[case["base"]])
        elif case.get("trace"):
            path = root / f"artifacts/evidence/M5-03-verified/execution-{case['trace']}.json"
            upstream = SupervisorResult.model_validate_json(path.read_text(encoding="utf-8"))
        else:
            snapshot = (
                recovery.snapshot_id
                if case.get("snapshot") == "recovery"
                else scopes[case["year"]]["snapshot_id"]
            )
            proposal = planner.plan(
                case["question"], PlannerContext(mode="deterministic", snapshot_id=snapshot)
            )
            assert proposal.plan is not None, (case["id"], proposal.reasons)
            save(output / f"plan-{case['id']}.json", proposal.model_dump(mode="json"))
            upstream = supervisor.execute(proposal.plan)
        if not (saved and saved.exists()):
            inject(upstream, case.get("injection"))
        cache[case["id"]] = upstream.model_copy(deep=True)
        return upstream

    adapter, attempts, rows = None, [], []
    mode = (
        "live_Gemini" if live else "saved_Gemini_replay" if replay_from else "real_BBS_mock_Gemini"
    )
    replayed = load(replay_from / "gateway-responses.json") if replay_from else []
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
    try:
        for case in cases:
            upstream = get_upstream(case)
            save(output / f"upstream-{case['id']}.json", upstream.model_dump(mode="json"))

            def transport(request, case=case):
                assert len(attempts) < len(cases)
                attempt = dict(
                    case=case["id"],
                    outcome="started",
                    mode=mode,
                    phase=phase,
                    request_id=request.request_id,
                )
                attempts.append(attempt)
                save(output / f"attempt-{case['id']}.json", attempt)
                save(output / f"request-{case['id']}.json", request.model_dump(mode="json"))
                if live:
                    response = adapter(request)
                elif replay_from:
                    raw = next(a["response"] for a in replayed if a["case"] == case["id"])
                    response = LLMResponse.model_validate(
                        dict(raw, request_id=request.request_id, correlation=None)
                    )
                else:
                    response = mock_response(request, case)
                attempt.update(outcome="returned", response=response.export())
                save(output / f"gateway-{case['id']}.json", attempt)
                return response

            result = CashFlowEarningsQualitySpecialist(
                SharedLLMGateway({"gemini": transport})
            ).analyze(question=case["question"], supervisor_result=upstream)
            save(output / f"result-{case['id']}.json", result.model_dump(mode="json"))
            assert SpecialistResult.model_validate_json(result.model_dump_json()) == result
            score = assess(case, result, references[case["id"]], data, retrieval)
            row = dict(
                id=case["id"],
                status=result.status,
                upstream_status=upstream.status,
                injection=case.get("injection"),
                origin="saved_upstream"
                if upstream_from
                else "persisted_M5_03_trace"
                if case.get("trace")
                else "deterministic_planner_supervisor",
                **score,
                llm=result.llm.model_dump(mode="json"),
                latency_ms=result.latency_ms,
                exclusions=[t.model_dump() for t in result.trace if t.outcome == "excluded"],
            )
            rows.append(row)
            save(output / f"score-{case['id']}.json", row)
            print(
                f"{case['id']}: {result.status}, candidates={len(result.candidates)}, "
                f"coverage={score['covered']}/{score['expected']}, correct={score['correct']}",
                flush=True,
            )
            if result.llm.error:
                break  # No automatic retry or key/model rotation.
        if run_regressions:
            accepted = [
                FinancialCalculationResponse.model_validate_json(json.dumps(c))
                for c in load(root / "artifacts/evidence/M4-03-final/executions.json")
            ]
            bounded_regressions(root, data, scopes, recovery, accepted, output, catalog, documents)
    except Exception as error:
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
    summary = summarize(
        rows, attempts, mode=mode, phase=phase, planned_ids=[c["id"] for c in cases]
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def latency_summary(rows):
    # Zero-call controls have unknown LLM latency, not a timed model response.
    values = [r["llm"]["latency_ms"] for r in rows if r["llm"]["latency_ms"] is not None]
    return dict(median=median(values) if values else None, maximum=max(values) if values else None)


def summarize(rows, attempts, *, mode, phase, planned_ids):
    live = mode == "live_Gemini"
    replay = mode == "saved_Gemini_replay"
    claims = [c for r in rows for c in r["candidates"]]
    signs = [c for c in claims if c["sign"] is not None]
    negatives = [r for r in rows if r["appropriate_abstention"] is not None]
    multi = [r for r in rows if r["expected"] > 1]

    def fraction(n, d):
        return dict(numerator=n, denominator=d, value=n / d if d else None)

    summary = dict(
        mode=mode,
        phase=phase,
        total=len(rows),
        correct=sum(r["correct"] for r in rows),
        failed_ids=[r["id"] for r in rows if not r["correct"]],
        not_run=[key for key in planned_ids if key not in {r["id"] for r in rows}],
        statuses=dict(Counter(r["status"] for r in rows)),
        scenario_correctness=fraction(sum(r["correct"] for r in rows), len(rows)),
        grounding=fraction(sum(c["grounded"] for c in claims), len(claims)),
        numeric_accuracy=fraction(sum(c["numeric"] for c in claims), len(claims)),
        citation_correctness=fraction(sum(c["citations"] for c in claims), len(claims)),
        sign_interpretation=fraction(sum(c["sign"] for c in signs), len(signs)),
        accounting_semantic_validity=fraction(sum(c["semantic"] for c in claims), len(claims)),
        multi_fact_completeness=fraction(sum(r["multi_fact_complete"] for r in multi), len(multi)),
        unsupported_claim_rate=fraction(sum(not c["grounded"] for c in claims), len(claims)),
        appropriate_abstention=fraction(
            sum(r["appropriate_abstention"] for r in negatives), len(negatives)
        ),
        claim_coverage=fraction(sum(r["covered"] for r in rows), sum(r["expected"] for r in rows)),
        calls=len(attempts) if live else 0,
        mocked_calls=len(attempts) if not live and not replay else 0,
        replayed_calls=len(attempts) if replay else 0,
        tokens={
            k: sum(r["llm"]["usage"][k] for r in rows)
            if live
            and rows
            and all(r["llm"]["usage"] and r["llm"]["usage"][k] is not None for r in rows)
            else None
            for k in ("input_tokens", "output_tokens", "total_tokens")
        },
        latency_ms=latency_summary(rows),
        quality_of_earnings_accuracy=None,
        financial_fact_verified=False,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--compatibility", action="store_true")
    parser.add_argument("--before", type=Path)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--replay-from", type=Path)
    parser.add_argument("--upstream-from", type=Path)
    parser.add_argument("--retest-of", type=Path)
    parser.add_argument("--regressions", action="store_true")
    parser.add_argument("--summarize-from", type=Path)
    args = parser.parse_args()
    root, output = Path.cwd().resolve(), args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M5-06"
    ):
        raise ValueError("output_must_be_new_M5-06_evidence_directory")
    output.mkdir(parents=True, exist_ok=False)
    hashes = protected(root)
    save(output / "hashes-before.json", hashes)
    try:
        if args.audit:
            audit(root, output)
        if args.compatibility:
            compatibility(root, output, args.before)
        if args.summarize_from:
            assert not args.allow_live and not args.replay_from
            source = args.summarize_from.resolve()
            assert source.is_relative_to(root / "artifacts/evidence")
            attempts = load(source / "gateway-responses.json")
            implementation = load(source / "implementation.json")
            summary = summarize(
                load(source / "scores.json"),
                attempts,
                mode=attempts[0]["mode"],
                phase=implementation["phase"],
                planned_ids=[c["id"] for c in load(root / "evaluation/m5-06-scenarios.json")],
            )
            summary.update(
                summary_repair_from=source.relative_to(root).as_posix(), fresh_execution=False
            )
            save(output / "summary.json", summary)
            save(
                output / "summary-source.json",
                dict(
                    scores_sha256=digest(source / "scores.json"),
                    responses_sha256=digest(source / "gateway-responses.json"),
                    implementation=implementation,
                    summary_writer_sha256=digest(Path(__file__)),
                ),
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        elif not args.audit and not args.compatibility:
            evaluate(
                root,
                output,
                live=args.allow_live,
                case_ids=args.cases,
                replay_from=args.replay_from.resolve() if args.replay_from else None,
                upstream_from=args.upstream_from.resolve() if args.upstream_from else None,
                retest_of=args.retest_of.resolve() if args.retest_of else None,
                run_regressions=args.regressions,
            )
    finally:
        after = {p: digest(root / p) for p in hashes}
        save(output / "hashes-after.json", after)
        assert after == hashes
