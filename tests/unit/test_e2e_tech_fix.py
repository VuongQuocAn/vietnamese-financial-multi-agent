"""Three offline technical controls; synthetic data does not measure QA accuracy."""

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.agents.evidence_coordination import (
    parse_retrieval_batches,
    propose,
)
from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationWorkspace
from vietnamese_financial_multi_agent.agents.specialist_common import _fact_error
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway
from vietnamese_financial_multi_agent.evidence.document_claim_support import document_projection
from vietnamese_financial_multi_agent.evidence.json_catalog import json_fact_bound
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)

from .test_financial_qa import gateway_for
from .test_json_source_readiness import catalog_fixture
from .test_v2_integration import setup_engine


def test_nested_graph_option_preserves_tool_choice_and_strict_validation():
    # Shape observed in saved SH-0013: no semantic repair or unknown-field drop.
    payload = dict(
        document_search=dict(query="Mục hợp đồng", kind="exact_text", goal_id="G1", use_graph=True),
        retrieve=[dict(source=f"S{i}") for i in range(8)],
    )
    original = deepcopy(payload)
    batches = parse_retrieval_batches(payload)
    assert [len(b.retrieve) for b in batches] == [6, 2]
    assert all(b.use_graph and b.document_search.query == "Mục hợp đồng" for b in batches)
    assert [d.source for b in batches for d in b.retrieve] == [f"S{i}" for i in range(8)]
    assert payload == original  # Keep raw provider trace verbatim.
    assert parse_retrieval_batches(payload | {"use_graph": True})[0].use_graph
    for invalid in (
        payload | {"use_graph": False},
        payload | {"document_search": payload["document_search"] | {"use_graph": "true"}},
        payload | {"document_search": payload["document_search"] | {"approved": True}},
    ):
        with pytest.raises(ValueError):
            parse_retrieval_batches(invalid)


def test_demand_thinking_budget_is_stage_bounded_within_24k(monkeypatch):
    _, context, engine, requirements = setup_engine()
    task = engine.supervisor.plan.return_value[0].tasks[0]
    workspace = IntegrationWorkspace(requirements)
    workspace.tasks[task.task_id] = {}
    context.model = ModelIdentity(provider="qwen", model="test-model")
    monkeypatch.setenv("QWEN_THINKING_BUDGET", "true")
    for size in (20, 42000):
        seen = []
        synthetic = gateway_for({"use_graph": False}, seen)
        # Reuse existing offline transport under the requested provider identity.
        gateway = SimpleNamespace(generate=synthetic._transports["gemini"])
        bounded = RequestGateway(gateway, max_calls=1, timeout_seconds=600)
        sources = {"S1": dict(kind="fact", item="item", label="x" * size, period="2030")}
        proposal, _ = propose(bounded, context, task, workspace, sources)
        assert not proposal.use_graph and len(seen) == 1
        bound = seen[0]
        cap = bound.generation.max_output_tokens
        chars = sum(len(m.content) for m in bound.messages)
        assert 0 < cap <= 2500
        assert (chars + 1) // 2 + cap + 1024 <= 24576
        assert cap == 2500 if size == 20 else cap < 2500
        assert json.loads(bound.messages[0].content)["inventory"]["S1"]["label"] == "x" * size


def test_found_json_fact_and_table_bindings_keep_source_contracts(tmp_path):
    catalog = catalog_fixture(tmp_path)
    table = next(e for e in catalog.evidence if e.kind == "table" and e.structure.cells)
    # Refined JSON imports UnderstoodCell.col, while extraction/unified use column.
    labels = [cell.text for cell in table.structure.cells if cell.col == 0 and cell.text]
    assert document_projection(table) == {"labels": labels}
    legacy = SimpleNamespace(
        kind="table",
        structure=SimpleNamespace(
            cells=[
                SimpleNamespace(row=0, column=0, text="Original label"),
                SimpleNamespace(row=0, column=1, text="123"),
            ]
        ),
    )
    assert document_projection(legacy) == {"labels": ["Original label"]}
    fact = next(f for f in catalog.facts if f.value.unit and json_fact_bound(catalog, f))

    def retrieve():
        return FinancialRetrievalTools(catalog).get_financial_fact(
            GetFinancialFactRequest(
                document_id=fact.document_id,
                snapshot_id=fact.snapshot_id,
                local_observation_id=fact.local_observation_id,
            )
        )

    good = retrieve()
    assert good.status == "found" and good.matches[0].json_source_bound
    bundle = SimpleNamespace(citations=good.matches[0].citations)
    assert _fact_error(good.matches[0], bundle) is None
    # A freshly pinned import with missing unit remains found, never eligible.
    fact.value.unit = fact.context.currency = fact.context.scale = None
    catalog.json_fact_pins[fact.observation_identity().model_dump_json()] = hashlib.sha256(
        fact.model_dump_json().encode()
    ).hexdigest()
    missing = retrieve()
    assert missing.status == "found" and not missing.matches[0].json_source_bound
    assert _fact_error(missing.matches[0], bundle) == "json_fact_unbound_or_ineligible"
