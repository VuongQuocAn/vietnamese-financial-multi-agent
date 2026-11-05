"""Frozen BBS report oracle, saved replay, fake attacks, three-call live and integrity.

Only M6 proof validation hydrates the source. No OCR, extraction, new verification
or calculations. All output paths are new and local to M7-03 evidence.
"""

import argparse
import hashlib
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from evaluate_m6_01_conversion import digest, save_new
from evaluate_m7_01_qa import SavedVerifiedView, load
from evaluate_m7_02_outline import oracle_matches_digest, wire_digest
from vietnamese_financial_multi_agent.api.qa_gateway import QACredentialError, create_qa_adapter
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError, LLMResponse
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import (
    GroundedFinancialReport,
    GroundedReportRequest,
    GroundedReportWriter,
    ReportOutlinePlanner,
    ReportOutlineRequest,
    validate_grounded_report,
)
from vietnamese_financial_multi_agent.outputs.grounded_report_writer import _retrieve
from vietnamese_financial_multi_agent.outputs.qa_composer import _assertion_signature
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

ORACLE_SHA256 = "4d8df72e5888e02602ed2648b90f8ca478eeef36b68146ddd62750e6271fffd3"


def fake_response(request, mode):
    if mode == "timeout":
        raise TimeoutError
    proposal = json.loads(request.messages[0].content)["example"]
    section = next(s for s in proposal["sections"] if s["paragraphs"])
    group = section["paragraphs"][0]
    if mode == "valid":
        group["slot_indexes"].reverse()
    elif mode == "section":
        section["section_index"] = 999
    elif mode == "slot":
        group["slot_indexes"] = [999]
    elif mode == "duplicate":
        section["paragraphs"].append(group.copy())
    elif mode == "missing":
        section["paragraphs"] = []
    elif mode == "move":
        proposal["sections"][0]["paragraphs"] = section["paragraphs"]
        section["paragraphs"] = []
    elif mode == "order":
        proposal["sections"].reverse()
    elif mode == "transition":
        group["transition"] = "strong_growth"
    elif mode == "interpretation":
        group["transition"] = "interpretation"
    elif mode in ("prose", "calculation", "citation", "caveats", "context"):
        proposal[mode] = "Doanh nghiệp an toàn; ROE tăng 999% [trang 999]."
    response = FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(proposal))(
        request
    )
    if mode == "503":
        response.status, response.finish_reason, response.output = "error", "error", None
        response.error = GatewayError(
            category="provider_unavailable",
            code="provider_unavailable",
            origin="provider",
            provider_error_code="http_503",
            retryability="retryable",
        )
    return response


def tamper_outline(outline, mode):
    section = next(s for s in outline.sections if s.claim_slots)
    slot = section.claim_slots[0]
    if mode == "id":
        slot.verified_claim_ids = ["fabricated"]
    elif mode == "content":
        slot.accepted_content += " Doanh nghiệp tăng trưởng tốt."
    elif mode == "citation":
        slot.citations[0].document_id = "fabricated"
    elif mode == "caveat":
        slot.caveats = []
    elif mode == "limitation":
        outline.limitations = []
    elif mode == "source":
        slot.claim_context.document_id = "other-document"
    elif mode == "snapshot":
        slot.claim_context.snapshot_id = "D-02/recovery-2022-v1"
    elif mode == "period":
        slot.claim_context.period = "2025-01-01"
    elif mode == "role":
        slot.period_role = (
            "closing_balance" if slot.period_role == "exact_period" else "exact_period"
        )
    elif mode == "kind":
        slot.claim_kind = (
            "supported_interpretation" if slot.claim_kind != "supported_interpretation" else "fact"
        )
    elif mode == "title":
        section.title_vi = "Doanh nghiệp an toàn tài chính"
    elif mode == "extra_section":
        outline.sections.insert(1, section.model_copy(deep=True))
    elif mode == "status":
        outline.status = "partial" if outline.status == "ready" else "ready"
    else:
        raise ValueError("unknown_tamper")
    outline.validation_result.valid = True


def selected_ledger(case, entries):
    ledger = VerifiedClaimLedger(SavedVerifiedView(entries))
    if case.get("empty_ledger"):
        return VerifiedClaimLedger(SavedVerifiedView([]))
    if case.get("wrong_facade"):

        class WrongFacade:
            def find_claims(self, query):
                return ledger.find_claims(VerifiedClaimQuery())

        return WrongFacade()
    if case.get("conflict_injection"):
        original = next(
            e
            for e in entries
            if e.identity.document_id == case["request"]["document_id"]
            and e.identity.snapshot_id == case["request"]["snapshot_id"]
            and e.identity.period == case["request"]["period"]
            and e.identity.kind == "fact"
            and e.accepted_claim.supporting_evidence[0].canonical_item_id == "b02.net_revenue"
        )
        injected = original.model_copy(deep=True)
        injected.identity.verified_claim_id = "injected:conflicting-source-context"
        reference = injected.accepted_claim.supporting_evidence[0].reference
        reference.observation = reference.observation.model_copy(
            update={"local_id": reference.observation.local_id + "-conflict"}
        )
        return VerifiedClaimLedger(SavedVerifiedView([*entries, injected]))
    return ledger


def assess(case, report, request, source, oracle, retrieved):
    required = set(case["required_verified_claim_ids"])
    selected = set(report.used_verified_claim_ids)
    paragraphs = [p for s in report.sections for p in s.paragraphs if p.source_slot_ids]
    slots = {slot.slot_id: slot for s in request.outline.sections for slot in s.claim_slots}
    unverified = len(selected - required)
    unsupported = fabricated = lost = context_errors = trace_errors = 0
    valid = validate_grounded_report(report, retrieved, request).valid
    if case.get("outline_tamper"):
        # Rejected input is not a generated report; validation must remain false.
        unsupported += bool(paragraphs or selected or report.citations)
        validation_ok = not valid and not report.validation_result.valid
    else:
        validation_ok = valid and report.validation_result.valid
        unsupported += not valid
    for paragraph in paragraphs:
        pids = set(paragraph.verified_claim_ids)
        bound_slots = [slots[k] for k in paragraph.source_slot_ids if k in slots]
        trace_errors += pids != {k for slot in bound_slots for k in slot.verified_claim_ids}
        expected_citations = set()
        for key in pids:
            if key not in source or key not in oracle["claims"]:
                unverified += 1
                continue
            accepted, pinned = source[key], oracle["claims"][key]
            unsupported += (
                hashlib.sha256(accepted.content.encode()).hexdigest() != pinned["content_sha256"]
            )

            # A suppressed wording must have an equivalent accepted assertion
            # with the same typed premises AND exact source identities here.
            def source_key(entry):
                return {
                    c.model_copy(update={"limitations": []}).model_dump_json()
                    for c in entry.citations
                }

            unsupported += not any(
                other in source
                and source[other].content in paragraph.text_vi
                and _assertion_signature(source[other]) == _assertion_signature(accepted)
                and source_key(source[other]) == source_key(accepted)
                for other in pids
            )
            fabricated += (
                wire_digest([c.model_dump(mode="json") for c in accepted.citations])
                != pinned["citations_sha256"]
            )
            expected_citations.update(c.model_dump_json() for c in accepted.citations)
            lost += len(set(pinned["required_caveats"]) - set(paragraph.caveats))
            lost += len(set(pinned["required_limitations"]) - set(paragraph.limitations))
            native = next(
                (c for c in paragraph.context if key in slots[c.source_slot_id].verified_claim_ids),
                None,
            )
            context_errors += native is None
            if native:
                values = native.claim_context.model_dump()
                context_errors += any(values[k] != v for k, v in pinned["context"].items())
                context_errors += values["reporting_scope"] != pinned["reporting_scope"]
                role = (
                    "exact_period"
                    if pinned["context"]["period"] == case["request"].get("period")
                    else "closing_balance"
                )
                context_errors += native.period_role != role
        fabricated += {c.model_dump_json() for c in paragraph.citations} != expected_citations
    for key in selected & set(source):
        lost += len(set(oracle["claims"][key]["required_caveats"]) - set(report.caveats))
    expected_citations = {
        c.model_dump_json() for k in selected & set(source) for c in source[k].citations
    }
    fabricated += {c.model_dump_json() for c in report.citations} != expected_citations
    context_errors += any(
        getattr(report.scope, k) != case["request"].get(k)
        for k in ("company_id", "document_id", "snapshot_id", "period")
    )
    if not case.get("outline_tamper"):
        context_errors += report.scope.included_periods != sorted(
            {oracle["claims"][k]["context"]["period"] for k in required}
        )
    actual_sections = [s.section_id for s in report.sections]
    expected_sections = [] if case.get("outline_tamper") else case["required_sections"]
    # Ordered section labels are pinned by the accepted M7-02 oracle.
    section_ok = actual_sections == expected_sections
    supported_ok = {s.section_id for s in report.sections if s.status == "supported"} == set(
        case["supported_sections"]
    )
    status_ok = report.status == case["expected_report_status"]
    ids_ok = selected == required
    json_ok = GroundedFinancialReport.model_validate_json(report.model_dump_json()) == report
    paragraph_ids = [key for p in paragraphs for key in p.verified_claim_ids]
    trace_errors += len(paragraph_ids) != len(set(paragraph_ids)) or set(paragraph_ids) != selected
    gateway_ok = report.llm_metadata.status == case.get("expected_gateway", "not_called")
    safety = dict(
        unverified_claims_used=unverified,
        unsupported_financial_statements=unsupported,
        fabricated_citations=fabricated,
        lost_required_caveats=lost,
        snapshot_scope_period_violations=context_errors,
        paragraph_binding_errors=trace_errors,
    )
    return dict(
        passed=all(
            (status_ok, ids_ok, section_ok, supported_ok, json_ok, validation_ok, gateway_ok)
        )
        and not any(safety.values()),
        status_agreement=status_ok,
        required_claim_coverage=len(selected & required) / len(required) if required else None,
        verified_claim_precision=len(selected & required) / len(selected) if selected else None,
        section_completeness=section_ok,
        section_order_correct=section_ok,
        json_roundtrip=json_ok,
        validation_ok=validation_ok,
        gateway_ok=gateway_ok,
        safety=safety,
        language_descriptors=dict(
            analysis_paragraphs=len(paragraphs),
            multi_slot_paragraphs=sum(len(p.source_slot_ids) > 1 for p in paragraphs),
            repeated_analysis_paragraphs=len(paragraphs) - len({p.text_vi for p in paragraphs}),
            limitations_visible=any(s.section_id == "limitations" for s in report.sections),
            quality_score=None,
        ),
    )


def integrity(root, output):
    before = load(root / "artifacts/evidence/M7-03-preflight/hashes-before.json")
    after = {name: digest(root / name) if (root / name).is_file() else None for name in before}
    summary = dict(
        protected_hashes=len(before),
        unchanged=before == after,
        changed=[name for name in before if before[name] != after[name]],
    )
    save_new(output / "hashes-after.json", after)
    save_new(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary["unchanged"]


def run_cases(root, output, cases, source, oracle, *, adapter=None, live=False, replay_root=None):
    output.mkdir(exist_ok=False)
    reports_dir = output / "reports"
    reports_dir.mkdir()
    rows, calls = [], []
    sentinels = Counter()

    def forbid(label):
        def blocked(*args, **kwargs):
            sentinels[label] += 1
            raise AssertionError("unverified_tool_called")

        return blocked

    with ExitStack() as guards:
        for target, label in (
            (
                "tools.financial_calculator.FinancialCalculator.calculate_financial_metric",
                "unauthorized_calculations",
            ),
            (
                "tools.financial_retrieval.FinancialRetrievalTools.find_financial_facts",
                "unverified_retrieval",
            ),
            ("agents.orchestrator.FinancialMultiAgentOrchestrator.run", "unverified_retrieval"),
        ):
            guards.enter_context(patch("vietnamese_financial_multi_agent." + target, forbid(label)))
        for case in cases:
            original = ReportOutlineRequest.model_validate(case["request"])
            ledger = selected_ledger(case, list(source.values()))
            outline = ReportOutlinePlanner(ledger).plan(original)
            if case.get("outline_tamper"):
                tamper_outline(outline, case["outline_tamper"])
            request = GroundedReportRequest(
                outline=outline,
                outline_request=original,
                allow_gateway=live or replay_root is not None or bool(case.get("gateway_mode")),
            )

            def transport(bound, scenario=case):
                if live:
                    budget = root / "artifacts/evidence/M7-03-call-budget"
                    budget.mkdir(exist_ok=True)
                    slot = next(
                        (i for i in range(1, 4) if not (budget / f"call-{i}.json").exists()), None
                    )
                    if slot is None:
                        raise ValueError("task_live_budget_exhausted")
                    save_new(
                        budget / f"call-{slot}.json",
                        dict(case_id=scenario["id"], request_id=bound.request_id),
                    )
                calls.append(bound.request_id)
                save_new(output / f"request-{len(calls)}.json", bound.model_dump(mode="json"))
                if replay_root is not None:
                    saved_rows = load(replay_root / "summary.json")["rows"]
                    index = next(
                        i for i, row in enumerate(saved_rows, 1) if row["id"] == scenario["id"]
                    )
                    saved_path = replay_root / f"gateway-{index}.json"
                    result = LLMResponse.model_validate_json(saved_path.read_text(encoding="utf8"))
                    result.request_id, result.correlation = bound.request_id, bound.correlation
                    save_new(
                        output / f"replay-source-{len(calls)}.json",
                        dict(
                            path=saved_path.relative_to(root).as_posix(), sha256=digest(saved_path)
                        ),
                    )
                else:
                    result = (
                        adapter(bound) if live else fake_response(bound, scenario["gateway_mode"])
                    )
                save_new(output / f"gateway-{len(calls)}.json", result.model_dump(mode="json"))
                return result

            gateway = SharedLLMGateway({"gemini": transport}) if request.allow_gateway else None
            # Prohibit the writer from invoking M7-02 again; the existing outline is its input.
            with patch.object(ReportOutlinePlanner, "plan", forbid("outline_replanning")):
                start = perf_counter()
                report = GroundedReportWriter(ledger, gateway).write(request)
                elapsed = (perf_counter() - start) * 1000
            scoring_case = case.copy()
            if live or replay_root is not None:
                # Provider acceptance is measured separately from source/structure agreement.
                scoring_case["expected_gateway"] = report.llm_metadata.status
            row = dict(
                id=case["id"],
                group="fresh_Gemini"
                if live
                else "saved_Gemini_replay"
                if replay_root
                else case["group"],
                status=report.status,
                warm_generation_ms=elapsed,
                llm=report.llm_metadata.model_dump(mode="json"),
                **assess(
                    scoring_case, report, request, source, oracle, _retrieve(ledger, original)
                ),
            )
            rows.append(row)
            save_new(output / f"response-{case['id']}.json", report.model_dump(mode="json"))
            if case.get("live") and not case.get("outline_tamper"):
                # Production writer body, not evaluator-authored prose.
                with (reports_dir / f"{case['id']}.md").open("x", encoding="utf8") as f:
                    f.write(report.body_vi + "\n")
                save_new(reports_dir / f"{case['id']}.json", report.model_dump(mode="json"))
                save_new(
                    reports_dir / f"{case['id']}-bindings.json",
                    dict(
                        scope=report.scope.model_dump(mode="json"),
                        caveats=report.caveats,
                        limitations=report.limitations,
                        missing_information=report.missing_information,
                        paragraphs=[
                            p.model_dump(mode="json") for s in report.sections for p in s.paragraphs
                        ],
                    ),
                )
            print(
                f"{case['id']}: {report.status} {'PASS' if row['passed'] else 'FAIL'}", flush=True
            )
    latencies = [r["warm_generation_ms"] for r in rows]
    summary = dict(
        cases=len(rows),
        all_passed=all(r["passed"] for r in rows) and not any(sentinels.values()),
        groups=dict(Counter(r["group"] for r in rows)),
        status_agreement=sum(r["status_agreement"] for r in rows) / len(rows),
        safety={k: sum(r["safety"][k] for r in rows) for k in rows[0]["safety"]},
        tool_sentinels=dict(sentinels),
        metrics={
            k: sum(v) / len(v) if (v := [r[k] for r in rows if r[k] is not None]) else None
            for k in [
                "required_claim_coverage",
                "verified_claim_precision",
                "section_completeness",
                "section_order_correct",
                "json_roundtrip",
            ]
        },
        warm_generation_ms=dict(
            min=min(latencies), mean=sum(latencies) / len(latencies), max=max(latencies)
        ),
        calls=len(calls),
        fresh_calls=len(calls) if live else 0,
        saved_response_replays=len(calls) if replay_root else 0,
        known_tokens=sum((r["llm"].get("usage") or {}).get("total_tokens") or 0 for r in rows),
        unknown_usage_calls=sum(
            r["llm"]["calls"] and (r["llm"].get("usage") or {}).get("total_tokens") is None
            for r in rows
        ),
        accepted_proposals=sum(r["llm"]["status"] == "accepted" for r in rows),
        fallback_cases=sum(r["llm"]["status"] == "fallback" for r in rows),
        fallback_success=sum(r["llm"]["status"] == "fallback" and r["passed"] for r in rows),
        provider_errors=sum(r["llm"]["error"] is not None for r in rows),
        rows=rows,
        language_quality="Descriptive paragraph/repetition/visibility heuristics only; no automatic language score. Tech Lead review required.",
        limitations="Source-bound oracle agreement, not independent financial accuracy; same contexts reused for different report types.",
    )
    if live:
        summary["live_status"] = (
            "SUCCESS"
            if len(calls) == 3 and summary["accepted_proposals"] == 3 and summary["all_passed"]
            else "PARTIAL"
        )
    save_new(output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}), flush=True)
    return summary["all_passed"]


def evaluate(root, output, ledger_root, mode, replay_root=None):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M7-03-"
    ):
        raise ValueError("new_M7_03_evidence_output_required")
    output.mkdir(exist_ok=False)
    if mode == "integrity":
        return integrity(root, output)
    oracle_path = root / "evaluation/m7-03-scenarios.json"
    if not oracle_matches_digest(oracle_path, ORACLE_SHA256):
        raise ValueError("frozen_oracle_changed")
    oracle = load(oracle_path)
    for path, pin in oracle["pins"].items():
        if not oracle_matches_digest(root / path, pin):
            raise ValueError("accepted_outline_oracle_changed")
    if (
        not ledger_root.is_dir()
        or digest(ledger_root / "verified-claims.json") != oracle["ledger_sha256"]
    ):
        raise ValueError("ledger_missing_or_not_pinned")
    save_new(output / "expected-oracle.json", oracle)
    print("Cold proof-validation read of pinned M6 ledger", flush=True)
    start = perf_counter()
    entries = (
        VerifiedClaimLedger(VerifiedClaimRepository(ledger_root))
        .find_claims(VerifiedClaimQuery())
        .claims
    )
    cold_seconds = perf_counter() - start
    source = {e.identity.verified_claim_id: e for e in entries}
    save_new(
        output / "preflight.json",
        dict(
            entries=len(entries),
            cold_read_seconds=cold_seconds,
            kinds=dict(Counter(e.identity.kind for e in entries)),
            ledger_sha256=oracle["ledger_sha256"],
            oracle_sha256=ORACLE_SHA256,
            unique_source_contexts=len(
                {
                    tuple(c["request"].get(k) for k in ("document_id", "snapshot_id"))
                    for c in oracle["scenarios"]
                    if c["group"] == "saved_source"
                }
            ),
        ),
    )
    print(f"Hydrated {len(entries)} entries in {cold_seconds:.3f}s", flush=True)
    passed = True
    if mode in ("offline", "saved-source", "fake", "all", "replay"):
        cases = oracle["scenarios"]
        if mode == "saved-source":
            cases = [c for c in cases if c["group"] == "saved_source"]
        elif mode == "fake":
            cases = [c for c in cases if c["group"] != "saved_source"]
        passed = run_cases(root, output / "offline", cases, source, oracle)
    if mode == "replay" and passed:
        if replay_root is None or not replay_root.is_relative_to(root / "artifacts/evidence"):
            raise ValueError("local_saved_Gemini_response_root_required")
        passed &= run_cases(
            root,
            output / "replay",
            [c for c in oracle["scenarios"] if c.get("live")],
            source,
            oracle,
            replay_root=replay_root,
        )
    if mode in ("live", "all") and passed:
        try:
            adapter, _ = create_qa_adapter(root)
        except QACredentialError:
            save_new(
                output / "live-blocked.json",
                dict(live_status="BLOCKED", reason="credential_unavailable", calls=0),
            )
            print("LIVE BLOCKED: credential unavailable", flush=True)
        else:
            try:
                passed &= run_cases(
                    root,
                    output / "live",
                    [c for c in oracle["scenarios"] if c.get("live")],
                    source,
                    oracle,
                    adapter=adapter,
                    live=True,
                )
            finally:
                adapter.close()
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ledger-root", type=Path, default=Path("artifacts/evidence/M6-06-ledger-final-v2/ledger")
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "saved-source", "fake", "live", "all", "replay", "integrity"),
        default="offline",
    )
    parser.add_argument("--replay-root", type=Path)
    args = parser.parse_args()
    raise SystemExit(
        0
        if evaluate(
            Path.cwd().resolve(),
            args.output.resolve(),
            args.ledger_root.resolve(),
            args.mode,
            args.replay_root.resolve() if args.replay_root else None,
        )
        else 1
    )
