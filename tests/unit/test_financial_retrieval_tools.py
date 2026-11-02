"""M4-02 synthetic controls; không chứng minh financial accuracy của BBS."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    SnapshotCatalog,
    build_graph,
    build_metric,
)
from vietnamese_financial_multi_agent.tools import (
    FinancialRetrievalTools,
    FinancialToolResponse,
    FindFinancialFactsRequest,
    GetFinancialFactRequest,
    GetFinancialMetricRequest,
    ListFinancialMetricsRequest,
)

from .test_m4_execution import fixture
from .test_reporting_scope import fixture as scope_fixture


def exact(fact):
    return GetFinancialFactRequest(
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        local_observation_id=fact.local_observation_id,
    )


def query(fact, **changes):
    fields = dict(
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        company_id=fact.company_id,
        canonical_item_id=fact.canonical_item_id,
        statement_type=fact.context.statement_type,
        period=fact.context.period,
        period_type=fact.context.period_type,
        source_page=fact.sources[0].reference.anchor.page.page,
    )
    return FindFinancialFactsRequest(**(fields | changes))


@pytest.mark.parametrize("document", [0, 1])
def test_exact_and_semantic_decimal_restart_and_isolated_outputs(document, tmp_path):
    data = fixture(document=document)
    fact = data["facts"][0]
    fact.value.normalized_value = Decimal("12345678901234567890.00100")
    fact.context.scale = Decimal("1000000.00")
    fact.value.unit, fact.context.currency = "triệu đồng", "VND"
    data["source_reviews"] = []
    # Exact fact queries không cần execution eligibility; giữ nguyên annotation.
    catalog = SnapshotCatalog(**data)
    tools = FinancialRetrievalTools(catalog)
    expected = tools.get_financial_fact(exact(fact))
    assert expected.status == "found" and expected.matches[0].record == fact
    assert expected.matches[0].citations[0].source == fact.sources[0]
    assert not expected.financial_fact_verified
    assert tools.find_financial_facts(query(fact)).matches == expected.matches
    wire = expected.model_dump_json()
    raw = json.loads(wire)["matches"][0]["record"]
    assert raw["value"]["normalized_value"] == "12345678901234567890.00100"
    assert raw["context"]["scale"] == "1000000.00" and raw["value"]["unit"] == "triệu đồng"
    assert FinancialToolResponse.model_validate_json(wire) == expected
    repository = CanonicalFactRepository(tmp_path / "facts")
    for record in data["facts"]:
        repository.put(record)
    data["facts"] = CanonicalFactRepository(repository.root).list_by_document(fact.document_id)
    restarted = FinancialRetrievalTools(SnapshotCatalog(**data))
    assert restarted.get_financial_fact(exact(fact)) == expected
    expected.matches[0].record.value.normalized_value = Decimal("0")
    expected.matches[0].source_review.matches.clear()
    expected.snapshot_candidates.clear()
    catalog.facts.clear()
    assert tools.get_financial_fact(exact(fact)).model_dump_json() == wire


def test_ambiguity_conflict_coverage_and_period():
    data = fixture()
    fact = data["facts"][0]
    duplicate = fact.model_copy(deep=True)
    duplicate.local_observation_id = "another-observation"
    data["facts"].append(duplicate)
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    result = tools.find_financial_facts(query(fact))
    assert result.status == "ambiguous" and len(result.matches) == 2
    duplicate.local_observation_id = fact.local_observation_id
    duplicate.value.normalized_value = Decimal("999")
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    result = tools.get_financial_fact(exact(fact))
    assert result.status == "conflicted" and len(result.matches) == 2
    coverage = CanonicalCoverage(
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        canonical_extraction="available",
        missing_canonical_items=["unmapped.item"],
        inventory_reference="synthetic/inventory",
    )
    tools = FinancialRetrievalTools(SnapshotCatalog(**fixture()), coverage=[coverage])
    missing = tools.find_financial_facts(query(fact, canonical_item_id="unmapped.item"))
    assert missing.status == "unavailable" and missing.reasons == ["canonical_mapping_missing"]
    assert missing.inventory_references == ["synthetic/inventory"]
    period = tools.find_financial_facts(query(fact, period="1900"))
    assert period.status == "not_found" and period.reasons == ["missing_period"]
    coverage.canonical_extraction = "missing"
    no_extraction = FinancialRetrievalTools(SnapshotCatalog(**fixture()), coverage=[coverage])
    assert (
        "canonical_extraction_missing"
        in no_extraction.find_financial_facts(query(fact, canonical_item_id="absent")).reasons
    )


def test_no_latest_no_parent_fallback_and_wrong_scope():
    data = fixture()
    fact = data["facts"][0]
    parent = data["descriptors"][0]
    child = parent.model_copy(
        update={
            "snapshot_id": "zzz-recovery",
            "parent_snapshot_id": parent.snapshot_id,
            "origin": "recovery",
        },
        deep=True,
    )
    data["descriptors"].append(child)
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    for response in (
        tools.find_financial_facts(query(fact, snapshot_id=None)),
        tools.list_financial_metrics(ListFinancialMetricsRequest(document_id=fact.document_id)),
    ):
        assert response.status == "ambiguous" and not response.matches
        assert len(response.snapshot_candidates) == 2
    assert (
        tools.find_financial_facts(query(fact, snapshot_id=child.snapshot_id)).status == "not_found"
    )
    assert tools.get_financial_fact(exact(fact)).status == "found"
    for fields in ({"document_id": "wrong"}, {"snapshot_id": "wrong"}):
        response = tools.get_financial_fact(exact(fact).model_copy(update=fields))
        assert response.status == "not_found" and not response.matches
        assert not response.snapshot_candidates and not response.reporting_scopes
        response = tools.get_financial_metric(
            GetFinancialMetricRequest(metric_id=data["metrics"][0].metric_id, **fields)
        )
        assert response.status == "not_found" and not response.matches
        assert not response.snapshot_candidates and not response.reporting_scopes


@pytest.mark.parametrize("document", [0, 1])
def test_scope_overlay_and_unknown_never_inherited(document):
    data = fixture(document=document)
    fact = data["facts"][0]
    _, descriptor, _, reviews = scope_fixture(document)
    for review in reviews:
        review.snapshot_id = fact.snapshot_id
        for source in review.sources:
            source.snapshot_id = fact.snapshot_id
    assert descriptor.document_id == fact.document_id
    original = fact.model_dump_json()
    data["reporting_scope_reviews"] = reviews
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    scope = ("separate", "consolidated")[document]
    result = tools.find_financial_facts(query(fact, reporting_scope=scope))
    assert result.status == "found" and result.matches[0].reporting_scope.reporting_scope == scope
    assert result.matches[0].record.context.reporting_scope is None
    assert result.matches[0].record.model_dump_json() == original
    wrong = tools.find_financial_facts(
        query(fact, reporting_scope=("consolidated", "separate")[document])
    )
    assert wrong.status == "not_found" and not wrong.matches
    data["reporting_scope_reviews"] = []
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    unknown = tools.find_financial_facts(query(fact, reporting_scope=scope))
    assert unknown.status == "unavailable" and unknown.reasons == ["reporting_scope_unresolved"]
    assert not unknown.matches
    unrestricted = tools.find_financial_facts(query(fact))
    assert unrestricted.status == "found" and "reporting_scope_unresolved" in unrestricted.caveats
    # Exact snapshot with no review cannot reuse parent's review.
    parent = data["descriptors"][0]
    child = parent.model_copy(
        update={
            "snapshot_id": "child",
            "parent_snapshot_id": parent.snapshot_id,
            "origin": "recovery",
        }
    )
    data["descriptors"].append(child)
    data["reporting_scope_reviews"] = reviews
    result = FinancialRetrievalTools(SnapshotCatalog(**data)).find_financial_facts(
        query(fact, snapshot_id="child", reporting_scope=scope)
    )
    assert result.status == "unavailable" and "reporting_scope_unresolved" in result.reasons


@pytest.mark.parametrize("control", ["insufficient", "conflicted", "null"])
def test_quality_and_null_not_promoted(control):
    data = fixture()
    fact = data["facts"][0]
    if control == "null":
        fact.value.normalized_value = None
        data["source_reviews"] = []
    else:
        for quality in fact.quality_context:
            quality.decision = control
    result = FinancialRetrievalTools(SnapshotCatalog(**data)).get_financial_fact(exact(fact))
    assert result.matches[0].display_status == "blocked"
    assert result.matches[0].record == fact
    assert result.status == ("conflicted" if control == "conflicted" else "found")
    if control == "null":
        assert result.matches[0].record.value.normalized_value is None


@pytest.mark.parametrize("formula", ["gross_margin", "debt_to_assets", "revenue_yoy"])
@pytest.mark.parametrize("document", [0, 1])
def test_metric_production_readiness_operands_list_and_restart(formula, document):
    data = fixture(formula=formula, document=document)
    catalog = SnapshotCatalog(**data)
    tools = FinancialRetrievalTools(catalog)
    metric = data["metrics"][0]
    request = GetFinancialMetricRequest(metric_id=metric.metric_id)
    response = tools.get_financial_metric(request)
    assert response.status == "found"
    match = response.matches[0]
    assert match.record == metric and match.record.result_status == "not_computed"
    assert match.record.result is None and match.closure.calculation_eligible
    assert match.closure == catalog.assess_metric(data["descriptors"][0], metric)
    assert match.closure.readiness["global_compatibility"]["status"] == "undetermined"
    assert match.closure.readiness["approved_execution_compatibility"]["status"] == "compatible"
    assert not match.closure.readiness["execution_blockers"]
    assert match.reviewed_lineage.lineage.completeness == "complete" and match.citations
    for operand, binding, fact in zip(match.operands, metric.operands, data["facts"], strict=True):
        assert operand.binding == binding
        assert operand.facts.matches[0].record == fact
        assert operand.source_review.matches[0].status == "value_row_verified"
        assert binding.source_fact_node_id
    assert match.accounting_bases == data["accounting_bases"]
    assert FinancialToolResponse.model_validate_json(response.model_dump_json()) == response
    restarted = deepcopy(data)
    for key in ("facts", "metrics", "source_reviews", "accounting_bases", "descriptors"):
        restarted[key] = [type(v).model_validate_json(v.model_dump_json()) for v in restarted[key]]
    assert (
        FinancialRetrievalTools(SnapshotCatalog(**restarted)).get_financial_metric(request)
        == response
    )
    listed = tools.list_financial_metrics(
        ListFinancialMetricsRequest(
            **metric.request.model_dump(exclude={"operand_periods"}), formula_id=formula
        )
    )
    assert listed.status == "found" and listed.matches == response.matches
    assert (
        tools.list_financial_metrics(
            ListFinancialMetricsRequest(
                document_id=metric.request.document_id, formula_id="missing"
            )
        ).status
        == "not_found"
    )
    assert (
        tools.get_financial_metric(GetFinancialMetricRequest(metric_id="missing")).status
        == "not_found"
    )
    match.closure.calculation_eligible = False
    match.operands[0].facts.matches[0].record.value.raw_value = "mutated"
    assert tools.get_financial_metric(request).matches[0].closure.calculation_eligible
    assert data == restarted


@pytest.mark.parametrize(
    "control", ["graph", "used_in", "fact", "review", "approval", "formula_approval"]
)
def test_metric_missing_lineage_and_gates_never_execution_ready(control):
    data = fixture()
    if control == "graph":
        data["graph"] = None
    elif control == "used_in":
        data["graph"].edges = [e for e in data["graph"].edges if e.relation != "used_in"]
    elif control == "fact":
        data["facts"].pop()
    elif control == "review":
        data["source_reviews"].clear()
    elif control == "approval":
        data["execution_approval"] = None
    else:
        data["formula_approvals"].clear()
    catalog = SnapshotCatalog(**data)
    response = FinancialRetrievalTools(catalog).get_financial_metric(
        GetFinancialMetricRequest(metric_id=data["metrics"][0].metric_id)
    )
    match = response.matches[0]
    assert response.status == "found" and not match.closure.calculation_eligible
    assert match.closure == catalog.assess_metric(data["descriptors"][0], data["metrics"][0])
    if control in {"graph", "used_in"}:
        assert match.reviewed_lineage.status == "unavailable"
        assert match.closure.issues
    assert match.record.result is None


def test_two_documents_and_multiple_list_results_deterministic():
    first, second = fixture(), fixture(document=1)
    metric = first["metrics"][0]
    first["metrics"].append(
        build_metric(
            metric.definition.model_copy(update={"formula_version": "another-version"}),
            metric.request,
            first["facts"],
        )
    )
    data = deepcopy(first)
    for key in (
        "descriptors",
        "facts",
        "evidence",
        "metrics",
        "source_reviews",
        "accounting_bases",
    ):
        data[key].extend(second[key])
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    tools = FinancialRetrievalTools(SnapshotCatalog(**data))
    listed = tools.list_financial_metrics(
        ListFinancialMetricsRequest(
            document_id=metric.request.document_id, formula_id="gross_margin"
        )
    )
    assert listed.status == "found" and len(listed.matches) == 2
    result = tools.find_financial_facts(
        FindFinancialFactsRequest(canonical_item_id=first["facts"][0].canonical_item_id)
    )
    assert result.status == "ambiguous" and len(result.matches) == 2
    for group in (first, second):
        assert (
            tools.get_financial_fact(exact(group["facts"][0])).matches[0].record
            == group["facts"][0]
        )
    for key in (
        "descriptors",
        "facts",
        "evidence",
        "metrics",
        "source_reviews",
        "accounting_bases",
    ):
        data[key].reverse()
    reordered = FinancialRetrievalTools(SnapshotCatalog(**data))
    assert (
        reordered.find_financial_facts(result.request).model_dump_json() == result.model_dump_json()
    )
    selected = reordered.find_financial_facts(
        FindFinancialFactsRequest(
            snapshot_id=first["descriptors"][0].snapshot_id,
            canonical_item_id=first["facts"][0].canonical_item_id,
        )
    )
    assert selected.status == "found" and selected.matches[0].record == first["facts"][0]
