"""CHAT-01: seven small real-source conversations, offline, separate new ledger."""

import argparse
import hashlib
import shutil
from decimal import Decimal
from pathlib import Path

from evaluate_evidence_fusion import save
from evaluate_generalization import pipeline as load_pipeline
from vietnamese_financial_multi_agent.api.conversations import ConversationService
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import EvidenceGraph, SnapshotCatalog
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

SCENARIOS = [
    [
        "Doanh thu BBS năm 2025 là bao nhiêu?",
        "So với năm trước thì sao?",
        "Tỷ suất lợi nhuận gộp năm đó thế nào?",
        "Công thức tính chỉ số này là gì?",
    ],
    ["Doanh thu BBS 2025?", "Còn BCC năm 2024?", "Công thức chỉ số này là gì?"],
    ["Thuyết minh BBS năm 2025 nói gì về nhân viên quản lý chủ chốt?", "Nội dung đó ở trang nào?"],
    ["Doanh thu là bao nhiêu?", "Doanh thu BCC 2025?", "Còn năm 2024?"],
    ["ROE BBS 2025?", "Công thức chỉ số này là gì?", "Doanh thu năm đó?"],
    [
        "Doanh thu BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "Chỉ số này là gì?",
    ],
    ["Biên lợi nhuận gộp BCC 2024?", "Công thức tính chỉ số này?"],
]


def unique(rows):
    return list({r.model_dump_json(): r for r in rows}.values())


def build(root, output):
    pipelines = [
        load_pipeline(root, label, output)[0] for label in ("BBS_2025", "BCC_2024", "BCC_2025")
    ]
    catalogs = [p.catalog for p in pipelines]
    base = catalogs[0]
    catalog = SnapshotCatalog(
        unique([r for c in catalogs for r in c.descriptors]),
        unique([r for c in catalogs for r in c.facts]),
        unique([r for c in catalogs for r in c.evidence]),
        unique([r for c in catalogs for r in c.metrics]),
        graph=EvidenceGraph(
            nodes=unique([r for c in catalogs for r in c.graph.nodes]),
            edges=unique([r for c in catalogs for r in c.graph.edges]),
        ),
        source_reviews=unique([r for c in catalogs for r in c.reviews]),
        accounting_bases=unique([r for c in catalogs for r in c.bases]),
        reporting_scope_reviews=unique([r for c in catalogs for r in c.scope_reviews]),
        approval=base.approval,
        formula_policies=base.policies,
        formula_approvals=base.formula_approvals,
        execution_approval=base.execution_approval,
    )
    return FinancialQAPipeline(
        catalog=catalog,
        documents=[d for p in pipelines for d in p.documents],
        repository=VerifiedClaimRepository(output / "ledger"),
        compositions=pipelines[0].compositions,
        document_repository=pipelines[0].document_repository,
    )


def audit(pipeline, turn):
    """Check source identity, direct values, Decimal formulas and original quotes.

    This checks accepted saved sources, not independent full-PDF OCR accuracy.
    """
    result = turn.response
    entries = {e.identity.verified_claim_id: e for e in pipeline.repository.list_all()}
    facts = {
        (f.document_id, f.snapshot_id, f.local_observation_id): f for f in pipeline.catalog.facts
    }
    errors = []
    for claim_id in result.used_verified_claim_ids:
        entry = entries[claim_id]
        claim = entry.accepted_claim
        if entry.identity.document_id != turn.context.document_id:
            errors.append("document_leakage")
        if entry.identity.company_id != turn.context.company_id:
            errors.append("company_leakage")
        if entry.identity.kind == "document":
            for ref, quote in zip(claim.references, claim.quotations, strict=True):
                r = ref.evidence
                record = next(
                    (
                        record
                        for record in pipeline.document_repository.list_by_document(r.document_id)
                        if record.evidence_identity() == r
                    ),
                    None,
                )
                if record is None or record.raw_text != quote:
                    errors.append("source_quote_mismatch")
        elif claim.calculation:
            operands = []
            for op in claim.calculation.trace.operands:
                ref = op.observation
                f = facts[(ref.document_id, ref.snapshot_id, ref.local_id)]
                operands.append(f.value.normalized_value)
            a, b = operands
            expected = (a / b - (1 if claim.calculation.formula_id == "revenue_yoy" else 0)) * 100
            if abs(Decimal(claim.calculation.result) - expected) > Decimal("0.005"):
                errors.append("independent_formula_mismatch")
        else:
            # Direct-fact claims carry their canonical observation reference.
            for support in claim.supporting_evidence:
                if support.reference.observation:
                    r = support.reference.observation
                    f = facts[(r.document_id, r.snapshot_id, r.local_id)]
                    if f.value.normalized_value != Decimal(support.value):
                        errors.append("direct_value_mismatch")
    for citation in result.citations:
        if citation.document_id != turn.context.document_id:
            errors.append("citation_document_leakage")
        if not set(citation.bound_verified_claim_ids) <= set(result.used_verified_claim_ids):
            errors.append("unverified_citation")
        originals = [
            f
            for f in pipeline.catalog.facts
            if f.document_id == citation.document_id and f.snapshot_id == citation.snapshot_id
        ]
        records = pipeline.document_repository.list_by_document(citation.document_id)
        sources = [source for record in [*originals, *records] for source in record.sources]
        for source_citation in citation.source_citations:
            if source_citation.source not in sources:
                errors.append("citation_not_in_original_source")
            ref = source_citation.source.reference
            if ref is None or ref.anchor.page.page != citation.pdf_page:
                errors.append("citation_page_mismatch")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/CHAT-01/run1"))
    parser.add_argument("--seed-ledger", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose_fresh_output")
    if args.seed_ledger:
        shutil.copytree(args.seed_ledger, args.output / "ledger")
    root = Path.cwd()
    protected = list((root / "artifacts/evidence/EXT-01").rglob("*.json"))
    protected += list((root / "artifacts/evidence/GEN-01").glob("*-release/*/*.json"))

    def hashes():
        return {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in protected
        }

    before = hashes()
    pipeline = build(root, args.output)
    service = ConversationService(pipeline)
    results = []
    sessions = []
    for index, questions in enumerate(SCENARIOS, 1):
        session = service.create()
        sessions.append(session)
        for question in questions:
            turn = service.send(
                session.conversation_id,
                FinancialQARequest(
                    question=question,
                    execution_mode="deterministic",
                ),
            )
            save(args.output / f"s{index}-t{turn.turn_id}.json", turn.model_dump(mode="json"))
            errors = audit(pipeline, turn)
            results.append(
                dict(
                    scenario=index,
                    turn=turn.turn_id,
                    status=turn.response.status,
                    errors=errors,
                    resolution_ms=turn.resolution_latency_ms,
                    total_ms=turn.total_latency_ms,
                )
            )
            print(
                index,
                turn.turn_id,
                turn.response.status,
                round(turn.total_latency_ms),
                errors,
                flush=True,
            )
    # Interleave an earlier conversation after other sessions changed company/year.
    turn = service.send(
        sessions[0].conversation_id,
        FinancialQARequest(
            question="Công thức chỉ số này là gì?",
            execution_mode="deterministic",
        ),
    )
    save(args.output / "s1-t5.json", turn.model_dump(mode="json"))
    errors = audit(pipeline, turn)
    assert (
        turn.context.company_id
        == service.history(sessions[0].conversation_id).selected_context.company_id
    )
    assert turn.context.period == "2025"
    results.append(
        dict(
            scenario=1,
            turn=5,
            status=turn.response.status,
            errors=errors,
            resolution_ms=turn.resolution_latency_ms,
            total_ms=turn.total_latency_ms,
        )
    )
    save(
        args.output / "summary.json",
        dict(
            results=results,
            source_hashes_unchanged=before == hashes(),
            protected_files=len(before),
            gemini_calls=0,
        ),
    )
    assert before == hashes()
    assert not any(r["errors"] for r in results)


if __name__ == "__main__":
    main()
