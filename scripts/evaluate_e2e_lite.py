"""Quick real BBS E2E; isolated committed runtime, private artifacts, no OCR/rebuild.

Run offline first, then optionally --live once (Q3/Q6, eight calls total).
"""

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import zipfile
from decimal import Decimal
from pathlib import Path

BASELINE = "e72f867d05f25d14f1c46cb5ee1ae6480a6b7146"
OUTPUT = Path("artifacts/evidence/E2E-LITE-01")
QUESTIONS = [
    ("Q1", "Doanh thu thuần của BBS năm 2025 là bao nhiêu?"),
    ("Q2", "Doanh thu thuần của BBS năm 2025 tăng hay giảm bao nhiêu phần trăm so với năm 2024?"),
    (
        "Q3",
        "Tỷ lệ nợ phải trả trên tổng tài sản của BBS tại ngày 31/12/2025 là bao nhiêu? Diễn giải ý nghĩa của tỷ lệ đó.",
    ),
    (
        "Q4",
        "So sánh doanh thu thuần và lợi nhuận gộp của BBS giữa năm 2024 và 2025. Kết quả cho thấy điều gì?",
    ),
    (
        "Q5",
        "Phân tích tình hình tổng tài sản và nợ phải trả của BBS năm 2025 dựa trên các số liệu đã có. Có thể kết luận gì và chưa thể kết luận gì?",
    ),
    (
        "Q6",
        "Dựa trên những dữ liệu hiện có, hãy nhận xét tình hình tài chính của BBS năm 2025, kết hợp khả năng sinh lời và cơ cấu nguồn vốn.",
    ),
    ("Q7", "Doanh thu BBS tăng có phải vì doanh nghiệp quản lý chi phí hiệu quả hơn không?"),
    ("Q8.1", "Tỷ lệ nợ trên tổng tài sản của BBS năm 2025 là bao nhiêu?"),
    ("Q8.2", "Vậy tỷ lệ đó có chứng minh doanh nghiệp đang mất khả năng thanh toán không?"),
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runtime(remediation=False):
    """Avoid evaluating unrelated, uncommitted runtime edits."""
    target = OUTPUT / ("runtime-remediation" if remediation else "runtime")
    if not target.exists():
        archive = subprocess.check_output(["git", "archive", "--format=zip", BASELINE, "src"])
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            zipped.extractall(target)
    if remediation:
        (target / "src/outputs/qa_lite.py").write_bytes(Path("src/outputs/qa_lite.py").read_bytes())
    spec = importlib.util.spec_from_file_location(
        "vietnamese_financial_multi_agent",
        target / "src/__init__.py",
        submodule_search_locations=[str((target / "src").resolve())],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


class BoundedGateway:
    def __init__(self, gateway, output):
        self.gateway, self.output, self.events = gateway, output, []

    def generate(self, request):
        from vietnamese_financial_multi_agent.core.llm_gateway import _failure

        known = sum(e.get("tokens") or 0 for e in self.events)
        # Conservative character + output reservation; one shared task budget.
        size = sum(len(m.content) for m in request.messages)
        reserve = size + request.generation.max_output_tokens
        if len(self.events) >= 8 or size > 12000 or known + reserve > 25000:
            return _failure(request, "quota_exceeded")
        event = dict(request_id=request.request_id, input_chars=size, status="reserved")
        self.events.append(event)
        save(self.output / "provider-events.json", self.events)
        started = time.perf_counter()
        response = self.gateway.generate(request)
        event.update(
            status=response.status,
            tokens=response.usage.total_tokens,
            usage=response.usage.model_dump(mode="json"),
            latency_ms=(time.perf_counter() - started) * 1000,
            error=response.error.model_dump(mode="json") if response.error else None,
            request=request.model_dump(mode="json"),
            response=response.model_dump(mode="json"),
        )
        save(self.output / "provider-events.json", self.events)
        return response


def source_oracle(service):
    facts = [f.model_dump(mode="json") for f in service.catalog.facts]

    def value(item, year):
        matches = [
            f
            for f in facts
            if f["canonical_item_id"] == item
            and f["context"]["period"] in {str(year), f"{year}-12-31"}
        ]
        assert len(matches) == 1, (item, year, len(matches))
        return Decimal(matches[0]["value"]["normalized_value"])

    return dict(
        facts=facts,
        revenue_yoy=str(
            (value("b02.net_revenue", 2025) / value("b02.net_revenue", 2024) - 1) * 100
        ),
        debt_to_assets=str(
            value("b01.total_liabilities", 2025) / value("b01.total_assets", 2025) * 100
        ),
        method="Independent Decimal calculation from saved canonical facts; source IDs retained",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--remediation", action="store_true")
    args = parser.parse_args()
    assert not (args.live and args.remediation)
    output = OUTPUT / ("remediation" if args.remediation else "live" if args.live else "offline")
    output.mkdir(parents=True, exist_ok=False)
    load_runtime(args.remediation)
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
            "src",
            "artifacts/evidence/EXT-01",
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
            questions=QUESTIONS,
            protected=before,
            local_status=subprocess.check_output(["git", "status", "--short"], text=True),
            runtime="isolated git archive; unrelated working tree runtime not imported",
        ),
    )
    service, _ = pipeline(Path.cwd(), "BBS_2025", output / "source")
    save(output / "oracle.json", source_oracle(service))
    if args.live:
        assert json.loads((OUTPUT / "offline/integrity.json").read_bytes())["unchanged"]
        adapter, _ = create_qa_adapter(Path.cwd())
        service.gateway = BoundedGateway(SharedLLMGateway({"gemini": adapter}), output)
    doc = service.documents[0]
    descriptor = next(d for d in service.catalog.descriptors if d.document_id == doc.document_id)
    scope = dict(
        document_id=doc.document_id, company_id=doc.company_id, snapshot_id=descriptor.snapshot_id
    )
    rows = []
    conversation = ConversationService(service)
    session = conversation.create()
    cases = [q for q in QUESTIONS if q[0] in {"Q3", "Q6"}] if args.live else QUESTIONS
    if args.remediation:
        cases = [q for q in QUESTIONS if q[0] == "Q6"]
        from vietnamese_financial_multi_agent.agents.orchestration_contracts import (
            OrchestrationResult,
        )

        recorded = next(
            r for r in json.loads((OUTPUT / "live/results.json").read_bytes()) if r["case"] == "Q6"
        )

        class ReplayOrchestrator:
            def run(self, *, question, context):
                assert question == recorded["question"]
                return OrchestrationResult.model_validate_json(
                    json.dumps(recorded["response"]["trace"]["financial_execution"])
                )

        service.orchestrator = ReplayOrchestrator()
        save(
            output / "overlay.json",
            dict(
                file="src/outputs/qa_lite.py",
                sha256=digest(Path("src/outputs/qa_lite.py")),
                execution="replay saved live M5, fresh M6 and Ledger, offline M7",
            ),
        )
    for case, question in cases:
        # A separate empty persisted ledger proves fresh admission for every question.
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
            max_provider_calls=5 if case == "Q6" else 4,
        )
        row = dict(
            case=case, question=question, execution="fresh", request=request.model_dump(mode="json")
        )
        if args.remediation:
            row["execution"] = "replay_M5_fresh_M6_offline_M7"
        try:
            if case.startswith("Q8"):
                turn = conversation.send(session.conversation_id, request)
                response = turn.response
                row["conversation"] = turn.model_dump(mode="json")
            else:
                response = service.run(request)
            row["response"] = response.model_dump(mode="json")
            reloaded = VerifiedClaimRepository(service.repository.root).list_all()
            row["reloaded_claims"] = [e.model_dump(mode="json") for e in reloaded]
            assert set(response.used_verified_claim_ids) <= {
                e.identity.verified_claim_id for e in reloaded
            }
            if case == "Q1":
                service.repository = VerifiedClaimRepository(service.repository.root)
                row["cached_response"] = service.run(
                    request.model_copy(update={"force_refresh": False})
                ).model_dump(mode="json")
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
