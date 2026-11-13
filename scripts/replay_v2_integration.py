"""V2-INT-01: saved real-data boundary replay, no LLM/PDF processing or source writes."""

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

from evaluate_composition_graph import bbs_catalog
from evaluate_generalization import pipeline
from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationRequirement
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    integration_plan,
)
from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
from vietnamese_financial_multi_agent.verification.ledger import validate_entry
from vietnamese_financial_multi_agent.verification.ledger_contracts import LedgerEntry
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime


def replay(root, source, output):
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("separate_output_required")
    output.mkdir(parents=True, exist_ok=True)

    def read(name):
        return json.loads((source / name).read_text(encoding="utf-8"))

    input_hashes = {
        str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source.rglob("*.json")
    }
    bbs = bbs_catalog(root)
    services = {
        label: pipeline(root, label, output / "inputs", bbs)[0]
        for label in ("BBS_2025", "BCC_2025")
    }
    report = dict(mode="offline_boundary_replay", model_calls=0, cases={})
    for case, label in (("C04", "BBS_2025"), ("C10", "BCC_2025")):
        saved = read(f"execution/{case}.json")
        financial = OrchestrationResult.model_validate_json(
            json.dumps(saved["response"]["trace"]["financial_execution"])
        )
        batch = to_verification_input(financial)
        runtime = LiteVerificationRuntime(services[label].catalog, integration_v2=True)
        histories = runtime.verify(batch)
        decisions = {h.outcome.final.candidate_id: h.outcome.final for h in histories}
        report["cases"][case] = [
            dict(candidate_id=cid, decision=d.decision, reasons=d.reason_codes)
            for cid, d in decisions.items()
        ]
        if case == "C04":
            absence_ids = (
                "candidate:132b0639d72899aa754133e4",
                "candidate:ecb5eb3d9cacdc6d38725547",
                "candidate:e1a18014d7a0431fa6466df3",
            )
            assert all(decisions[c].decision != "ACCEPT" for c in absence_ids)
            assert any(d.decision == "ACCEPT" for d in decisions.values())
        else:
            correct_ids = (
                "candidate:9b36f2a651a2399a6351b6e0",
                "candidate:56dbd146a346b8bf7ec20259",
                "candidate:493da2d1bacb2ceaa9341529",
            )
            assert all(decisions[c].decision == "ACCEPT" for c in correct_ids)
            assert decisions["candidate:022da587dd08a70ce6f2610a"].decision != "ACCEPT"
            for cid in correct_ids:
                from vietnamese_financial_multi_agent.verification.ledger import (
                    build_verified_claim,
                )

                validate_entry(
                    build_verified_claim(
                        next(h for h in histories if h.outcome.final.candidate_id == cid)
                    )
                )

    event = next(
        e
        for e in read("provider-events.json")
        if e["case"] == "C01" and "supervisor" in e["request"]["request_id"]
    )
    wire = event["response"]["output"]["payload"]
    # Explicit counterfactual binding fixture: not a claim that Qwen generated IDs.
    requirements = [
        IntegrationRequirement(
            requirement_id="R1",
            text="Tăng trưởng doanh thu",
            kind="metric",
            target_id="revenue_yoy",
        ),
        IntegrationRequirement(
            requirement_id="R2", text="Tỷ trọng nợ", kind="metric", target_id="debt_to_assets"
        ),
        IntegrationRequirement(
            requirement_id="R3",
            text="Dòng tiền kinh doanh",
            kind="fact",
            target_id="b03.operating_cash_flow",
            period="2025",
        ),
    ]
    wire["requirements"] = [r.model_dump(mode="json") for r in requirements]
    for index, task in enumerate(wire["tasks"], 1):
        task.update(task_id=f"T{index}", requirement_ids=[f"R{index}"])
    plan, errors = integration_plan(wire)
    assert len(plan.tasks) == 3 and not errors
    saved = read("execution/C01.json")
    context = PlannerContext.model_validate_json(
        json.dumps(saved["response"]["trace"]["financial_execution"]["context"])
    )
    context.mode = "deterministic"
    engine = FinancialLiteOrchestrator(
        services["BBS_2025"].catalog,
        integration_v2=True,
        supervisor=Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), []))),
    )
    result = engine.run(question=saved["request"]["question"], context=context)
    assert len(result.specialist_executions) == 3 and result.candidates
    assert all(x.assigned_requirement_ids for x in result.specialist_executions)
    assert all(x.result and x.result.supporting_evidence for x in result.specialist_executions)
    evidence_ids = {}
    for execution in result.specialist_executions:
        for evidence in execution.result.supporting_evidence:
            identity = evidence.reference.model_dump_json()
            assert evidence_ids.setdefault(identity, evidence.evidence_id) == evidence.evidence_id
    report["cases"]["C01_counterfactual_binding"] = dict(
        task_count=3,
        candidate_count=len(result.candidates),
        shared_evidence_count=len(evidence_ids),
        requirement_ids=[r.requirement_id for r in requirements],
        note="Saved plan plus explicit IDs; no model-generated completeness claim.",
    )
    (output / "C01-orchestration.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    history_count = 0
    for index in range(1, 13):
        for wire_entry in read(f"execution/C{index:02d}.json")["ledger"]:
            entry = TypeAdapter(LedgerEntry).validate_json(json.dumps(wire_entry))
            validate_entry(entry)
            assert entry.model_dump(mode="json") == wire_entry
            history_count += 1
    report["historical_entries_unchanged"] = history_count
    report["source_json_unchanged"] = all(
        hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
        for name, digest in input_hashes.items()
    )
    assert history_count == 22 and report["source_json_unchanged"]
    (output / "replay.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        "Offline replay PASS: C01 shared context, C04 absence, C10 typed proofs, 22 historical entries; 0 model calls"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("artifacts/evidence/E2E-GEN-01"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/V2-INT-01/offline"))
    args = parser.parse_args()
    replay(Path(__file__).resolve().parents[1], args.source, args.output)
