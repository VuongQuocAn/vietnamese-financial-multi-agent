"""CORE-FLOW-01: same E2E questions, fresh isolated runtime and real Gemini.

Private traces stay under ignored artifacts. No OCR, extraction or source writes.
"""

import argparse
import importlib.util
import io
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from evaluate_e2e_lite import QUESTIONS, digest, save, source_oracle

BASELINE = "a92bc8f"
OVERLAYS = [
    "src/agents/lite_orchestrator.py",
    "src/api/claim_selection.py",
    "src/api/conversations.py",
    "src/api/financial_qa_pipeline.py",
    "src/outputs/qa_lite.py",
    "src/verification/lite_runtime.py",
    "src/verification/validators.py",
    "src/core/request_gateway.py",
]


def load_runtime(output):
    target = output / "runtime"
    archive = subprocess.check_output(["git", "archive", "--format=zip", BASELINE, "src"])
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        zipped.extractall(target)
    for name in OVERLAYS:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(name).read_bytes())
    # This shared file has pre-existing, unrelated local prompt edits. Apply only
    # CORE-FLOW's fact-operand projection to the baseline in the isolated runtime.
    shared = target / "src/agents/specialist_common.py"
    content = shared.read_text(encoding="utf-8")
    content = content.replace(
        '                if any(s.kind != "fact" for s in sources):\n                    raise ValueError("dynamic_requires_fact_operands")\n',
        "",
    ).replace(
        "                    for s in sources\n                }\n                valid_operations",
        '                    for s in sources\n                    if s.kind == "fact"\n                }\n                valid_operations',
    )
    content = content.replace(
        "[analysis.statement, *analysis.assumptions, *analysis.limitations]",
        '[analysis.statement, *("Giả định: " + a for a in analysis.assumptions), *("Giới hạn: " + note for note in analysis.limitations)]',
    )
    content = content.replace(
        "*, gateway, model, result, prompt, proposal_type, render, prefix, deterministic=False",
        "*, gateway, model, result, prompt, proposal_type, render, prefix, deterministic=False, emit_derived=True",
    ).replace(
        "if computation and reasoning.claim_type not in {",
        "if emit_derived and computation and reasoning.claim_type not in {",
    )
    shared.write_text(content, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "vietnamese_financial_multi_agent",
        target / "src/__init__.py",
        submodule_search_locations=[str((target / "src").resolve())],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


class TracedGateway:
    """Observe real requests without a task-wide four/eight-call ceiling."""

    def __init__(self, gateway, output):
        self.gateway, self.output, self.events = gateway, output, []

    def generate(self, request):
        started = time.perf_counter()
        response = self.gateway.generate(request)
        self.events.append(
            dict(
                request=request.model_dump(mode="json"),
                response=response.model_dump(mode="json"),
                latency_ms=(time.perf_counter() - started) * 1000,
                tokens=response.usage.total_tokens,
                status=response.status,
                error=response.error.model_dump(mode="json") if response.error else None,
            )
        )
        save(self.output / "provider-events.json", self.events)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    load_runtime(output)
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.api.conversations import ConversationService
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    protected = [
        p
        for folder in (
            "artifacts/evidence/EXT-01",
            "artifacts/evidence/E2E-LITE-01",
            "artifacts/evidence/M5-LITE-01",
            "artifacts/evidence/M6-LITE-01",
        )
        for p in Path(folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    before = {p.as_posix(): digest(p) for p in protected}
    save(
        output / "freeze.json",
        dict(
            baseline=BASELINE,
            overlays={p: digest(Path(p)) for p in OVERLAYS},
            runtime_sources={
                p.relative_to(output / "runtime").as_posix(): digest(p)
                for p in (output / "runtime/src").rglob("*.py")
            },
            protected=before,
            questions=QUESTIONS,
        ),
    )
    service, _ = pipeline(Path.cwd(), "BBS_2025", output / "source")
    save(output / "oracle.json", source_oracle(service))
    if args.live:
        adapter, _ = create_qa_adapter(Path.cwd())
        service.gateway = TracedGateway(SharedLLMGateway({"gemini": adapter}), output)
    doc = service.documents[0]
    descriptor = next(d for d in service.catalog.descriptors if d.document_id == doc.document_id)
    scope = dict(
        document_id=doc.document_id, company_id=doc.company_id, snapshot_id=descriptor.snapshot_id
    )
    conversation = ConversationService(service)
    session = conversation.create()
    rows = []
    for case, question in QUESTIONS:
        if args.cases and case not in args.cases:
            continue
        if case != "Q8.2":
            service.repository = VerifiedClaimRepository(output / case / "ledger")
        request = FinancialQARequest(
            question=question,
            **scope,
            m5_lite=True,
            m6_lite=True,
            m7_lite=True,
            force_refresh=True,
            execution_mode="gemini" if args.live else "deterministic",
            allow_gateway=args.live,
            max_provider_calls=32,
            request_timeout_seconds=300,
        )
        row = dict(
            case=case,
            question=question,
            execution="fresh_live" if args.live else "fresh_deterministic",
        )
        try:
            if case.startswith("Q8"):
                turn = conversation.send(session.conversation_id, request)
                row["conversation"] = turn.model_dump(mode="json")
                response = turn.response
            else:
                response = service.run(request)
            row["response"] = response.model_dump(mode="json")
            reloaded = VerifiedClaimRepository(service.repository.root).list_all()
            row["reloaded_claims"] = [e.model_dump(mode="json") for e in reloaded]
            assert set(response.used_verified_claim_ids) <= {
                e.identity.verified_claim_id for e in reloaded
            }
            print(case, response.status, response.newly_accepted_claims, "accepted", flush=True)
        except Exception as error:
            row["technical_failure"] = type(error).__name__
            print(case, type(error).__name__, flush=True)
        rows.append(row)
        save(output / "results.json", rows)
    after = {p: digest(Path(p)) for p in before}
    save(output / "integrity.json", dict(files=len(before), unchanged=before == after))
    assert before == after


if __name__ == "__main__":
    main()
