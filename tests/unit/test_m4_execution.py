"""M4 generic controls; synthetic PASS chỉ chứng minh contracts/guards."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from vietnamese_financial_multi_agent.accounting.quality import QualityIssue
from vietnamese_financial_multi_agent.evidence import (
    ExecutionCompatibilityApproval,
    FinancialOperand,
    FormulaDefinition,
    OperationCompatibilitySpec,
    PeriodPair,
    SnapshotCatalog,
    SnapshotDescriptor,
    TableEvidence,
    assess_execution_compatibility,
    build_graph,
    rebuild_snapshot_metrics,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    assess_analytical_readiness,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparedFormulaPolicy,
    check_metric_formula_policy,
)

from .test_d02_readiness import preparation_approval, sample


def registry():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "configs/m4-execution-policies.json").read_text(
            encoding="utf-8"
        )
    )


def fixture(formula="gross_margin", document=0):
    policy = PreparedFormulaPolicy(
        **next(p for p in registry()["formula_policies"] if p["formula_id"] == formula)
    )
    _, operands, reviews, bases = sample()
    salt = ("a", "d")[document]
    descriptor = SnapshotDescriptor(
        document_id="sha256:" + salt * 64,
        pdf_sha256=salt * 64,
        snapshot_id=f"selected-{document}",
        origin="original_extraction",
    )
    evidence = []
    year = 2030 + document
    for i, (operand, requirement, review) in enumerate(
        zip(operands, policy.operands, reviews, strict=True)
    ):
        operand.role = requirement.role
        f = operand.fact
        f.document_id, f.snapshot_id = descriptor.document_id, descriptor.snapshot_id
        f.company_id = f"independent-company-{document}"
        f.canonical_item_id, f.semantic_role = (
            requirement.canonical_item_id,
            requirement.semantic_role,
        )
        f.context.mapped_item_code = requirement.canonical_item_id
        f.context.statement_type = requirement.statement_type
        f.context.period = (
            f"{year}-12-31"
            if formula == "debt_to_assets"
            else str(year - i)
            if formula == "revenue_yoy"
            else str(year)
        )
        f.context.period_type = "as_of" if formula == "debt_to_assets" else "fiscal_year"
        f.raw_header = f"Synthetic period {f.context.period}"
        for source in f.sources:
            source.document_id, source.snapshot_id = f.document_id, f.snapshot_id
            source.reference.anchor.page.source_ref = f.document_id
            source.reference.anchor.page.page = 7 + document
            source.reference.source_pointer = source.reference.source_pointer.replace(
                "/tables/0/", f"/tables/{i + document}/"
            )
        review.observation = f.observation_identity()
        review.sources = [s.model_copy(deep=True) for s in f.sources]
        review.pdf_sha256, review.pdf_page = salt * 64, 7 + document
        review.raw_header, review.period, review.statement_type = (
            f.raw_header,
            f.context.period,
            f.context.statement_type,
        )
        for field in ("value_selector", "label_selector", "header_selector"):
            setattr(
                review,
                field,
                getattr(review, field).replace("/tables/0/", f"/tables/{i + document}/"),
            )
        evidence.append(
            TableEvidence(
                document_id=f.document_id,
                snapshot_id=f.snapshot_id,
                local_evidence_id=f"table-{i}",
                member_sources=f.sources,
            )
        )
    basis = bases[0]
    basis.document_id, basis.snapshot_id, basis.pdf_sha256 = (
        descriptor.document_id,
        descriptor.snapshot_id,
        descriptor.pdf_sha256,
    )
    definition = FormulaDefinition(
        formula_reference="synthetic/descriptive-example",
        formula_version="reference-v1",
        name=formula,
        expression=policy.expression,
        compatibility=OperationCompatibilitySpec(
            operation_id=formula,
            rule_reference="synthetic/not-execution-authority",
            operands=policy.operands,
            document_relation="same",
            period_relation="ordered_pair" if formula == "revenue_yoy" else "same",
            period_pairs=[
                PeriodPair(left=str(year), right=str(year - 1), period_type="fiscal_year")
            ]
            if formula == "revenue_yoy"
            else [],
        ),
    )
    metrics = rebuild_snapshot_metrics(
        [(definition, {o.role: o.fact.context.period for o in operands})],
        descriptor,
        [o.fact for o in operands],
    )
    # Test-only authority, not a production approval or claim of completed controls.
    approval = FormulaExecutionApproval(
        formula_id=formula,
        version=policy.version,
        definition_sha256=policy.definition_digest(),
        authority="Tech Lead",
        purpose="formula_execution",
        decision_reference="synthetic/decision",
        negative_controls_reference="synthetic/controls",
    )
    return dict(
        descriptors=[descriptor],
        facts=[o.fact for o in operands],
        evidence=evidence,
        metrics=metrics,
        graph=build_graph([o.fact for o in operands], evidence, metrics),
        source_reviews=reviews,
        accounting_bases=bases,
        approval=preparation_approval(),
        formula_policies=[policy],
        formula_approvals=[approval],
        execution_approval=ExecutionCompatibilityApproval(**registry()["execution_approval"]),
    )


def assess(inputs):
    return SnapshotCatalog(**inputs).assess_metric(inputs["descriptors"][0], inputs["metrics"][0])


@pytest.mark.parametrize("formula", ["gross_margin", "debt_to_assets", "revenue_yoy"])
@pytest.mark.parametrize("document", [0, 1])
def test_independent_documents_positive_restart_and_immutable_inputs(formula, document):
    inputs = fixture(formula, document)
    before = [f.model_dump_json() for f in inputs["facts"]]
    metric_before = inputs["metrics"][0].model_dump_json()
    result = assess(inputs)
    assert result.status == "closed" and result.preparation_ready and result.calculation_eligible
    readiness = result.readiness
    assert readiness["global_compatibility"]["status"] == "undetermined"
    assert readiness["approved_execution_compatibility"]["status"] == "compatible"
    assert readiness["execution_profile_approved"] and not readiness["execution_blockers"]
    assert readiness["formula_policy"]["execution_approved"]
    assert not inputs["metrics"][0].result and inputs["metrics"][0].result_status == "not_computed"
    for key in ("facts", "metrics", "source_reviews", "accounting_bases", "formula_approvals"):
        inputs[key] = [type(r).model_validate_json(r.model_dump_json()) for r in inputs[key]]
    assert assess(inputs) == result
    assert before == [f.model_dump_json() for f in inputs["facts"]]
    assert metric_before == inputs["metrics"][0].model_dump_json()
    # Neither a missing preparation approval nor its candidate flags grant authority.
    inputs["approval"] = None
    assert assess(inputs).calculation_eligible
    inputs["execution_approval"] = None
    assert not assess(inputs).calculation_eligible


@pytest.mark.parametrize(
    "control",
    [
        "missing_approval",
        "wrong_profile",
        "wrong_version",
        "wrong_purpose",
        "wrong_authority",
        "cross_document",
        "cross_snapshot",
        "wrong_statement",
        "wrong_company",
        "missing_company",
        "scope_conflict",
        "scope_mixed",
        "wrong_period",
        "wrong_period_type",
        "missing_operand",
        "ambiguous_operand",
        "missing_review",
        "duplicate_review",
        "wrong_raw",
        "wrong_normalized",
        "wrong_selector",
        "reused_selector",
        "wrong_binding",
        "wrong_pdf_hash",
        "missing_basis",
        "duplicate_basis",
        "basis_hash",
        "basis_reuse",
        "review_reuse",
        "unit",
        "scale",
        "currency",
        "missing_unit",
        "missing_scale",
        "missing_currency",
        "currency_unit",
        "numeric_missing",
        "numeric_unresolved",
        "numeric_conflict",
        "quality_insufficient",
        "quality_conflicted",
        "missing_direct_qa",
        "context",
    ],
)
def test_execution_negative_controls(control):
    inputs = fixture()
    metric, f, review = inputs["metrics"][0], inputs["facts"][1], inputs["source_reviews"][1]
    approval = inputs["execution_approval"]
    if control == "missing_approval":
        inputs["execution_approval"] = None
    elif control == "wrong_profile":
        approval.profile = "D-02/document-statement-v1"
    elif control == "wrong_version":
        approval.version = "execution_compatibility_approval_v2"
    elif control == "wrong_purpose":
        approval.purpose = "analytical_preparation"
    elif control == "wrong_authority":
        approval.authority = "reference_example"
    elif control == "cross_document":
        f.document_id = "sha256:" + "d" * 64
    elif control == "cross_snapshot":
        f.snapshot_id = "other"
    elif control == "wrong_statement":
        f.context.statement_type = "B01"
    elif control == "wrong_company":
        f.company_id = "other"
    elif control == "missing_company":
        f.company_id = None
    elif control == "scope_conflict":
        inputs["facts"][0].context.reporting_scope = "separate"
        f.context.reporting_scope = "consolidated"
    elif control == "scope_mixed":
        f.context.reporting_scope = "separate"
    elif control == "wrong_period":
        f.context.period = "2028"
    elif control == "wrong_period_type":
        f.context.period_type = "quarter"
    elif control == "missing_operand":
        inputs["facts"].remove(f)
    elif control == "ambiguous_operand":
        inputs["facts"].append(f.model_copy(deep=True))
    elif control == "missing_review":
        inputs["source_reviews"].remove(review)
    elif control == "duplicate_review":
        inputs["source_reviews"].append(review.model_copy(deep=True))
    elif control == "wrong_raw":
        review.raw_value = "9.999"
    elif control == "wrong_normalized":
        f.value.normalized_value = Decimal("9999")
    elif control == "wrong_selector":
        review.value_selector = "/tables/99/cells/99"
    elif control == "reused_selector":
        review.value_selector = review.label_selector
    elif control == "wrong_binding":
        review.observation = review.observation.model_copy(update={"snapshot_id": "parent"})
    elif control == "wrong_pdf_hash":
        review.pdf_sha256 = "f" * 64
    elif control == "missing_basis":
        inputs["accounting_bases"] = []
    elif control == "duplicate_basis":
        inputs["accounting_bases"].append(inputs["accounting_bases"][0].model_copy(deep=True))
    elif control == "basis_hash":
        inputs["accounting_bases"][0].pdf_sha256 = "e" * 64
    elif control == "basis_reuse":
        inputs["accounting_bases"][0].reused_from_snapshot = "parent"
    elif control == "review_reuse":
        review.reused_from = review.observation.model_copy(update={"snapshot_id": "parent"})
    elif control == "unit":
        f.value.unit = "USD"
    elif control == "scale":
        f.context.scale = Decimal("1000")
    elif control == "currency":
        f.context.currency = "USD"
    elif control == "missing_unit":
        f.value.unit = None
    elif control == "missing_scale":
        f.context.scale = None
    elif control == "missing_currency":
        f.context.currency = None
    elif control == "currency_unit":
        for fact in inputs["facts"]:
            fact.value.unit = "shares"
    elif control == "numeric_missing":
        f.value.normalized_value = None
    elif control == "numeric_unresolved":
        f.value.status = "uncertain"
    elif control == "numeric_conflict":
        f.value.issues.append("conflicting_value")
    elif control.startswith("quality_"):
        f.quality_context[0].decision = control.removeprefix("quality_")
    elif control == "missing_direct_qa":
        f.quality_context[0].task_type = "calculation"
    elif control == "context":
        f.resolution_issues.append(QualityIssue(code="extra_context", detail="unresolved"))
    result = assess(inputs)
    assert not result.calculation_eligible, control
    if control != "missing_approval":
        assert result.readiness["execution_blockers"], control
    # Direct API also fails closed for missing/duplicate roles; no candidate shortcut.
    operands = [
        FinancialOperand(role=o.role, fact=fact)
        for o, fact in zip(metric.operands, inputs["facts"], strict=False)
    ]
    if control not in {"missing_operand", "ambiguous_operand"}:
        direct = assess_execution_compatibility(
            metric.definition.compatibility,
            operands,
            inputs["source_reviews"],
            inputs["accounting_bases"],
            approval=inputs["execution_approval"],
            formula_policy=inputs["formula_policies"][0],
        )
        assert direct.approved_execution_compatibility.status != "compatible"


@pytest.mark.parametrize(
    "control",
    [
        "missing",
        "version",
        "digest",
        "duplicate",
        "duplicate_wrong_digest",
        "purpose",
        "expression",
        "definition_expression",
        "definition_roles",
        "coherent_expression",
        "coherent_roles",
        "guard",
        "relation",
    ],
)
def test_formula_approval_and_definition_controls(control):
    inputs = fixture()
    policy, metric = inputs["formula_policies"][0], inputs["metrics"][0]
    approval = inputs["formula_approvals"][0]
    if control == "missing":
        inputs["formula_approvals"] = []
    elif control == "version":
        approval.version = "other-version"
    elif control == "digest":
        approval.definition_sha256 = "0" * 64
    elif control == "duplicate":
        inputs["formula_approvals"].append(approval.model_copy())
    elif control == "duplicate_wrong_digest":
        inputs["formula_approvals"].append(
            approval.model_copy(update={"definition_sha256": "0" * 64})
        )
    elif control == "purpose":
        approval.purpose = "analytical_preparation"
    elif control == "expression":
        policy.expression = "revenue / gross_profit"
    elif control == "definition_expression":
        metric.definition.expression = "revenue / gross_profit"
    elif control == "definition_roles":
        metric.definition.compatibility.operands[0].role = "revenue"
    elif control == "guard":
        policy.nonnegative_roles = ["gross_profit"]
    elif control == "relation":
        policy.period_relation = "consecutive_fiscal_years_descending"
    elif control in {"coherent_expression", "coherent_roles"}:
        definition = metric.definition.model_copy(deep=True)
        periods = dict(metric.request.operand_periods)
        if control == "coherent_expression":
            definition.expression = "revenue / gross_profit"
        else:
            definition.compatibility.operands[0].role = "net_profit"
            periods["net_profit"] = periods.pop("gross_profit")
        inputs["metrics"] = rebuild_snapshot_metrics(
            [(definition, periods)], inputs["descriptors"][0], inputs["facts"]
        )
        inputs["graph"] = build_graph(inputs["facts"], inputs["evidence"], inputs["metrics"])
    result = assess(inputs)
    assert not result.calculation_eligible
    assert result.readiness["execution_blockers"]


@pytest.mark.parametrize("formula", ["gross_margin", "debt_to_assets", "revenue_yoy"])
def test_numeric_guards_and_period_relations(formula):
    inputs = fixture(formula)
    policy, metric = inputs["formula_policies"][0], inputs["metrics"][0]
    operands = [
        FinancialOperand(role=o.role, fact=f)
        for o, f in zip(metric.operands, inputs["facts"], strict=True)
    ]

    def check():
        return check_metric_formula_policy(
            policy, metric.definition, operands, inputs["formula_approvals"]
        )

    denominator = operands[1].fact
    for invalid in (Decimal("0"), Decimal("-1")):
        denominator.value.normalized_value = invalid
        assert "denominator_non_positive_or_missing" in check()["blockers"]
        assert not assess(inputs).calculation_eligible
    denominator.value.normalized_value = Decimal("1234")
    numerator = operands[0].fact
    numerator.value.normalized_value = Decimal("-1")
    assert ("nonnegative_operand_required" in check()["blockers"]) == (formula != "gross_margin")
    # Review the negative gross-profit token too: valid gross loss can become eligible.
    numerator.value.raw_value = "-1"
    inputs["source_reviews"][0].raw_value = "-1"
    if formula == "gross_margin":
        assert assess(inputs).calculation_eligible
    numerator.context.period = "2027" if formula == "revenue_yoy" else "invalid"
    assert any("period" in b for b in check()["blockers"])
    assert not assess(inputs).calculation_eligible


@pytest.mark.parametrize(
    "damage", ["evidence", "used_in", "associated_with", "from_source", "parent"]
)
def test_snapshot_closure_and_lineage_veto(damage):
    inputs = fixture()
    if damage == "evidence":
        inputs["evidence"] = []
    elif damage == "parent":
        inputs["descriptors"][0].parent_snapshot_id = "missing-parent"
    else:
        inputs["graph"].edges = [e for e in inputs["graph"].edges if e.relation != damage]
    result = assess(inputs)
    assert result.status in {"partial", "blocked"} and not result.calculation_eligible
    assert "snapshot_closure_not_closed" in result.readiness["execution_blockers"]


def test_preparation_and_formula_flags_never_bypass_execution_approval():
    inputs = fixture()
    for fact in inputs["facts"]:
        fact.context.reporting_scope = "separate"
        fact.resolution_issues = []
        for source in fact.sources:
            source.reference.anchor.status = "resolved"
    for review, fact in zip(inputs["source_reviews"], inputs["facts"], strict=True):
        review.sources = [s.model_copy(deep=True) for s in fact.sources]
    metric = inputs["metrics"][0]
    operands = [
        FinancialOperand(role=o.role, fact=f)
        for o, f in zip(metric.operands, inputs["facts"], strict=True)
    ]
    readiness = assess_analytical_readiness(
        metric.definition.compatibility,
        operands,
        inputs["source_reviews"],
        inputs["accounting_bases"],
        approval=inputs["approval"],
        formula_policy=inputs["formula_policies"][0],
        formula_approvals=inputs["formula_approvals"],
    )
    assert readiness["preparation_ready"] and readiness["formula_policy"]["execution_approved"]
    assert readiness["global_compatibility"]["status"] == "compatible"
    assert not readiness["calculation_eligible"]
    inputs["execution_approval"] = None
    assert not assess(inputs).calculation_eligible


def test_direct_duplicate_missing_roles_and_cross_document_rule_fail_closed():
    inputs = fixture()
    spec = inputs["metrics"][0].definition.compatibility
    operands = [
        FinancialOperand(role=o.role, fact=f)
        for o, f in zip(inputs["metrics"][0].operands, inputs["facts"], strict=True)
    ]
    for supplied in (operands[:1], [operands[0], operands[0]]):
        result = assess_execution_compatibility(
            spec,
            supplied,
            inputs["source_reviews"],
            inputs["accounting_bases"],
            approval=inputs["execution_approval"],
            formula_policy=inputs["formula_policies"][0],
        )
        assert result.approved_execution_compatibility.status != "compatible"
    spec.document_relation = "any"
    assert assess_execution_compatibility(
        spec,
        operands,
        inputs["source_reviews"],
        inputs["accounting_bases"],
        approval=inputs["execution_approval"],
        formula_policy=inputs["formula_policies"][0],
    ).execution_blockers


def test_direct_compatibility_requires_formula_period_semantics():
    inputs = fixture()
    metric = inputs["metrics"][0]
    operands = [
        FinancialOperand(role=o.role, fact=f)
        for o, f in zip(metric.operands, inputs["facts"], strict=True)
    ]

    def check(policy):
        return assess_execution_compatibility(
            metric.definition.compatibility,
            operands,
            inputs["source_reviews"],
            inputs["accounting_bases"],
            approval=inputs["execution_approval"],
            formula_policy=policy,
        )

    policy = inputs["formula_policies"][0]
    assert check(policy).approved_execution_compatibility.status == "compatible"
    assert check(None).approved_execution_compatibility.status != "compatible"
    # Exact reviews and both contexts agree, but a quarter is not a fiscal year.
    for fact in inputs["facts"]:
        fact.context.period_type = "quarter"
    result = check(policy)
    assert "formula_period_type_mismatch" in result.execution_blockers
    assert result.approved_execution_compatibility.status != "compatible"


def test_production_registry_has_three_exact_versioned_approvals():
    config = registry()
    assert config["version"] == "M4/execution-registry-v1"
    ExecutionCompatibilityApproval(**config["execution_approval"])
    policies = [PreparedFormulaPolicy(**p) for p in config["formula_policies"]]
    approvals = [FormulaExecutionApproval(**a) for a in config["formula_execution_approvals"]]
    assert len(policies) == len(approvals) == 3
    assert {p.formula_id for p in policies} == {"gross_margin", "debt_to_assets", "revenue_yoy"}
    for policy in policies:
        selected = [a for a in approvals if a.formula_id == policy.formula_id]
        assert len(selected) == 1
        assert selected[0].version == policy.version == "M4/formula-execution-v1"
        assert selected[0].definition_sha256 == policy.definition_digest()
        assert selected[0].decision_reference == "M4-01/design-decision/2026-11-02"
        assert selected[0].negative_controls_reference.endswith("#negative-controls")
