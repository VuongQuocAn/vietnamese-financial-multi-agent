"""GEN-01 offline PDF-reading comparison and production M4 gates; zero LLM calls."""

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

from run_cross_company_ingestion import load
from vietnamese_financial_multi_agent.accounting.automated_extraction import parse_vietnamese_number
from vietnamese_financial_multi_agent.accounting.context_resolution import ContextEvidence
from vietnamese_financial_multi_agent.accounting.contracts import FinancialSourceReference
from vietnamese_financial_multi_agent.api.document_store import atomic_json
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    EvidenceGraph,
    ExecutionCompatibilityApproval,
    FormulaDefinition,
    OperationCompatibilitySpec,
    ReportingScopeReview,
    SnapshotCatalog,
    SnapshotDescriptor,
    bind_source_review,
    build_graph,
    evidence_from_persisted_result,
    rebuild_snapshot_metrics,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import AccountingBasisReview
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculator,
    FinancialRetrievalTools,
    FindFinancialFactsRequest,
)

TARGETS = {
    ("B01", "270"): "b01.total_assets",
    ("B01", "300"): "b01.total_liabilities",
    ("B02", "10"): "b02.net_revenue",
    ("B02", "20"): "b02.gross_profit",
    ("B02", "60"): "b02.profit_after_tax",
    ("B03", "20"): "b03.operating_cash_flow",
}


def normalized_label(text):
    text = " ".join(text.casefold().split())
    return re.sub(r"^(?:\d+\.|[a-d]\s*[.-])\s*", "", text)


def audit(folder, readings, metadata_reviews, output):
    started = time.monotonic()
    result = load(folder / "result.json")
    facts = [
        CanonicalFinancialFact.model_validate_json(json.dumps(f))
        for f in load(folder / "facts.json")
    ]
    graph = EvidenceGraph.model_validate_json((folder / "graph.json").read_text(encoding="utf-8"))
    descriptor = SnapshotDescriptor(**load(folder / "descriptor.json"))
    assert all(
        (f.document_id, f.snapshot_id, f.company_id)
        == (descriptor.document_id, descriptor.snapshot_id, result["company_id"])
        and all(
            (s.document_id, s.snapshot_id, s.reference.anchor.page.source_ref)
            == (descriptor.document_id, descriptor.snapshot_id, descriptor.document_id)
            for s in f.sources
        )
        for f in facts
    ), "fact/source identity mismatch"
    valid = [
        r
        for r in result["records"]
        if "invalid_extraction_response" not in r["extraction"]["issues"]
    ]
    evidence = evidence_from_persisted_result(dict(result, records=valid))
    rows, reviews = [], []
    for reference in readings:
        candidates = [
            (r, link)
            for r in valid
            for link in r["extraction"]["links"]
            if r["source"]["page"]["page"] == reference["pdf_page"]
            and link["source_item_code"] == reference["source_item_code"]
            and link["raw_header"].casefold() == reference["raw_header"].casefold()
        ]
        row = dict(reference=reference, matches=len(candidates), correct=False)
        if len(candidates) == 1:
            record, link = candidates[0]
            expected = parse_vietnamese_number(reference["raw_value"])
            raw_correct = parse_vietnamese_number(link["raw_value"] or "") == expected
            fact_matches = [
                f
                for f in facts
                if f.source_item_code == reference["source_item_code"]
                and f.raw_header == link["raw_header"]
                and f.context.statement_type == reference["statement_type"]
                and any(s.reference.anchor.page.page == reference["pdf_page"] for s in f.sources)
            ]
            row.update(
                raw_correct=raw_correct,
                pipeline_raw_value=link["raw_value"],
                pipeline_label=link["raw_label"],
                issues=link["issues"],
                canonical_item_id=link["canonical_item_id"],
            )
            label_correct = normalized_label(link["raw_label"] or "") == normalized_label(
                reference["raw_label"]
            )
            if len(fact_matches) == 1:
                fact = fact_matches[0]
                context_correct = (
                    fact.context.period == reference["period"]
                    and fact.context.currency == reference["unit"]
                    and str(fact.context.scale) == reference["scale"]
                )
                row.update(
                    period=fact.context.period,
                    scope=fact.context.reporting_scope,
                    context_correct=context_correct,
                    label_correct=label_correct,
                    normalized_value=str(fact.value.normalized_value),
                    correct=raw_correct
                    and label_correct
                    and context_correct
                    and fact.value.normalized_value == expected,
                )
                if row["correct"]:
                    image = (
                        folder.parent.parent / folder.name / f"pdf-page-{reference['pdf_page']}.png"
                    )
                    # Image paths come from the explicit independent reading, not extraction.
                    image = Path(metadata_reviews["render_folder"]) / image.name
                    reading = dict(
                        observation=fact.observation_identity(),
                        pdf_sha256=descriptor.pdf_sha256,
                        pdf_page=reference["pdf_page"],
                        review_image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                        review_reference=reference["review_reference"],
                        verification_reference=reference["review_reference"],
                        method="controlled_original_pdf_visual_read",
                        level="value_row_verified",
                        raw_value=link["raw_value"],
                        raw_label=link["raw_label"],
                        raw_header=link["raw_header"],
                        period=fact.context.period,
                        statement_type=reference["statement_type"],
                    )
                    reviews.append(
                        bind_source_review(fact, reading, record["response"]["output"]["payload"])
                    )
        rows.append(row)
    policies = load(Path("configs/m4-execution-policies.json"))
    formula_policies = [PreparedFormulaPolicy(**p) for p in policies["formula_policies"]]
    metrics = []
    for policy in formula_policies[:2]:
        definition = FormulaDefinition(
            formula_reference="configs/m4-execution-policies.json",
            formula_version=policy.version,
            name=policy.formula_id,
            expression=policy.expression,
            compatibility=OperationCompatibilitySpec(
                operation_id=policy.formula_id,
                rule_reference="M4-01/design-decision/2026-11-02",
                operands=policy.operands,
                period_relation="same",
                document_relation="same",
            ),
        )
        period = str(result["metadata"]["reporting_year"])
        if policy.formula_id == "debt_to_assets":
            period += "-12-31"
        metrics.extend(
            rebuild_snapshot_metrics(
                [(definition, {o.role: period for o in policy.operands})], descriptor, facts
            )
        )
    graph = build_graph(facts, evidence, metrics)
    validation = validate_graph(graph, facts, evidence, metrics)
    bases = []
    for reading in metadata_reviews.get("accounting_basis", []):
        image = Path(metadata_reviews["render_folder"]) / f"pdf-page-{reading['pdf_page']}.png"
        bases.append(
            AccountingBasisReview(
                **reading,
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                pdf_sha256=descriptor.pdf_sha256,
                review_image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                method="controlled_original_pdf_visual_read",
                statement_types=["B01", "B02"],
            )
        )
    cover = result["metadata"]["identity_source_pdf_page"]
    cover_hash = hashlib.sha256(
        (Path(metadata_reviews["render_folder"]) / f"pdf-page-{cover}.png").read_bytes()
    ).hexdigest()
    quote = "BÁO CÁO TÀI CHÍNH " + (
        "RIÊNG" if metadata_reviews["scope"] == "separate" else "HỢP NHẤT"
    )
    reference = FinancialSourceReference(
        anchor=SourceAnchor(
            page=RawPageIdentity(
                symbol=result["records"][0]["source"]["page"]["symbol"],
                year=str(result["metadata"]["reporting_year"]),
                page=cover,
                image=f"sha256:{cover_hash}",
                source_ref=descriptor.document_id,
            ),
            status="uncertain",
        ),
        source_pointer="/independent_pdf_reading/cover/title/scope",
        provenance_level="page",
    )
    scope_review = ReportingScopeReview(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        pdf_sha256=descriptor.pdf_sha256,
        pdf_page=cover,
        source_quote=quote,
        evidence_role="filing_scope",
        reporting_scope=metadata_reviews["scope"],
        evidence=ContextEvidence(raw_text=quote, provenance=[reference]),
        sources=[
            EvidenceAnchor(
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                reference=reference,
            )
        ],
        method="controlled_original_pdf_visual_read",
        review_image_sha256=cover_hash,
        verification_reference=f"GEN-01/independent-pdf/{folder.name}/cover",
        inspection_reference=f"GEN-01/independent-pdf/{folder.name}/cover",
    )
    catalog = SnapshotCatalog(
        [descriptor],
        facts,
        evidence,
        metrics,
        graph=graph,
        source_reviews=reviews,
        accounting_bases=bases,
        approval=PreparationApproval(
            **load(Path("configs/d02-analytical-policies.json"))["preparation_approval"]
        ),
        formula_policies=formula_policies,
        formula_approvals=[
            FormulaExecutionApproval(**a) for a in policies["formula_execution_approvals"]
        ],
        execution_approval=ExecutionCompatibilityApproval(**policies["execution_approval"]),
        reporting_scope_reviews=[scope_review],
    )
    tools = FinancialRetrievalTools(catalog)
    calculator = FinancialCalculator(catalog)
    fact_responses = []
    for (statement, code), canonical in TARGETS.items():
        period = str(result["metadata"]["reporting_year"]) + (
            "-12-31" if statement == "B01" else ""
        )
        response = tools.find_financial_facts(
            FindFinancialFactsRequest(
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                company_id=result["company_id"],
                canonical_item_id=canonical,
                period=period,
            )
        )
        fact_responses.append(
            dict(
                source_code=code,
                canonical_item_id=canonical,
                response=response.model_dump(mode="json"),
            )
        )
    calculations = [
        calculator.calculate_financial_metric(
            CalculateFinancialMetricRequest(
                metric_id=m.metric_id,
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
            )
        ).model_dump(mode="json")
        for m in metrics
    ]
    for name, data in (
        ("audit", rows),
        ("source-reviews", [r.model_dump(mode="json") for r in reviews]),
        ("metrics", [m.model_dump(mode="json") for m in metrics]),
        ("m4-facts", fact_responses),
        ("m4-calculations", calculations),
        ("reporting-scope-reviews", [scope_review.model_dump(mode="json")]),
        ("graph", graph.model_dump(mode="json")),
        ("graph-validation", validation.model_dump(mode="json")),
    ):
        atomic_json(output / f"{name}.json", data)
    summary = dict(
        observations=len(rows),
        correct=sum(r["correct"] for r in rows),
        source_reviews=len(reviews),
        graph_nodes=len(graph.nodes),
        graph_edges=len(graph.edges),
        graph_statuses=dict(Counter(a.status for a in validation.nodes + validation.edges)),
        m4_fact_statuses=dict(Counter(r["response"]["status"] for r in fact_responses)),
        calculations=[
            dict(
                formula=r["formula_id"],
                status=r["status"],
                result=r["result"],
                reasons=r["reasons"],
            )
            for r in calculations
        ],
        seconds=time.monotonic() - started,
        financial_fact_verified=False,
    )
    atomic_json(output / "summary.json", summary)
    print(json.dumps(dict(document=folder.name, **summary)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--readings", type=Path, required=True)
    parser.add_argument("--metadata-reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((Path.cwd() / "artifacts/evidence").resolve()):
        parser.error("output must be under artifacts/evidence")
    args.output.mkdir(parents=True, exist_ok=False)
    readings = load(args.readings)
    for document, metadata in load(args.metadata_reviews).items():
        output = args.output / document
        output.mkdir()
        audit(
            args.source / document,
            [r for r in readings if r["document"] == document],
            metadata,
            output,
        )


if __name__ == "__main__":
    main()
