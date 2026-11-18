"""Three offline controls for known E2E failures; no financial accuracy claim."""

import json
from copy import deepcopy
from types import SimpleNamespace

from vietnamese_financial_multi_agent.agents.coordinator_plan import (
    adapt_plan,
    retain_requested_conclusion,
)
from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output
from vietnamese_financial_multi_agent.evidence.document_claim_support import source_assertion
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import (
    LiteVerificationRuntime,
    semantic_output,
)

from .test_evidence_obligations import gateway_with_goals, selection_case


def test_omitted_comparison_retains_original_question_and_valid_task_dependencies():
    question = "Cuối năm 2030, phải thu ngắn hạn của khách hàng hay hàng tồn kho lớn hơn?"
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Tra số dư phải thu ngắn hạn của khách hàng", mode="value")],
            tasks=[
                dict(
                    goal_indexes=[0],
                    role="liquidity_and_leverage",
                    objective="Tra số dư",
                    input_handles=[],
                    after=[],
                )
            ],
        ),
        {},
    )
    assert not errors
    original = deepcopy(plan.tasks)
    assert retain_requested_conclusion(question, plan, {})
    assert plan.tasks[:-1] == original
    assert plan.tasks[-1].depends_on == ["T1"]
    assert plan.requirements[-1].text == question
    assert plan.tasks[-1].requirement_ids == [plan.requirements[-1].requirement_id]
    assert not retain_requested_conclusion(question, plan, {})


def test_partial_verdict_repair_preserves_verified_proof_and_blocks_unverified(tmp_path):
    catalog, batch, context = selection_case()
    second = batch.claims[0].model_copy(deep=True)
    second.candidate_id = second.provenance.m5_candidate_id = "second"
    batch.claims.append(second)
    context["candidate_requirements"]["second"] = ["G1"]
    gateway = gateway_with_goals(["G1"])
    generate = gateway.generate.side_effect
    sent = []

    def partial(request):
        rows = json.loads(request.messages[-1].content)
        sent.append([row["claim_id"] for row in rows])
        response = generate(request)
        raw = response.output.payload
        raw["verdicts"] = raw["verdicts"][:1] if len(sent) == 1 else []
        if len(sent) == 1:
            response = response.model_copy(
                update=dict(status="malformed", output=parse_json_output(json.dumps(raw) + "}"))
            )
        else:
            response = response.model_copy(update=dict(output=parse_json_output(json.dumps(raw))))
        return response

    gateway.generate.side_effect = partial
    runtime = LiteVerificationRuntime(catalog, gateway, integration_v2=True)
    histories = runtime.verify(batch, integration_context=context)
    assert len(sent) == 2 and sent[1] == ["second"]
    assert histories[0].outcome.final.decision == "ACCEPT"
    assert histories[1].outcome.final.decision == "INVESTIGATE"
    assert histories[1].proof.semantic_error == "semantic_verdict_missing_or_invalid"
    assert VerifiedClaimRepository(tmp_path).admit(histories[0]).status == "stored"
    assert runtime.summary["supported_requirements"][batch.claims[0].candidate_id] == ["G1"]
    for text in (
        '{"verdicts":[],"verdicts":[]}}',
        '{"verdicts":[]} {"verdicts":[]}',
        '{"verdicts":[{',
    ):
        assert (
            semantic_output(SimpleNamespace(status="malformed", output=parse_json_output(text)))
            is None
        )
    assert (
        semantic_output(
            SimpleNamespace(status="partial", output=parse_json_output('{"verdicts":[]}'))
        )
        is None
    )


def test_duration_routes_to_literal_source_row_without_promoting_raw_numbers():
    intent, requirements = document_intent(
        "Ước tính thời gian phân bổ phần mềm trong khoảng bao nhiêu năm?"
    )
    assert intent == "document" and len(requirements) == 1
    requirement = requirements[0]
    assert requirement.kind == "exact_text" and requirement.query == "phần mềm"
    table = dict(
        columns=["Loại tài sản", "Thời gian sử dụng"],
        rows=[["Phần mềm", "03–05 năm"], ["Giấy phép", "02 năm"]],
    )
    result = source_assertion(requirement, [dict(literal_table=table)])
    assert result[0] == ["Loại tài sản | Thời gian sử dụng", "Phần mềm | 03–05 năm"]
    changed = deepcopy(table)
    changed["rows"].append(["Phần mềm", "07 năm"])
    assert source_assertion(requirement, [dict(literal_table=changed)]) is None
    changed["rows"] = [["Phần mềm", None]]
    assert source_assertion(requirement, [dict(literal_table=changed)]) is None
