"""EF-CORE-01: isolated implementation, persisted BBS, genuine opt-in Gemini QA."""

import argparse
import importlib.util
import io
import subprocess
import sys
import zipfile
from pathlib import Path

from evaluate_e2e_lite import digest, save

BASELINE = "0f6165546d2db7a130fbcca666d0e2abf95b7649"
OVERLAYS = [
    "src/tools/graph_retrieval.py",
    "src/agents/supervisor.py",
    "src/agents/lite_orchestrator.py",
    "src/api/financial_qa_pipeline.py",
    "src/api/qa_pipeline_contracts.py",
]
QUESTIONS = [
    ("G1", "Doanh thu thuần BBS năm 2025 là bao nhiêu? Hãy truy vết số liệu và chỉ rõ nguồn PDF."),
    (
        "G2",
        "Doanh thu thuần BBS năm 2025 tăng bao nhiêu phần trăm so với 2024? Truy vết các số liệu tạo ra tỷ lệ đó và nguồn của từng toán hạng.",
    ),
    (
        "G3",
        "Doanh thu và lợi nhuận gộp BBS thay đổi như thế nào từ 2024 sang 2025? Những dữ liệu và nguồn nào hỗ trợ kết luận?",
    ),
    (
        "G4",
        "Hãy phân tích mối liên hệ giữa tổng tài sản, nợ phải trả và tỷ lệ nợ trên tổng tài sản của BBS năm 2025. Truy vết các thành phần và nguồn, không suy diễn nhân quả.",
    ),
    (
        "G5",
        "Tổng nợ phải trả BBS tại ngày 31/12/2025 là bao nhiêu? Truy vết nguồn và các liên kết ngữ cảnh trích xuất bằng EF-EG. Phân biệt association chính xác, cùng ngữ cảnh trích xuất và bằng chứng ngữ nghĩa; có thể suy ra nhân quả từ các liên kết này không?",
    ),
    (
        "G6",
        "Hãy truy vết nguồn số lượng khách hàng mới của BBS năm 2025 và giải thích vì sao làm doanh thu tăng. Nếu không có node hoặc quan hệ phù hợp hãy nói rõ giới hạn.",
    ),
]


def load_runtime(output):
    target = output / "runtime"
    archive = subprocess.check_output(["git", "archive", "--format=zip", BASELINE, "src"])
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        zipped.extractall(target)
    for name in OVERLAYS:
        (target / name).write_bytes(Path(name).read_bytes())
    spec = importlib.util.spec_from_file_location(
        "vietnamese_financial_multi_agent",
        target / "src/__init__.py",
        submodule_search_locations=[str((target / "src").resolve())],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    load_runtime(args.output)
    from evaluate_core_flow import TracedGateway
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
        LitePlan,
        fallback_plan,
    )
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerLLMMetadata
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.tools.graph_retrieval import (
        GetSnapshotGraphContextRequest,
        GraphRetrievalTools,
    )
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    protected = [
        p
        for folder in (
            "artifacts/evidence/EXT-01",
            "artifacts/evidence/D-04-review",
            "artifacts/evidence/M4-05",
        )
        for p in Path(folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    before = {p.as_posix(): digest(p) for p in protected}
    save(
        args.output / "freeze.json",
        dict(
            baseline=BASELINE,
            overlays={p: digest(Path(p)) for p in OVERLAYS},
            protected=before,
            questions=QUESTIONS,
        ),
    )
    service, manifest = pipeline(Path.cwd(), "BBS_2025", args.output / "source")
    if args.live:
        adapter, _ = create_qa_adapter(Path.cwd())
        service.gateway = TracedGateway(SharedLLMGateway({"gemini": adapter}), args.output)
    descriptor = service.catalog.descriptors[0]
    scope = dict(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        company_id=service.documents[0].company_id,
    )
    # Real negative controls use the pinned catalog and never fabricate graph edges.
    tools = GraphRetrievalTools.from_catalog(
        service.catalog, document_id=descriptor.document_id, snapshot_id=descriptor.snapshot_id
    )
    request = GetSnapshotGraphContextRequest(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        node_id=service.catalog.graph.nodes[0].node_id,
    )
    controls = {
        "wrong_snapshot": tools.get_graph_context(
            request.model_copy(update={"snapshot_id": "unbound"})
        ),
        "missing_node": tools.get_graph_context(request.model_copy(update={"node_id": "absent"})),
    }
    assert controls["wrong_snapshot"].status == "unavailable"
    assert controls["missing_node"].status == "not_found"
    save(
        args.output / "negative-controls.json",
        {k: v.model_dump(mode="json") for k, v in controls.items()},
    )
    original_m5 = service._m5
    rows = []
    for case, question in QUESTIONS:
        if args.cases and case not in args.cases:
            continue
        frozen_plan = None
        # OFF first records the real Supervisor plan; ON reuses it unchanged.
        for enabled in [False, True] if case in {"G2", "G3", "G4"} else [True]:
            captured = []

            def create(request, frozen=frozen_plan, sink=captured, **kwargs):
                engine = original_m5(request, **kwargs)
                if not hasattr(engine, "supervisor"):
                    return engine

                class FixedSupervisor:
                    def plan(self, user_question, context, sources):
                        if frozen is not None:
                            return frozen, PlannerLLMMetadata(status="paired_plan_reused"), []
                        plan = fallback_plan(user_question, sources)
                        for task in plan.tasks:
                            task.use_graph = True
                        return plan, PlannerLLMMetadata(status="offline_graph_smoke"), []

                if frozen is not None or not args.live:
                    engine.supervisor = FixedSupervisor()
                run = engine.run

                def capture(**kw):
                    result = run(**kw)
                    sink.append(result)
                    return result

                engine.run = capture
                return engine

            service._m5 = create
            phase = case + ("-on" if enabled else "-off")
            service.repository = VerifiedClaimRepository(args.output / phase / "ledger")
            row = dict(
                case=case,
                question=question,
                graph=enabled,
                execution="fresh_live" if args.live else "offline",
            )
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
                        execution_mode="gemini" if args.live else "deterministic",
                        allow_gateway=args.live,
                        max_provider_calls=32,
                        request_timeout_seconds=300,
                    )
                )
                row["response"] = response.model_dump(mode="json")
                row["m5"] = [r.model_dump(mode="json") for r in captured]
                row["ledger"] = [e.model_dump(mode="json") for e in service.repository.list_all()]
                if captured:
                    frozen_plan = LitePlan.model_validate_json(captured[0].trace[0].reasons[0])
                graphs = [
                    g for r in captured for g in r.supervisor_result.evidence_bundle.graph_contexts
                ]
                print(
                    phase,
                    response.status,
                    response.newly_accepted_claims,
                    "ACCEPT",
                    len(graphs),
                    "graph calls",
                    sorted({e.edge.relation for g in graphs for e in g.edges}),
                    flush=True,
                )
            except Exception as error:
                row["technical_failure"] = type(error).__name__ + ": " + str(error)
                print(phase, row["technical_failure"], flush=True)
            rows.append(row)
            save(args.output / "results.json", rows)
    after = {p: digest(Path(p)) for p in before}
    save(args.output / "integrity.json", dict(files=len(before), unchanged=before == after))
    assert before == after


if __name__ == "__main__":
    main()
