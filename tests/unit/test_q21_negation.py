"""Scope routing only; a limitation still requires independent semantic/M6 checks."""

import json
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerProposal,
    UserRequestedTarget,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.adaptive_judge import (
    AdaptiveJudge,
    bind_coverage,
)
from vietnamese_financial_multi_agent.verification.logic_rules import assertion_category
from vietnamese_financial_multi_agent.verification.validators import DeterministicFinancialValidator

from .test_evidence_critic import response
from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_verified_claim_ledger import history_for


@pytest.mark.parametrize(
    "text",
    [
        "Dữ liệu chưa đủ để tính tỷ lệ chuyển đổi.",
        "Thông tin hiện có vẫn chưa đủ để kết luận tỷ lệ cải thiện.",
        "Bằng chứng hiện có không đủ để khẳng định tỷ số tốt hơn.",
        "Chưa có đủ căn cứ để kết luận tỷ lệ cải thiện.",
        "Không có đủ dữ liệu để tính toán hệ số này.",
        "Chưa đủ cơ sở tính toán tỷ lệ chuyển đổi hoặc kết luận chất lượng lợi nhuận.",
        "Báo cáo ghi nhận dữ liệu; tuy nhiên, dữ liệu chưa đủ để tính toán tỷ lệ chuyển đổi do thiếu thông tin đối chiếu.",
        "Trong kỳ này, báo cáo ghi nhận số liệu lợi nhuận sau thuế và lưu chuyển tiền thuần từ hoạt động kinh doanh; tuy nhiên, dữ liệu chưa đủ để tính toán tỷ lệ chuyển đổi dòng tiền hoặc kết luận chi tiết về chất lượng lợi nhuận do thiếu thông tin đối chiếu và điều chỉnh chi tiết.",
    ],
)
def test_evidence_predicate_and_governed_complement_defer_to_semantics(text):
    assert assertion_category(text) == "EVIDENCE_LIMITATION"
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind, claim.analysis_premises, claim.content = (
        "supported_interpretation",
        [claim.content],
        text,
    )
    validation = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch).claims[0]
    assert not any(c.status == "fail" for c in validation.checks)
    assert any(c.check_id == "numeric" and c.status == "pass" for c in validation.checks)
    assert (
        next(c for c in validation.checks if c.check_id == "semantic_conclusion").status
        == "undetermined"
    )


@pytest.mark.parametrize(
    "text",
    [
        "Tỷ lệ tăng 15%.",
        "Chưa đủ dữ liệu, nhưng tỷ lệ đã tăng 15%.",
        "Dữ liệu chưa đủ để kết luận, tuy nhiên tỷ lệ tăng mạnh.",
        "Chưa đủ dữ liệu để kết luận tỷ lệ cải thiện và tỷ lệ đã tăng.",
        "Chưa đủ dữ liệu để kết luận tỷ lệ cải thiện, tỷ lệ vẫn tăng.",
        "Chưa đủ dữ liệu để tính tỷ lệ, nên tỷ lệ này tăng mạnh.",
        "Tỷ lệ đã tăng dù dữ liệu chưa đủ để kết luận.",
        "Không thiếu dữ liệu để kết luận tỷ lệ tăng.",
        "Không phải dữ liệu chưa đủ để kết luận tỷ lệ tăng.",
    ],
)
def test_negation_does_not_consume_independent_numeric_or_double_negative_claim(text):
    assert assertion_category(text) == "NUMERIC_ASSERTION"
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind, claim.analysis_premises, claim.content = (
        "supported_interpretation",
        [claim.content],
        text,
    )
    validation = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch).claims[0]
    assert any(
        c.check_id in {"formula", "numeric"} and c.status == "fail" for c in validation.checks
    )


@pytest.mark.parametrize(
    "support,logic_status,accept",
    [
        (False, "consistent", False),
        (True, "insufficient_context", False),
        (True, "consistent", True),
    ],
)
def test_limitation_requires_independent_evidence_logic_and_native_admission(
    tmp_path, support, logic_status, accept
):
    from vietnamese_financial_multi_agent.verification import EvidenceCritic, FinancialLogicCritic
    from vietnamese_financial_multi_agent.verification.decision_contracts import (
        VerificationLoopResult,
    )
    from vietnamese_financial_multi_agent.verification.judge import VerificationJudge
    from vietnamese_financial_multi_agent.verification.ledger_contracts import (
        VerificationHistory,
        VerificationProofContext,
    )
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    from .test_evidence_critic import semantic_gateway
    from .test_financial_logic_critic import gateway as logic_gateway

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind, claim.analysis_premises, claim.content = (
        "supported_interpretation",
        [claim.content],
        "Dữ liệu chưa đủ để kết luận tỷ lệ cải thiện.",
    )
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)

    def assess(payload):
        for assertion in payload["assertions"]:
            assertion.update(
                status="supported" if support else "unsupported",
                evidence_ids=["E1"],
                reason="direct_support" if support else "beyond_evidence",
                missing=[],
            )

    evidence = EvidenceCritic(catalog, semantic_gateway(assess)).assess(batch, validation)
    logic = FinancialLogicCritic(logic_gateway(status=logic_status)).assess(
        batch, validation, evidence
    )
    decision = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert (decision.decision == "ACCEPT") == accept
    history = VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=VerificationLoopResult(
            parent_candidate_id=claim.candidate_id,
            initial_input=batch,
            attempts=[decision],
            stopped=True,
            stop_reason="initial_decision_terminal",
        ),
    )
    assert VerifiedClaimRepository(tmp_path).admit(history).status == (
        "stored" if accept else "rejected"
    )


@pytest.mark.parametrize("accepted", [False, True])
def test_judge_receives_native_coverage_before_call_and_cannot_override_guard(accepted):
    history = history_for()
    claim = history.outcome.final.original_claim
    proposal = PlannerProposal(
        intent="direct_fact",
        reasoning_required=True,
        user_requested_targets=[
            UserRequestedTarget(
                kind="fact", target_id=claim.supporting_evidence[0].canonical_item_id
            )
        ],
    )
    output = SimpleNamespace(
        planner_result=SimpleNamespace(effective_proposal=proposal),
        supervisor_result=None,
        context=PlannerContext(
            **{k: getattr(claim, k) for k in ("company_id", "document_id", "snapshot_id", "period")}
        ),
    )
    seen = []

    def transport(request):
        payload = json.loads(request.messages[0].content)
        seen.append(payload)
        return response(
            request,
            dict(
                assessment="PASS",
                issues=[],
                revision_required=False,
                explanation="model_recommendation",
            ),
        )

    histories = [history] if accepted else []
    feedback = AdaptiveJudge(
        SharedLLMGateway({"gemini": transport}), PlannerContext().model
    ).assess("Chỉ tiêu đã yêu cầu TEST 2030?", output, histories)
    assert feedback.assessment == "PASS"
    payload = seen[0]
    assert payload["answer_coverage"]["complete"] == accepted
    assert bool(payload["answer_coverage"]["goals"][0]["verified_candidate_ids"]) == accepted
    assert "answer_coverage.complete=false" in payload["instruction"]
    checked = bind_coverage(feedback, "Chỉ tiêu đã yêu cầu TEST 2030?", output, histories)
    assert checked.assessment == ("PASS" if accepted else "INSUFFICIENT_EVIDENCE")
