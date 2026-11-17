"""Three targeted controls; Docker evidence requires the explicitly configured worker."""

import os
from unittest.mock import Mock, patch

import pytest
from vietnamese_financial_multi_agent.agents.python_agent import (
    PythonAgent,
    input_manifest,
    requires_python,
)
from vietnamese_financial_multi_agent.tools.financial_retrieval import FinancialRetrievalTools
from vietnamese_financial_multi_agent.tools.python_execution import PythonExecutor

from .test_financial_qa import gateway_for
from .test_v2_integration import setup_engine


def matches():
    catalog, context, _, _ = setup_engine()
    from vietnamese_financial_multi_agent.tools.financial_retrieval import GetFinancialFactRequest

    fact = catalog.facts[0]
    response = FinancialRetrievalTools(catalog).get_financial_fact(
        GetFinancialFactRequest(
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            local_observation_id=fact.local_observation_id,
        )
    )
    return response.matches, context


def test_container_isolation_execution_and_timeout():
    if not os.environ.get("PYTHON_WORKER_IMAGE"):
        pytest.skip("explicit local worker required; no host fallback")
    worker = PythonExecutor()
    assert worker.preflight()["status"] == "ready"
    operands, _ = matches()
    manifest = input_manifest(operands)
    key = next(iter(manifest))
    result = worker.execute(
        f'def solve(data):\n    return {{"value": data["{key}"]}}',
        manifest,
        {"value": "VND"},
        [],
    )
    assert (
        result["status"] == "success" and result["results"]["value"] == manifest[key]["base_value"]
    )
    timed = PythonExecutor(timeout_seconds=0.3).execute(
        "def solve(data):\n    while True:\n        pass",
        manifest,
        {"value": "VND"},
        [],
    )
    assert timed["status"] == "timeout"
    assert not worker._cli(["ps", "-aq", "--filter", "name=financial-python-"]).strip()
    assert PythonExecutor(image="missing").execute("", {}, {}, [])["status"] == "python_unavailable"


def test_one_repair_uses_same_manifest_and_stops_after_second_failure():
    operands, context = matches()
    seen = []
    proposal = dict(
        code='def solve(data):\n    return {"value": missing}',
        outputs={"value": "VND"},
        computation="Diagnostic runtime error",
        constants=[],
    )
    worker = Mock()
    worker.preflight.return_value = dict(status="ready")
    worker.execute.return_value = dict(status="code_error", traceback="NameError: missing")
    record, metadata = PythonAgent(gateway_for(proposal, seen), worker).run(
        objective="Diagnostic",
        requirement="sqrt",
        matches=operands,
        context=context,
    )
    assert len(seen) == metadata.calls == len(record["executions"]) == 2
    assert "NameError" in seen[1].messages[-1].content
    first, second = worker.execute.call_args_list
    assert first.args[1] == second.args[1] == record["operands"]
    assert len({e["input_digest"] for e in record["executions"]}) == 1
    assert record["verification"] == "requires_M6-PY-01" and "results" not in record
    worker.reset_mock()
    unavailable = dict(status="python_unavailable")
    worker.preflight.return_value = unavailable
    blocked, _ = PythonAgent(gateway_for(proposal, []), worker).run(
        objective="Diagnostic",
        requirement="sqrt",
        matches=operands,
        context=context,
    )
    assert blocked["calls"] == 0 and not worker.execute.called


def test_coordinator_keeps_python_candidate_out_of_v1_claims_and_calculator_unchanged():
    assert not requires_python("Cost divided by revenue", "compute percentage", "power")
    assert requires_python("RMS revenue", "RMS from dependencies", "power")
    _, context, engine, _ = setup_engine()
    engine.adaptive_coordinator = True
    plan = engine.supervisor.plan.return_value[0]
    plan.tasks[0].python_requirement = "sqrt"
    plan.tasks[0].objective = "Diagnostic RMS"
    diagnostic = dict(
        version="python_execution_proof_v1",
        status="candidate",
        financial_fact_verified=False,
        verification="requires_M6-PY-01",
        execution_status="success",
        calls=2,
        results={"rms": "1"},
        executions=[],
    )
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerLLMMetadata

    with patch.object(PythonAgent, "run", return_value=(diagnostic, PlannerLLMMetadata())) as run:
        output = engine.run(question="Diagnostic RMS", context=context)
    assert run.call_count == 1
    assert engine.workspace.repair_used  # Shared request repair budget, including Python.
    python_result = output.integration_context["task_results"][plan.tasks[0].task_id]
    assert python_result["python_candidate"] == diagnostic
    assert python_result["candidates"] == []
    assert output.candidates  # Independent existing numeric/Calculator branch survives.
    assert all("python_execution_proof" not in c.model_dump_json() for c in output.candidates)
