"""Three bounded controls; synthetic engineering evidence, not benchmark accuracy."""

from copy import deepcopy
from types import SimpleNamespace as NS

from vietnamese_financial_multi_agent.agents.coordinator_plan import adapt_plan
from vietnamese_financial_multi_agent.tools.goal_targets import target_groups
from vietnamese_financial_multi_agent.tools.question_understanding import normalize
from vietnamese_financial_multi_agent.verification.evidence_obligations import goal_binding_issue


def test_goal_alias_alternatives_do_not_grant_scalar_coverage():
    text = "Cuối năm 2025, phải thu ngắn hạn của khách hàng hay hàng tồn kho lớn hơn?"
    groups = target_groups(normalize(text))
    assert {("fact", "b01.inventory_total"), ("fact", "b01.inventory_gross")} in groups
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text=text)],
            tasks=[
                dict(
                    goal_indexes=[0],
                    role="liquidity_and_leverage",
                    objective=text,
                    after=[],
                )
            ],
        )
    )
    assert not errors
    requirement = plan.requirements[0].model_dump(mode="json")
    assert not requirement["required_indicators"]
    facts = [
        NS(kind="fact", canonical_item_id=key, unit="VND")
        for key in ["b01.short_term_trade_receivables", "b01.inventory_total"]
    ]
    claim = NS(
        supporting_evidence=facts,
        reasoning=None,
        python_execution=None,
        period="2025-12-31",
        calculation=None,
    )
    proof = NS(batch=NS(claims=[claim]), goal_context={})
    requirement.update(
        required_indicators=[f.canonical_item_id for f in facts], reasoning_operations=["greater"]
    )
    assert goal_binding_issue(proof, requirement) == "goal_formula_mismatch"
    claim.supporting_evidence = facts[:1]
    assert goal_binding_issue(proof, requirement) == "goal_indicator_mismatch"
    explicit = deepcopy(requirement)
    explicit["required_indicators"] = ["b01.inventory_gross"]
    claim.supporting_evidence = facts
    assert goal_binding_issue(proof, explicit) == "goal_indicator_mismatch"
