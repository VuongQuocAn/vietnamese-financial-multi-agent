"""Minimal offline integration controls; synthetic fixtures are not financial evaluation."""

import json
from unittest.mock import Mock, patch

from vietnamese_financial_multi_agent.agents.integration_workspace import (
    IntegrationRequirement,
)
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    inventory,
    normalize_candidate_envelope,
    resolve_source,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification.ledger import validate_entry
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_m4_execution import fixture
from .test_m6_lite import semantic_gateway
from .test_multihop_reasoning import reasoning_case


def test_v2_analysis_envelope_normalization_keeps_untrusted_content_and_strict_schema():
    proposal = dict(
        statement="A candidate calculation, not a verified result",
        evidence_ids=["left", "right"],
        claim_type="derived_fact",
        operations=[
            dict(
                operation_id="op",
                operator="subtract",
                inputs=["left", "right"],
                period_relation="same",
            )
        ],
    )
    payload = dict(claims=[proposal, "left"], analyses=[], missing_information=[])
    original = json.dumps(payload)
    normalized = normalize_candidate_envelope(payload)
    assert normalized["claims"] == ["left"] and normalized["analyses"] == [proposal]
    assert json.dumps(payload) == original  # raw provider output is not rewritten
    malformed = dict(proposal, operations=[dict(operator="direct_value")])
    invalid = dict(payload, claims=[malformed])
    assert normalize_candidate_envelope(invalid) is invalid
    unknown = dict(payload, claims=[dict(proposal, accepted=True)])
    assert normalize_candidate_envelope(unknown) is unknown
    annotated = dict(
        payload,
        claims=[],
        analyses=[
            dict(
                proposal,
                limitations=["Unverified absence assertion must not accompany verified arithmetic"],
            )
        ],
    )
    clean = normalize_candidate_envelope(annotated)
    assert clean["analyses"][0]["limitations"] == []
    assert annotated["analyses"][0]["limitations"]  # retained verbatim in raw output
    narrative = dict(annotated["analyses"][0], claim_type="reasoned_conclusion")
    semantic = dict(payload, claims=[], analyses=[narrative])
    assert normalize_candidate_envelope(semantic) is semantic  # M6 must assess its limits


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
        FinancialLiteOrchestrator(catalog, supervisor=supervisor),
        requirements,
    )


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
        assert '"supported_requirement_ids":[]' in request.messages[0].content
        rows = json.loads(request.messages[-1].content)
        assert all("question" not in row and row["local_requirements"] for row in rows)
        response = original(request)
        body = response.output.payload
        body["verdicts"][0]["supported_requirement_ids"] = ["R1"]
        return response.model_copy(update={"output": parse_json_output(json.dumps(body))})

    gateway.generate.side_effect = assess
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway)
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
            execution_mode="deterministic",
            allow_gateway=False,
        )
    )
    assert failed.status == "internal_error" and not failed.used_verified_claim_ids
    assert failed.trace.integration_context["technical_errors"]


def test_v2_m6_reuses_detached_request_catalog_and_preserves_input(tmp_path):
    catalog, context, engine, _ = setup_engine()
    before = [f.model_dump_json() for f in catalog.facts]
    seen = []

    def runtime_factory(snapshot, *args, **kwargs):
        assert snapshot is not catalog and snapshot._request_snapshot
        runtime = LiteVerificationRuntime(snapshot, *args, **kwargs)
        assert runtime.validator._catalog is snapshot
        assert runtime.builder._tools._catalog is snapshot
        seen.append(snapshot)
        return runtime

    service = FinancialQAPipeline(
        catalog=catalog,
        orchestrator=engine,
        repository=VerifiedClaimRepository(tmp_path),
        documents=[
            QADocument(
                document_id=context.document_id,
                company_id=context.company_id,
                company_aliases=["TEST"],
                reporting_year=2030,
            )
        ],
    )
    with patch(
        "vietnamese_financial_multi_agent.verification.lite_runtime.LiteVerificationRuntime",
        side_effect=runtime_factory,
    ):
        response = service.run(
            FinancialQARequest(
                question="Doanh thu thuần và lợi nhuận gộp TEST năm 2030?",
                document_id=context.document_id,
                snapshot_id=context.snapshot_id,
                execution_mode="deterministic",
                allow_gateway=False,
            )
        )
    assert seen and response.used_verified_claim_ids
    assert before == [f.model_dump_json() for f in catalog.facts]
    seen[0].facts[0].context.raw_item_label = "changed after request"
    assert before == [f.model_dump_json() for f in catalog.facts]
    data, batch = balance_reasoning_case("revenue_yoy", "percentage_change")
    sibling = batch.claims[0].model_copy(deep=True)
    sibling.candidate_id += "-sibling"
    sibling.provenance.m5_candidate_id = sibling.candidate_id
    batch.claims.append(sibling)
    histories = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)
    assert all(h.outcome.final.decision == "ACCEPT" for h in histories)
    histories[0].proof.batch.caveats.append("mutated by caller")
    assert "mutated by caller" not in histories[1].proof.batch.caveats
    assert "mutated by caller" not in batch.caveats


def test_atomic_json_preserves_wire_and_previous_snapshot_on_encoding_error(tmp_path):
    from vietnamese_financial_multi_agent.core.persistence import atomic_json

    path = tmp_path / "snapshot.json"
    payload = {"claims": [{"text": "Nguồn tiếng Việt", "values": [1, 0.56, None]}]}
    atomic_json(path, payload)
    expected = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    assert path.read_text(encoding="utf-8") == expected
    import pytest

    with pytest.raises(ValueError):
        atomic_json(path, {"invalid": float("nan")})
    assert path.read_text(encoding="utf-8") == expected
    assert not list(tmp_path.glob(".snapshot-*"))


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
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data))
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
    ctx = dict(
        requirements=[req.model_dump()],
        candidate_requirements={claim.candidate_id: [req.requirement_id]},
    )
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data))
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "INVESTIGATE"
    gateway = semantic_gateway()
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway)
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: []}
    # Correct statement alone is not full-answer coverage; M6 must affirm the goal too.
    original = gateway.generate.side_effect

    def confirm(request):
        response = original(request)
        response.output.payload["verdicts"][0]["supported_requirement_ids"] = [req.requirement_id]
        return response

    gateway.generate.side_effect = confirm
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway)
    assert runtime.verify(batch, integration_context=ctx)[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: [req.requirement_id]}


def test_v2_inferred_question_date_is_not_an_explicit_pin_on_annual_facts(tmp_path):
    catalog, context, engine, _ = setup_engine()
    service = FinancialQAPipeline(
        catalog=catalog,
        documents=[
            QADocument(
                document_id=context.document_id,
                company_id=context.company_id,
                company_aliases=["TEST"],
                reporting_year=2030,
            )
        ],
        repository=VerifiedClaimRepository(tmp_path),
        orchestrator=engine,
    )
    request = FinancialQARequest(
        question="Doanh thu thuần và lợi nhuận gộp TEST năm 2030, đối chiếu tại 31/12/2030?",
        document_id=context.document_id,
        snapshot_id=context.snapshot_id,
        execution_mode="deterministic",
        allow_gateway=False,
    )
    response = service.run(request)
    assert response.trace.financial_execution["context"]["period"] is None
    assert response.used_verified_claim_ids
    service.repository = VerifiedClaimRepository(tmp_path / "explicit-pin")
    pinned = service.run(request.model_copy(update={"period": "2030-12-31", "force_refresh": True}))
    assert pinned.trace.financial_execution["context"]["period"] == "2030-12-31"
    assert not pinned.used_verified_claim_ids


def test_numeric_only_specialist_reuses_typed_path_without_model_call():
    catalog, context, engine, _ = setup_engine()
    engine.gateway = Mock()
    context.mode = "llm"
    result = engine.run(question="N?u s? li?u", context=context)
    assert result.candidates
    engine.gateway.generate.assert_not_called()
    assert all(e.result.llm.status == "deterministic" for e in result.specialist_executions)
    sources = inventory(catalog, context)
    metric_handle, metric = next((h, s) for h, s in sources.items() if s["kind"] == "metric")
    plan = LitePlan(
        requirements=[
            IntegrationRequirement(
                requirement_id="R",
                text=metric["label"],
                kind="metric",
                target_id=metric_handle,
                period=metric["period"],
            )
        ],
        tasks=[
            LiteTask(
                task_id="T",
                specialist="profitability",
                objective=metric["label"],
                requirement_ids=["R"],
                sources=[h for h, s in sources.items() if s["kind"] == "fact"],
            )
        ],
    )
    engine.supervisor.plan.return_value = (plan, PlannerLLMMetadata(), [])
    result = engine.run(question="Numeric metric", context=context)
    engine.gateway.generate.assert_not_called()
    assert any(c.calculation is not None for c in result.candidates)


def test_aggregation_keeps_declared_premise_order_and_m6_owner():
    from vietnamese_financial_multi_agent.agents.orchestration_contracts import SpecialistExecution
    from vietnamese_financial_multi_agent.agents.orchestrator import aggregate_candidates
    from vietnamese_financial_multi_agent.agents.specialist_common import (
        SpecialistCandidate,
        SpecialistResult,
    )

    data, batch = balance_reasoning_case("revenue_yoy", "percentage_change")
    claim = batch.claims[0]
    candidate = SpecialistCandidate(
        **claim.model_dump(include=set(SpecialistCandidate.model_fields))
    )
    result = SpecialistResult(
        question=batch.question,
        role="profitability",
        upstream_status="completed",
        candidates=[candidate],
        supporting_evidence=list(reversed(claim.supporting_evidence)),
    )
    aggregated, _ = aggregate_candidates(
        [
            SpecialistExecution(
                execution_id="T",
                role="profitability",
                status="generated",
                result=result,
                assigned_requirement_ids=[],
            )
        ]
    )
    assert aggregated[0].supporting_evidence == claim.supporting_evidence
    batch.claims[0].supporting_evidence = aggregated[0].supporting_evidence
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final.decision
        == "ACCEPT"
    )


def test_v2_readable_arithmetic_preserves_sign_period_and_citations():
    from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
    from vietnamese_financial_multi_agent.verification.ledger import build_verified_claim

    data, batch = balance_reasoning_case("revenue_yoy", "percentage_change")
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data))
    entry = build_verified_claim(runtime.verify(batch)[0])
    key = entry.identity.verified_claim_id
    context = dict(
        requirements=[dict(requirement_id="R", text="Tăng trưởng doanh thu")],
        verified_requirements={key: ["R"]},
    )
    request = FinancialQARequest(question="Tăng trưởng doanh thu", allow_gateway=False)
    fields, trace = compose_lite(request, [entry], coverage_context=context)
    assert "thay đổi" in fields["answer_vi"] and "so với kỳ" in fields["answer_vi"]
    assert fields["answer_vi"].count("thay đổi") == 1
    assert trace["released_claims"] == [key] and fields["citations"]

    from types import SimpleNamespace

    from vietnamese_financial_multi_agent.agents.grounded_observations import observation_proposal

    items = ["b01.current_assets", "b01.short_term_liabilities", "b03.operating_cash_flow"]
    evidence = [
        SimpleNamespace(
            evidence_id=f"E{i}",
            kind="fact",
            canonical_item_id=item,
            value=value,
            scale="1",
            unit="VND",
            company_id="C",
            document_id="D",
            snapshot_id="S",
            period="2030" if i == 2 else "2030-12-31",
        )
        for i, (item, value) in enumerate(zip(items, ["100", "200", "50"], strict=True))
    ]
    goal = IntegrationRequirement(
        requirement_id="R",
        text="Nêu giới hạn thanh khoản",
        kind="explanation",
        answer_goal="synthesis",
        required_indicators=items,
    )
    observation = observation_proposal([goal], evidence, goal.text)
    assert "nhỏ hơn" in observation.statement and "dương" in observation.statement
    assert "tương lai" in observation.statement and observation.claim_type == "reasoned_conclusion"
    assert observation_proposal([goal], evidence[:-1], goal.text) is None
    evidence[-1].period = "2029"
    assert observation_proposal([goal], evidence, goal.text) is None
