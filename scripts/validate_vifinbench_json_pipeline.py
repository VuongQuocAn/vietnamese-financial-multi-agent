"""Offline refined import -> persisted JSON catalog -> Financial Tools/M5; no API."""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from time import perf_counter

from import_vifinbench_refined import PILOT_DOCUMENTS, check_fidelity
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    DOMAINS,
    FinancialLiteOrchestrator,
    SupervisorLite,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.graph import build_graph, validate_graph
from vietnamese_financial_multi_agent.evidence.json_catalog import (
    json_fact_bound,
    load_json_catalog,
)
from vietnamese_financial_multi_agent.evidence.refined_import import (
    import_refined_document,
    read_refined,
)
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceQuery, RetrievalReference
from vietnamese_financial_multi_agent.tools.financial_calculator import (
    DynamicOperation,
    FinancialCalculator,
)
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)


class OfflineGraphSupervisor(SupervisorLite):
    """Existing lexical plan with explicit graph use for this offline smoke."""

    def plan(self, question, context, sources):
        plan, metadata, gaps = super().plan(question, context, sources)
        for task in plan.tasks:
            task.use_graph = True
        return plan, metadata, gaps


def discover_documents(root):
    """Inventory page JSON only, without reading benchmark/Gold or PDF files."""
    documents = {}
    for path in sorted(root.glob("*/*/page_*.json")):
        alias = f"{path.parent.parent.name}_{path.parent.name}"
        if not re.fullmatch(r"[A-Z0-9]+_20\d{2}", alias):
            raise ValueError("invalid_refined_directory")
        documents[alias] = documents.get(alias, 0) + 1
    if not documents:
        raise ValueError("no_refined_documents")
    return documents


def context_coverage(catalog, eligible):
    """Counts overlap: an excluded observation may lack several requirements."""
    facts = catalog.facts
    excluded = [f for f in facts if f not in eligible]
    requirements = {
        "company_missing": lambda f: not f.company_id,
        "mapping_missing": lambda f: not f.canonical_item_id,
        "period_missing": lambda f: not (f.context.period and f.context.period_type),
        "unit_missing": lambda f: not (f.value.unit and f.context.currency and f.context.scale),
        "value_unresolved": lambda f: f.value.status != "resolved",
        "quality_blocked": lambda f: (
            not f.quality_context
            or any(q.decision not in {"usable", "usable_with_caveat"} for q in f.quality_context)
        ),
    }
    return dict(
        company_bound_facts=sum(bool(f.company_id) for f in facts),
        periods=dict(sorted(Counter(f.context.period or "unresolved" for f in facts).items())),
        units=dict(
            sorted(
                Counter(
                    f"{f.value.unit or 'unresolved'}@{f.context.scale or 'unresolved'}"
                    for f in facts
                ).items()
            )
        ),
        mapped_items=dict(
            sorted(Counter(f.canonical_item_id for f in facts if f.canonical_item_id).items())
        ),
        mapped_with_period=sum(bool(f.context.period) for f in facts if f.canonical_item_id),
        mapped_with_unit=sum(bool(f.value.unit) for f in facts if f.canonical_item_id),
        excluded_facts=len(excluded),
        exclusion_counts={k: sum(test(f) for f in excluded) for k, test in requirements.items()},
        mapped_exclusion_counts={
            k: sum(test(f) for f in excluded if f.canonical_item_id)
            for k, test in requirements.items()
        },
    )


def smoke_question(fact):
    # This is a plumbing smoke, not an evaluation of source-label paraphrases.
    label = next(
        (
            module.ITEM_LABELS[fact.canonical_item_id]
            for module, _ in DOMAINS.values()
            if fact.canonical_item_id in module.ITEM_LABELS
        ),
        fact.context.raw_item_label,
    )
    period = fact.context.period
    return f"{label} năm {period[:4]} là bao nhiêu?" if period else f"{label} là bao nhiêu?"


def compatible_pair(numerator, denominator):
    return (
        numerator.context.period == denominator.context.period
        and numerator.context.currency == denominator.context.currency
        and numerator.value.unit == denominator.value.unit
        and numerator.context.scale == denominator.context.scale
        and denominator.value.normalized_value != 0
    )


def write_coverage(output, summaries):
    fields = [
        "document_alias",
        "pages",
        "text_records",
        "table_records",
        "facts",
        "numeric_values",
        "mapped_facts",
        "facts_with_period",
        "facts_with_unit",
        "eligible_mapped_facts",
        "financial_lookups",
        "m5_status",
        "m5_candidates",
        "graph_nodes",
        "graph_edges",
    ]
    with (output / "coverage.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    lines.extend("| " + " | ".join(str(s[f]) for f in fields) + " |" for s in summaries)
    (output / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate(root, output, documents=PILOT_DOCUMENTS, *, projection_version=None):
    root, output = root.resolve(), output.resolve()
    if output == root or root in output.parents or output in root.parents:
        raise ValueError("source_output_overlap")
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    inventory = {alias: read_refined(root, alias, projection_version)[1] for alias in documents}
    atomic_json(output / "source-inventory.json", inventory)
    for alias in inventory:
        started = perf_counter()
        print(json.dumps(dict(document_alias=alias, stage="import_started")), flush=True)
        manifest, facts, evidence, summary = import_refined_document(
            root, alias, projection_version=projection_version
        )
        assert manifest == inventory[alias], "source_changed_during_import"
        target = output / alias
        target.mkdir()
        graph = build_graph(facts, evidence)
        validation = validate_graph(graph, facts, evidence)
        assert all(
            a.status == "valid" for a in [*validation.nodes, *validation.edges, *validation.inputs]
        )
        assert not validation.orphan_nodes
        for name, payload in {
            "manifest.json": manifest,
            "canonical-facts.json": dict(
                version="canonical_facts_v1",
                observations=[f.model_dump(mode="json") for f in facts],
                quarantine=[],
            ),
            "document-evidence.json": dict(
                version="document_evidence_v1",
                records=[e.model_dump(mode="json") for e in evidence],
                quarantine=[],
            ),
            "graph.json": graph.model_dump(mode="json"),
            "graph-validation.json": validation.model_dump(mode="json"),
        }.items():
            atomic_json(target / name, payload)
        catalog = load_json_catalog(root, target).request_snapshot()
        assert catalog.facts == facts and catalog.evidence == evidence
        assert catalog.select(manifest["document_id"], manifest["snapshot_id"]).status == "selected"
        retrieval = {}
        for kind in ("text", "table"):
            record = next((e for e in catalog.evidence if e.kind == kind), None)
            if record is None:
                retrieval[kind] = "not_available_in_source"
                continue
            result = catalog.api.get_evidence(record.evidence_identity())
            assert result.status == "found" and result.matches[0].record == record
            assert all(
                c.pdf_page is None and "json_source_not_pdf_verified" in c.limitations
                for c in result.matches[0].citations
            )
            retrieval[kind] = result.status
        assert (
            catalog.api.find_facts(EvidenceQuery(document_id="wrong-document")).status
            == "not_found"
        )
        eligible = [f for f in catalog.facts if json_fact_bound(catalog, f)]
        tools, calculator = FinancialRetrievalTools(catalog), FinancialCalculator(catalog)
        lookups = []
        for fact in eligible:
            response = tools.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=fact.document_id,
                    snapshot_id=fact.snapshot_id,
                    local_observation_id=fact.local_observation_id,
                )
            )
            assert response.status == "found" and response.matches[0].json_source_bound
            assert all(c.pdf_page is None for c in response.matches[0].citations)
            lookups.append(fact.local_observation_id)
        # Keep exclusions honest at the same Financial Tools boundary.
        excluded = next((f for f in catalog.facts if f not in eligible), None)
        excluded_probe = None
        if excluded:
            excluded_probe = tools.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=excluded.document_id,
                    snapshot_id=excluded.snapshot_id,
                    local_observation_id=excluded.local_observation_id,
                )
            )
            assert all(not m.json_source_bound for m in excluded_probe.matches)
        # Ratio on actual mapped operands: same filing/period/unit, no Gold inputs.
        pair = next(
            (
                (g, r)
                for g in eligible
                for r in eligible
                if g.canonical_item_id == "b02.gross_profit"
                and r.canonical_item_id == "b02.net_revenue"
                and compatible_pair(g, r)
            ),
            None,
        )
        if pair is None:
            pair = next(
                (
                    (cash, assets)
                    for cash in eligible
                    for assets in eligible
                    if cash.canonical_item_id == "b01.cash_equivalents"
                    and assets.canonical_item_id == "b01.total_assets"
                    and compatible_pair(cash, assets)
                ),
                None,
            )
        calculation = None
        if pair:
            refs = {
                key: RetrievalReference(kind="fact", observation=f.observation_identity())
                for key, f in zip(["numerator", "denominator"], pair, strict=True)
            }
            calculation = calculator.calculate_dynamic(
                refs,
                [
                    DynamicOperation(
                        operation_id="source_ratio", operator="ratio", inputs=list(refs)
                    )
                ],
            )
            assert calculation.standard_metric is False
            assert calculation.steps and calculation.steps[-1].result is not None
        m5 = None
        if catalog.facts:
            available = (
                eligible or [f for f in catalog.facts if f.canonical_item_id] or catalog.facts
            )
            focus = next(
                (f for f in available if f.canonical_item_id == "b02.net_revenue"), available[0]
            )
            question = smoke_question(focus)
            m5 = FinancialLiteOrchestrator(catalog, supervisor=OfflineGraphSupervisor()).run(
                question=question,
                context=PlannerContext(
                    document_id=focus.document_id,
                    snapshot_id=focus.snapshot_id,
                    company_id=focus.company_id,
                    period=focus.context.period,
                    mode="deterministic",
                ),
            )
            assert not m5.candidates or eligible, m5.model_dump_json()
            assert all(not c.financial_fact_verified for c in m5.candidates)
            if eligible:
                assert m5.candidates, m5.model_dump_json()
                assert m5.supervisor_result and any(
                    t.operation == "get_graph_context" for t in m5.supervisor_result.tool_trace
                )
        else:
            m5 = FinancialLiteOrchestrator(catalog).run(
                question="Dữ liệu tài chính của tài liệu này?",
                context=PlannerContext(
                    document_id=manifest["document_id"],
                    snapshot_id=manifest["snapshot_id"],
                    mode="deterministic",
                ),
            )
            assert not m5.candidates
        fidelity = check_fidelity(root, manifest, catalog.facts, catalog.evidence)
        atomic_json(
            target / "pipeline-probes.json",
            dict(
                financial_lookup_ids=lookups,
                excluded_fact=excluded_probe.model_dump(mode="json") if excluded_probe else None,
                document_retrieval=retrieval,
                calculation=calculation.model_dump(mode="json") if calculation else None,
                m5=m5.model_dump(mode="json") if m5 else None,
                pdf_verified=False,
                model_calls=0,
            ),
        )
        summary.update(
            document_alias=alias,
            document_id=manifest["document_id"],
            snapshot_id=manifest["snapshot_id"],
            context_coverage=context_coverage(catalog, eligible),
            eligible_periods=dict(Counter(f.context.period for f in eligible)),
            table_issue_counts=dict(Counter(i for t in summary["tables"] for i in t["issues"])),
            eligible_mapped_facts=len(eligible),
            graph_nodes=len(graph.nodes),
            graph_edges=len(graph.edges),
            graph_status_counts=dict(
                Counter(
                    a.status for a in [*validation.nodes, *validation.edges, *validation.inputs]
                )
            ),
            orphan_nodes=len(validation.orphan_nodes),
            document_retrieval=retrieval,
            fidelity=fidelity,
            financial_lookups=len(lookups),
            calculation="computed" if calculation else "no_eligible_pair",
            m5_status=m5.status if m5 else "no_eligible_facts",
            m5_candidates=len(m5.candidates) if m5 else 0,
            m5_tool_operations=dict(Counter(t.operation for t in m5.supervisor_result.tool_trace))
            if m5 and m5.supervisor_result
            else {},
            restart_exact=True,
            seconds=round(perf_counter() - started, 3),
        )
        atomic_json(target / "summary.json", summary)
        _, current = read_refined(root, alias, projection_version)
        assert current == manifest
        summaries.append(summary)
        print(
            json.dumps({k: v for k, v in summary.items() if k != "tables"}, ensure_ascii=False),
            flush=True,
        )
    # Verify every source again at the end, including early documents in long runs.
    for alias, original in inventory.items():
        assert read_refined(root, alias, projection_version)[1] == original, "source_hash_changed"
    atomic_json(
        output / "catalog-index.json",
        dict(
            version="vifinbench-json-corpus-v1",
            documents={
                s["document_alias"]: dict(
                    bundle=s["document_alias"],
                    document_id=s["document_id"],
                    snapshot_id=s["snapshot_id"],
                )
                for s in summaries
            },
        ),
    )
    atomic_json(
        output / "summary.json",
        dict(documents=summaries, source_hashes_unchanged=True, model_calls=0),
    )
    write_coverage(output, summaries)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("ViFinBench/refined"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/VFB-IMPORT-02/pilot-v1")
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--all", action="store_true", help="Import every document under refined root"
    )
    selection.add_argument("--documents", nargs="+", default=None)
    parser.add_argument("--projection-version", default=None)
    args = parser.parse_args()
    documents = discover_documents(args.root) if args.all else args.documents or PILOT_DOCUMENTS
    if args.all and args.output == parser.get_default("output"):
        parser.error("--all requires an explicit new --output directory")
    validate(args.root, args.output, documents, projection_version=args.projection_version)
