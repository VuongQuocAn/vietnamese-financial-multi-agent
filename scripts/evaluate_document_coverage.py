"""EXT-01 offline before/after evaluation, using a separately reviewed local oracle.

The oracle must be authored from PDF renders before observing QA answers. It is
kept in ignored artifacts, along with actual source quotes and financial data.
"""

import argparse
import json
import time
from pathlib import Path

from complete_document_evidence import (
    atomic_json,
    check_native_fidelity,
    native_payload,
    read,
)
from evaluate_document_qa import build_pipeline
from vietnamese_financial_multi_agent.agents.document_qa_contracts import DocumentRequirement
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.document_processing.vision_ocr import validate_components
from vietnamese_financial_multi_agent.evidence.composition import (
    EvidenceComposition,
    load_composition,
    verify_saved_pages,
)
from vietnamese_financial_multi_agent.evidence.document_claim_support import source_assertion
from vietnamese_financial_multi_agent.evidence.document_repository import (
    DocumentEvidenceRepository,
    EvidenceConflict,
)
from vietnamese_financial_multi_agent.evidence.search import (
    EvidenceSearchIndex,
    SearchDocumentEvidenceRequest,
    normalize_search,
)


def evaluate(input_path, output, oracle, case_indices=None):
    started = time.monotonic()
    cases = read(oracle)
    if not 12 <= len(cases) <= 20:
        raise ValueError("expected_12_to_20_independently_prepared_cases")
    if case_indices is not None:
        if not case_indices or any(i < 0 or i >= len(cases) for i in case_indices):
            raise ValueError("invalid_case_selection")
        cases = [case for i, case in enumerate(cases) if i in case_indices]
    pipeline = build_pipeline(input_path, output / "ledger")
    repository = DocumentEvidenceRepository(input_path / "repository")
    indices, manifests = {}, {}
    for path in sorted(input_path.glob("*/composition.json")):
        manifest = EvidenceComposition.model_validate(read(path))
        manifests[path.parent.name] = manifest
        indices[path.parent.name] = EvidenceSearchIndex(
            manifest,
            repository,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
    results = []
    try:
        for case in cases:
            label = case["document"]
            manifest = manifests[label]
            retrieval = indices[label].search(
                SearchDocumentEvidenceRequest(
                    document_id=manifest.logical_document_id,
                    composition_id=manifest.composition_id,
                    query=case["query"],
                    top_k=5,
                    evidence_type=case.get("evidence_type", "both"),
                )
            )
            actual = pipeline.run(FinancialQARequest(question=case["question"], force_refresh=True))
            relevant = False
            for match in retrieval.matches:
                assert match.document_id == manifest.logical_document_id
                content = getattr(match.evidence.record, "raw_text", None) or " ".join(
                    c.text for c in match.cells if c.text
                )
                phrases = [
                    normalize_search(case["query"]),
                    normalize_search(case.get("source_text") or ""),
                ]
                if match.pdf_page in case["expected_pages"] and any(
                    phrase and phrase in normalize_search(content) for phrase in phrases
                ):
                    relevant = True
            results.append(
                dict(
                    oracle=case,
                    retrieval=retrieval.model_dump(mode="json"),
                    relevant_source_found=relevant,
                    relevance_basis="expected_page_and_original_phrase_in_primary_evidence",
                    actual=actual.model_dump(mode="json"),
                    failure_stage=None if relevant else "retrieval_or_missing_extraction",
                    verification_limitation=actual.trace.unanswered_requirements,
                )
            )
            # Convert typed requirements without losing the replayable M5/M6/M7 trace.
            results[-1]["verification_limitation"] = [
                r.model_dump(mode="json") for r in actual.trace.unanswered_requirements
            ]
            atomic_json(output / "quick-qa.json", results)
            print(label, actual.status, "relevant", relevant, flush=True)
        summary = dict(
            cases=len(results),
            relevant_retrieval=sum(r["relevant_source_found"] for r in results),
            accepted_claims=sum(
                r["actual"]["trace"]["native_decisions"].get("ACCEPT", 0) for r in results
            ),
            investigate_claims=sum(
                r["actual"]["trace"]["native_decisions"].get("INVESTIGATE", 0) for r in results
            ),
            m7_with_citations=sum(bool(r["actual"]["citations"]) for r in results),
            elapsed_seconds=time.monotonic() - started,
            provider_calls=sum(r["actual"]["trace"]["provider_calls"] for r in results),
        )
        atomic_json(output / "summary.json", summary)
        print(summary)
    finally:
        for index in indices.values():
            index.close()


def controls(input_path, output, root):
    repository = DocumentEvidenceRepository(input_path / "repository")
    manifest = EvidenceComposition.model_validate(read(input_path / "BBS_2025/composition.json"))
    results = []

    def load(value):
        return load_composition(
            value,
            repository,
            document_id=value.logical_document_id,
            composition_id=value.composition_id,
        )

    def rejected(name, operation):
        try:
            operation()
        except (ValueError, EvidenceConflict) as error:
            results.append(dict(case=name, passed=True, reason=str(error)))
        else:
            raise AssertionError(name)

    index = EvidenceSearchIndex(
        manifest,
        repository,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    for name, update in [
        ("wrong_document", dict(document_id="wrong")),
        ("wrong_snapshot", dict(snapshot_id="wrong")),
        ("wrong_page", dict(source_page=999)),
    ]:
        fields = dict(
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
            query="kiểm toán",
        )
        response = index.search(SearchDocumentEvidenceRequest(**(fields | update)))
        assert not response.matches
        results.append(dict(case=name, passed=True, status=response.status))
    parent = next((s for s in manifest.sources if not s.evidence), None)
    if parent is not None:
        response = index.search(
            SearchDocumentEvidenceRequest(
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
                snapshot_id=parent.descriptor.snapshot_id,
                query="báo cáo",
            )
        )
        assert not response.matches
        results.append(
            dict(
                case="unselected_original_projection_not_hydrated",
                passed=True,
                snapshot_id=parent.descriptor.snapshot_id,
            )
        )
    index.close()
    baseline = load(manifest)
    changed = manifest.model_copy(deep=True)
    for source in changed.sources:
        source.status = "quarantine"
    assert not load(changed).evidence
    results.append(dict(case="unverified_source", passed=True))
    changed = manifest.model_copy(deep=True)
    changed.sources[0].evidence.append(changed.sources[0].evidence[0])
    rejected("duplicate_evidence", lambda: load(changed))
    changed = manifest.model_copy(deep=True)
    changed.sources[0].evidence[0].identity = (
        changed.sources[0].evidence[0].identity.model_copy(update={"local_id": "missing"})
    )
    rejected("partial_materialization", lambda: load(changed))
    changed = manifest.model_copy(deep=True)
    changed.sources[0].pages[0].image_sha256 = "0" * 64
    rejected("wrong_page_image_binding", lambda: load(changed))
    first = baseline.evidence[0]
    rejected(
        "cache_conflict",
        lambda: repository.put(
            first.model_copy(update={"resolution_issues": ["intentional_conflict"]})
        ),
    )
    restarted = load_composition(
        manifest,
        DocumentEvidenceRepository(input_path / "repository"),
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    assert baseline.evidence == restarted.evidence
    results.append(dict(case="restart_reload", passed=True, records=len(restarted.evidence)))
    source_path = input_path / "BBS_2025/responses/page-4.json"
    record = read(source_path)
    rows = [
        r for r in baseline.evidence if r.snapshot_id == source_path.relative_to(root).as_posix()
    ]
    assert rows
    check_native_fidelity(rows, record)
    row = rows[0].model_copy(deep=True)
    row.sources[0].reference.source_pointer = "/text_elements/999999"
    rejected("source_pointer_mismatch", lambda: check_native_fidelity([row], record))
    truncated = json.loads(json.dumps(record))
    truncated["response"]["finish_reason"] = "length"
    assert native_payload(truncated) is None
    requirement = DocumentRequirement(
        target="y kien kiem toan", label="opinion", kind="exact_text", query="ý kiến kiểm toán"
    )
    assert source_assertion(requirement, [{"text": "ý kiến kiểm toán"}]) is None
    results.append(
        dict(
            case="truncated_auditor_opinion",
            passed=True,
            reason="truncated_response_not_reused_and_semantic_opinion_policy_blocked",
        )
    )
    requirement = DocumentRequirement(
        target="ke toan truong", label="role", kind="entity_role", query="Kế toán trưởng"
    )
    native = read(root / "artifacts/gemini-ingestion/M1-15/pdf/page-7.json")
    payload = json.loads(json.dumps(native["response"]["output"]["payload"]))
    role, person = payload["text_elements"][7], payload["text_elements"][10]
    for name, projections in [
        ("missing_signature_relation", [{"text": role["text"]}, {"text": person["text"]}]),
        ("ocr_uncertain_name", [{"text": role["text"]}, {"text": "?"}]),
    ]:
        assert source_assertion(requirement, projections) is None
        results.append(
            dict(
                case=name,
                passed=True,
                reason="existing_M6_source_assertion_requires_explicit_relation",
            )
        )
    person["reading"] = "unknown"
    pdf2025 = next((root / "data/raw/Financial_Report_pdf/BBS/2025").glob("*.pdf"))
    image = load_pages(
        pdf2025, symbol="BBS", year="2025", pages=[7], dpi=native["provenance"]["render_dpi"]
    )[0].image
    validated = validate_components(payload, image, source=native["source"])
    assert validated["text_elements"][10]["status"] == "unresolved"
    results.append(
        dict(
            case="real_name_counterfactual_unknown_reading",
            passed=True,
            source_pointer="/text_elements/10",
            reason="unknown_name_remains_unresolved_not_verified",
        )
    )
    partial = json.loads(json.dumps(record))
    partial["response"]["output"]["payload"] = {"context": ["partial only"]}
    assert native_payload(partial) is None
    results.append(
        dict(
            case="partial_extraction",
            passed=True,
            reason="financial_context_only_is_not_full_document_extraction",
        )
    )
    pdf = next((root / "data/raw/Financial_Report_pdf/BBS/2024").glob("*.pdf"))
    rejected("wrong_pdf_binding", lambda: verify_saved_pages(pdf, [record]))
    consolidated = EvidenceComposition.model_validate(
        read(input_path / "BCC_2024/composition.json")
    )
    separate = EvidenceComposition.model_validate(read(input_path / "BCC_2025/composition.json"))
    assert consolidated.logical_document_id != separate.logical_document_id
    mixed = consolidated.model_copy(deep=True)
    mixed.sources.extend(separate.sources)
    rejected("BCC_consolidated_separate_source_mix", lambda: load(mixed))
    for selected, scope in [(consolidated, "consolidated_2024"), (separate, "separate_2025")]:
        scoped_index = EvidenceSearchIndex(
            selected,
            repository,
            document_id=selected.logical_document_id,
            composition_id=selected.composition_id,
        )
        hits = scoped_index.search(
            SearchDocumentEvidenceRequest(
                document_id=selected.logical_document_id,
                composition_id=selected.composition_id,
                query="báo cáo tài chính",
                top_k=20,
            )
        )
        assert hits.matches and all(
            h.document_id == selected.logical_document_id for h in hits.matches
        )
        results.append(
            dict(
                case="BCC_document_scope_isolation:" + scope,
                passed=True,
                document_id=selected.logical_document_id,
                observed_pages=sorted({h.pdf_page for h in hits.matches}),
            )
        )
        scoped_index.close()
    atomic_json(output / "negative-controls.json", results)
    print(f"{len(results)} negative/reload controls passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--case-index", type=int, action="append")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.controls:
        controls(args.input.resolve(), args.output.resolve(), Path(".").resolve())
    else:
        if args.oracle is None:
            parser.error("--oracle is required for QA evaluation")
        evaluate(args.input, args.output, args.oracle, args.case_index)
