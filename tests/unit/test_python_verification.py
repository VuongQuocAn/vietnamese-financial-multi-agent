"""Three focused synthetic controls; live research evidence is recorded separately."""

from copy import deepcopy
from decimal import Decimal, localcontext
from unittest.mock import Mock

from vietnamese_financial_multi_agent.agents.evidence_coordination import observation
from vietnamese_financial_multi_agent.agents.python_agent import PythonAgent, input_manifest
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)
from vietnamese_financial_multi_agent.tools.python_execution import digest
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime
from vietnamese_financial_multi_agent.verification.python_proof import project_python

from .test_evidence_obligations import gateway_with_goals
from .test_financial_qa import gateway_for
from .test_multihop_reasoning import reasoning_case


def python_case():
    data, batch = reasoning_case(formula="revenue_yoy")
    catalog = SnapshotCatalog(**data)
    tools = FinancialRetrievalTools(catalog)
    matches = [
        tools.get_financial_fact(
            GetFinancialFactRequest(
                document_id=f.document_id,
                snapshot_id=f.snapshot_id,
                local_observation_id=f.local_observation_id,
            )
        ).matches[0]
        for f in data["facts"][:2]
    ]
    manifest = input_manifest(matches)
    left, right = list(manifest)
    code = (
        f'def solve(data):\n    return {{"rms": ((data["{left}"] ** 2 + '
        f'data["{right}"] ** 2) / 2).sqrt()}}'
    )
    with localcontext() as ctx:
        ctx.prec = 34
        a, b = (Decimal(r["base_value"]) for r in manifest.values())
        expected = str(((a**2 + b**2) / 2).sqrt())
    worker = Mock(image="sha256:" + "a" * 64)
    ready = dict(status="ready", image=worker.image, isolation=dict(harness="python_worker_v1"))
    worker.preflight.return_value = ready
    worker.execute.return_value = dict(status="success", results=dict(rms=expected), worker=ready)
    years = " và ".join(r["context"]["period"] for r in manifest.values())
    question = f"Tính RMS doanh thu thuần hai năm {years} bằng VND."
    proposal = dict(code=code, outputs=dict(rms="VND"), computation="sqrt((a²+b²)/2)", constants=[])
    record, _ = PythonAgent(gateway_for(proposal, []), worker).run(
        objective=question,
        requirement="sqrt",
        matches=matches,
        context=batch.context,
    )
    tid = "python-task"
    result = dict(
        task_id=tid,
        handle="result:python-task:v1",
        revision=1,
        input_results=[],
        selected_observations=[observation(m) for m in matches],
        coordination={},
        python_candidate=record,
    )
    result["digest"] = digest(result)
    context = dict(
        adaptive_coordinator=True,
        tasks={
            tid: dict(
                role="profitability", requirement_ids=["G1"], depends_on=[], python_candidate=record
            )
        },
        task_results={tid: result},
        requirements=[
            dict(
                requirement_id="G1",
                text=question,
                interpretation_topic="dynamic_calculation",
                requested_unit="VND",
            )
        ],
        candidate_requirements={},
    )
    batch.question = question
    batch.claims = project_python(context)
    assert len(batch.claims) == 1
    return catalog, batch, context, worker


def test_python_replay_goal_ledger_restart_and_m7(tmp_path):
    catalog, batch, context, worker = python_case()
    runtime = LiteVerificationRuntime(
        catalog, gateway_with_goals(["G1"]), integration_v2=True, python_executor=worker
    )
    history = runtime.verify(batch, integration_context=context)[0]
    assert history.outcome.final.decision == "ACCEPT"
    assert (
        history.proof.python_replay["results"]
        == batch.claims[0].python_execution.execution["results"]
    )
    repository = VerifiedClaimRepository(tmp_path)
    admission = repository.admit(history)
    assert admission.status == "stored", admission.reason
    entry = VerifiedClaimRepository(tmp_path).list_all()[0]
    assert entry.history == history and entry.version == "verified_claim_v2"
    key = entry.identity.verified_claim_id
    fields, trace = compose_lite(
        FinancialQARequest(question=batch.question, allow_gateway=False),
        [entry],
        coverage_context=dict(
            requirements=context["requirements"], verified_requirements={key: ["G1"]}
        ),
    )
    assert trace["released_claims"] == [key] and fields["citations"]
    changed = history.model_copy(deep=True)
    changed.proof.batch.claims[0].python_execution.execution["executions"][-1]["code"] += "\n"
    assert repository.admit(changed).status == "rejected"


def test_python_wrong_code_operand_replay_and_unavailable_never_admitted(tmp_path):
    catalog, original, context, original_worker = python_case()
    for mode in ("code", "operand", "replay", "unavailable"):
        batch, worker = original.model_copy(deep=True), deepcopy(original_worker)
        record = batch.claims[0].python_execution.execution
        if mode == "code":
            record["executions"][-1]["code"] += "\n"
        elif mode == "operand":
            next(iter(record["operands"].values()))["base_value"] = "999"
            record["input_digest"] = record["executions"][-1]["input_digest"] = digest(
                record["operands"]
            )
            batch.claims[0].python_execution.execution_sha256 = digest(record)
        elif mode == "replay":
            worker.execute.return_value["results"] = dict(rms="999")
        else:
            worker.execute.return_value = dict(status="python_unavailable")
        gateway = gateway_with_goals(["G1"])
        runtime = LiteVerificationRuntime(
            catalog, gateway, integration_v2=True, python_executor=worker
        )
        history = runtime.verify(batch, integration_context=context)[0]
        assert history.outcome.final.decision != "ACCEPT", mode
        assert not gateway.generate.called
        assert VerifiedClaimRepository(tmp_path / mode).admit(history).status == "rejected"


def test_replay_success_does_not_prove_financial_formula_or_goal(tmp_path):
    catalog, batch, context, worker = python_case()
    gateway = gateway_with_goals(["G1"])
    assess = gateway.generate.side_effect

    def reject_formula(request):
        response = assess(request)
        verdict = response.output.payload["verdicts"][0]
        verdict.update(
            verdict="UNSUPPORTED",
            reason="Formula does not answer RMS",
            supported_requirement_ids=[],
        )
        return response

    gateway.generate.side_effect = reject_formula
    runtime = LiteVerificationRuntime(catalog, gateway, integration_v2=True, python_executor=worker)
    history = runtime.verify(batch, integration_context=context)[0]
    assert history.proof.python_replay and history.outcome.final.decision == "ABSTAIN"
    assert VerifiedClaimRepository(tmp_path / "formula").admit(history).status == "rejected"
    runtime = LiteVerificationRuntime(
        catalog, gateway_with_goals([]), integration_v2=True, python_executor=worker
    )
    history = runtime.verify(batch, integration_context=context)[0]
    assert history.outcome.final.decision == "ACCEPT"  # truth and goal coverage stay separate
    assert VerifiedClaimRepository(tmp_path / "goal").admit(history).status == "rejected"
