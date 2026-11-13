"""Minimal offline integration controls; synthetic fixtures are not financial evaluation."""

import json
from unittest.mock import Mock, patch

from vietnamese_financial_multi_agent.agents.integration_workspace import (
    IntegrationRequirement,
    matches_requirement,
)
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    SupervisorLite,
    integration_plan,
    inventory,
    preserve_answer_goal,
    resolve_requirements,
    resolve_source,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import JSONOutput, parse_json_output
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification.ledger import validate_entry
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture
from .test_m6_lite import semantic_gateway
from .test_multihop_reasoning import reasoning_case


def balance_reasoning_case(formula, operator):
    from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import ITEM_LABELS

    from .test_financial_validators import ITEM_LABELS as labels

    # The shared fixture renderer originally only knew profitability labels.
    with patch.dict(labels, ITEM_LABELS):
        data, batch = reasoning_case(formula=formula, operator=operator)
    claim = batch.claims[0]
    batch.context = PlannerContext(
        company_id=claim.company_id,
        document_id=claim.document_id,
        snapshot_id=claim.snapshot_id,
    )
    if formula == "debt_to_assets":
        claim.analysis_premises = [s.replace(" kỳ ", " tại ngày ") for s in claim.analysis_premises]
    return data, batch


def setup_engine():
    data = fixture()
    catalog = SnapshotCatalog(**data)
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="deterministic",
    )
    sources = inventory(catalog, context)
    requirements = [
        IntegrationRequirement(
            requirement_id=f"R{i}",
            text=s["label"],
            kind="fact",
            target_id=s["item"],
            period=s["period"],
        )
        for i, s in enumerate((s for s in sources.values() if s["kind"] == "fact"), 1)
    ]
    tasks = [
        LiteTask(
            task_id=f"T{i}",
            specialist=role,
            objective=req.text,
            requirement_ids=[req.requirement_id],
            sources=[handle],
        )
        for i, (req, handle, role) in enumerate(
            zip(
                requirements,
                [h for h, s in sources.items() if s["kind"] == "fact"],
                ["profitability", "liquidity_and_leverage"],
                strict=True,
            ),
            1,
        )
    ]
    supervisor = Mock()
    supervisor.plan.return_value = (
        LitePlan(tasks=tasks, requirements=requirements),
        PlannerLLMMetadata(),
        [],
    )
    return (
        catalog,
        context,
        FinancialLiteOrchestrator(catalog, supervisor=supervisor, integration_v2=True),
        requirements,
    )


def test_plan_retains_valid_requirements_and_tasks_with_explicit_failure():
    _, _, engine, _ = setup_engine()
    plan = engine.supervisor.plan.return_value[0]
    wire = plan.model_dump(mode="json")
    wire["use_graph"] = False  # Saved C01 transport shape: unrelated root field.
    wire["tasks"].append({"specialist": "invented"})
    parsed, errors = integration_plan(wire)
    assert len(parsed.tasks) == 2 and parsed.requirements == plan.requirements
    assert errors == ["supervisor_invalid_task:T3", "requirement_plan_incomplete"]
    fenced = '```json\n{"tasks": []}\n```'
    assert parse_json_output(fenced, allow_markdown_fence=True).payload == {"tasks": []}
    parsed_output = parse_json_output(fenced, allow_markdown_fence=True)
    assert JSONOutput.model_validate_json(parsed_output.model_dump_json()) == parsed_output
    assert parse_json_output(fenced).validation_status == "invalid_json"
    assert parse_json_output(fenced + " trailing", allow_markdown_fence=True).payload is None
    catalog, context, _, _ = setup_engine()
    context.mode = "gemini"
    seen = []
    supervisor = SupervisorLite(
        gateway_for(plan.model_dump(mode="json"), seen), integration_v2=True
    )
    decoded, _, errors = supervisor.plan("TEST 2030", context, inventory(catalog, context))
    assert not errors and decoded.requirements == plan.requirements
    prompt = json.loads(seen[0].messages[0].content)
    assert "{requirements:[...],tasks:[...]}" in prompt["instruction"]
    assert "Không DAG, approval, coverage" not in prompt["instruction"]
    service = FinancialQAPipeline(catalog=SnapshotCatalog([]), documents=[], repository=Mock())
    with patch("vietnamese_financial_multi_agent.api.fusion_pipeline.run_fusion") as fusion:
        service.run(
            FinancialQARequest(
                question="Lợi nhuận sau thuế TEST năm 2030 và chính sách chi phí đi vay trong thuyết minh?",
                integration_v2=True,
                execution_mode="deterministic",
                allow_gateway=False,
            )
        )
        assert fusion.call_count == 1
        assert fusion.call_args.args[1].m7_lite  # Presentation flag cannot bypass mixed routing.
        fusion.reset_mock()
        service.run(
            FinancialQARequest(
                question="Lợi nhuận sau thuế TEST năm 2030 và chính sách chi phí đi vay trong thuyết minh?",
                integration_v2=True,
                integration_lane="financial",
                execution_mode="deterministic",
                allow_gateway=False,
            )
        )
        assert not fusion.called  # A bound lane is never decomposed recursively.


def test_shared_evidence_ids_and_task_outputs_survive_sibling_failure():
    _, context, engine, _ = setup_engine()
    plan = engine.supervisor.plan.return_value[0]
    plan.tasks.append(
        LiteTask(
            task_id="T3",
            specialist="cash_flow_and_earnings_quality",
            objective="fail",
            requirement_ids=["R1"],
        )
    )
    plan.tasks.append(
        LiteTask(
            task_id="T4",
            specialist="profitability",
            objective="combine",
            requirement_ids=["R1", "R2"],
            depends_on=["T1", "T2"],
        )
    )
    original = engine._specialist
    seen = {}

    def analyze(task, upstream, *args):
        if task.task_id == "T3":
            raise RuntimeError("isolated failure")
        assert len(upstream.evidence_bundle.facts) == 2
        if task.task_id == "T4":
            assert engine.workspace.tasks["T1"]["candidate_statements"]
            assert engine.workspace.tasks["T2"]["candidate_statements"]
        result = original(task, upstream, *args)
        seen[task.task_id] = {
            e.reference.model_dump_json(): e.evidence_id for e in result.supporting_evidence
        }
        return result

    engine._specialist = analyze
    output = engine.run(question="Doanh thu thuần và lợi nhuận gộp năm 2030", context=context)
    assert output.status == "partial" and len(output.errors) == 1
    assert seen["T1"] == seen["T2"] == seen["T4"]
    assert output.integration_context["tasks"]["T3"]["status"] == "technical_error"
    assert all(e.assigned_requirement_ids for e in output.specialist_executions)
    assert all(c.origins and c.citations for c in output.candidates)


def test_pipeline_preserves_requirements_through_native_m6_ledger_and_m7(tmp_path):
    catalog, context, engine, requirements = setup_engine()
    repository = VerifiedClaimRepository(tmp_path)
    document = QADocument(
        document_id=context.document_id,
        company_id=context.company_id,
        company_aliases=["TEST"],
        reporting_year=2030,
    )
    service = FinancialQAPipeline(
        catalog=catalog, documents=[document], repository=repository, orchestrator=engine
    )
    response = service.run(
        FinancialQARequest(
            question="Doanh thu thuần và lợi nhuận gộp TEST năm 2030?",
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            integration_v2=True,
            execution_mode="deterministic",
            allow_gateway=False,
        )
    )
    assert response.status == "completed_with_caveats", response.model_dump()
    coverage = response.trace.m7_lite["coverage"]
    assert coverage["complete"]
    assert {r["requirement_id"] for r in coverage["requirements"]} == {
        r.requirement_id for r in requirements
    }
    assert set(response.used_verified_claim_ids) == {
        key for r in coverage["requirements"] for key in r["verified_claim_ids"]
    }
    for entry in VerifiedClaimRepository(tmp_path).list_all():
        validate_entry(entry)
        assert entry.identity.policy_version == "verification_lite_v2"
    # M6 assesses the local proposition, and independently confirms relevance;
    # assignment alone cannot mark every requirement covered.
    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = "Các số liệu đã chọn cho phép đối chiếu hai chỉ tiêu trong cùng kỳ."
    gateway = semantic_gateway()
    original = gateway.generate.side_effect

    def assess(request):
        rows = json.loads(request.messages[-1].content)
        assert all("question" not in row and row["local_requirements"] for row in rows)
        response = original(request)
        body = response.output.payload
        body["verdicts"][0]["supported_requirement_ids"] = ["R1"]
        return response.model_copy(update={"output": parse_json_output(json.dumps(body))})

    gateway.generate.side_effect = assess
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway, integration_v2=True)
    histories = runtime.verify(
        batch,
        integration_context=dict(
            candidate_requirements={claim.candidate_id: ["R1", "R2"]},
            requirements=[
                dict(requirement_id="R1", text="Đối chiếu"),
                dict(requirement_id="R2", text="Kết luận khác"),
            ],
        ),
    )
    assert histories[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: ["R1"]}
    engine.supervisor.plan.return_value = (
        LitePlan(),
        PlannerLLMMetadata(),
        ["supervisor_invalid_task:T1"],
    )
    service.repository = VerifiedClaimRepository(tmp_path / "invalid-plan")
    failed = service.run(
        FinancialQARequest(
            question="Doanh thu thuần TEST năm 2030?",
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            integration_v2=True,
            execution_mode="deterministic",
            allow_gateway=False,
        )
    )
    assert failed.status == "internal_error" and not failed.used_verified_claim_ids
    assert failed.trace.integration_context["technical_errors"]


def test_inventory_resolution_uses_period_and_pins_without_role_ownership():
    data = fixture("revenue_yoy")
    catalog = SnapshotCatalog(**data)
    fact = data["facts"][0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        mode="deterministic",
    )
    sources = inventory(catalog, context)
    handle = next(
        h for h, s in sources.items() if s["kind"] == "fact" and s["period"] == fact.context.period
    )
    assert resolve_source(fact.canonical_item_id, sources)[1] == "source_ambiguous"
    assert resolve_source(handle, sources, ["1900"])[1] == "source_period_mismatch"
    assert resolve_source("R1", sources)[1] == "source_unknown"
    assert resolve_source("unknown.item", sources)[0] is None
    assert resolve_source(fact.canonical_item_id, sources, [fact.context.period]) == (handle, None)
    for field in ("company_id", "document_id", "snapshot_id"):
        assert not inventory(catalog, context.model_copy(update={field: "foreign"}))
    ambiguous = {**sources, "another": sources[handle]}
    assert (
        resolve_source(fact.canonical_item_id, ambiguous, [fact.context.period])[1]
        == "source_ambiguous"
    )
    duplicate = {handle: {**sources[handle], "records": [fact, fact.model_copy(deep=True)]}}
    assert resolve_source(handle, duplicate)[1] == "source_ambiguous"
    req = IntegrationRequirement(
        requirement_id="R1",
        text="Tìm doanh thu",
        kind="fact",
        target_id=handle,
        period=fact.context.period,
    )
    plan = LitePlan(
        requirements=[req],
        tasks=[
            LiteTask(
                task_id="T1",
                specialist="cash_flow_and_earnings_quality",
                objective=req.text,
                requirement_ids=["R1"],
                sources=[fact.canonical_item_id],
            )
        ],
    )
    engine = FinancialLiteOrchestrator(
        catalog,
        integration_v2=True,
        supervisor=Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), []))),
    )
    result = engine.run(question=req.text, context=context)
    assert (
        result.candidates
        and result.integration_context["requirements"][0]["target_id"] == fact.canonical_item_id
    )
    assert {m.record.context.period for m in result.supervisor_result.evidence_bundle.facts} == {
        fact.context.period
    }
    assert any(result.integration_context["candidate_requirements"].values())


def test_dynamic_requirement_binding_checks_formula_order_period_unit_and_goal():
    for formula, operator in (
        ("debt_to_assets", "divide"),
        ("revenue_yoy", "percentage_change"),
        ("gross_margin", "ratio"),
    ):
        data, batch = balance_reasoning_case(formula, operator)
        claim = batch.claims[0]
        sources = inventory(
            SnapshotCatalog(**data), batch.context.model_copy(update={"period": None})
        )
        handle = next(h for h, s in sources.items() if s["kind"] == "metric")
        req = IntegrationRequirement(
            requirement_id="R1",
            text="Tính chỉ tiêu",
            kind="metric",
            target_id=handle,
            period=claim.period,
            interpretation=True,
            interpretation_topic="metric_meaning",
            requested_unit=claim.reasoning.calculation.steps[-1].unit,
        )
        plan = LitePlan(requirements=[req])
        target = resolve_requirements(plan, sources)["R1"]
        assert req.target_id == formula and matches_requirement(claim, req, target)
        for update in (
            dict(period="1900"),
            dict(requested_unit="USD"),
            dict(text="Diễn giải ý nghĩa chỉ tiêu"),
            dict(required_indicators=["wrong.item"]),
            dict(reasoning_periods=["1900"]),
        ):
            assert not matches_requirement(claim, req.model_copy(update=update), target)
        wrong = claim.model_copy(deep=True)
        wrong.reasoning.calculation.steps[-1].operation.inputs.reverse()
        assert not matches_requirement(wrong, req, target)
        other = target.copy()
        other["records"] = [target["records"][0].model_copy(deep=True)]
        other["records"][0].definition.compatibility.operands[0].canonical_item_id = "another.item"
        assert not matches_requirement(claim, req, other)
        # A numeric derived proof is bound in Python even without an extra
        # semantic verdict; only M6 ACCEPT may make the proposed binding usable.
        context = dict(
            requirements=[req.model_dump()], candidate_requirements={claim.candidate_id: ["R1"]}
        )
        runtime = LiteVerificationRuntime(SnapshotCatalog(**data), integration_v2=True)
        assert (
            runtime.verify(batch, integration_context=context)[0].outcome.final.decision == "ACCEPT"
        )
        assert runtime.summary["supported_requirements"] == {claim.candidate_id: ["R1"]}


def test_claim_local_periods_keep_exact_source_and_content_guards():
    from .test_financial_validators import batch_for

    data, batch = balance_reasoning_case("debt_to_assets", "divide")
    batch.question = "So sánh doanh thu năm 2029 và 2030, nợ cuối năm và dòng tiền."
    from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import ITEM_LABELS

    from .test_financial_validators import ITEM_LABELS as labels

    with patch.dict(labels, ITEM_LABELS):
        fact = batch_for(data).claims[0]
    fact.content = fact.content.replace(" kỳ ", " tại ngày ")
    fact.candidate_id = fact.provenance.m5_candidate_id = "F1"
    batch.claims.append(fact)
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), integration_v2=True)
    assert all(h.outcome.final.decision == "ACCEPT" for h in runtime.verify(batch))
    for update in (
        dict(period="2029-12-31"),
        dict(company_id="foreign"),
        dict(document_id="foreign"),
        dict(snapshot_id="foreign"),
        dict(content=fact.content.replace("2030-12-31", "2029-12-31")),
        dict(content=fact.content.replace("VND", "USD")),
        dict(content=fact.content.replace("1.234", "9.999")),
        dict(content=fact.content.replace("tại ngày", "kỳ")),
        dict(citations=[]),
    ):
        changed = batch.model_copy(deep=True)
        changed.claims = [fact.model_copy(update=update)]
        assert runtime.verify(changed)[0].outcome.final.decision != "ACCEPT"
    wrong_source = batch.model_copy(deep=True)
    wrong_source.claims = [fact.model_copy(deep=True)]
    source = wrong_source.claims[0].supporting_evidence[0]
    source.reference = source.reference.model_copy(
        update={
            "observation": source.reference.observation.model_copy(
                update={"local_id": "foreign-source"}
            )
        }
    )
    assert runtime.verify(wrong_source)[0].outcome.final.decision != "ACCEPT"
    wrong_pin = batch.model_copy(deep=True)
    wrong_pin.context.period = "2029-12-31"
    assert all(h.outcome.final.decision != "ACCEPT" for h in runtime.verify(wrong_pin))
    wrong_name = batch.model_copy(deep=True)
    wrong_name.claims = [batch.claims[0].model_copy(deep=True)]
    wrong_name.claims[0].content = "Biên lợi nhuận gộp kỳ 2030 là 0,50 lần."
    assert runtime.verify(wrong_name)[0].outcome.final.decision != "ACCEPT"


def test_original_commentary_goal_has_dependent_owner_and_cannot_bind_a_number():
    catalog, context, engine, _ = setup_engine()
    sources = inventory(catalog, context)
    for question in (
        "Nhận xét hai chỉ tiêu và nêu giới hạn khi đánh giá.",
        "Phân tích tổng hợp, không suy nguyên nhân từ biến động.",
        "Đặt hai kết quả bên cạnh nhau và nêu hạn chế.",
    ):
        plan = engine.supervisor.plan.return_value[0].model_copy(deep=True)
        targets = resolve_requirements(plan, sources)
        preserve_answer_goal(plan, question, targets)
        goal = plan.requirements[-1]
        assert goal.text == question and goal.answer_goal == "synthesis"
        assert set(goal.required_indicators) == {f.canonical_item_id for f in catalog.facts}
        task = plan.tasks[-1]
        assert task.depends_on == ["T1", "T2"] and goal.requirement_id in task.requirement_ids
        preserve_answer_goal(plan, question, targets)
        assert len(plan.tasks) == 3 and len(plan.requirements) == 3
        data, batch = reasoning_case()
        claim = batch.claims[0]
        assert not matches_requirement(claim, goal)  # derived arithmetic is not commentary
        claim.reasoning.claim_type = "reasoned_conclusion"
        claim.reasoning.goal = question
        assert matches_requirement(claim, goal)
        claim.supporting_evidence = claim.supporting_evidence[:1]
        assert not matches_requirement(claim, goal)


def test_multiperiod_commentary_still_requires_semantic_truth_and_goal_support():
    data, batch = balance_reasoning_case("revenue_yoy", "percentage_change")
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.reasoning.calculation = None
    claim.content = "Hai kỳ doanh thu là các quan sát trong báo cáo; riêng chúng chưa xác định nguyên nhân biến động."
    req = IntegrationRequirement(
        requirement_id="R-comment",
        text=claim.reasoning.goal,
        kind="explanation",
        interpretation=True,
        answer_goal="analysis",
        required_indicators=["b02.net_revenue"],
    )
    assert matches_requirement(claim, req)
    ctx = dict(
        requirements=[req.model_dump()],
        candidate_requirements={claim.candidate_id: [req.requirement_id]},
    )
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), integration_v2=True)
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "INVESTIGATE"
    gateway = semantic_gateway()
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway, integration_v2=True)
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: []}
    # Correct statement alone is not full-answer coverage; M6 must affirm the goal too.
    original = gateway.generate.side_effect

    def confirm(request):
        response = original(request)
        response.output.payload["verdicts"][0]["supported_requirement_ids"] = [req.requirement_id]
        return response

    gateway.generate.side_effect = confirm
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway, integration_v2=True)
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: [req.requirement_id]}


def test_provider_goal_shorthand_and_catalog_operand_periods_survive_missing_model_periods():
    data, batch = balance_reasoning_case("revenue_yoy", "percentage_change")
    catalog = SnapshotCatalog(**data)
    context = batch.context.model_copy(update={"mode": "deterministic"})
    sources = inventory(catalog, context)
    metric = next(h for h, s in sources.items() if s["kind"] == "metric")
    facts = [h for h, s in sources.items() if s["kind"] == "fact"]
    wire = dict(
        requirements=[
            dict(
                requirement_id="R1",
                text="Tính tăng trưởng",
                kind="metric",
                target_id=metric,
                period="2030",
                interpretation=True,
                required_indicators=facts,
            ),
            dict(
                requirement_id="R2",
                text="Nhận xét",
                kind="analysis",
                aspect="analysis",
                required_indicators=["R1"],
                answer_goal="analysis",
            ),
        ],
        tasks=[
            dict(
                task_id="T1",
                specialist="profitability",
                objective="Tính tăng trưởng",
                requirement_ids=["R1"],
                sources=facts,
            ),
            dict(
                task_id="T2",
                specialist="profitability",
                objective="Nhận xét",
                requirement_ids=["R2"],
                sources=["T1"],
                depends_on=["T1"],
            ),
        ],
    )
    plan, errors = integration_plan(wire)
    assert not errors and plan.tasks[1].sources == []
    engine = FinancialLiteOrchestrator(
        catalog,
        integration_v2=True,
        supervisor=Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), []))),
    )
    result = engine.run(
        question="Nhận xét tăng trưởng doanh thu năm 2030 so với 2029", context=context
    )
    assert {f.record.context.period for f in result.supervisor_result.evidence_bundle.facts} == {
        "2029",
        "2030",
    }
    assert not result.errors
    assert any(r["answer_goal"] != "value" for r in result.integration_context["requirements"])
