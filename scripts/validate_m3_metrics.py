"""M3-05 readiness trên hai attempts đã persist; không extraction/LLM/calculation."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    DerivedMetric,
    EvidenceGraph,
    FormulaDefinition,
    MetricRequest,
    OperandRequirement,
    OperationCompatibilitySpec,
    PeriodPair,
    build_graph,
    build_metric,
    facts_from_persisted_result,
    validate_graph,
)


def examples():
    # Scope cố định trước khi đọc kết quả. Reference examples, chưa executable policy.
    cases = [
        (
            "gross_margin",
            "gross_profit / revenue",
            "B02",
            [
                ("gross_profit", "b02.gross_profit", "gross_profit", "2025"),
                ("revenue", "b02.net_revenue", "revenue", "2025"),
            ],
        ),
        (
            "debt_to_assets",
            "liabilities / assets",
            "B01",
            [
                ("liabilities", "b01.total_liabilities", "liabilities", "2025-12-31"),
                ("assets", "b01.total_assets", "assets", "2025-12-31"),
            ],
        ),
        (
            "revenue_yoy",
            "(current_revenue - prior_revenue) / prior_revenue",
            "B02",
            [
                ("current_revenue", "b02.net_revenue", "revenue", "2025"),
                ("prior_revenue", "b02.net_revenue", "revenue", "2024"),
            ],
        ),
    ]
    for name, expression, statement, operands in cases:
        spec = OperationCompatibilitySpec(
            operation_id=name,
            rule_reference="M3-05/reference-examples/v1",
            operands=[
                OperandRequirement(
                    role=r, canonical_item_id=i, semantic_role=s, statement_type=statement
                )
                for r, i, s, _ in operands
            ],
            period_relation="ordered_pair" if name == "revenue_yoy" else "same",
            period_pairs=[PeriodPair(left="2025", right="2024", period_type="fiscal_year")]
            if name == "revenue_yoy"
            else [],
            document_relation="same",
        )
        yield (
            FormulaDefinition(
                formula_reference=f"M3-05/reference/{name}",
                formula_version="1",
                name=name,
                expression=expression,
                compatibility=spec,
            ),
            {r: p for r, _, _, p in operands},
        )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    definitions = list(examples())
    baseline = json.loads(
        (root / "artifacts/evidence/M3-03-real-validation/final/validation.json").read_text(
            encoding="utf-8"
        )
    )
    hashes = {p: digest(root / p) for p in baseline["hashes"]}
    all_facts, metrics, rows, audits = [], [], [], []
    for family in ("storage", "fresh-storage"):
        storage = root / "artifacts/w07" / family
        paths = sorted(storage.rglob("result.json"))
        assert len(paths) == 1, "Scope changed: expected exactly one persisted W-07 attempt"
        path = paths[0]
        raw = json.loads(path.read_text(encoding="utf-8"))
        documents = [
            p
            for p in storage.rglob("document.json")
            if json.loads(p.read_text(encoding="utf-8"))["id"] == raw["document_id"]
        ]
        assert len(documents) == 1
        docpath = documents[0]
        doc = json.loads(docpath.read_text(encoding="utf-8"))
        for p in (path, docpath):
            hashes[p.relative_to(root).as_posix()] = digest(p)
        metadata = doc["metadata"]
        audit = dict(
            attempt=family,
            origin=docpath.relative_to(root).as_posix(),
            snapshot_revision=raw["metadata_revision"],
            current_revision=doc["metadata_revision"],
            accepted=metadata["accepted"],
            confirmed=metadata["confirmed"],
            acceptance_origin=metadata["acceptance_origin"],
            acceptance_history=metadata["acceptance_history"],
            snapshot_matches_current_values=raw["metadata"] == metadata["values"],
            field_origins=metadata["suggestions"],
            field_statuses={k: v["status"] for k, v in metadata["suggestions"].items()},
            snapshot_fields_present=[k for k, v in raw["metadata"].items() if v is not None],
            bound_fields=[],
            unavailable=["company_id", "reporting_scope", "semantic_role"],
            reason="Accepted company_name is not company_id; no identity policy. Scope absent; "
            "document-level main period cannot assign operand semantic roles/comparative periods.",
            runtime_identity_used=False,
        )
        audits.append(audit)
        facts = facts_from_persisted_result(raw)
        original = [f.model_dump_json() for f in facts]
        all_facts.extend(facts)
        for definition, periods in definitions:
            request = MetricRequest(
                document_id=raw["document_id"],
                snapshot_id=raw["attempt_id"],
                operand_periods=periods,
            )
            metric = build_metric(definition, request, facts)
            metrics.append(metric)
            rows.append(
                dict(
                    attempt=family,
                    metric=definition.name,
                    metric_id=metric.metric_id,
                    candidates={o.role: o.candidate_count for o in metric.operands},
                    bound=[o.role for o in metric.operands if o.status == "bound"],
                    missing=[o.role for o in metric.operands if o.status == "missing"],
                    ambiguous=[o.role for o in metric.operands if o.status == "ambiguous"],
                    structural=metric.structural_readiness,
                    binding=metric.binding_status,
                    compatibility=metric.compatibility.status,
                    reasons=dict(Counter(r.code for r in metric.compatibility.reasons)),
                    usability=[u.model_dump(mode="json") for u in metric.evidence_usability],
                    blockers=metric.preparation_blockers,
                    executable_now=False,
                    eventual_m4="Conditional: approved formula/period policy, complete unambiguous "
                    "canonical mappings, source-backed company identity/scope/roles, "
                    "resolved context/provenance and task-specific quality review required.",
                    before_binding=metric.compatibility.status,
                    after_binding=metric.compatibility.status,
                    canonical_candidates_by_period={
                        req.role: dict(
                            Counter(
                                f.context.period
                                for f in facts
                                if f.canonical_item_id == req.canonical_item_id
                            )
                        )
                        for req in definition.compatibility.operands
                    },
                    unmapped_b01_code300=sum(
                        f.context.statement_type == "B01"
                        and f.source_item_code == "300"
                        and f.canonical_item_id is None
                        for f in facts
                    ),
                )
            )
        assert original == [f.model_dump_json() for f in facts]
    graph = build_graph(all_facts, metrics=metrics)
    assessments = validate_graph(graph, all_facts, metrics=metrics)
    assert all(a.status == "valid" for a in assessments.nodes + assessments.edges)
    atomic_json(output / "metrics.json", [m.model_dump(mode="json") for m in metrics])
    atomic_json(output / "graph.json", graph.model_dump(mode="json"))
    atomic_json(output / "graph-assessments.json", assessments.model_dump(mode="json"))
    restarted = TypeAdapter(list[DerivedMetric]).validate_json(
        (output / "metrics.json").read_text()
    )
    assert restarted == metrics
    assert EvidenceGraph.model_validate_json((output / "graph.json").read_text()) == graph
    assert all(digest(root / p) == h for p, h in hashes.items())
    summary = dict(
        facts=len(all_facts),
        metrics=len(metrics),
        rows=rows,
        metadata_audit=audits,
        used_in_edges=sum(e.relation == "used_in" for e in graph.edges),
        structural_nodes=dict(Counter(a.status for a in assessments.nodes)),
        structural_edges=dict(Counter(a.status for a in assessments.edges)),
        source_hashes=hashes,
        unchanged_source_files=len(hashes),
        restart_exact=True,
        calculation_executed=False,
        metadata_bindings_applied=0,
    )
    atomic_json(output / "readiness.json", summary)
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in {"rows", "metadata_audit", "source_hashes"}
            }
        )
    )
    for row in rows:
        print(
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "attempt",
                        "metric",
                        "candidates",
                        "bound",
                        "missing",
                        "structural",
                        "compatibility",
                        "reasons",
                        "canonical_candidates_by_period",
                        "unmapped_b01_code300",
                    )
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(Path.cwd(), args.output)
