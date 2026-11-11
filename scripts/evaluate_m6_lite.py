"""M6 Lite on existing BBS/M5 artifacts. One opt-in semantic live batch, no retry."""

import argparse
import json
import tempfile
from pathlib import Path

from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.api.claim_selection import select_claims
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.contracts import VerificationInput
from vietnamese_financial_multi_agent.verification.ledger import build_verified_claim
from vietnamese_financial_multi_agent.verification.ledger_contracts import VerifiedClaimQuery
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_contracts import LiteVerificationHistory
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

OUTPUT = Path("artifacts/evidence/M6-LITE-01")


def save(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def real_inputs():
    rows = json.loads(Path("artifacts/evidence/M5-LITE-01/replay.json").read_text(encoding="utf-8"))
    return [VerificationInput.model_validate_json(json.dumps(r["m6_adapter"])) for r in rows]


class BoundedGateway:
    def __init__(self, gateway):
        self.gateway, self.events = gateway, []

    def generate(self, request):
        if self.events:
            raise ValueError("single_live_call_budget_exhausted")
        self.events.append(dict(request=request.model_dump(mode="json")))
        save("provider-events.json", self.events)
        response = self.gateway.generate(request)
        self.events[-1]["response"] = response.model_dump(mode="json")
        save("provider-events.json", self.events)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--replay-release", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.replay_release:
        saved = json.loads((OUTPUT / "live.json").read_text(encoding="utf-8"))
        entries = [
            build_verified_claim(LiteVerificationHistory.model_validate_json(json.dumps(h)))
            for h in saved["histories"]
            if h["outcome"]["attempts"][0]["decision"] == "ACCEPT"
        ]
        owner = entries[0].identity
        request = FinancialQARequest(
            question="Phân tích tổng tài sản và tổng nợ phải trả năm 2025 của BBS.",
            company_id=owner.company_id,
            document_id=owner.document_id,
            snapshot_id=owner.snapshot_id,
            m5_lite=True,
            m6_lite=True,
            m7_lite=True,
        )
        selected, excluded = select_claims(request, entries)
        fields, metadata = compose_lite(request, selected)
        semantic_ids = {
            e.identity.verified_claim_id
            for e in entries
            if e.accepted_claim.kind == "supported_interpretation"
        }
        used = set(fields["used_verified_claim_ids"]) & semantic_ids
        assert used and fields["citations"] and metadata["calls"] == 0
        save(
            "semantic-m7-smoke.json",
            dict(
                response={
                    k: [v.model_dump(mode="json") for v in value] if k == "citations" else value
                    for k, value in fields.items()
                },
                metadata=metadata,
                excluded=excluded,
                semantic_used=sorted(used),
            ),
        )
        print("M7 offline uses semantic ACCEPTs:", len(used), "calls:", metadata["calls"])
        return
    service, _ = pipeline(
        Path.cwd(),
        "BBS_2025",
        Path(tempfile.mkdtemp(dir=OUTPUT, prefix="live-" if args.live else "offline-")),
    )
    batches = real_inputs()
    gateway = None
    if args.live:
        with (OUTPUT / "live-reserved.json").open("x", encoding="utf-8") as stream:
            json.dump(dict(max_calls=1, task_budget=4, retry=False), stream)
        adapter, _ = create_qa_adapter(Path.cwd())
        gateway = BoundedGateway(SharedLLMGateway({"gemini": adapter}))
    # Keep original saved M5 candidates. Designed controls are explicitly labelled.
    batch = batches[0].model_copy(deep=True)
    batch.claims.extend(batches[1].claims[4:])
    control = batch.claims[0].model_copy(deep=True)
    control.candidate_id = "m6-adversarial-causal-control"
    control.provenance.m5_candidate_id = control.candidate_id
    control.content = "Doanh thu tăng vì doanh nghiệp quản lý chi phí xuất sắc."
    batch.claims.append(control)
    runtime = LiteVerificationRuntime(service.catalog, gateway)
    histories = runtime.verify(batch)
    receipts = service.repository.admit_many(histories)
    reloaded = VerifiedClaimRepository(service.repository.root).list_all()
    result = dict(
        mode="live" if args.live else "offline",
        provenance="M5-LITE-01 final offline replay of saved live responses; causal control designed",
        summary=runtime.summary,
        histories=[h.model_dump(mode="json") for h in histories],
        admission=[r.model_dump(mode="json") for r in receipts],
        reloaded_ids=[e.identity.verified_claim_id for e in reloaded],
    )
    save("live.json" if args.live else "offline.json", result)
    for h, r in zip(histories, receipts, strict=True):
        print(
            h.outcome.final.candidate_id,
            h.outcome.final.decision,
            h.outcome.final.reason_codes,
            r.status,
            flush=True,
        )
    assert all(e.decision.decision == "ACCEPT" for e in reloaded)
    assert histories[-1].outcome.final.decision != "ACCEPT", "unsupported causal control accepted"
    assert len(reloaded) == sum(r.status in {"stored", "idempotent"} for r in receipts)
    if not args.live:
        service, _ = pipeline(
            Path.cwd(), "BBS_2025", Path(tempfile.mkdtemp(dir=OUTPUT, prefix="pipeline-"))
        )
        doc = service.documents[0]
        descriptor = next(
            d for d in service.catalog.descriptors if d.document_id == doc.document_id
        )
        response = service.run(
            FinancialQARequest(
                question="Doanh thu thuần năm 2025 và tăng trưởng doanh thu 2025 so với 2024 của BBS là bao nhiêu?",
                document_id=doc.document_id,
                company_id=doc.company_id,
                snapshot_id=descriptor.snapshot_id,
                m5_lite=True,
                m6_lite=True,
                m7_lite=True,
                execution_mode="deterministic",
                force_refresh=True,
            )
        )
        save("pipeline-smoke.json", response.model_dump(mode="json"))
        print(
            "pipeline",
            response.status,
            response.newly_accepted_claims,
            response.trace.verification_mode,
            flush=True,
        )
        assert response.trace.verification_mode == "lite"
        assert response.used_verified_claim_ids and response.citations
        assert response.trace.provider_calls == 0
        assert service.repository.query(VerifiedClaimQuery(document_id=doc.document_id))


if __name__ == "__main__":
    main()
