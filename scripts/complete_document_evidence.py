"""EXT-01: cache-first page inventory, bounded extraction, additive composition.

Artifacts are local and inspectable. Discovery prose is never evidence. Full
coverage requires independent page review; a successful OCR call is not proof.
"""

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

import pypdfium2 as pdfium
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.core.persistence import atomic_json as _atomic_json
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import (
    ingest_page,
    load_pages,
)
from vietnamese_financial_multi_agent.document_processing.understanding_pipeline import (
    UnderstandingOptions,
    run_document_understanding,
)
from vietnamese_financial_multi_agent.document_processing.vision_ocr import (
    QUALITY_REF,
    quality_schema,
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
from vietnamese_financial_multi_agent.evidence.search import EvidenceSearchIndex

LABELS = ("BBS_2025", "BCC_2025", "BCC_2024", "BBS_2022", "BBS_2024")


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(path, payload)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_native_fidelity(rows, record):
    payload = native_payload(record)
    if payload is None:
        raise ValueError("native_payload_required")
    for row in rows:
        value = payload
        try:
            for key in row.sources[0].reference.source_pointer.strip("/").split("/"):
                value = value[int(key)] if isinstance(value, list) else value[key]
        except (KeyError, IndexError, ValueError, TypeError):
            raise ValueError("source_pointer_mismatch") from None
        if row.kind == "text":
            if row.raw_text != value.get("text"):
                raise ValueError("source_text_mismatch")
        else:
            component = row.structure.source_component
            if (component["rows"], component["columns"]) != (value["rows"], value["columns"]):
                raise ValueError("source_table_dimensions_mismatch")
            if len(component["cells"]) != len(value["cells"]):
                raise ValueError("source_table_cells_mismatch")
            for cell, raw in zip(component["cells"], value["cells"], strict=True):
                if (
                    cell["text"],
                    cell["reading"],
                    cell["layout"]["row"],
                    cell["layout"]["column"],
                    cell["geometry"]["candidate_bbox"],
                ) != (raw["text"], raw["reading"], raw["row"], raw["column"], raw["bbox"]):
                    raise ValueError("source_cell_mismatch")


def native_payload(record):
    response = record.get("response") or {}
    output = response.get("output") or {}
    payload = output.get("payload") or {}
    if (
        response.get("finish_reason") == "stop"
        and response.get("status") in {"success", "malformed"}
        and output.get("validation_status") != "invalid_json"
        and isinstance(payload, dict)
        and "text_elements" in payload
    ):
        return payload
    return None


def extraction_complete(record):
    """Structural completion only. Visual/full-prose review remains independent."""
    payload = native_payload(record)
    if payload is None or payload.get("disposition") != "assessed":
        return False
    for table in payload.get("tables", []):
        rows, columns = table.get("rows"), table.get("columns")
        if type(rows) is not int or type(columns) is not int or rows < 1 or columns < 1:
            return False
        positions = [(c.get("row"), c.get("column")) for c in table.get("cells", [])]
        if len(set(positions)) != len(positions) or any(
            type(r) is not int or type(c) is not int or not (0 <= r < rows and 0 <= c < columns)
            for r, c in positions
        ):
            return False
    items = [
        *payload.get("text_elements", []),
        *(c for t in payload.get("tables", []) for c in t.get("cells", [])),
    ]
    return bool(items) and all(i.get("reading") == "observed" for i in items)


def target_pages(label, total):
    if label == "BBS_2022":
        return [11, 18]
    if label == "BBS_2024":
        return [21, 24]
    # Primary financial tables remain accepted; only signature/footer supplements
    # need new textual/layout evidence. Other pages require document extraction.
    primary_without_text_gap = {"BBS_2025": {5}, "BCC_2025": {5}, "BCC_2024": {9}}[label]
    pages = [p for p in range(1, total + 1) if p not in primary_without_text_gap]
    priority = {"BBS_2025": [4, 7, 8], "BCC_2025": [3, 4, 7, 8], "BCC_2024": [7, 8, 11, 12]}[label]
    return priority + [p for p in pages if p not in priority]


def source_caches(root, label):
    company, year = label.split("_")
    paths = []
    if label == "BBS_2025":
        paths += sorted((root / "artifacts/gemini-ingestion/M1-15/pdf").glob("page-*.json"))
    prefix = root / "artifacts/evidence"
    paths += (
        [prefix / f"D-01/{year}/result.json"]
        if company == "BBS"
        else [prefix / f"GEN-01/normalized-release/{label}/result.json"]
    )
    result = []
    for path in paths:
        value = read(path)
        for record in value.get("records", [value]):
            result.append((path, record))
    return result


def build_inventory(root, output, label, manifest, baseline, pdf, targets):
    """Every page is listed, including out-of-scope historical pages."""
    company, year = label.split("_")
    discovery_path = root / f"artifacts/evidence/GEN-01a/{label}/inventory.json"
    if company == "BCC" and discovery_path.exists():
        discovery = read(discovery_path)
        if discovery["document_id"] != manifest.logical_document_id:
            raise ValueError("discovery_document_mismatch")
        discovered = discovery["inventory"]
    else:
        discovered = read(root / f"artifacts/evidence/D-01/{year}/result.json")["inventory"]
    classifications = {r["page"]: r for r in discovered}
    rows = defaultdict(list)
    for row in baseline.evidence:
        rows[row.sources[0].reference.anchor.page.page].append(row)
    cached = defaultdict(list)
    quarantine = []
    for path, record in source_caches(root, label):
        number = record.get("source", {}).get("page", {}).get("page")
        if number is None:
            continue
        try:
            verify_saved_pages(pdf, [record])
        except (ValueError, KeyError) as error:
            quarantine.append(
                dict(source=path.relative_to(root).as_posix(), page=number, reason=str(error))
            )
            continue
        cached[number].append((path, record))
    with pdfium.PdfDocument(pdf) as document:
        total = len(document)
    inventory = []
    for number in range(1, total + 1):
        entries = cached[number]
        native = [(p, r) for p, r in entries if native_payload(r) is not None]
        page_rows = rows[number]
        inventory.append(
            dict(
                page=number,
                classification=classifications.get(number, {}).get("classification"),
                statement_type=classifications.get(number, {}).get("statement_type"),
                discovery_present=number in classifications,
                discovery_is_extraction=False,
                in_scope=number in targets,
                saved_responses=[p.relative_to(root).as_posix() for p, _ in entries],
                unified_page_available=bool(native),
                text_count=sum(r.kind == "text" for r in page_rows),
                table_count=sum(r.kind == "table" for r in page_rows),
                full_prose="not_independently_reviewed" if native else False,
                auditor_opinion="not_reviewed",
                signer_footer="not_reviewed",
                structural_layout="candidate_only" if native else False,
                binding="BOUND" if entries or page_rows else "missing",
                retrievable=bool(page_rows),
                states=(["DISCOVERED"] if number in classifications else [])
                + (["EXTRACTED_PARTIAL"] if entries else [])
                + (["MATERIALIZED", "BOUND", "RETRIEVABLE"] if page_rows else [])
                + (["COVERAGE_GAP"] if number in targets and not native else []),
                needs_gemini=number in targets and not native,
                not_applicable_reason=None
                if number in targets
                else (
                    "historical_page_outside_assigned_prose_gaps"
                    if company == "BBS" and year != "2025"
                    else "accepted_primary_financial_table_no_text_gap_identified"
                ),
            )
        )
    atomic_json(output / label / "baseline-inventory.json", inventory)
    atomic_json(output / label / "quarantine.json", quarantine)
    return inventory, cached


def materialize(root, output, label, pdf, original, repository, selected):
    persisted = {
        r.evidence_identity(): r for r in repository.list_by_document(original.logical_document_id)
    }

    def persist(rows):
        if any(persisted.get(r.evidence_identity()) != r for r in rows):
            repository.put_many(rows)
            persisted.update({r.evidence_identity(): r for r in rows})

    manifest = original.model_copy(deep=True)
    manifest.composition_id = f"EXT-01/{label}/v1"
    summary = []
    # The original composition contains only the selected native BBS pages.
    # Bind the accepted financial page missing from that selection; no OCR or
    # recalculation, and preserve the original record-index source pointers.
    if label == "BBS_2025":
        original_pages = {p.page for source in original.sources for p in source.pages}
        path = root / "artifacts/evidence/D-01/2025/result.json"
        result = read(path)
        records = [
            r
            for r in result["records"]
            if r["source"]["page"]["page"] == 6 and 6 not in original_pages
        ]
        pages = {r["source"]["page"]["page"] for r in records}
        rows = [
            r
            for r in evidence_from_persisted_result(result)
            if r.sources[0].reference.anchor.page.page in pages
        ]
        if rows:
            bindings = verify_saved_pages(pdf, records)
            persist(rows)
            manifest.sources.append(
                CompositionSource(
                    descriptor=SnapshotDescriptor(
                        document_id=rows[0].document_id,
                        snapshot_id=rows[0].snapshot_id,
                        pdf_sha256=original.financial_snapshot.pdf_sha256,
                        origin="original_extraction",
                    ),
                    original_source=path.relative_to(root).as_posix(),
                    artifact_sha256=digest(path),
                    status="verified",
                    pages=bindings,
                    evidence=[
                        EvidencePin(
                            identity=r.evidence_identity(),
                            payload_sha256=payload_sha256(r.model_dump(mode="json")),
                        )
                        for r in rows
                    ],
                )
            )
    for number, (path, record, origin) in selected.items():
        binding = verify_saved_pages(pdf, [record])
        source_path = path.relative_to(root).as_posix()
        # Existing native source already approved: retain exact identity once.
        if any(
            s.original_source == source_path and number in [p.page for p in s.pages]
            for s in original.sources
        ):
            summary.append(
                dict(
                    page=number,
                    origin=origin,
                    source=source_path,
                    existing=True,
                    structural_complete=extraction_complete(record),
                )
            )
            continue
        page = run_document_understanding(
            pdf,
            UnderstandingOptions(
                symbol=label.split("_")[0],
                year=label.split("_")[1],
                pages=(number,),
                dpi=record["provenance"]["render_dpi"],
                persisted_results={number: record},
            ),
        ).pages[0]
        atomic_json(
            output / label / "unified" / f"page-{number}.json", page.model_dump(mode="json")
        )
        review_path = output / label / "quality-reviews.json"
        review = (
            next(
                (
                    r
                    for r in read(review_path)
                    if r["page"] == number and r["response_sha256"] == digest(path)
                ),
                None,
            )
            if review_path.exists()
            else None
        )
        snapshot_id = source_path
        if review and review.get("issues"):
            # Explicit new quality projection; never mutate the saved OCR or a
            # previously pinned identity to attach independent visual caveats.
            snapshot_id += "#quality-review/" + payload_sha256(review)[:12]
            # Retain a resolvable original descriptor without hydrating the
            # unreviewed projection. Only the child evidence pins are selected.
            manifest.sources.append(
                CompositionSource(
                    descriptor=SnapshotDescriptor(
                        document_id=page.identity.source_ref,
                        snapshot_id=source_path,
                        pdf_sha256=original.financial_snapshot.pdf_sha256,
                        origin="original_extraction",
                    ),
                    original_source=source_path,
                    artifact_sha256=digest(path),
                    status="verified",
                    pages=binding,
                    evidence=[],
                )
            )
        rows = evidence_from_unified_page(
            page, document_id=page.identity.source_ref, snapshot_id=snapshot_id
        )
        if review and review.get("issues"):
            for row in rows:
                row.source_metadata["independent_pdf_review"] = review
                row.resolution_issues.extend("pdf_review:" + issue for issue in review["issues"])
        check_native_fidelity(rows, record)
        persist(rows)
        if rows:
            manifest.sources.append(
                CompositionSource(
                    descriptor=SnapshotDescriptor(
                        document_id=page.identity.source_ref,
                        snapshot_id=snapshot_id,
                        pdf_sha256=original.financial_snapshot.pdf_sha256,
                        parent_snapshot_id=source_path if snapshot_id != source_path else None,
                        origin="normalized_projection"
                        if snapshot_id != source_path
                        else "original_extraction",
                    ),
                    original_source=source_path,
                    artifact_sha256=digest(path),
                    status="verified",
                    pages=binding,
                    evidence=[
                        EvidencePin(
                            identity=r.evidence_identity(),
                            payload_sha256=payload_sha256(r.model_dump(mode="json")),
                        )
                        for r in rows
                    ],
                )
            )
        summary.append(
            dict(
                page=number,
                origin=origin,
                source=source_path,
                existing=False,
                structural_complete=extraction_complete(record),
                counts=dict(Counter(r.kind for r in rows)),
                issues=page.issues,
            )
        )
    apply_reviewed_layout(root, output, label, manifest, repository)
    # Full preflight then reload; index is a disposable projection.
    load_composition(
        manifest,
        repository,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    index = EvidenceSearchIndex(
        manifest,
        repository,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    units = index.unit_count
    index.close()
    atomic_json(output / label / "composition.json", manifest.model_dump(mode="json"))
    atomic_json(output / label / "page-results.json", summary)
    return manifest, units


def apply_reviewed_layout(root, output, label, manifest, repository):
    path = output / label / "reviewed-layout.json"
    if not path.exists():
        return
    review = read(path)
    if review["pdf_sha256"] != manifest.financial_snapshot.pdf_sha256:
        raise ValueError("layout_review_pdf_mismatch")
    catalog = load_composition(
        manifest,
        repository,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    candidates = []
    for entry in review["relations"]:
        rendered = root / entry["review_image"]
        if digest(rendered) != entry["review_image_sha256"]:
            raise ValueError("layout_review_image_mismatch")

        def find(pointer, entry=entry):
            matches = [
                r
                for r in catalog.evidence
                if r.kind == "text"
                and r.sources[0].reference.anchor.page.page == entry["page"]
                and r.sources[0].reference.source_pointer == pointer
                and r.snapshot_id == entry["original_snapshot_id"]
            ]
            if len(matches) != 1:
                raise ValueError("layout_review_ambiguous_source")
            return matches[0]

        role, person = find(entry["role_pointer"]), find(entry["person_pointer"])
        candidate = dict(
            entry,
            role_evidence_id=role.evidence_identity().model_dump(mode="json"),
            person_evidence_id=person.evidence_identity().model_dump(mode="json"),
            printed_role=role.raw_text,
            printed_person=person.raw_text,
            status="candidate_not_verified_claim",
            review_source=path.relative_to(root).as_posix(),
        )
        supplement = role.model_copy(deep=True)
        supplement.local_evidence_id += "/EXT-01-layout-v1"
        supplement.structural_role = "signature_relation_candidate"
        supplement.source_metadata["signature_relation_candidate"] = candidate
        supplement.resolution_issues.append("signature_relation_requires_M6_policy")
        repository.put_many([supplement])
        source = next(
            s
            for s in manifest.sources
            if any(p.identity == role.evidence_identity() for p in s.evidence)
        )
        source.evidence.append(
            EvidencePin(
                identity=supplement.evidence_identity(),
                payload_sha256=payload_sha256(supplement.model_dump(mode="json")),
            )
        )
        candidates.append(candidate)
    atomic_json(output / label / "signer-candidates.json", candidates)


def run(root, output, *, live=False, max_pages=100):
    output.mkdir(parents=True, exist_ok=True)
    baseline_root = root / "artifacts/evidence/INT-01a/final"
    before_repo = DocumentEvidenceRepository(baseline_root / "repository")
    repository = DocumentEvidenceRepository(output / "repository")
    service = pool = None
    metrics, calls, started = [], 0, time.monotonic()
    # Existing Free Tier policies, rotation and bounded retries remain authoritative.
    if live:
        service, pool, options = compose_metadata_service(
            SimpleNamespace(root=output), extra_schemas=[(QUALITY_REF, quality_schema())]
        )
        if service is None:
            raise ValueError("existing_gateway_configuration_unavailable")
    try:
        for label in LABELS:
            company, year = label.split("_")
            original = EvidenceComposition.model_validate(
                read(baseline_root / label / "composition.json")
            )
            baseline = load_composition(
                original,
                before_repo,
                document_id=original.logical_document_id,
                composition_id=original.composition_id,
            )
            repository.put_many(baseline.evidence)
            pdfs = list((root / f"data/raw/Financial_Report_pdf/{company}/{year}").glob("*.pdf"))
            if len(pdfs) != 1 or digest(pdfs[0]) != original.financial_snapshot.pdf_sha256:
                raise ValueError("pdf_selection_or_fingerprint_mismatch")
            pdf = pdfs[0]
            with pdfium.PdfDocument(pdf) as document:
                total = len(document)
            targets = target_pages(label, total)
            exemptions_path = output / label / "extraction-exemptions.json"
            exemptions = read(exemptions_path) if exemptions_path.exists() else []
            for exemption in exemptions:
                if (
                    exemption["pdf_sha256"] != original.financial_snapshot.pdf_sha256
                    or digest(root / exemption["review_image"]) != exemption["review_image_sha256"]
                    or exemption["reason"] != "cached_table_and_context_no_missing_prose"
                ):
                    raise ValueError("invalid_extraction_exemption")
                if exemption["page"] in targets:
                    targets.remove(exemption["page"])
            inventory, caches = build_inventory(
                root, output, label, original, baseline, pdf, targets
            )
            for exemption in exemptions:
                inventory[exemption["page"] - 1].update(
                    in_scope=True,
                    needs_gemini=False,
                    full_prose="not_applicable",
                    not_applicable_reason=exemption,
                )
            atomic_json(output / label / "baseline-inventory.json", inventory)
            selected, failures = {}, []
            for number in targets:
                local = output / label / "responses" / f"page-{number}.json"
                selection = output / label / "recovery-selection.json"
                if selection.exists() and str(number) in read(selection):
                    relative = read(selection)[str(number)]
                    local = (output / label / relative).resolve()
                    if not local.is_relative_to((output / label).resolve()):
                        raise ValueError("recovery_selection_outside_document_storage")
                if local.exists():
                    record = read(local)
                    verify_saved_pages(pdf, [record])
                    if native_payload(record) is not None:
                        selected[number] = local, record, "new_extraction"
                    else:
                        failures.append(
                            dict(page=number, reason="saved_failed_response_no_automatic_retry")
                        )
                    continue
                native = [(p, r) for p, r in caches[number] if native_payload(r) is not None]
                if native:
                    if (
                        len({payload_sha256(r["response"]["output"]["payload"]) for _, r in native})
                        > 1
                    ):
                        failures.append(
                            dict(page=number, reason="cache_conflict_requires_selection")
                        )
                    else:
                        selected[number] = (*native[0], "reused_cache")
                    continue
                if not live or calls >= max_pages:
                    failures.append(dict(page=number, reason="live_disabled_or_page_budget"))
                    continue
                print(f"EXT-01 extracting {label}/{number}", flush=True)
                page = load_pages(pdf, symbol=company, year=year, pages=[number])[0]
                render = output / label / "renders" / f"page-{number}.png"
                render.parent.mkdir(parents=True, exist_ok=True)
                if (
                    render.exists()
                    and hashlib.sha256(render.read_bytes()).hexdigest() != page.image.sha256
                ):
                    raise ValueError("render_cache_conflict")
                render.write_bytes(page.image.content)
                tick = time.monotonic()
                footer_only = (label, number) in {
                    ("BBS_2025", 6),
                    ("BCC_2025", 6),
                    ("BCC_2024", 10),
                }
                focus = (
                    (
                        "This is a FOOTER-ONLY supplement to an already accepted financial table. "
                        "Extract only the printed date, signer/footer roles and names, any footer "
                        "sentence and printed page number. Keep roles/names separate with original "
                        "pixel bbox where reliable. Output tables=[]; the financial table is already "
                        "retained unchanged in its original snapshot. Do not infer role-name relations "
                        "or identify handwritten signatures."
                    )
                    if footer_only
                    else None
                )
                record = ingest_page(
                    service,
                    page,
                    credential_ref=options["credential_ref"],
                    document_mode=True,
                    document_focus=focus,
                )
                record["extraction_scope"] = "footer_only" if footer_only else "full_page"
                atomic_json(local, record)  # Save before any adaptation or next call.
                attempts = service.last_attempts
                with (output / "provider-usage.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            dict(
                                document=label,
                                page=number,
                                elapsed_seconds=time.monotonic() - tick,
                                attempts=attempts,
                                response_status=(record.get("response") or {}).get("status"),
                            )
                        )
                        + "\n"
                    )
                calls += 1
                if native_payload(record) is not None:
                    selected[number] = local, record, "new_extraction"
                else:
                    failures.append(dict(page=number, reason="provider_or_structural_failure"))
                time.sleep(4.5)
            tick = time.monotonic()
            manifest, units = materialize(root, output, label, pdf, original, repository, selected)
            after = load_composition(
                manifest,
                repository,
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
            )
            by_page = defaultdict(list)
            for row in after.evidence:
                by_page[row.sources[0].reference.anchor.page.page].append(row)
            for row in inventory:
                number = row["page"]
                records = by_page[number]
                if number in selected:
                    row.update(
                        extraction_source=selected[number][0].relative_to(root).as_posix(),
                        extraction_origin=selected[number][2],
                        structural_complete=extraction_complete(selected[number][1]),
                        extraction_scope=selected[number][1].get("extraction_scope", "full_page"),
                        full_prose="pending_independent_review",
                        states=[
                            "DISCOVERED",
                            "EXTRACTED_PARTIAL",
                            "MATERIALIZED",
                            "BOUND",
                            "RETRIEVABLE",
                        ],
                    )
                row.update(
                    text_count=sum(r.kind == "text" for r in records),
                    table_count=sum(r.kind == "table" for r in records),
                    retrievable=bool(records),
                )
                if number in selected and not records:
                    row["states"] = ["DISCOVERED", "COVERAGE_GAP"]
            reviews_path = output / label / "quality-reviews.json"
            reviews = read(reviews_path) if reviews_path.exists() else []
            for review in reviews:
                number = review["page"]
                if number not in selected:
                    continue
                selected_path = selected[number][0]
                if digest(selected_path) != review["response_sha256"]:
                    continue  # A recovery requires a fresh visual review.
                row = inventory[number - 1]
                row.update(
                    full_prose=review["narrative_complete"],
                    auditor_opinion=review.get("auditor_opinion", False),
                    signer_footer=review.get("signer_footer", False),
                    quality_review=review,
                )
                if review.get("full_content_checked") and review.get("full_content_fidelity"):
                    row["states"] = [s for s in row["states"] if s != "EXTRACTED_PARTIAL"]
                    row["states"].insert(1, "EXTRACTED_FULL")
            atomic_json(output / label / "inventory.json", inventory)
            atomic_json(output / label / "failed-pages.json", failures)
            metric = dict(
                document=label,
                total_pages=total,
                requiring_extraction=len(targets),
                before_pages=len(
                    {r.sources[0].reference.anchor.page.page for r in baseline.evidence}
                ),
                reused_pages=sum(v[2] == "reused_cache" for v in selected.values()),
                newly_extracted_pages=sum(v[2] == "new_extraction" for v in selected.values()),
                missing_pages=[p for p in targets if p not in selected or not by_page[p]],
                partial_pages=[
                    p for p, (_, r, _) in selected.items() if not extraction_complete(r)
                ],
                independently_reviewed_full_pages=0,
                retrievable_pages=sum(bool(rows) for rows in by_page.values()),
                evidence_counts=dict(Counter(r.kind for r in after.evidence)),
                index_units=units,
                materialization_index_seconds=time.monotonic() - tick,
                reporting_scope="consolidated"
                if label == "BCC_2024"
                else ("separate" if label == "BCC_2025" else "unchanged_original_scope"),
            )
            metric.update(
                reused_saved_pages=sorted(
                    {p.page for s in original.sources for p in s.pages}
                    | ({6} if label == "BBS_2025" else set())
                ),
                extraction_not_applicable_pages=[e["page"] for e in exemptions],
                footer_only_pages=[
                    p
                    for p, (_, r, _) in selected.items()
                    if r.get("extraction_scope") == "footer_only"
                ],
                discovered_pages=sum(r["discovery_present"] for r in inventory),
                native_extracted_pages=len(selected),
                narrative_reviewed_pages=[r["page"] for r in inventory if r["full_prose"] is True],
                narrative_retained_pages=[
                    p
                    for p, (_, record, _) in selected.items()
                    if any(
                        len(t.get("text") or "") >= 120
                        for t in native_payload(record).get("text_elements", [])
                    )
                ],
                auditor_opinion_reviewed_pages=[
                    r["page"] for r in inventory if r["auditor_opinion"] is True
                ],
                signer_reviewed_pages=[r["page"] for r in inventory if r["signer_footer"] is True],
                table_pages=[
                    p for p, rows in by_page.items() if any(r.kind == "table" for r in rows)
                ],
                full_extraction_reviewed_pages=[
                    r["page"] for r in inventory if "EXTRACTED_FULL" in r["states"]
                ],
            )
            metric["independently_reviewed_full_pages"] = len(
                metric["full_extraction_reviewed_pages"]
            )
            metrics.append(metric)
            atomic_json(output / "coverage-metrics.json", metrics)
            print(json.dumps(metric), flush=True)
    finally:
        if pool:
            pool.close()
        atomic_json(
            output / "last-run.json",
            dict(page_requests=calls, elapsed_seconds=time.monotonic() - started),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/EXT-01"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()
    if not 0 <= args.max_pages <= 100:
        parser.error(
            "--max-pages must be between 0 and 100; Gateway attempts remain bounded separately"
        )
    run(args.root.resolve(), args.output.resolve(), live=args.live, max_pages=args.max_pages)
