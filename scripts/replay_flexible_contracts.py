"""Replay exact saved Q21 revision and historical proofs without provider calls.

Artifacts stay ignored. Deterministic Specialist dispatch is an engineering
smoke only: no missing round-1 provider response or M6 ACCEPT is fabricated.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from evaluate_real_pdf import build, digest, protected, runtime, save

FIXES = (
    "src/agents/query_planner.py",
    "src/agents/specialist_common.py",
    "src/outputs/qa_composer.py",
    "src/outputs/qa_contracts.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh_output_directory_required")
    root = Path.cwd()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    guard = {p: h for p, h in protected(root).items() if not p.startswith("src/")}
    runtime(args.output, head)
    if args.candidate:
        for name in FIXES:
            shutil.copyfile(root / name, args.output / "runtime" / name)
    from vietnamese_financial_multi_agent.agents import PlannerContext
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerProposal
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.outputs.firewall_qa_binding import request_inventory
    from vietnamese_financial_multi_agent.outputs.qa_composer import planned_requirements
    from vietnamese_financial_multi_agent.outputs.qa_contracts import VietnameseQARequest
    from vietnamese_financial_multi_agent.verification.ledger import validate_entry
    from vietnamese_financial_multi_agent.verification.ledger_contracts import (
        VerifiedClaimLedgerSnapshot,
    )

    base = root / "artifacts/evidence/FIX-02/planner-dependencies/live"
    saved = [json.loads(p.read_bytes()) for p in (base / "provider").glob("planner-*.json")]
    revision = next(
        s
        for s in saved
        if any(
            t.get("interpretation") and t.get("target_id")
            for t in s["response"]["output"]["payload"]["user_requested_targets"]
        )
    )
    prompt = json.loads(revision["request"]["messages"][0]["content"])
    context = PlannerContext.model_validate(prompt["context"])
    context.mode = "auto"
    payload = revision["response"]["output"]["payload"]
    calls = []

    def transport(request):
        calls.append(request.request_id)
        # Only the transport envelope is rebound; raw Gemini output is untouched.
        return LLMResponse.model_validate(
            dict(
                revision["response"], request_id=request.request_id, correlation=request.correlation
            )
        )

    pipeline = build(root, args.output)
    pipeline.gateway = SharedLLMGateway({"gemini": transport})
    question = next(
        q["question"]
        for q in json.loads((root / "artifacts/evidence/E2E-02/questions.json").read_bytes())
        if q["id"] == "Q21"
    )
    m5 = pipeline._m5(
        FinancialQARequest(question=question, execution_mode="auto", allow_gateway=True)
    )
    for specialist in m5._specialists.values():
        specialist._deterministic = True
    result = m5.run(question=question, context=context)
    save(args.output / "revision.json", result.model_dump(mode="json"))
    assert result.planner_result.raw_proposal == payload
    proofs, prior_entries = [], []
    # Replay captured native M6 decisions/proofs from Q21/Q11/F08. Never invoke
    # a fake Critic or replace a stored non-ACCEPT decision with acceptance.
    historical = root / "artifacts/evidence/FIX-02/controlled-live-9a356bf/run"
    for folder in (base, historical):
        path = folder / "ledger/verified-claims.json"
        if not path.exists():
            continue
        before = digest(path)
        snapshot = VerifiedClaimLedgerSnapshot.model_validate_json(path.read_bytes())
        for entry in snapshot.entries:
            validate_entry(entry)
        if folder == base:
            prior_entries = snapshot.entries
        assert digest(path) == before
        proofs.append(
            dict(path=str(path.relative_to(root)), count=len(snapshot.entries), unchanged=True)
        )
    compatibility = []
    for path in sorted((historical / "provider").glob("planner-*.json")):
        source = json.loads(path.read_bytes())
        parsed = PlannerProposal.model_validate(source["response"]["output"]["payload"])
        revision = source
        saved_prompt = json.loads(source["request"]["messages"][0]["content"])
        saved_context = PlannerContext.model_validate(saved_prompt["context"])
        saved_context.mode = "auto"
        saved_question = source["request"]["messages"][-1]["content"]
        m5.reset_request()
        replay = m5.run(question=saved_question, context=saved_context)
        save(args.output / (path.stem + "-dispatch.json"), replay.model_dump(mode="json"))
        compatibility.append(
            dict(
                path=path.name,
                intent=parsed.intent,
                roles=parsed.ordered_specialist_roles(),
                planner_status=replay.planner_result.status,
                supervisor_status=replay.supervisor_result.status
                if replay.supervisor_result
                else None,
                executed=[e.role for e in replay.specialist_executions],
                raw_unchanged=replay.planner_result.raw_proposal
                == source["response"]["output"]["payload"],
            )
        )
    identity = prior_entries[0].identity
    inventory, coverage_status = request_inventory(
        VietnameseQARequest(
            question=question,
            **{
                field: getattr(identity, field)
                for field in ("company_id", "document_id", "snapshot_id", "period")
            },
            answer_requirements=planned_requirements(
                question, result.planner_result.effective_proposal
            ),
        ),
        prior_entries,
    )
    summary = dict(
        baseline_sha=head,
        candidate=args.candidate,
        planner_status=result.planner_result.status,
        reasons=result.planner_result.reasons,
        supervisor_status=result.supervisor_result.status if result.supervisor_result else None,
        roles=result.routing_decision.selected_roles if result.routing_decision else [],
        executions=[dict(role=e.role, status=e.status) for e in result.specialist_executions],
        formula_ids=result.planner_result.effective_proposal.formula_ids,
        provider_calls=0,
        raw_output_unchanged=True,
        replayed_envelopes=len(calls),
        proofs=proofs,
        compatibility=compatibility,
        prior_accept_coverage=dict(
            status=coverage_status,
            covered=sum(bool(r.verified_claim_ids) for r in inventory.requirements),
            total=len(inventory.requirements),
            retained_ids=inventory.selected_verified_claim_ids,
        ),
        unavailable_stages=[
            "Q21 revision Specialist/Critics/Judge raw responses were never captured"
        ],
        protected_count=len(guard),
        protected_unchanged=all(digest(root / p) == h for p, h in guard.items()),
    )
    save(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
