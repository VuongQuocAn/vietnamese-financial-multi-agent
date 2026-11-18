"""Three bounded controls; synthetic engineering evidence, not benchmark accuracy."""

from copy import deepcopy
from types import SimpleNamespace as NS

from vietnamese_financial_multi_agent.agents.coordinator_plan import adapt_plan
from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.evidence.document_table_selection import table_assertion
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
    assert goal_binding_issue(proof, requirement) == "goal_comparison_mismatch"
    claim.supporting_evidence = facts[:1]
    assert goal_binding_issue(proof, requirement) == "goal_indicator_mismatch"
    explicit = deepcopy(requirement)
    explicit["required_indicators"] = ["b01.inventory_gross"]
    claim.supporting_evidence = facts
    assert goal_binding_issue(proof, explicit) == "goal_indicator_mismatch"


def table_case():
    _, specs = document_intent(
        "Trong thuyết minh Phải thu khách hàng cuối năm 2024, đối tượng nêu tên riêng có số dư lớn nhất là ai?"
    )
    return specs[0], [
        {
            "selection_table": dict(
                title="6. PHẢI THU KHÁCH HÀNG",
                columns=["Chỉ tiêu", "31/12/2024 VND", "01/01/2024 VND"],
                rows=[
                    ["Công ty A", "30", "50"],
                    ["Công ty B", "40", "20"],
                    ["Các khách hàng khác", "100", "90"],
                    ["Cộng", "170", "160"],
                ],
            )
        }
    ]


def test_named_table_domain_excludes_aggregates_and_keeps_ties():
    requirement, source = table_case()
    assertion = table_assertion(requirement, source)
    assert "là Công ty B: 40 VND" in assertion[1]
    assert "Các khách hàng khác: 100" in assertion[0] and "Cộng: 170" in assertion[0]
    source[0]["selection_table"]["rows"][0][1] = "40"
    source[0]["selection_table"]["rows"][-1][1] = "180"
    assert "Công ty A; Công ty B" in table_assertion(requirement, source)[1]


def test_missing_period_unknown_entity_partial_domain_and_false_total_are_blocked():
    requirement, source = table_case()
    for mutation in ("missing", "unknown", "partial", "total", "period"):
        bad = deepcopy(source)
        table = bad[0]["selection_table"]
        if mutation == "missing":
            table["rows"][0][1] = "-"
        if mutation == "unknown":
            table["rows"][0][0] = "Nhóm không rõ"
        if mutation == "partial":
            table["rows"].pop(0)
        if mutation == "total":
            table["rows"].pop()
        if mutation == "period":
            table["columns"][1] = "31/12/2023 VND"
        assert table_assertion(requirement, bad) is None
