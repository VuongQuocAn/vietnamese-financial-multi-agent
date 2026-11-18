"""M7-only replay from saved M6/Ledger; two or three questions, at most 3 calls."""

import argparse
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from fastapi.encoders import jsonable_encoder
from vietnamese_financial_multi_agent.agents.integration_workspace import answer_coverage
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse, ModelIdentity
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.outputs.citation_renderer import _identity
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--saved-provider-events", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    assert 2 <= len(cases) <= 3
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = {args.cases}
    if args.saved_provider_events:
        inputs.add(args.saved_provider_events)
    for case in cases:
        inputs.update([Path(case["trace"]), Path(case["ledger"]) / "verified-claims.json"])
        if case.get("saved_m5"):
            inputs.add(Path(case["saved_m5"]))
        inputs.update(Path(case["source_json_root"]).rglob("*.json"))
    before = {str(p): sha(p) for p in inputs}
    runtime = {str(p.relative_to(root)): sha(p) for p in (root / "src").rglob("*.py")}
    events = []
    saved_events = (
        json.loads(args.saved_provider_events.read_text(encoding="utf-8"))
        if args.saved_provider_events
        else None
    )
    configured = (
        SimpleNamespace(
            model=ModelIdentity.model_validate(saved_events[0]["request"]["model"]),
            close=lambda: None,
        )
        if saved_events
        else create_text_gateway(root, provider="qwen")
    )

    def transport(request):
        assert len(events) < 3 and request.request_id.startswith("m7-lite-")
        # Record the attempt before transport, so an interrupted call still counts.
        event = dict(request=request.model_dump(mode="json"), response=None)
        events.append(event)
        atomic_json(args.output / "provider-events.json", events)
        if saved_events:
            saved_event = saved_events[len(events) - 1]
            wire = request.model_dump(mode="json")
            for key in ("model", "messages", "generation", "output_spec", "constraints"):
                assert wire[key] == saved_event["request"][key], "saved_m7_input_changed:" + key
            response = LLMResponse.model_validate(saved_event["response"]).model_copy(
                update=dict(request_id=request.request_id, correlation=request.correlation)
            )
        else:
            response = configured.adapter(request)
        event["response"] = response.model_dump(mode="json")
        atomic_json(args.output / "provider-events.json", events)
        print(json.dumps(dict(call=len(events), status=response.status)), flush=True)
        return response

    gateway = SharedLLMGateway({"qwen": transport})
    summaries = []
    try:
        for case in cases:
            saved = json.loads(Path(case["trace"]).read_text(encoding="utf-8"))
            if case.get("saved_m5"):
                m5 = json.loads(Path(case["saved_m5"]).read_text(encoding="utf-8"))
                question = m5["question"]
                # Match the saved M6 release context, rather than reviving M5's
                # earlier task failures or unverified candidate proposals.
                context = dict(
                    requirements=deepcopy(m5["integration_context"]["requirements"]),
                    verified_requirements=deepcopy(saved["verified_requirements"]),
                )
                old_coverage = saved["m7"]["coverage"]
            else:
                question = saved["request"]["question"]
                context = deepcopy(saved["response"]["trace"]["integration_context"])
                old_coverage = saved["response"]["trace"]["m7_lite"]["coverage"]
            entries = VerifiedClaimRepository(case["ledger"]).list_all()
            entry_bytes = [e.model_dump_json() for e in entries]
            context_before = deepcopy(context)
            request = FinancialQARequest(
                question=question,
                model=configured.model,
                execution_mode="gemini",
                allow_gateway=True,
                max_provider_calls=1,
            )
            fields, trace = compose_lite(
                request, entries, gateway=gateway, coverage_context=context
            )
            released = {e.identity.verified_claim_id: e for e in entries}
            assert context == context_before
            assert entry_bytes == [e.model_dump_json() for e in entries]
            assert trace["coverage"] == old_coverage, "saved_m6_coverage_changed"
            assert trace["coverage"] == answer_coverage(
                context, [released[k] for k in fields["used_verified_claim_ids"]]
            )
            for binding in trace["citation_bindings"]:
                entry = released[binding["verified_claim_id"]]
                assert set(binding["source_ids"]) == {_identity(c) for c in entry.citations}
            for ref in fields["citations"]:
                expected = [
                    c
                    for key in ref.bound_verified_claim_ids
                    for c in released[key].citations
                    if c.document_id == ref.document_id
                    and c.snapshot_id == ref.snapshot_id
                    and c.pdf_page == ref.pdf_page
                    and (c.pdf_page is not None or "citation:" + _identity(c) == ref.citation_id)
                ]
                assert {_identity(c) for c in ref.source_citations} == {
                    _identity(c) for c in expected
                }
                assert all(c in expected for c in ref.source_citations)
                assert ref.display_label in fields["answer_vi"]
            atomic_json(
                args.output / (case["id"] + ".json"),
                jsonable_encoder(dict(request=request, fields=fields, m7=trace)),
            )
            summary = dict(
                case=case["id"],
                status=fields["status"],
                complete=trace["coverage"]["complete"],
                natural=trace["rendering_mode"] == "grounded_natural_answer",
                fallback=trace["fallback"],
                rejected_segments=trace["rejected_segments"],
                claims=len(fields["used_verified_claim_ids"]),
                citations=len(fields["citations"]),
                exact_bindings=len(trace["citation_bindings"]),
                tokens=trace["known_total_tokens"],
            )
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
    finally:
        configured.close()
        assert all(sha(Path(p)) == digest for p, digest in before.items())
        assert all(sha(root / p) == digest for p, digest in runtime.items())
        atomic_json(
            args.output / "receipt.json",
            dict(
                implementation_sha=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                calls=0 if saved_events else len(events),
                replayed_calls=len(events) if saved_events else 0,
                known_total_tokens=sum(s["tokens"] for s in summaries),
                inputs_sha256=before,
                runtime_sha256=runtime,
                summaries=summaries,
                scope="Saved M5/M6/Ledger -> live M7 only; no M6 replay or source extraction",
            ),
        )


if __name__ == "__main__":
    main()
