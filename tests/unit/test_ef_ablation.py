"""Targeted evaluator controls; these are not financial-quality evidence."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "ef_ablation_runner", SCRIPTS / "evaluate_ef_ablation.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
audit_spec = importlib.util.spec_from_file_location(
    "ef_ablation_audit", SCRIPTS / "summarize_ef_ablation.py"
)
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)


def test_usage_does_not_treat_unknown_provider_usage_as_observed_zero():
    events = [
        {
            "response": {"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
            "status": "success",
        },
        {
            "response": {
                "usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None}
            },
            "status": "failure",
        },
    ]
    result = runner.summarize_usage(events)
    assert result["total_tokens"] == 15
    assert result["unknown_usage_calls"] == result["failed_calls"] == 1
    assert result["logical_calls"] == 2


def test_oracle_preserves_opening_balance_period_and_computes_independently():
    facts = []
    for key, amounts in [
        ("b02.net_revenue", [100, 120]),
        ("b02.gross_profit", [20, 18]),
        ("b01.total_assets", [200, 240]),
        ("b01.total_liabilities", [100, 120]),
    ]:
        for index, amount in enumerate(amounts):
            period = (
                ["2024", "2025"][index]
                if key.startswith("b02")
                else ["2025-01-01", "2025-12-31"][index]
            )
            fact = {
                "canonical_item_id": key,
                "context": {"period": period},
                "value": {"normalized_value": str(amount)},
            }
            facts.append(SimpleNamespace(model_dump=lambda mode, fact=fact: fact))
    oracle = runner.source_oracle(SimpleNamespace(catalog=SimpleNamespace(facts=facts)))
    assert oracle["facts"]["assets24"]["context"]["period"] == "2025-01-01"
    assert float(oracle["values"]["growth"]) == 20
    assert float(oracle["values"]["gross_growth"]) == -10
    assert float(oracle["values"]["debt_ratio"]) == 50


def test_pipeline_exception_is_technical_and_citations_bind_to_source_snapshot_page():
    source = {
        "document_id": "doc",
        "snapshot_id": "snap",
        "reference": {"anchor": {"page": {"page": 7}}},
    }
    oracle = {
        "facts": {
            "revenue25": {
                "document_id": "doc",
                "snapshot_id": "snap",
                "local_observation_id": "f1",
                "sources": [source],
            }
        }
    }
    row = dict(
        run_id="A1-r1-off",
        case="A1",
        graph=False,
        repetition=1,
        question="question",
        requirements=["page7"],
        usage={"failed_calls": 0},
        provider_attempts=[],
        timings={},
        comparison_latency_ms=1,
        events=[],
        response={"citations": [{"document_id": "doc", "snapshot_id": "snap", "pdf_page": 7}]},
        m5=[
            {
                "errors": [{"code": "specialist_execution_failed"}],
                "candidates": [],
                "specialist_executions": [],
                "supervisor_result": {
                    "tool_trace": [
                        {
                            "operation": "get_graph_context",
                            "response": {
                                "edges": [{"edge": {"edge_id": "edge1", "relation": "from_source"}}]
                            },
                        }
                    ],
                    "evidence_bundle": {"facts": [], "graph_contexts": []},
                },
            }
        ],
    )
    result = audit.inspect(row, oracle)
    assert result["technical_affected"]
    assert result["graph_calls"] == 1 and result["relations"] == {"from_source": 1}
    assert result["citation_binding_mismatches"] == 0
    row["response"]["citations"][0]["snapshot_id"] = "different"
    assert audit.inspect(row, oracle)["citation_binding_mismatches"] == 1
