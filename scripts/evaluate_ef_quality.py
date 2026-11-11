"""EF-CORE-03: targeted real-data profiling; private traces stay outside Git."""

import argparse
import cProfile
import hashlib
import importlib.util
import io
import json
import pstats
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from evaluate_e2e_lite import digest, save

BASELINE = "48b9d78"
OVERLAYS = [
    "src/agents/lite_orchestrator.py",
    "src/agents/specialist_common.py",
    "src/tools/graph_retrieval.py",
    "src/verification/lite_runtime.py",
]


def load_runtime(output, patched):
    target = output / ("patched-runtime" if patched else "baseline-runtime")
    archive = subprocess.check_output(["git", "archive", "--format=zip", BASELINE, "src"])
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        zipped.extractall(target)
    if patched:
        for name in OVERLAYS:
            local = Path(name).read_text(encoding="utf-8")
            if name.endswith("specialist_common.py"):
                # Keep pre-existing legacy prompt edits out of research/runtime.
                baseline = (
                    subprocess.check_output(["git", "show", f"{BASELINE}:{name}"])
                    .decode()
                    .replace("\r\n", "\n")
                )
                start = local.index("def with_assignment(")
                end = local.index("def _numeric_proposals(")
                local = (
                    local[:start]
                    + baseline[
                        baseline.index("def with_assignment(") : baseline.index(
                            "def _numeric_proposals("
                        )
                    ]
                    + local[end:]
                )
            (target / name).write_text(local, encoding="utf-8", newline="\n")
    spec = importlib.util.spec_from_file_location(
        "vietnamese_financial_multi_agent",
        target / "src/__init__.py",
        submodule_search_locations=[str((target / "src").resolve())],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def profile(output, patched, repeats, instrument=True):
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
        FinancialLiteOrchestrator,
        compact_graph_context,
    )
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
    from vietnamese_financial_multi_agent.tools.graph_retrieval import GetGraphContextRequest

    service, manifest = pipeline(Path.cwd(), "BBS_2025", output / "source")
    engine = FinancialLiteOrchestrator(
        service.catalog, composition=manifest, document_repository=service.document_repository
    )
    context = PlannerContext(
        company_id=service.documents[0].company_id,
        document_id=manifest.financial_snapshot.document_id,
        snapshot_id=manifest.financial_snapshot.snapshot_id,
    )
    rows = []
    profiler = cProfile.Profile()
    for i in range(repeats):
        begin = time.perf_counter()
        if i == 0 and instrument:
            profiler.enable()
        tools = engine._graph_tools(context)
        setup = time.perf_counter() - begin
        begin = time.perf_counter()
        facts = [
            f
            for f in service.catalog.facts
            if f.canonical_item_id
            in {"b02.net_revenue", "b02.gross_profit", "b01.total_liabilities"}
        ]
        from vietnamese_financial_multi_agent.evidence.graph import graph_id

        requests = [
            GetGraphContextRequest(
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
                node_id=graph_id("source_fact", f.observation_identity().model_dump()),
                depth=2,
                limit=8,
            )
            for f in facts[:6]
        ]
        contexts = [tools.get_graph_context(r) for r in requests]
        traversal = time.perf_counter() - begin
        if i == 0 and instrument:
            profiler.disable()
        projection = compact_graph_context(contexts, [])
        rows.append(
            dict(
                setup_s=setup,
                traversal_s=traversal,
                calls=len(requests),
                nodes=sorted(
                    {n.node.node_id for c in contexts for n in [c.start, *c.matches] if n}
                ),
                edges=sorted({e.edge.edge_id for c in contexts for e in c.edges}),
                relations=sorted({r["relation"] for r in projection}),
                projection_chars=len(json.dumps(projection, ensure_ascii=False)),
                responses_sha256=[
                    hashlib.sha256(c.model_dump_json().encode()).hexdigest() for c in contexts
                ],
                projected_operand_roles=sorted(
                    {r["operand_role"] for r in projection if r["operand_role"]}
                ),
            )
        )
    label = "after" if patched else "before"
    save(output / f"performance-{label}.json", rows)
    if instrument:
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(35)
        (output / f"profile-{label}.txt").write_text(stream.getvalue(), encoding="utf-8")
    print(
        label,
        [{k: v for k, v in r.items() if k not in {"nodes", "edges"}} for r in rows],
        flush=True,
    )


def live(output, cases, arms, retry_technical=False, tag=None):
    from evaluate_core_flow import TracedGateway
    from evaluate_ef_ablation import QUESTIONS, summarize_usage
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.agents import lite_orchestrator as m5
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerLLMMetadata
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.verification import lite_runtime as m6
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    questions = {k: q for k, q, _ in QUESTIONS}
    from evaluate_e2e_lite import QUESTIONS as CORE_QUESTIONS

    questions["Q5"] = dict(CORE_QUESTIONS)["Q5"]
    service, _ = pipeline(Path.cwd(), "BBS_2025", output / "live-source")
    adapter, _ = create_qa_adapter(Path.cwd())
    gateway = TracedGateway(SharedLLMGateway({"gemini": adapter}), output)
    service.gateway = gateway
    descriptor = service.catalog.descriptors[0]
    scope = dict(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        company_id=service.documents[0].company_id,
    )
    original_m5, projection = service._m5, m5.source_projection
    setup_original = m5.FinancialLiteOrchestrator._graph_tools
    from vietnamese_financial_multi_agent.tools.graph_retrieval import GraphRetrievalTools

    traversal_original = GraphRetrievalTools.get_graph_context
    timing = {}

    def setup(engine, context):
        start = time.perf_counter()
        try:
            return setup_original(engine, context)
        finally:
            timing["graph_setup_ms"] += (time.perf_counter() - start) * 1000

    def traverse(tools, request):
        start = time.perf_counter()
        try:
            return traversal_original(tools, request)
        finally:
            timing["graph_traversal_ms"] += (time.perf_counter() - start) * 1000

    m5.FinancialLiteOrchestrator._graph_tools = setup
    GraphRetrievalTools.get_graph_context = traverse
    try:
        for case in cases:
            for arm in arms:
                destination = output / "runs" / f"{case}-{arm}.json"
                if tag:
                    destination = output / "runs" / f"{case}-{arm}-{tag}.json"
                if destination.exists():
                    previous = json.loads(destination.read_bytes())
                    if previous["question"] != questions[case]:
                        destination = output / "runs" / f"{case}-{arm}-exact.json"
                        if destination.exists():
                            continue
                    else:
                        if not retry_technical or not previous["usage"]["failed_calls"]:
                            continue
                        destination = destination.with_stem(destination.stem + "-retry1")
                        if destination.exists():
                            continue
                m5.source_projection = m6.source_projection = (
                    projection if arm != "A" else lambda e: {}
                )
                captured = []
                plan_path = output / "plans" / f"{case}.json"
                if destination.stem.endswith("exact"):
                    plan_path = output / "plans" / f"{case}-exact.json"

                def create(request, plan_path=plan_path, captured=captured, **kwargs):
                    engine = original_m5(request, **kwargs)
                    supervisor = engine.supervisor

                    class SharedSupervisor:
                        def plan(self, question, context, sources):
                            if plan_path.exists():
                                data = json.loads(plan_path.read_bytes())
                                return (
                                    m5.LitePlan.model_validate(data["plan"]),
                                    PlannerLLMMetadata(status="shared_plan"),
                                    [],
                                )
                            plan, metadata, gaps = supervisor.plan(question, context, sources)
                            if metadata.status != "success" or gaps:
                                raise ValueError("fresh_supervisor_plan_failed")
                            save(
                                plan_path,
                                dict(
                                    plan=plan.model_dump(mode="json"),
                                    metadata=metadata.model_dump(mode="json"),
                                ),
                            )
                            return plan, metadata, gaps

                    engine.supervisor = SharedSupervisor()
                    run = engine.run

                    def capture(**kw):
                        result = run(**kw)
                        captured.append(result.model_dump(mode="json"))
                        return result

                    engine.run = capture
                    return engine

                service._m5 = create
                service.repository = VerifiedClaimRepository(output / "ledgers" / f"{case}-{arm}")
                timing.clear()
                timing.update(graph_setup_ms=0, graph_traversal_ms=0)
                start_events, start_attempts = len(gateway.events), len(adapter.events)
                begin = time.perf_counter()
                row = dict(case=case, arm=arm, question=questions[case], execution="fresh_live")
                row["runtime_sha256"] = {
                    name: digest(output / "patched-runtime" / name) for name in OVERLAYS
                }
                try:
                    response = service.run(
                        FinancialQARequest(
                            question=questions[case],
                            **scope,
                            m5_lite=True,
                            m6_lite=True,
                            m7_lite=True,
                            m5_graph=arm == "C",
                            force_refresh=True,
                            execution_mode="gemini",
                            allow_gateway=True,
                            max_provider_calls=32,
                            request_timeout_seconds=300,
                        )
                    )
                    row["response"] = response.model_dump(mode="json")
                except Exception as error:
                    row["technical_failure"] = type(error).__name__
                events = gateway.events[start_events:]
                row.update(
                    m5=captured,
                    events=events,
                    usage=summarize_usage(events),
                    provider_attempts=adapter.events[start_attempts:],
                    ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
                    timings=dict(timing),
                    wall_latency_ms=(time.perf_counter() - begin) * 1000,
                )
                save(destination, row)
                print(
                    case,
                    arm,
                    row.get("response", {}).get("status", row.get("technical_failure")),
                    row["usage"],
                    flush=True,
                )
    finally:
        adapter.close()


def semantic_probe(output):
    """Fresh semantic call on canonical BBS claims, not replayed verdicts."""
    from evaluate_core_flow import TracedGateway
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
    from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

    destination = output / "semantic-probe.json"
    if destination.exists():
        return
    row = json.loads((output / "runs/C1-C-retry1.json").read_bytes())
    wire = row["m5"][0]
    # Tool traces are diagnostic, not M6 proof inputs. Restore the candidate
    # boundary only; JSON's typed record unions require model_validate_json.
    wire["supervisor_result"] = None
    batch = to_verification_input(OrchestrationResult.model_validate_json(json.dumps(wire)))
    original = next(c for c in batch.claims if c.reasoning and c.reasoning.calculation)
    statements = {
        "page-contradiction": "Không có thông tin trang nguồn để truy vết các số liệu này.",
        "page-limitation": "Có liên kết trang nguồn, nhưng mức độ chính xác provenance còn giới hạn cấp trang hoặc chưa chắc chắn.",
        "unsupported-materials": "Biến động lợi nhuận này là do chi phí nguyên liệu tăng.",
        "ambiguous-materials": "Đây là phần chênh lệch lợi nhuận từ nguyên liệu.",
    }
    batch.claims = []
    for name, statement in statements.items():
        claim = original.model_copy(deep=True)
        claim.candidate_id = claim.provenance.m5_candidate_id = name
        claim.content = statement
        claim.reasoning.claim_type = "reasoned_conclusion"
        claim.reasoning.assumptions = []
        claim.reasoning.limitations = []
        batch.claims.append(claim)
    missing = batch.claims[0].model_copy(deep=True)
    missing.candidate_id = missing.provenance.m5_candidate_id = "missing-source"
    missing.citations = []
    batch.claims.append(missing)
    service, _ = pipeline(Path.cwd(), "BBS_2025", output / "probe-source")
    adapter, _ = create_qa_adapter(Path.cwd())
    gateway = TracedGateway(SharedLLMGateway({"gemini": adapter}), output / "probe")
    try:
        histories = LiteVerificationRuntime(service.catalog, gateway).verify(batch)
        result = dict(
            histories=[h.model_dump(mode="json") for h in histories],
            events=gateway.events,
            provider_attempts=adapter.events,
            decisions={h.outcome.final.candidate_id: h.outcome.final.decision for h in histories},
        )
        save(destination, result)
        print(result["decisions"], flush=True)
    finally:
        adapter.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/EF-CORE-03"))
    parser.add_argument("--patched", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--measure-only", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--retry-technical", action="store_true")
    parser.add_argument("--semantic-probe", action="store_true")
    parser.add_argument("--tag", choices=["final"])
    parser.add_argument("--cases", nargs="+", default=["C1", "D1", "B2", "C3", "Q5"])
    parser.add_argument("--arms", nargs="+", choices=["A", "B", "C"], default=["C"])
    args = parser.parse_args()
    load_runtime(args.output, args.patched)
    if args.semantic_probe:
        if not args.patched or not args.live:
            parser.error("semantic probe requires --patched --live")
        semantic_probe(args.output)
    elif args.live:
        if not args.patched:
            parser.error("live requires --patched")
        live(args.output, args.cases, args.arms, args.retry_technical, args.tag)
    else:
        profile(args.output, args.patched, args.repeats, not args.measure_only)


if __name__ == "__main__":
    main()
