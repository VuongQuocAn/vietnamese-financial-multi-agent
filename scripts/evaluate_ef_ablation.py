"""EF-CORE-02: resumable controlled development evaluation, private source artifacts.

Prepare first, review the frozen source oracle, then opt into --live. Runtime is
the accepted commit, never unrelated local edits. Completed runs are not repeated.
"""

import argparse
import importlib.util
import io
import json
import subprocess
import sys
import time
import zipfile
from decimal import Decimal
from pathlib import Path

from evaluate_e2e_lite import digest, save

BASELINE = "f5bbac6b6d5befd0b3021654b48218feeab54942"
DEFAULT_OUTPUT = Path("artifacts/evidence/EF-CORE-02")
# Each requirement is an independently assessable, source-answerable content unit.
QUESTIONS = [
    (
        "A1",
        "Doanh thu thuần của BBS năm 2025 là bao nhiêu, đơn vị gì và ở trang PDF nào?",
        ["revenue25", "unit", "page7"],
    ),
    (
        "A2",
        "Tổng tài sản BBS cuối năm 2025 là bao nhiêu và nằm ở trang PDF nào?",
        ["assets25", "page5"],
    ),
    (
        "B1",
        "Tăng trưởng doanh thu thuần BBS 2025 so với 2024 được tính như thế nào? Nêu cả hai toán hạng, kỳ gốc/kỳ mục tiêu, công thức, kết quả và nguồn từng toán hạng.",
        ["revenue25", "revenue24", "growth", "growth_formula", "page7"],
    ),
    (
        "B2",
        "Biên lợi nhuận gộp BBS năm 2025 được tính từ những số liệu nào? Nêu tử số, mẫu số, công thức, kết quả và trang nguồn.",
        ["gross25", "revenue25", "margin25", "margin_formula", "page7"],
    ),
    (
        "B3",
        "Tính tỷ lệ nợ phải trả trên tổng tài sản BBS cuối 2025; giải thích toán hạng, kỳ, công thức, kết quả và nguồn.",
        ["debt25", "assets25", "debt_ratio", "debt_formula", "page5", "page6"],
    ),
    (
        "C1",
        "So sánh doanh thu thuần và lợi nhuận gộp BBS năm 2024 với 2025: nêu giá trị từng kỳ, biến động tuyệt đối và phần trăm của từng chỉ tiêu, kèm nguồn. Có thể kết luận gì từ hai chiều biến động?",
        [
            "revenue25",
            "revenue24",
            "gross25",
            "gross24",
            "revenue_delta",
            "growth",
            "gross_delta",
            "gross_growth",
            "divergence",
            "page7",
        ],
    ),
    (
        "C2",
        "So sánh biên lợi nhuận gộp BBS năm 2024 và 2025, nêu doanh thu và lợi nhuận gộp hỗ trợ, chênh lệch điểm phần trăm và giới hạn khi đánh giá hiệu quả quản lý chi phí.",
        [
            "revenue25",
            "revenue24",
            "gross25",
            "gross24",
            "margin25",
            "margin24",
            "margin_delta",
            "no_cause",
        ],
    ),
    (
        "C3",
        "Tổng tài sản và nợ phải trả BBS cuối 2025 so với đầu năm thay đổi bao nhiêu tuyệt đối và phần trăm? Kết hợp nhận xét cơ cấu nợ và giới hạn suy luận về khả năng thanh toán.",
        [
            "assets25",
            "assets24",
            "debt25",
            "debt24",
            "assets_delta",
            "assets_growth",
            "debt_delta",
            "debt_growth",
            "no_insolvency",
        ],
    ),
    (
        "D1",
        "Tổng nợ phải trả BBS cuối 2025 có bằng chứng nguồn và ngữ cảnh bảng/văn bản nào? Nếu dùng EF-EG, phân biệt from_source, associated_with, used_in và same_extraction_context; nói rõ liên kết nào thực sự có, liên kết nào không chứng minh hỗ trợ ngữ nghĩa hoặc nhân quả.",
        [
            "debt25",
            "page6",
            "from_source",
            "associated_with",
            "used_in",
            "same_extraction_context",
            "no_cause",
        ],
    ),
    (
        "D2",
        "Số liệu doanh thu thuần BBS 2025 được truy vết về bảng báo cáo kết quả kinh doanh và trang PDF nào? Phân biệt số liệu tài chính đã chuẩn hóa với ngữ cảnh trích xuất; chỉ nêu ô hoặc anchor khi có bằng chứng, không đoán tọa độ.",
        ["revenue25", "page7", "source_limit"],
    ),
    (
        "D3",
        "Dữ liệu BBS 2025 hiện có có đủ để giải thích nguyên nhân lợi nhuận gộp biến động do giá nguyên liệu không? Nêu số liệu lợi nhuận gộp hai kỳ, nguồn và phần bằng chứng còn thiếu; liên kết chung ngữ cảnh có chứng minh nguyên nhân đó không?",
        ["gross25", "gross24", "page7", "no_material_cause"],
    ),
    (
        "E1",
        "Doanh thu BBS tăng từ 2024 sang 2025 có chứng minh doanh nghiệp quản lý chi phí tốt hơn không? Đối chiếu lợi nhuận gộp và nêu giới hạn của kết luận nhân quả.",
        ["growth", "gross_growth", "no_cause"],
    ),
    (
        "E2",
        "Có thể dùng số lượng khách hàng mới để giải thích doanh thu BBS 2025 tăng không? Nếu dữ liệu hiện có thiếu chỉ tiêu đó hoặc liên kết nhân quả, hãy nói rõ; không suy ra từ các liên kết cùng trang.",
        ["missing_customers", "no_cause"],
    ),
    (
        "F1",
        "Theo cột so sánh trên báo cáo BBS 2025, doanh thu và lợi nhuận gộp năm 2024 là bao nhiêu? Phân biệt năm của tài liệu với kỳ của số liệu và dẫn nguồn.",
        ["revenue24", "gross24", "comparative_period", "page7"],
    ),
    (
        "F2",
        "Vậy tỷ lệ đó có chứng minh BBS mất khả năng thanh toán không? Giải thích giới hạn và nhắc rõ tỷ lệ đang nói tới.",
        ["debt_ratio", "no_insolvency"],
    ),
]


def read(path):
    return json.loads(path.read_bytes())


def load_runtime(output):
    target = output / "runtime"
    if not target.exists():
        archive = subprocess.check_output(["git", "archive", "--format=zip", BASELINE, "src"])
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            zipped.extractall(target)
    spec = importlib.util.spec_from_file_location(
        "vietnamese_financial_multi_agent",
        target / "src/__init__.py",
        submodule_search_locations=[str((target / "src").resolve())],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def source_oracle(service):
    facts = [f.model_dump(mode="json") for f in service.catalog.facts]
    selected = {}
    for key, item in [
        ("revenue", "b02.net_revenue"),
        ("gross", "b02.gross_profit"),
        ("assets", "b01.total_assets"),
        ("debt", "b01.total_liabilities"),
    ]:
        for year in [2024, 2025]:
            period = (
                str(year)
                if key in {"revenue", "gross"}
                else ("2025-12-31" if year == 2025 else "2025-01-01")
            )
            matches = [
                f
                for f in facts
                if f["canonical_item_id"] == item and f["context"]["period"] == period
            ]
            assert len(matches) == 1, (key, year, len(matches))
            selected[key + str(year)[2:]] = matches[0]
    values = {k: Decimal(f["value"]["normalized_value"]) for k, f in selected.items()}
    for key in ["revenue", "gross", "assets", "debt"]:
        values[key + "_delta"] = values[key + "25"] - values[key + "24"]
        values[key + "_growth"] = values[key + "_delta"] / values[key + "24"] * 100
    values["growth"] = values["revenue_growth"]
    for year in ["24", "25"]:
        values["margin" + year] = values["gross" + year] / values["revenue" + year] * 100
    values["margin_delta"] = values["margin25"] - values["margin24"]
    values["debt_ratio"] = values["debt25"] / values["assets25"] * 100
    return dict(
        facts=selected,
        values={k: str(v) for k, v in values.items()},
        provenance="Canonical source records + independent Decimal; PDF review recorded separately",
        relation_semantics={
            "from_source": "provenance, not full semantic entailment",
            "associated_with": "exact extraction association, not causality",
            "used_in": "operand role, not causality",
            "same_extraction_context": "context only, not semantic support",
        },
        forbidden=[
            "causality from context/association",
            "raw-material price explanation without direct evidence",
            "insolvency from leverage alone",
            "invented customer counts/coordinates",
        ],
        semantic_requirements="Assessed independently by Codex; M6 ACCEPT is not ground truth",
    )


def summarize_usage(events):
    usages = [e["response"]["usage"] for e in events]
    return {
        **{
            key: sum(u[key] for u in usages if u.get(key) is not None)
            for key in ["input_tokens", "output_tokens", "total_tokens"]
        },
        "unknown_usage_calls": sum(u.get("total_tokens") is None for u in usages),
        "logical_calls": len(events),
        "failed_calls": sum(e["status"] != "success" for e in events),
    }


def prepare(output, service, manifest):
    frozen = output / "freeze.json"
    if frozen.exists():
        state = read(frozen)
        assert state["baseline"] == BASELINE and state["questions"] == [list(q) for q in QUESTIONS]
        for p, expected in state["protected"].items():
            assert digest(Path(p)) == expected, p
        assert digest(output / "oracle.json") == state["oracle_sha256"]
        return
    paths = [
        p
        for folder in [
            "src",
            "data/raw",
            "data/processed",
            "artifacts/evidence/EXT-01",
            "artifacts/evidence/D-04-review",
            "artifacts/evidence/M4-05",
        ]
        for p in Path(folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    status = subprocess.check_output(["git", "status", "--porcelain", "-uall"], text=True)
    local_paths = [Path(line[3:]) for line in status.splitlines() if Path(line[3:]).is_file()]
    save(output / "preexisting.json", {p.as_posix(): digest(p) for p in local_paths})
    save(output / "oracle.json", source_oracle(service))
    save(output / "composition.json", manifest.model_dump(mode="json"))
    save(
        frozen,
        dict(
            baseline=BASELINE,
            questions=QUESTIONS,
            protected={p.as_posix(): digest(p) for p in paths},
            oracle_sha256=digest(output / "oracle.json"),
            runtime_hashes={
                p.relative_to(output / "runtime").as_posix(): digest(p)
                for p in (output / "runtime/src").rglob("*.py")
            },
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--retry-technical",
        action="store_true",
        help="One retained replacement attempt per technically affected slot; never repeat a clean run",
    )
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--repetitions", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    load_runtime(output)
    from evaluate_core_flow import TracedGateway
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
        FinancialLiteOrchestrator,
        LitePlan,
    )
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerLLMMetadata
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.tools.graph_retrieval import GraphRetrievalTools
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    service, manifest = pipeline(Path.cwd(), "BBS_2025", output / "source")
    prepare(output, service, manifest)
    if not args.live:
        print("PREPARED", len(QUESTIONS), "questions; oracle frozen; no provider calls", flush=True)
        return
    assert (output / "source-review.json").exists(), "Review real PDF and graph oracle before live"
    adapter, _ = create_qa_adapter(Path.cwd())
    gateway = TracedGateway(SharedLLMGateway({"gemini": adapter}), output)
    # Preserve event history across process resumes.
    if (output / "provider-events.json").exists():
        gateway.events = read(output / "provider-events.json")
    service.gateway = gateway
    descriptor = service.catalog.descriptors[0]
    scope = dict(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        company_id=service.documents[0].company_id,
    )
    original_m5 = service._m5
    active = {}
    original_setup, original_get = (
        FinancialLiteOrchestrator._graph_tools,
        GraphRetrievalTools.get_graph_context,
    )

    def setup(engine, context):
        start = time.perf_counter()
        try:
            return original_setup(engine, context)
        finally:
            active["graph_setup_ms"] += (time.perf_counter() - start) * 1000

    def traversal(tools, request):
        start = time.perf_counter()
        try:
            return original_get(tools, request)
        finally:
            active["graph_traversal_ms"] += (time.perf_counter() - start) * 1000

    FinancialLiteOrchestrator._graph_tools = setup
    GraphRetrievalTools.get_graph_context = traversal
    try:
        for case, question, requirements in QUESTIONS:
            if args.cases and case not in args.cases:
                continue
            plan_path = output / "plans" / (case + ".json")
            for repetition in range(1, args.repetitions + 1):
                # Alternate order to reduce period/provider-load confounding.
                for enabled in [False, True] if repetition == 1 else [True, False]:
                    run_id = f"{case}-r{repetition}-{'on' if enabled else 'off'}"
                    destination = output / "runs" / (run_id + ".json")
                    if destination.exists():
                        previous = read(destination)
                        technical = bool(
                            previous["usage"]["failed_calls"]
                            or previous.get("technical_failure")
                            or any(m.get("errors") for m in previous.get("m5", []))
                            or previous.get("response", {}).get("status")
                            in {"internal_error", "provider_unavailable"}
                        )
                        if not args.retry_technical or not technical:
                            continue
                        run_id += "-retry1"
                        destination = output / "runs" / (run_id + ".json")
                        if destination.exists():
                            continue
                    captured, planning_events = [], []
                    active.clear()
                    active.update(graph_setup_ms=0.0, graph_traversal_ms=0.0)

                    def create(
                        request,
                        plan_path=plan_path,
                        planning_events=planning_events,
                        captured=captured,
                        **kwargs,
                    ):
                        engine = original_m5(request, **kwargs)
                        supervisor = engine.supervisor

                        class ControlledSupervisor:
                            def plan(self, user_question, context, sources):
                                if plan_path.exists():
                                    return (
                                        LitePlan.model_validate(read(plan_path)["plan"]),
                                        PlannerLLMMetadata(status="paired_plan_reused"),
                                        [],
                                    )
                                start = len(gateway.events)
                                plan, metadata, gaps = supervisor.plan(
                                    user_question, context, sources
                                )
                                planning_events.extend(gateway.events[start:])
                                if metadata.status != "success" or gaps:
                                    raise RuntimeError("shared_plan_provider_or_validation_failure")
                                save(
                                    plan_path,
                                    dict(
                                        plan=plan.model_dump(mode="json"),
                                        metadata=metadata.model_dump(mode="json"),
                                        events=planning_events,
                                    ),
                                )
                                return plan, metadata, gaps

                        engine.supervisor = ControlledSupervisor()
                        run = engine.run

                        def capture(**kw):
                            result = run(**kw)
                            captured.append(result.model_dump(mode="json"))
                            return result

                        engine.run = capture
                        return engine

                    service._m5 = create
                    service.repository = VerifiedClaimRepository(output / "ledgers" / run_id)
                    start_events, start_attempts = len(gateway.events), len(adapter.events)
                    row = dict(
                        run_id=run_id,
                        case=case,
                        question=question,
                        requirements=requirements,
                        graph=enabled,
                        repetition=repetition,
                        execution="fresh_live",
                        baseline=BASELINE,
                    )
                    conversation = []
                    if case == "F2":
                        ratio = Decimal(read(output / "oracle.json")["values"]["debt_ratio"])
                        conversation = [
                            {
                                "role": "user",
                                "content": "Tỷ lệ nợ phải trả trên tổng tài sản BBS cuối 2025 là bao nhiêu?",
                            },
                            {
                                "role": "assistant",
                                "content": f"Tỷ lệ nợ phải trả trên tổng tài sản BBS cuối 2025 là {ratio:.2f}%, theo số liệu báo cáo.",
                            },
                        ]
                    started = time.perf_counter()
                    try:
                        response = service.run(
                            FinancialQARequest(
                                question=question,
                                **scope,
                                m5_lite=True,
                                m6_lite=True,
                                m7_lite=True,
                                m5_graph=enabled,
                                force_refresh=True,
                                execution_mode="gemini",
                                allow_gateway=True,
                                max_provider_calls=32,
                                request_timeout_seconds=300,
                                conversation_context=conversation,
                            )
                        )
                        row["response"] = response.model_dump(mode="json")
                    except Exception as error:
                        # Only fixed/type codes: provider exception strings may contain credentials.
                        row["technical_failure"] = type(error).__name__
                    row.update(
                        m5=captured,
                        ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
                        timings=dict(active),
                        wall_latency_ms=(time.perf_counter() - started) * 1000,
                        conversation_context=conversation,
                    )
                    events = gateway.events[start_events:]
                    planning_ids = {e["request"]["request_id"] for e in planning_events}
                    comparison_events = [
                        e for e in events if e["request"]["request_id"] not in planning_ids
                    ]
                    row["events"] = comparison_events
                    row["usage"] = summarize_usage(comparison_events)
                    row["provider_attempts"] = [
                        a
                        for a in adapter.events[start_attempts:]
                        if a["request_id"] not in planning_ids
                    ]
                    row["comparison_latency_ms"] = row["wall_latency_ms"] - sum(
                        e["latency_ms"] for e in planning_events
                    )
                    if plan_path.exists():
                        row["plan_sha256"] = digest(plan_path)
                    save(destination, row)
                    print(
                        run_id,
                        row.get("response", {}).get("status", row.get("technical_failure")),
                        row["usage"],
                        flush=True,
                    )
                    # No uncontrolled repeated failure loops. Resume only with deliberate action.
                    recent = sorted(
                        (output / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime
                    )[-3:]
                    if len(recent) == 3 and all(
                        (
                            read(p)["usage"]["logical_calls"] > 0
                            and read(p)["usage"]["failed_calls"]
                            == read(p)["usage"]["logical_calls"]
                        )
                        or read(p).get("technical_failure")
                        for p in recent
                    ):
                        print(
                            "STOP: three consecutive fully blocked executions",
                            flush=True,
                        )
                        return
    finally:
        adapter.close()
        frozen = read(output / "freeze.json")
        changed = [p for p, expected in frozen["protected"].items() if digest(Path(p)) != expected]
        save(
            output / "integrity.json",
            dict(files=len(frozen["protected"]), changed=changed, unchanged=not changed),
        )
        assert not changed


if __name__ == "__main__":
    main()
