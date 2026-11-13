"""Replay unmodified saved provider responses through V2; no provider/network adapter."""

import argparse
import hashlib
import json
from pathlib import Path

from evaluate_composition_graph import bbs_catalog
from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class SavedGateway:
    """Return original typed responses, including raw JSON and missing verdicts."""

    def __init__(self, events, case):
        self.responses = {}
        self.calls = []
        self.unsaved_calls = []
        for event in events:
            if event["case"] == case and event["status"] == "success":
                prefix = event["request"]["request_id"].rsplit("-", 1)[0]
                self.responses.setdefault(prefix, []).append(event["response"])

    def generate(self, request):
        prefix = request.request_id.rsplit("-", 1)[0]
        index = self.calls.count(prefix)
        if prefix not in self.responses or index >= len(self.responses[prefix]):
            self.unsaved_calls.append(prefix)
            raise AssertionError("unsaved_provider_call:" + prefix)
        self.calls.append(prefix)
        return LLMResponse.model_validate(self.responses[prefix][index])


def replay(root, source, output):
    if output.exists():
        raise ValueError("fresh_output_required")
    output.mkdir(parents=True)
    events = read(source / "provider-events.json")
    inputs = [source / "provider-events.json", *(source / "execution").glob("*.json")]
    digests = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    catalog = bbs_catalog(root)
    report = dict(mode="raw_saved_provider_replay", new_model_calls=0, cases={})
    for case in ("C01", "C07"):
        saved = read(source / f"execution/{case}.json")
        service, _ = pipeline(root, "BBS_2025", output / "inputs" / case, catalog)
        gateway = SavedGateway(events, case)
        service.gateway = gateway
        request = FinancialQARequest.model_validate(saved["request"])
        response = service.run(request)
        assert not gateway.unsaved_calls
        assert len(gateway.calls) == sum(len(rows) for rows in gateway.responses.values())
        (output / f"{case}.json").write_text(response.model_dump_json(indent=2), encoding="utf-8")
        context = response.trace.integration_context
        if case == "C07":
            financial = response.trace.fusion_bundle["lane_results"][0]["response"]
            context = financial["trace"]["integration_context"]
            execution = financial["trace"]["financial_execution"]
        else:
            execution = response.trace.financial_execution
        previous = saved["response"]
        before_context = previous["trace"]["integration_context"]
        if case == "C07":
            before_context = previous["trace"]["fusion_bundle"]["lane_results"][0]["response"][
                "trace"
            ]["integration_context"]
        report["cases"][case] = dict(
            saved_responses_consumed=gateway.calls,
            before_decisions=previous["trace"].get("native_decisions"),
            after_decisions=response.trace.native_decisions,
            requirements=context.get("requirements"),
            before_requirements=before_context.get("requirements"),
            before_candidate_requirements=before_context.get("candidate_requirements"),
            before_verified_requirements=before_context.get("verified_requirements"),
            candidate_requirements=context.get("candidate_requirements"),
            supported_requirements=context.get("supported_requirements"),
            verified_requirements=context.get("verified_requirements"),
            before_coverage=previous["trace"]["m7_lite"].get("coverage"),
            after_coverage=response.trace.m7_lite.get("coverage"),
            before_answer=previous["answer_vi"],
            after_answer=response.answer_vi,
            retrieved_references=execution["integration_context"].get("evidence_references"),
            after_findings=[
                {key: f[key] for key in ("candidate_id", "decision", "reasons")}
                for f in response.trace.m6_lite.get("findings", [])
            ],
        )
        if case == "C01":
            rows = {
                r["requirement_id"]: r for r in response.trace.m7_lite["coverage"]["requirements"]
            }
            assert all(rows[r]["status"] == "satisfied" for r in ("R001", "R002", "R003"))
            assert response.answer_vi.count("26,71") == 1
            decisions = {f["candidate_id"]: f for f in response.trace.m6_lite["findings"]}
            for cid in (
                "eb85321eafb8cfc367d7fb9a",
                "37663657fb14968dbe7421b2",
                "f3d5f7da6c87b5bccc13935f",
            ):
                assert decisions["candidate:" + cid]["decision"] == "ACCEPT"
            assert decisions["candidate:2285c67b1361fd374c95e34f"]["decision"] != "ACCEPT"
        else:
            facts = execution["supervisor_result"]["evidence_bundle"]["facts"]
            assert {f["record"]["context"]["period"] for f in facts} == {"2025", "2024"}
            assert all(f["record"]["canonical_item_id"] == "b02.profit_after_tax" for f in facts)
            assert {7, 12} <= {c.pdf_page for c in response.citations}
            assert set(previous["used_verified_claim_ids"]) <= set(response.used_verified_claim_ids)
            report["cases"][case]["limitation"] = (
                "Original specialists still return empty claims and invalid absence analyses. "
                "The existing V2 typed numeric fallback now uses resolved sources and passes M6; "
                "this is backend source replay, not newly generated Qwen content. "
                "The model's extra 2024 requirement remains."
            )
    for case, label in (("C04", "BBS_2025"), ("C10", "BCC_2025")):
        path = root / f"artifacts/evidence/E2E-GEN-01/execution/{case}.json"
        digests[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        saved = read(path)
        service, _ = pipeline(root, label, output / "inputs" / case, catalog)
        batch = to_verification_input(
            OrchestrationResult.model_validate_json(
                json.dumps(saved["response"]["trace"]["financial_execution"])
            )
        )
        runtime = LiteVerificationRuntime(service.catalog, integration_v2=True)
        histories = runtime.verify(batch)
        decisions = {h.outcome.final.candidate_id: h.outcome.final.decision for h in histories}
        if case == "C04":
            assert all(
                decisions["candidate:" + cid] != "ACCEPT"
                for cid in (
                    "132b0639d72899aa754133e4",
                    "ecb5eb3d9cacdc6d38725547",
                    "e1a18014d7a0431fa6466df3",
                )
            )
        else:
            assert all(
                decisions["candidate:" + cid] == "ACCEPT"
                for cid in (
                    "9b36f2a651a2399a6351b6e0",
                    "56dbd146a346b8bf7ec20259",
                    "493da2d1bacb2ceaa9341529",
                )
            )
            assert decisions["candidate:022da587dd08a70ce6f2610a"] != "ACCEPT"
        report["cases"][case] = dict(mode="saved_execution_replay", decisions=decisions)
    report["inputs_unchanged"] = all(
        hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in digests.items()
    )
    assert report["inputs_unchanged"]
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PASS: raw C01/C07, saved C04/C10; zero new model calls; source inputs unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path("artifacts/evidence/V2-INT-01/qa-completion/live")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    replay(Path(__file__).resolve().parents[1], args.source, args.output)
