"""Fixed-oracle BBS outline replay, fake attacks and optional task-bounded live.

Outputs stay local and new. The real repository validates proof histories once;
warm planning uses the existing public AND-query semantics over that saved view.
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
from vietnamese_financial_multi_agent.api.qa_gateway import QACredentialError, create_qa_adapter
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import ReportOutlinePlanner, ReportOutlineRequest
from vietnamese_financial_multi_agent.outputs.report_outline_planner import SECTION_CATALOG
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)


def wire_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def fake_response(request, mode):
    if mode == "timeout":
        raise TimeoutError
    projection = json.loads(request.messages[0].content)
    sections = [
        dict(
            section_id=s["section_id"],
            slot_order=[slot["slot_id"] for slot in reversed(s["slots"])],
        )
        for s in projection["sections"]
    ]
    sections[1:-1] = reversed(sections[1:-1])
    populated = next(s for s in sections if s["slot_order"])
    wire = dict(sections=sections)
    if mode == "section":
        sections[1]["section_id"] = "invented"
    elif mode == "slot":
        populated["slot_order"] = ["invented"]
    elif mode == "duplicate":
        populated["slot_order"] *= 2
    elif mode == "missing":
        populated["slot_order"] = []
    elif mode == "move_slot":
        sections[0]["slot_order"] = populated["slot_order"]
        populated["slot_order"] = []
    elif mode == "position":
        sections.reverse()
    elif mode in ("title", "prose", "citation", "caveats", "scope"):
        wire[mode] = "Unsupported financial assertion 999"
    response = FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(wire))(request)
    if mode == "503":
        response.status, response.finish_reason, response.output = "error", "error", None
        response.error = GatewayError(
            category="provider_unavailable",
            code="provider_unavailable",
            origin="provider",
            retryability="retryable",
            provider_error_code="http_503",
        )
    return response


def assess(case, response, source, oracle):
    """Compare accepted payloads/independent oracle, never generate labels from plans."""
    selected = set(response.used_verified_claim_ids)
    expected = set(case["required_verified_claim_ids"])
    supported = {s.section_id for s in response.sections if s.status == "supported"}
    required_sections = set(case["supported_sections"])
    unsupported = fabricated = lost = violations = unverified = 0
    unsupported_objectives = sum(
        (s.title_vi, s.purpose) != SECTION_CATALOG[s.section_type] for s in response.sections
    )
    slots = [slot for section in response.sections for slot in section.claim_slots]
    for slot in slots:
        originals = [source[k] for k in slot.verified_claim_ids if k in source]
        for key in slot.verified_claim_ids:
            if key not in source or key not in oracle["claims"]:
                unverified += 1
                continue
            original = source[key]
            bound = oracle["claims"][key]
            unsupported += (
                hashlib.sha256(slot.accepted_content.encode()).hexdigest()
                != bound["content_sha256"]
            )
            unsupported += slot.claim_kind != bound["kind"]
            context = slot.claim_context.model_dump(exclude={"reporting_scope"})
            violations += context != bound["context"]
            violations += slot.claim_context.reporting_scope != bound["reporting_scope"]
            violations += any(
                case["request"].get(k) is not None and v != case["request"][k]
                for k, v in context.items()
            )
            violations += any(getattr(response.scope, k) != v for k, v in context.items())
            violations += bool(
                case["request"].get("reporting_scope")
                and slot.claim_context.reporting_scope != case["request"]["reporting_scope"]
            )
            required = set(bound["required_caveats"])
            lost += len(required - set(slot.caveats)) + len(required - set(response.caveats))
            limits = set(bound["required_limitations"])
            lost += len(limits - set(slot.limitations)) + len(limits - set(response.limitations))
            fabricated += sum(c not in slot.citations for c in original.citations)
            # Independent frozen oracle also pins the complete original citation wire.
            fabricated += (
                wire_digest([c.model_dump(mode="json") for c in original.citations])
                != bound["citations_sha256"]
            )
        fabricated += sum(not any(c in e.citations for e in originals) for c in slot.citations)
        section = next(s for s in response.sections if slot in s.claim_slots)
        unsupported_objectives += section.section_id != "overview" and any(
            oracle["claims"].get(k, {}).get("category") != section.section_id
            for k in slot.verified_claim_ids
        )
    fabricated += sum(not any(c in slot.citations for slot in slots) for c in response.citations)
    status_ok = response.status == case["expected_status"]
    sections_ok = (
        set(s.section_id for s in response.sections) == set(case["required_sections"])
        and supported == required_sections
    )
    gateway_ok = (
        not case.get("expected_gateway") or response.llm_metadata.status == case["expected_gateway"]
    )
    omitted_ok = response.omitted_sections == case["omitted_sections"]
    safety = dict(
        unsupported_financial_claims=unsupported,
        fabricated_citations=fabricated,
        lost_caveats=lost,
        snapshot_scope_violations=violations,
        unverified_claim_leakage=unverified,
        unsupported_sections_objectives=int(unsupported_objectives),
    )
    return dict(
        passed=bool(
            status_ok
            and sections_ok
            and omitted_ok
            and gateway_ok
            and selected == expected
            and not any(safety.values())
            and response.validation_result.valid
        ),
        status_agreement=status_ok,
        section_agreement=sections_ok,
        omitted_agreement=omitted_ok,
        gateway_agreement=gateway_ok,
        claim_precision=len(selected & expected) / len(selected) if selected else None,
        claim_recall=len(selected & expected) / len(expected) if expected else None,
        section_precision=len(supported & required_sections) / len(supported)
        if supported
        else None,
        section_recall=len(supported & required_sections) / len(required_sections)
        if required_sections
        else None,
        missing_ids=sorted(expected - selected),
        unexpected_ids=sorted(selected - expected),
        **safety,
    )


def integrity(root, output):
    before = load(root / "artifacts/evidence/M7-02-preflight/hashes-before.json")
    # Additional normalized/canonical/crop inputs pinned by the accepted M7-01 baseline.
    # These were compared unchanged before inclusion; retain both manifests intact.
    before.update(
        load(root / "artifacts/evidence/M7-02-preflight/supplemental-accepted-hashes.json")
    )
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


def run_cases(root, output, cases, source, oracle, *, live=False, adapter=None):
    output.mkdir(exist_ok=False)
    ledger = VerifiedClaimLedger(SavedVerifiedView(source.values()))
    empty = VerifiedClaimLedger(SavedVerifiedView([]))
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

            def transport(request, scenario=case):
                if live:
                    budget = root / "artifacts/evidence/M7-02-call-budget"
                    budget.mkdir(exist_ok=True)
                    slot = next(
                        (i for i in range(1, 4) if not (budget / f"call-{i}.json").exists()), None
                    )
                    if slot is None:
                        raise ValueError("task_live_budget_exhausted")
                    save_new(
                        budget / f"call-{slot}.json",
                        dict(case_id=scenario["id"], request_id=request.request_id),
                    )
                calls.append(dict(case_id=scenario["id"]))
                save_new(output / f"request-{len(calls)}.json", request.model_dump(mode="json"))
                result = (
                    adapter(request) if live else fake_response(request, scenario["gateway_mode"])
                )
                save_new(output / f"gateway-{len(calls)}.json", result.model_dump(mode="json"))
                return result

            gateway = (
                SharedLLMGateway({"gemini": transport})
                if live or case.get("gateway_mode")
                else None
            )
            request = ReportOutlineRequest.model_validate(case["request"])
            if live:
                request.allow_gateway = True
            selected_ledger = empty if case.get("empty_ledger") else ledger
            if case.get("wrong_facade"):

                class WrongFacade:
                    def find_claims(self, query):
                        return ledger.find_claims(VerifiedClaimQuery())

                selected_ledger = WrongFacade()
            if case.get("conflict_injection"):
                candidates = ledger.find_claims(
                    VerifiedClaimQuery(
                        **{
                            k: case["request"][k]
                            for k in ("company_id", "document_id", "snapshot_id", "period")
                        }
                    )
                ).claims
                original = next(
                    e
                    for e in candidates
                    if e.identity.kind == "fact"
                    and e.accepted_claim.supporting_evidence[0].canonical_item_id
                    == "b02.net_revenue"
                )
                injected = original.model_copy(deep=True)
                injected.identity.verified_claim_id = "injected:conflicting-source-context"
                # Preserve the accepted value; alter the source selector only, in a detached adversarial view.
                reference = injected.accepted_claim.supporting_evidence[0].reference
                reference.observation = reference.observation.model_copy(
                    update={"local_id": reference.observation.local_id + "-conflict"}
                )
                selected_ledger = VerifiedClaimLedger(
                    SavedVerifiedView([*source.values(), injected])
                )
            started = perf_counter()
            response = ReportOutlinePlanner(selected_ledger, gateway).plan(request)
            row = dict(
                id=case["id"],
                group="fresh_Gemini" if live else case["group"],
                status=response.status,
                latency_ms=(perf_counter() - started) * 1000,
                llm=response.llm_metadata.model_dump(mode="json"),
                **assess(case, response, source, oracle),
            )
            rows.append(row)
            save_new(output / f"response-{case['id']}.json", response.model_dump(mode="json"))
            print(
                f"{case['id']}: {response.status} {'PASS' if row['passed'] else 'FAIL'}", flush=True
            )
    safety_keys = (
        "unsupported_financial_claims",
        "fabricated_citations",
        "lost_caveats",
        "snapshot_scope_violations",
        "unverified_claim_leakage",
        "unsupported_sections_objectives",
    )
    summary = dict(
        mode="live" if live else "offline",
        all_passed=all(r["passed"] for r in rows),
        cases=len(rows),
        groups={
            name: dict(
                cases=len(group := [r for r in rows if r["group"] == name]),
                passed=sum(r["passed"] for r in group),
            )
            for name in sorted({r["group"] for r in rows})
        },
        status_agreement=sum(r["status_agreement"] for r in rows) / len(rows),
        safety={k: sum(r[k] for r in rows) for k in safety_keys},
        tool_sentinels=dict(sentinels),
        calls=len(calls),
        proposal_statuses=dict(Counter(r["llm"]["status"] for r in rows)),
        fallback_cases=sum(r["llm"]["status"] == "fallback" for r in rows),
        fallback_success=sum(r["llm"]["status"] == "fallback" and r["passed"] for r in rows),
        tokens=sum((r["llm"].get("usage") or {}).get("total_tokens") or 0 for r in rows),
        provider_errors=sum(r["llm"]["error"] is not None for r in rows),
        metrics={
            key: sum(values) / len(values)
            if (values := [r[key] for r in rows if r[key] is not None])
            else None
            for key in ("claim_precision", "claim_recall", "section_precision", "section_recall")
        },
        warm_latency_ms=dict(
            min=min(r["latency_ms"] for r in rows), max=max(r["latency_ms"] for r in rows)
        ),
        rows=rows,
        limitations="Saved-source oracle agreement, synthetic adversarial boundary injections and fresh live are separate; no independent PDF financial accuracy or OCR/extraction.",
    )
    summary["all_passed"] &= not any(sentinels.values())
    if live:
        summary["live_status"] = (
            "SUCCESS"
            if len(calls) == 3
            and all(r["llm"]["status"] == "accepted" and r["passed"] for r in rows)
            else "PARTIAL"
        )
    save_new(output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}), flush=True)
    return summary["all_passed"]


def evaluate(root, output, ledger_root, mode):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M7-02-"
    ):
        raise ValueError("new_M7_02_evidence_output_required")
    output.mkdir(exist_ok=False)
    if mode == "integrity":
        return integrity(root, output)
    oracle_path = root / "evaluation/m7-02-scenarios.json"
    oracle = load(oracle_path)
    save_new(output / "expected-oracle.json", oracle)
    if digest(ledger_root / "verified-claims.json") != oracle["ledger_sha256"]:
        raise ValueError("ledger_missing_or_not_pinned")
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
            cold_read_seconds=cold_seconds,
            entries=len(entries),
            kinds=dict(Counter(e.identity.kind for e in entries)),
            oracle_sha256=digest(oracle_path),
            ledger_sha256=oracle["ledger_sha256"],
        ),
    )
    print(f"Hydrated {len(entries)} entries in {cold_seconds:.3f}s", flush=True)
    passed = True
    if mode in ("offline", "all"):
        passed &= run_cases(root, output / "offline", oracle["scenarios"], source, oracle)
    if mode in ("live", "all"):
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
                    live=True,
                    adapter=adapter,
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
        "--mode", choices=("offline", "live", "all", "integrity"), default="offline"
    )
    args = parser.parse_args()
    raise SystemExit(
        0
        if evaluate(
            Path.cwd().resolve(), args.output.resolve(), args.ledger_root.resolve(), args.mode
        )
        else 1
    )
