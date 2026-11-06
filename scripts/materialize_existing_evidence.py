"""INT-01a: replay caches offline, exact PDF binding, manifest và M4 probes."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedDocument,
)
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.document_processing.understanding_pipeline import (
    UnderstandingOptions,
    run_document_understanding,
)
from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    SnapshotDescriptor,
    evidence_from_persisted_result,
    evidence_from_unified_page,
)
from vietnamese_financial_multi_agent.evidence.composition import (
    CompositionSource,
    EvidenceComposition,
    EvidencePin,
    load_composition,
    payload_sha256,
    verify_saved_pages,
)
from vietnamese_financial_multi_agent.evidence.document_evidence import DocumentEvidence
from vietnamese_financial_multi_agent.evidence.document_repository import EvidenceConflict
from vietnamese_financial_multi_agent.tools import (
    EvidenceRetrievalTools,
    FindDocumentEvidenceRequest,
    GetEvidenceItemRequest,
    GetEvidenceSourcesRequest,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fidelity(rows, records):
    """Exact raw text/cells/layout so với saved payload, không financial scoring."""
    from vietnamese_financial_multi_agent.accounting.raw_corrections import extraction_payload

    checked = Counter()
    for row in rows:
        page = row.sources[0].reference.anchor.page.page
        record = next(r for r in records if r["source"]["page"]["page"] == page)
        payload = record["response"]["output"]["payload"]
        native = "text_elements" in payload
        if not native:
            payload = extraction_payload(record)
        value = payload
        for key in row.sources[0].reference.source_pointer.strip("/").split("/"):
            value = value[int(key)] if isinstance(value, list) else value[key]
        if row.kind == "text":
            assert row.raw_text == (value["text"] if native else value)
            checked["texts"] += 1
        elif native:
            table = row.structure.source_component
            assert (table["rows"], table["columns"]) == (value["rows"], value["columns"])
            assert len(table["cells"]) == len(value["cells"]) == len(row.structure.cells)
            for raw, cell in zip(value["cells"], table["cells"], strict=True):
                assert (raw["text"], raw["reading"]) == (cell["text"], cell["reading"])
                assert (raw["row"], raw["column"]) == (
                    cell["layout"]["row"],
                    cell["layout"]["column"],
                )
                assert raw["bbox"] == cell["geometry"]["candidate_bbox"]
                checked["cells"] += 1
            checked["tables"] += 1
        else:
            assert row.structure.model_dump(mode="json") == value
            checked["tables"] += 1
            checked["cells"] += len(value["cells"]) + len(value["headers"])
    return dict(checked)


def verify_materialized(root, output):
    """Acceptance trên outputs thật sau restart; không gọi extraction/provider."""
    summary = json.loads((output / "coverage-summary.json").read_text(encoding="utf-8"))
    repository = DocumentEvidenceRepository(output / "repository")
    checks = []

    def rejected(name, operation):
        try:
            operation()
        except ValueError as error:
            checks.append(dict(case=name, status="rejected", reason=str(error)))
        else:
            raise AssertionError(name + ": expected rejection")

    for path in sorted(output.glob("*/composition.json")):
        manifest = EvidenceComposition.model_validate_json(path.read_text(encoding="utf-8"))

        def load(selected=manifest, selection=manifest):
            return load_composition(
                selected,
                repository,
                document_id=selection.logical_document_id,
                composition_id=selection.composition_id,
            )

        catalog = load()
        for source in manifest.sources:
            if source.status == "verified":
                row = repository.get(source.evidence[0].identity)
                assert repository.put(row) == "idempotent"
        tools = EvidenceRetrievalTools(catalog)
        first = catalog.evidence[0]
        assert (
            tools.find_document_evidence(
                FindDocumentEvidenceRequest(
                    document_id="wrong-document", snapshot_id=first.snapshot_id
                )
            ).status
            == "not_found"
        )
        assert (
            tools.find_document_evidence(
                FindDocumentEvidenceRequest(
                    document_id=first.document_id, snapshot_id="wrong-snapshot"
                )
            ).status
            == "not_found"
        )
        assert (
            tools.find_document_evidence(
                FindDocumentEvidenceRequest(
                    document_id=first.document_id, snapshot_id=first.snapshot_id, source_page=999
                )
            ).status
            == "not_found"
        )
        for case in (
            "wrong_page_image",
            "duplicate_evidence",
            "conflicting_payload",
            "partial_materialization",
        ):
            changed = manifest.model_copy(deep=True)
            source = changed.sources[0]
            if case == "wrong_page_image":
                source.pages[0].image_sha256 = "0" * 64
            elif case == "duplicate_evidence":
                source.evidence.append(source.evidence[0])
            elif case == "conflicting_payload":
                source.evidence[0].payload_sha256 = "0" * 64
            else:
                source.evidence[0].identity = source.evidence[0].identity.model_copy(
                    update={"local_id": "missing-materialization"}
                )
            rejected(manifest.composition_id + ":" + case, lambda changed=changed: load(changed))
        try:
            repository.put(first.model_copy(update={"resolution_issues": ["intentional_conflict"]}))
        except EvidenceConflict:
            checks.append(
                dict(case=manifest.composition_id + ":repository_conflict", status="rejected")
            )
        else:
            raise AssertionError("repository conflict was overwritten")
        checks.append(
            dict(
                case=manifest.composition_id + ":restart_idempotence_and_scope",
                status="pass",
                exact_records=len(catalog.evidence),
            )
        )
    record = json.loads(
        (root / "artifacts/gemini-ingestion/M1-15/pdf/page-7.json").read_text(encoding="utf-8")
    )
    wrong_pdf = next(p for p in summary["source_hashes"] if p.endswith("BBS_2024.pdf"))
    rejected("real_wrong_pdf_image_binding", lambda: verify_saved_pages(root / wrong_pdf, [record]))
    record["provenance"].pop("pdf_sha256")
    rejected("real_missing_fingerprint", lambda: verify_saved_pages(root / wrong_pdf, [record]))
    # Original M3 native records/payload giữ nguyên, không chỉ ID/count equality.
    previous = (
        root / "artifacts/evidence/M3-03-real-validation/final/m1-native/document-evidence.json"
    )
    old = TypeAdapter(list[DocumentEvidence]).validate_python(
        json.loads(previous.read_text(encoding="utf-8"))["records"]
    )
    for row in old:
        assert repository.get(row.evidence_identity()) == row
    checks.append(dict(case="accepted_M3_native_exact_payload", status="pass", records=len(old)))
    assert all(digest(root / p) == h for p, h in summary["source_hashes"].items())
    assert all(digest(root / p) == h for p, h in summary["inherited_hashes"].items())
    checks.append(
        dict(
            case="protected_sources_and_inherited_files",
            status="pass",
            source_count=len(summary["source_hashes"]),
            inherited_count=len(summary["inherited_hashes"]),
        )
    )
    target = output / "acceptance-checks.json"
    content = json.dumps(checks, ensure_ascii=False, indent=2) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != content:
        raise ValueError("acceptance_output_conflict")
    target.write_text(content, encoding="utf-8")
    print(f"Real acceptance: {len(checks)} checks passed; zero provider calls")


def run(root, output):
    output.mkdir(parents=True, exist_ok=True)
    hashes, inventory, manifests, retrieval, samples, traces = {}, [], [], [], [], []
    inherited = [
        ".github/workflows/ci.yml",
        "src/accounting/financial_runtime.py",
        "src/api/extraction_sessions.py",
        "src/document_processing/financial_discovery.py",
        "tests/unit/test_financial_discovery.py",
        "web/next-env.d.ts",
        "scripts/complete_pdf_discovery.py",
        "tests/unit/test_full_pdf_discovery.py",
    ]
    before = {p: digest(root / p) for p in inherited if (root / p).exists()}
    # Chỉ source/accepted outputs liên quan, không hash toàn dataset.
    for pattern in (
        "artifacts/evidence/GEN-01/normalized-release/*/*.json",
        "artifacts/evidence/D-01/evaluation/*/*.json",
        "artifacts/evidence/D-01/evaluation/*/canonical/*.json",
        "artifacts/evidence/D-01/evaluation/*/document-evidence/*.json",
        "artifacts/evidence/D-04-review/*.json",
        "artifacts/evidence/D-04-review/canonical/*.json",
        "artifacts/evidence/D-02/*reviews.json",
        "artifacts/evidence/M4-03-final/*.json",
    ):
        for path in root.glob(pattern):
            hashes[path.relative_to(root).as_posix()] = digest(path)

    def read(relative):
        path = root / relative
        hashes[relative] = digest(path)
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def save(name, value):
        path = output / name
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError(f"output_conflict:{name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    repository = DocumentEvidenceRepository(output / "repository")
    pdfs = {}
    for symbol in ("BBS", "BCC"):
        for year in (2022, 2024, 2025) if symbol == "BBS" else (2024, 2025):
            for path in (root / f"data/raw/Financial_Report_pdf/{symbol}/{year}").glob("*.pdf"):
                hashes[path.relative_to(root).as_posix()] = digest(path)
                pdfs[digest(path)] = path

    def materialize(label, financial, source_path, rows, records, *, coverage):
        pdf = pdfs.get(financial.pdf_sha256)
        reasons, bindings = [], []
        try:
            if pdf is None:
                raise ValueError("source_pdf_unavailable")
            bindings = verify_saved_pages(pdf, records)
        except ValueError as error:
            reasons.append(str(error))
        identities = {(e.document_id, e.snapshot_id) for e in rows}
        if len(identities) != 1:
            raise ValueError("ambiguous_source_snapshot")
        document, snapshot = next(iter(identities))
        descriptor = SnapshotDescriptor(
            document_id=document,
            snapshot_id=snapshot,
            pdf_sha256=financial.pdf_sha256,
            origin="original_extraction",
        )
        fidelity = check_fidelity(rows, records)
        source = CompositionSource(
            descriptor=descriptor,
            original_source=source_path,
            artifact_sha256=hashes[source_path],
            status="quarantine" if reasons else "verified",
            reasons=reasons,
            pages=bindings,
            unverified_pages=[r["source"]["page"]["page"] for r in records] if reasons else [],
            evidence=[
                EvidencePin(
                    identity=e.evidence_identity(),
                    payload_sha256=payload_sha256(e.model_dump(mode="json")),
                )
                for e in rows
            ],
        )
        # Bound và unbound lưu riêng; không rewrite identity để vào quarantine M3.
        target = (
            repository if not reasons else DocumentEvidenceRepository(output / "quarantine" / label)
        )
        for row in rows:
            target.put(row)
        inventory.append(
            dict(
                label=label,
                source=source_path,
                extracted=True,
                persisted=True,
                materialized=len(rows),
                bound=not reasons,
                retrievable=not reasons,
                coverage=coverage,
                fidelity=fidelity,
                counts=dict(Counter(e.kind for e in rows)),
                pages=[r["source"]["page"]["page"] for r in records],
                reasons=reasons,
                source_fingerprint_present=all(
                    r.get("provenance", {}).get("pdf_sha256") for r in records
                ),
                page_fingerprint_present=all(
                    r.get("provenance", {}).get("image_sha256") for r in records
                ),
                response_content=dict(
                    text=len([e for e in rows if e.kind == "text"]),
                    table=len([e for e in rows if e.kind == "table"]),
                ),
                can_reuse_without_gemini=True,
                pdf=pdf.relative_to(root).as_posix() if pdf else None,
                snapshot=snapshot,
                document=document,
            )
        )
        traces.append(
            dict(
                label=label,
                stages=[
                    dict(stage="Gemini Saved Response", source=source_path, records=len(records)),
                    dict(
                        stage="Adapter",
                        identities=[e.evidence_identity().model_dump() for e in rows],
                        records=len(rows),
                    ),
                    dict(
                        stage="Document Evidence Repository",
                        root=target.root.relative_to(root).as_posix(),
                        records=len(rows),
                    ),
                    dict(stage="Composition", status=source.status, reasons=reasons),
                ],
            )
        )
        for stage in traces[-1]["stages"]:
            stage.update(
                pdf=inventory[-1]["pdf"],
                pages=inventory[-1]["pages"],
                status=source.status if stage["stage"] == "Composition" else "available",
                errors=reasons if stage["stage"] == "Composition" else [],
            )
        return source

    native_path = "artifacts/document-understanding/M1-16/native.json"
    native = UnifiedDocument.model_validate(read(native_path))
    native_records = {
        n: read(f"artifacts/gemini-ingestion/M1-15/pdf/page-{n}.json") for n in (5, 7, 8, 14, 15)
    }
    # Existing accepted native snapshot giữ nguyên identity/payload.
    financials = {}
    for year in (2022, 2024, 2025):
        result_path = f"artifacts/evidence/D-01/{year}/result.json"
        result = read(result_path)
        normalized = read(f"artifacts/evidence/D-01/evaluation/{year}/normalized-result.json")
        scope = dict(document_id=normalized["document_id"], snapshot_id=normalized["attempt_id"])
        pdf_hash = result["records"][0]["provenance"]["pdf_sha256"]
        financial = SnapshotDescriptor(**scope, pdf_sha256=pdf_hash, origin="normalized_projection")
        financials[year] = financial
        sources = []
        if year == 2025:
            rows = [
                e
                for page in native.pages
                for e in evidence_from_unified_page(
                    page, document_id=page.identity.source_ref, snapshot_id=native_path
                )
            ]
            sources.append(
                materialize(
                    "BBS_2025_native",
                    financial,
                    native_path,
                    rows,
                    [native_records[n] for n in (5, 7, 8)],
                    coverage="native_text_and_tables",
                )
            )
            for n in (14, 15):
                path = f"artifacts/gemini-ingestion/M1-15/pdf/page-{n}.json"
                unified = run_document_understanding(
                    pdfs[pdf_hash],
                    UnderstandingOptions(
                        symbol="BBS",
                        year="2025",
                        pages=(n,),
                        persisted_results={n: native_records[n]},
                    ),
                )
                rows = [
                    e
                    for page in unified.pages
                    for e in evidence_from_unified_page(
                        page, document_id=page.identity.source_ref, snapshot_id=path
                    )
                ]
                sources.append(
                    materialize(
                        f"BBS_2025_B09_{n}",
                        financial,
                        path,
                        rows,
                        [native_records[n]],
                        coverage="native_text_and_tables",
                    )
                )
        else:
            pages = {11, 18} if year == 2022 else {21, 24}
            # Adapter nhận nguyên result để giữ record index gốc.
            rows = [
                e
                for e in evidence_from_persisted_result(result)
                if e.sources[0].reference.anchor.page.page in pages
            ]
            sources.append(
                materialize(
                    f"BBS_{year}_B09",
                    financial,
                    result_path,
                    rows,
                    [r for r in result["records"] if r["source"]["page"]["page"] in pages],
                    coverage="financial_context_and_tables_only_not_full_prose",
                )
            )
        manifests.append(
            EvidenceComposition(
                composition_id=f"INT-01a/BBS_{year}/v1",
                logical_document_id=financial.document_id,
                financial_snapshot=financial,
                sources=sources,
            )
        )

    for year in (2024, 2025):
        prefix = f"artifacts/evidence/GEN-01/normalized-release/BCC_{year}"
        result = read(prefix + "/result.json")
        rows = TypeAdapter(list[DocumentEvidence]).validate_python(read(prefix + "/evidence.json"))
        financial = SnapshotDescriptor.model_validate(read(prefix + "/descriptor.json"))
        source = materialize(
            f"BCC_{year}",
            financial,
            prefix + "/evidence.json",
            rows,
            result["records"],
            coverage="accepted_primary_pages_context_and_tables_only",
        )
        manifests.append(
            EvidenceComposition(
                composition_id=f"INT-01a/BCC_{year}/v1",
                logical_document_id=financial.document_id,
                financial_snapshot=financial,
                sources=[source],
            )
        )

    legacy_path = "artifacts/document-understanding/M1-16/existing.json"
    legacy = UnifiedDocument.model_validate(read(legacy_path))
    inventory.append(
        dict(
            label="legacy_OCR",
            source=legacy_path,
            extracted=True,
            persisted=True,
            materialized=0,
            bound=False,
            retrievable=False,
            counts=dict(
                text=sum(len(p.text_regions) for p in legacy.pages),
                table=sum(len(p.tables) for p in legacy.pages),
            ),
            reasons=["missing_verified_pdf_image_binding"],
            coverage="quarantine_inventory_only",
        )
    )
    for manifest in manifests:
        save(
            manifest.composition_id.split("/")[1] + "/composition.json",
            manifest.model_dump(mode="json"),
        )
        # Fresh repository instance: simulate restart, exact identities/payloads.
        catalog = load_composition(
            manifest,
            DocumentEvidenceRepository(output / "repository"),
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
        tools = EvidenceRetrievalTools(catalog)
        for row in catalog.evidence:
            response = tools.get_evidence_item(
                GetEvidenceItemRequest(
                    document_id=row.document_id,
                    snapshot_id=row.snapshot_id,
                    local_evidence_id=row.local_evidence_id,
                    kind=row.kind,
                )
            )
            assert response.status == "found" and response.matches[0].record == row
            sources = tools.get_evidence_sources(
                GetEvidenceSourcesRequest(
                    reference=response.matches[0].reference,
                    document_id=row.document_id,
                    snapshot_id=row.snapshot_id,
                )
            )
            assert sources.status == "found" and sources.matches[0].citations
        for source in manifest.sources:
            if source.status != "verified":
                continue
            for binding in source.pages:
                response = tools.find_document_evidence(
                    FindDocumentEvidenceRequest(
                        document_id=source.descriptor.document_id,
                        snapshot_id=source.descriptor.snapshot_id,
                        source_page=binding.page,
                    )
                )
                assert response.status in {"found", "ambiguous"}
                expected = [
                    e
                    for e in catalog.evidence
                    if e.snapshot_id == source.descriptor.snapshot_id
                    and e.sources[0].reference.anchor.page.page == binding.page
                ]
                assert len(response.matches) == len(expected)
                retrieval.append(
                    dict(
                        composition=manifest.composition_id,
                        page=binding.page,
                        status=response.status,
                        matches=len(response.matches),
                        response=response.model_dump(mode="json"),
                    )
                )
                for row in expected:
                    samples.append(
                        dict(
                            composition=manifest.composition_id,
                            page=binding.page,
                            type=row.kind,
                            text=row.raw_text if row.kind == "text" else None,
                            structure=row.structure.model_dump(mode="json")
                            if row.kind == "table"
                            else None,
                            identity=row.evidence_identity().model_dump(),
                            sources=[s.model_dump(mode="json") for s in row.sources],
                        )
                    )
                # Source PDF, original page, tiện đối chiếu trực quan; ảnh output riêng.
                pdf = pdfs[source.descriptor.pdf_sha256]
                identity = expected[0].sources[0].reference.anchor.page
                image = load_pages(
                    pdf, symbol=identity.symbol, year=identity.year, pages=[binding.page]
                )[0].image
                name = f"visual/{manifest.composition_id.split('/')[1]}-{binding.page}.png"
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_bytes(image.content)
        # Public tools chỉ thấy sources được explicit pin, không latest.
        assert (
            tools.find_document_evidence(
                FindDocumentEvidenceRequest(
                    document_id=manifest.logical_document_id, snapshot_id="outside-composition"
                )
            ).status
            == "not_found"
        )
        traces.append(
            dict(
                composition=manifest.composition_id,
                stage="Evidence Retrieval API",
                status="found" if catalog.evidence else "unavailable",
                records=len(catalog.evidence),
                restart_exact=True,
            )
        )

    assert all(digest(root / p) == h for p, h in hashes.items())
    assert all(digest(root / p) == h for p, h in before.items())
    save("source-inventory.json", inventory)
    save("binding-decisions.json", [m.model_dump(mode="json") for m in manifests])
    save("retrieval-results.json", retrieval)
    save("sample-evidence-local.json", samples)
    save("trace.json", traces)
    summary = dict(
        gateway_calls=0,
        ocr_calls=0,
        materialized=sum(x.get("materialized", 0) for x in inventory),
        verified=sum(
            len(s.evidence) for m in manifests for s in m.sources if s.status == "verified"
        ),
        quarantined=sum(
            len(s.evidence) for m in manifests for s in m.sources if s.status == "quarantine"
        ),
        legacy_excluded=7,
        pages=len(retrieval),
        exact_lookup_count=sum(
            len(s.evidence) for m in manifests for s in m.sources if s.status == "verified"
        ),
        source_hashes=hashes,
        inherited_hashes=before,
        implementation_base=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
    )
    save("coverage-summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("hashes")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/INT-01a"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/INT-01a"):
        parser.error("output must stay within artifacts/evidence/INT-01a")
    if args.verify_only:
        verify_materialized(root, output)
    else:
        run(root, output)
