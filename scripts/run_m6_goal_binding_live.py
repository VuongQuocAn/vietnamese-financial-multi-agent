"""Saved M5 only: up to two live M6 batches, ordinary Ledger and unmodified M7."""

import argparse
import json
import subprocess
from pathlib import Path

from fastapi.encoders import jsonable_encoder
from run_vfb_qwen_e2e import digest
from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
from vietnamese_financial_multi_agent.verification.evidence_obligations import (
    current_goal_support,
    goal_binding_issue,
    goal_context,
)
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import (
    LiteVerificationRuntime,
    semantic_payload,
)


def run(root, source, output):
    saved = json.loads(source.read_bytes())
    original = OrchestrationResult.model_validate_json(
        json.dumps(saved["response"]["trace"]["financial_execution"])
    )
    context = original.integration_context
    batch = to_verification_input(original)
    # Same serialization/48KB bound as M6; split only when required, never retry.
    local = batch.model_copy(deep=True)
    if len({c.period[:4] for c in batch.claims}) > 1:
        local.context.reporting_year = None
    chunks, current, rows = [], [], []
    for claim in batch.claims:
        row = semantic_payload(local, claim, goal_context(context, claim))
        if rows and len(json.dumps([*rows, row], ensure_ascii=False)) > 48000:
            chunks.append(current)
            current, rows = [], []
        current.append(claim)
        rows.append(row)
    chunks.append(current)
    assert 1 <= len(chunks) <= 2
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    alias = saved["case"]["document_alias"]
    company, year = alias.split("_")
    receipt = dict(
        baseline_sha=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        runtime_hashes={
            p.relative_to(root).as_posix(): digest(p) for p in sorted((root / "src").rglob("*.py"))
        },
        source_hashes={
            p.relative_to(root).as_posix(): digest(p)
            for p in sorted((root / "ViFinBench/refined" / company / year).glob("*.json"))
        },
        source_trace_sha256=digest(source),
        runner_sha256=digest(Path(__file__)),
        settings=dict(
            max_live_calls=2,
            batches=len(chunks),
            retries=0,
            mode="exact_saved_m5_live_m6_no_coordinator",
        ),
    )
    atomic_json(output / "implementation.json", receipt)
    atomic_json(output / "saved-m5-input.json", original.model_dump(mode="json"))
    historical = VerifiedClaimRepository(source.parent / "ledger").list_all()
    before = [
        dict(
            candidate_id=e.identity.accepted_candidate_id,
            decision=e.decision.decision,
            raw_supported=e.history.proof.semantic.supported_requirement_ids,
            effective_supported=current_goal_support(e, original.question, context["requirements"]),
        )
        for e in historical
    ]
    atomic_json(output / "historical-binding-replay.json", before)
    configured = create_text_gateway(root, provider="qwen")
    calls = 0

    def transport(request):
        nonlocal calls
        assert calls < 2 and request.request_id.startswith("m6-")
        calls += 1
        atomic_json(
            output / "provider" / f"{calls:03}-request.json", request.model_dump(mode="json")
        )
        response = configured.adapter(request)
        atomic_json(output / "provider" / f"{calls:03}.json", response.model_dump(mode="json"))
        return response

    try:
        catalog = load_json_corpus_document(
            root / "ViFinBench/refined", root / "artifacts/evidence/VFB-IMPORT-03/full-final", alias
        )
        runtime = LiteVerificationRuntime(
            catalog,
            SharedLLMGateway({"qwen": transport}),
            model=configured.model,
            integration_v2=True,
        )
        histories = []
        for claims in chunks:
            histories.extend(
                runtime.verify(
                    batch.model_copy(update=dict(claims=claims)), integration_context=context
                )
            )
        repository = VerifiedClaimRepository(output / "ledger")
        admissions = repository.admit_many(
            [h for h in histories if h.outcome.final.decision == "ACCEPT"]
        )
        entries = VerifiedClaimRepository(output / "ledger").list_all()
        bindings = {
            e.identity.verified_claim_id: current_goal_support(
                e, original.question, context["requirements"]
            )
            for e in entries
        }
        fields, m7 = compose_lite(
            FinancialQARequest(question=original.question, allow_gateway=False),
            entries,
            coverage_context=dict(
                requirements=context["requirements"], verified_requirements=bindings
            ),
        )
        result = dict(
            mode="exact_saved_m5_live_m6_no_coordinator",
            actual_live_calls=calls,
            histories=[h.model_dump(mode="json") for h in histories],
            admissions=[r.model_dump(mode="json") for r in admissions],
            decisions=[
                dict(
                    candidate_id=h.outcome.final.candidate_id,
                    decision=h.outcome.final.decision,
                    supported=current_goal_support(e, original.question, context["requirements"])
                    if (
                        e := next(
                            (
                                e
                                for e in entries
                                if e.identity.accepted_candidate_id == h.outcome.final.candidate_id
                            ),
                            None,
                        )
                    )
                    else [],
                    binding_checks={
                        r["requirement_id"]: goal_binding_issue(h.proof, r)
                        for r in h.proof.goal_context["local_requirements"]
                    },
                )
                for h in histories
            ],
            verified_requirements=bindings,
            fields=fields,
            m7=m7,
        )
        atomic_json(output / "result.json", jsonable_encoder(result))
        print(
            json.dumps(
                dict(
                    calls=calls,
                    decisions=result["decisions"],
                    released=len(m7["released_claims"]),
                    citations=len(fields["citations"]),
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        configured.close()
        assert all(
            digest(root / name) == expected for name, expected in receipt["source_hashes"].items()
        )
        print(json.dumps(dict(source_hashes_unchanged=len(receipt["source_hashes"]))), flush=True)


def finish_saved(output):
    """Complete rendering after export failure, using admitted histories; no API."""
    original = OrchestrationResult.model_validate_json(
        (output / "saved-m5-input.json").read_text(encoding="utf-8")
    )
    context = original.integration_context
    entries = VerifiedClaimRepository(output / "ledger").list_all()
    assert {e.identity.accepted_candidate_id for e in entries} == {
        c.candidate_id for c in original.candidates
    }
    bindings = {
        e.identity.verified_claim_id: current_goal_support(
            e, original.question, context["requirements"]
        )
        for e in entries
    }
    fields, m7 = compose_lite(
        FinancialQARequest(question=original.question, allow_gateway=False),
        entries,
        coverage_context=dict(requirements=context["requirements"], verified_requirements=bindings),
    )
    calls = len(
        [p for p in (output / "provider").glob("*.json") if not p.name.endswith("-request.json")]
    )
    result = dict(
        mode="saved_m5_live_m6_saved_ledger_m7",
        actual_live_calls=calls,
        histories=[e.history.model_dump(mode="json") for e in entries],
        decisions=[
            dict(
                candidate_id=e.identity.accepted_candidate_id,
                decision=e.decision.decision,
                supported=bindings[e.identity.verified_claim_id],
                binding_checks={
                    r["requirement_id"]: goal_binding_issue(e.history.proof, r)
                    for r in e.history.proof.goal_context["local_requirements"]
                },
            )
            for e in entries
        ],
        verified_requirements=bindings,
        fields=fields,
        m7=m7,
    )
    atomic_json(output / "result.json", jsonable_encoder(result))
    print(
        json.dumps(
            dict(
                calls=calls,
                decisions=result["decisions"],
                released=len(m7["released_claims"]),
                citations=len(fields["citations"]),
            ),
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-result", type=Path, required=True)
    parser.add_argument("--compose-saved", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/M6-GOAL-FIX-01/live-v1")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/M6-GOAL-FIX-01"):
        parser.error("output outside M6-GOAL-FIX-01")
    if args.compose_saved:
        finish_saved(output)
    else:
        run(root, args.saved_result.resolve(), output)
