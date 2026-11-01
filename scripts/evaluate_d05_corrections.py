"""Đánh giá D-05 có giới hạn; dữ liệu BBS chỉ ở runner, không trong runtime."""

import argparse
import json
import os
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pypdfium2 as pdfium
from evaluate_d01_coverage import ROLES, persist
from evaluate_d04_closure import save
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    EXTRACTION_REF,
    ExtractedPage,
    extraction_schema_registry,
    run_automated_pdf,
)
from vietnamese_financial_multi_agent.accounting.completeness import (
    SourceRow,
    SourceRowInventory,
    assess_row_completeness,
)
from vietnamese_financial_multi_agent.accounting.extraction_semantics import numeric_token_issues
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.accounting.raw_corrections import extraction_payload
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    DerivedMetric,
    DocumentEvidenceRepository,
    EvidenceGraph,
    build_graph,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    trace_metric_lineage,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
    source_review_status,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    PreparationApproval,
    PreparedFormulaPolicy,
)
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog, SnapshotDescriptor
from vietnamese_financial_multi_agent.evidence.source_reviews import bind_source_review


def manifest(root):
    paths = set(load(root / "artifacts/evidence/D-04-review/hashes-before.json"))
    for folder in ("D-04-review",):
        paths.update(
            p.relative_to(root).as_posix()
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return {p: digest(root / p) for p in sorted(paths)}


def prepare(root, output):
    if output.exists():
        raise ValueError("Use a new ignored output directory")
    output.mkdir(parents=True)
    save(output / "hashes-before.json", manifest(root))
    inventory = load(root / "artifacts/evidence/D-01/inventory.json")
    renders = []
    for year, numbers in ((2021, (6, 7)), (2023, (5,)), (2024, (9, 25)), (2025, (7, 23))):
        row = next(r for r in inventory if r["year"] == year)
        assert digest(root / row["pdf"]) == row["sha256"]
        with pdfium.PdfDocument(root / row["pdf"]) as pdf:
            for number in numbers:
                page = pdf[number - 1]
                bitmap = page.render(scale=1.5)
                name = f"source-{year}-{number}.png"
                try:
                    bitmap.to_pil().save(output / name)
                finally:
                    bitmap.close()
                    page.close()
                renders.append(
                    dict(
                        document_id="sha256:" + row["sha256"],
                        pdf_sha256=row["sha256"],
                        pdf_page=number,
                        reference=name,
                        image_sha256=digest(output / name),
                    )
                )
    save(output / "renders.json", renders)
    print(json.dumps(dict(prepared=True, source_pages=len(renders))))


def recover(root, output):
    """One full-table recovery on the faulty page, no other live page requests."""
    path = output / "recovery-extraction.json"
    if path.exists():
        raise ValueError("Recovery already exists; evaluate it without another live call")
    assert manifest(root) == load(output / "hashes-before.json")
    row = next(
        r for r in load(root / "artifacts/evidence/D-01/inventory.json") if r["year"] == 2024
    )
    assert digest(root / row["pdf"]) == row["sha256"]
    # Existing launcher convention; never read/print keys here.
    if not os.environ.get("GEMINI_API_KEY_FILE") and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY_FILE"] = str(root / "src/api/api_key/api_gemini.txt")
    os.environ["WEB_GEMINI_MAX_ATTEMPTS"] = "1"
    (output / "gateway").mkdir(exist_ok=True)
    service, pool, options = compose_metadata_service(SimpleNamespace(root=output / "gateway"))
    if service is None:
        raise ValueError("existing_gateway_configuration_unavailable")
    try:
        record = run_automated_pdf(
            root / row["pdf"],
            symbol="BBS",
            year="2024",
            pages=[9],
            service=service,
            credential_ref=options["credential_ref"],
        )[0]
        save(path, record)
        save(output / "gateway-usage.json", service.last_attempts)
        print(
            json.dumps(
                dict(
                    status=record["response"]["status"],
                    finish_reason=record["response"]["finish_reason"],
                    usage=record["response"]["usage"],
                )
            )
        )
    finally:
        pool.close()


def evaluate(root, output):
    before_hashes = load(output / "hashes-before.json")
    assert manifest(root) == before_hashes
    base = root / "artifacts/evidence/D-01/evaluation"
    inventory = load(base.parent / "inventory.json")
    results = {r["year"]: load(base / str(r["year"]) / "normalized-result.json") for r in inventory}
    raw_recovery = load(output / "recovery-extraction.json")
    assert raw_recovery["response"]["status"] == "success"
    renders = {(r["document_id"], r["pdf_page"]): r for r in load(output / "renders.json")}
    for render in renders.values():
        assert digest(output / render["reference"]) == render["image_sha256"]
    source = results[2024]["records"][2]
    assert source["source"]["page"]["page"] == 9
    original_page = ExtractedPage(**source["response"]["output"]["payload"])
    # Controlled visual read of the full source table, including the terminal row.
    # Reuse transcribed labels only after comparison to source-2024-9.png.
    table = original_page.tables[0]
    source_rows = []
    for row in sorted({c.row for c in table.cells}):
        label = next(c.text for c in table.cells if c.row == row and c.column == table.label_column)
        code = next(c.text for c in table.cells if c.row == row and c.column == table.code_column)
        source_rows.append(
            SourceRow(
                label=label, code=code, selector=f"PDF:p9/table0/code:{code}", value_columns=[3, 4]
            )
        )
    source_rows.append(
        SourceRow(
            label="18. Lãi cơ bản trên cổ phiếu",
            code="70",
            selector="PDF:p9/table0/terminal-code:70",
            value_columns=[3, 4],
        )
    )
    render = renders[(results[2024]["document_id"], 9)]
    source_inventory = SourceRowInventory(
        document_id=results[2024]["document_id"],
        pdf_page=9,
        table=0,
        statement_type="B02",
        source_reference=render["reference"],
        source_image_sha256=render["image_sha256"],
        method="controlled_original_pdf_visual_read",
        full_table=True,
        terminal_boundary_observed=True,
        rows=source_rows,
    )
    original_image = load_pages(
        root / next(r["pdf"] for r in inventory if r["year"] == 2024),
        symbol="BBS",
        year="2024",
        pages=[9],
    )[0].image
    coverage_before = assess_row_completeness(
        original_page, original_image.identity, source_inventory
    )
    assert coverage_before["status"] == "rows_missing"
    assert [r["code"] for r in coverage_before["rows"] if r["status"] == "row_missing"] == ["70"]
    # First-loss evidence: raw JSON == parsed payload; rendered input binding is exact.
    diagnostics = []
    for year, number in ((2024, 9), (2023, 5)):
        record = next(r for r in results[year]["records"] if r["source"]["page"]["page"] == number)
        output_record = record["response"]["output"]
        assert json.loads(output_record["raw_text"]) == output_record["payload"]
        assert extraction_schema_registry().is_valid(EXTRACTION_REF, output_record["payload"])
        diagnostics.append(
            dict(
                year=year,
                pdf_page=number,
                request_id=record["response"]["request_id"],
                raw_text_equals_payload=True,
                schema_valid=True,
                finish_reason=record["response"]["finish_reason"],
                usage=record["response"]["usage"],
                limitations=output_record["payload"]["limitations"],
                first_observed_defect="model_response_before_json_parsing",
                historical_request="prompt/schema reconstructible from accepted code; exact request envelope not retained",
            )
        )
    (
        corrected_results,
        corrected_facts,
        corrected_evidence,
        descriptors,
        counts,
        removed,
        corrections,
    ) = [], [], [], [], [], [], []
    baseline_facts, baseline_evidence = [], []
    for row in inventory:
        year = row["year"]
        old = results[year]
        old_facts = CanonicalFactRepository(base / str(year) / "canonical").list_by_document(
            old["document_id"], old["attempt_id"]
        )
        baseline_facts.extend(old_facts)
        baseline_evidence.extend(evidence_from_persisted_result(old))
        descriptors.append(
            SnapshotDescriptor(
                document_id=old["document_id"],
                pdf_sha256=row["sha256"],
                snapshot_id=old["attempt_id"],
                origin="normalized_projection",
            )
        )
        records = deepcopy(old["records"])
        for i, record in enumerate(records):
            number = record["source"]["page"]["page"]
            if year == 2023 and number == 5:
                page = record["response"]["output"]["payload"]
                for ti, table in enumerate(page["tables"]):
                    for ci, cell in enumerate(table["cells"]):
                        if cell["column"] not in {3, 4} or not numeric_token_issues(cell["text"]):
                            continue
                        review = renders[(old["document_id"], number)]
                        correction = dict(
                            document_id=old["document_id"],
                            pdf_page=number,
                            request_id=record["response"]["request_id"],
                            selector=f"/tables/{ti}/cells/{ci}",
                            original_raw_value=cell["text"],
                            corrected_raw_value="-",
                            review_reference=review["reference"],
                            review_image_sha256=review["image_sha256"],
                            method="controlled_original_pdf_visual_read",
                        )
                        record.setdefault("raw_corrections", []).append(correction)
                        corrections.append(correction)
            if year == 2024 and number == 9:
                record = deepcopy(raw_recovery)
                raw_table = record["response"]["output"]["payload"]["tables"][0]
                cells = raw_table["headers"] + raw_table["cells"]
                corrected_bounds = dict(
                    rows=max(c["row"] for c in cells) + 1,
                    columns=max(c["column"] for c in cells) + 1,
                )
                if corrected_bounds != {k: raw_table[k] for k in ("rows", "columns")}:
                    record["structure_corrections"] = [
                        dict(
                            document_id=old["document_id"],
                            pdf_page=number,
                            request_id=record["response"]["request_id"],
                            table=0,
                            original_bounds={k: raw_table[k] for k in ("rows", "columns")},
                            corrected_bounds=corrected_bounds,
                            review_reference=render["reference"],
                            review_image_sha256=render["image_sha256"],
                            method="controlled_original_pdf_visual_read",
                        )
                    ]
            records[i] = run_automated_pdf(
                root / row["pdf"],
                symbol=record["source"]["page"]["symbol"],
                year=record["source"]["page"]["year"],
                pages=[number],
                cached_records={number: record},
                source_inventories={number: source_inventory}
                if year == 2024 and number == 9
                else None,
            )[0]
            projected = records[i]
            new_slots = {
                (link["table"], link["row"], link["column"])
                for link in projected["extraction"]["links"]
            }
            for link in old["records"][i]["extraction"]["links"]:
                if (link["table"], link["row"], link["column"]) in new_slots:
                    continue
                structure = projected["extraction"]["structure"]
                col_role = next(
                    (
                        s["role"]
                        for s in structure
                        if s.get("table") == link["table"] and s.get("column") == link["column"]
                    ),
                    "unknown",
                )
                role = (
                    col_role
                    if col_role != "financial_value"
                    else next(
                        (
                            s["role"]
                            for s in structure
                            if s.get("table") == link["table"] and s.get("row") == link["row"]
                        ),
                        "unknown",
                    )
                )
                removed.append(dict(year=year, page=number, role=role, link=link))
                assert role not in {"financial_item", "subtotal"}, "financial_row_removed"
        quality = assess_evidence_for_task(evidence_from_automated_records(records))
        result = dict(
            old,
            attempt_id="D-05/corrected-v1",
            parent_snapshot_id=old["attempt_id"],
            records=records,
            quality=quality.model_dump(mode="json"),
            semantics_version="financial-table-semantics-v1",
        )
        facts = facts_from_persisted_result(
            result, company_id=old["metadata_binding"]["company_id"]
        )
        for fact in facts:
            fact.semantic_role = ROLES.get(fact.canonical_item_id)

        def key(f):
            return (
                f.context.statement_type,
                f.source_item_code,
                f.context.raw_item_label,
                f.raw_header,
            )

        old_by_key = {key(f): f for f in old_facts}
        changed = []
        for f in facts:
            prior = old_by_key.get(key(f))
            if prior:
                assert prior.value.normalized_value == f.value.normalized_value
                assert prior.context.period == f.context.period
                if prior.value != f.value:
                    changed.append(
                        dict(
                            before=prior.observation_identity().model_dump(),
                            after=f.observation_identity().model_dump(),
                            old_value=prior.value.model_dump(mode="json"),
                            new_value=f.value.model_dump(mode="json"),
                        )
                    )
        mapped_old = {key(f) for f in old_facts if f.canonical_item_id and f.context.period}
        assert mapped_old <= {key(f) for f in facts if f.canonical_item_id}
        counts.append(
            dict(
                year=year,
                before=len(old_facts),
                after=len(facts),
                removed=sum(r["year"] == year for r in removed),
                removed_by_role=dict(Counter(r["role"] for r in removed if r["year"] == year)),
                changes=changed,
            )
        )
        corrected_results.append(result)
        corrected_facts.extend(facts)
        corrected_evidence.extend(evidence_from_persisted_result(result))
        descriptors.append(
            SnapshotDescriptor(
                document_id=old["document_id"],
                pdf_sha256=row["sha256"],
                snapshot_id=result["attempt_id"],
                parent_snapshot_id=old["attempt_id"],
                origin="recovery" if year == 2024 else "normalized_projection",
            )
        )
    assert len(corrections) == 5
    recovered = next(
        r for r in corrected_results if r["document_id"] == results[2024]["document_id"]
    )
    recovery_record = next(r for r in recovered["records"] if r["source"]["page"]["page"] == 9)
    coverage_after = recovery_record["extraction"]["completeness"]
    assert coverage_after["status"] == "covered", coverage_after
    eps = [
        f
        for f in corrected_facts
        if f.document_id == recovered["document_id"]
        and f.context.statement_type == "B02"
        and f.source_item_code == "70"
    ]
    assert sorted((f.context.period, f.value.raw_value, f.value.unit) for f in eps) == [
        ("2023", "917", "VND/share"),
        ("2024", "1.032", "VND/share"),
    ]
    eps_reviews = []
    for fact in eps:
        reading = dict(
            observation=fact.observation_identity(),
            pdf_sha256=fact.document_id.removeprefix("sha256:"),
            pdf_page=9,
            review_image_sha256=render["image_sha256"],
            review_reference=render["reference"],
            method="controlled_original_pdf_visual_read",
            level="value_row_verified",
            raw_value=fact.value.raw_value,
            raw_label=fact.context.raw_item_label,
            raw_header=fact.raw_header,
            period=fact.context.period,
            statement_type="B02",
        )
        eps_reviews.append(bind_source_review(fact, reading, extraction_payload(recovery_record)))
    correction_reviews = []
    corrected_2023 = next(
        r for r in corrected_results if r["document_id"] == results[2023]["document_id"]
    )
    correction_record = next(
        r for r in corrected_2023["records"] if r["source"]["page"]["page"] == 5
    )
    for correction in corrections:
        fact = next(
            f
            for f in corrected_facts
            if f.document_id == correction["document_id"]
            and any(
                s.reference.source_pointer == correction["selector"]
                and s.reference.anchor.page.page == 5
                for s in f.sources
            )
        )
        assert fact.value.normalized_value is None and fact.value.raw_value == "-"
        reading = dict(
            observation=fact.observation_identity(),
            pdf_sha256=fact.document_id.removeprefix("sha256:"),
            pdf_page=5,
            review_image_sha256=correction["review_image_sha256"],
            review_reference=correction["review_reference"],
            method="controlled_original_pdf_visual_read",
            level="value_row_verified",
            raw_value=fact.value.raw_value,
            raw_label=fact.context.raw_item_label,
            raw_header=fact.raw_header,
            period=fact.context.period,
            statement_type="B01",
        )
        correction_reviews.append(
            bind_source_review(fact, reading, extraction_payload(correction_record))
        )
    # Rebuild accepted D-04 catalog with the current runtime; no extraction/review inheritance.
    previous = root / "artifacts/evidence/D-04-review"
    recovery_descriptor = next(
        SnapshotDescriptor(**d)
        for d in load(previous / "snapshots.json")
        if d.get("parent_snapshot_id")
    )
    descriptors.append(recovery_descriptor)
    recovery_facts = CanonicalFactRepository(previous / "canonical").list_by_document(
        recovery_descriptor.document_id, recovery_descriptor.snapshot_id
    )
    recovery_evidence = DocumentEvidenceRepository(previous / "document-evidence").list_by_document(
        recovery_descriptor.document_id, recovery_descriptor.snapshot_id
    )
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m))
        for m in load(base / "metrics.json") + load(previous / "metrics.json")
    ]
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for path in (
            root / "artifacts/evidence/D-02/source-reviews.json",
            root / "artifacts/evidence/D-02/recovery-source-reviews.json",
            previous / "source-reviews.json",
        )
        for r in load(path)
    ]
    bases = [
        AccountingBasisReview(**b)
        for path in (
            root / "artifacts/evidence/D-02/accounting-basis-reviews.json",
            previous / "accounting-basis-reviews.json",
        )
        for b in load(path)
    ]
    registry = load(root / "configs/d02-analytical-policies.json")
    accepted_facts, accepted_evidence = (
        baseline_facts + recovery_facts,
        baseline_evidence + recovery_evidence,
    )
    accepted_graph = build_graph(accepted_facts, accepted_evidence, metrics)
    assert accepted_graph == EvidenceGraph.model_validate_json(
        (previous / "graph.json").read_text(encoding="utf-8")
    )
    catalog = SnapshotCatalog(
        descriptors,
        accepted_facts + corrected_facts,
        accepted_evidence + corrected_evidence,
        metrics,
        graph=build_graph(
            accepted_facts + corrected_facts, accepted_evidence + corrected_evidence, metrics
        ),
        source_reviews=reviews + eps_reviews + correction_reviews,
        accounting_bases=bases,
        approval=PreparationApproval(**registry["preparation_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in registry["formula_policies"]],
    )
    prior_catalog = load(previous / "catalog.json")
    for entry in prior_catalog:
        selected = catalog.select(
            entry["descriptor"]["document_id"], entry["descriptor"]["snapshot_id"]
        )
        assert selected.candidates[0].model_dump(mode="json") == entry
    assert len(baseline_facts) == 981
    assert all(
        catalog.api.get_fact(f.observation_identity()).matches[0].record == f
        for f in accepted_facts
    )
    assert [
        trace_metric_lineage(
            m, accepted_graph, accepted_facts, accepted_evidence, expected_formula=m.definition
        ).model_dump(mode="json")
        for m in metrics[:15]
    ] == load(base / "lineages.json")
    # Persist only after all before/after assertions; repositories reject identity conflicts.
    for result in corrected_results:
        folder = output / next(
            str(y) for y, old in results.items() if old["document_id"] == result["document_id"]
        )
        folder.mkdir(exist_ok=True)
        save(folder / "normalized-result.json", result)
        selected_facts = [f for f in corrected_facts if f.document_id == result["document_id"]]
        repo = CanonicalFactRepository(folder / "canonical")
        for fact in selected_facts:
            persist(repo, fact)
        assert repo.list_by_document(result["document_id"], result["attempt_id"]) == selected_facts
        evidence_repo = DocumentEvidenceRepository(folder / "document-evidence")
        selected_evidence = [
            e for e in corrected_evidence if e.document_id == result["document_id"]
        ]
        for e in selected_evidence:
            persist(evidence_repo, e)
        assert (
            evidence_repo.list_by_document(result["document_id"], result["attempt_id"])
            == selected_evidence
        )
    for name, value in (
        ("source-inventory.json", source_inventory.model_dump(mode="json")),
        ("coverage.json", dict(before=coverage_before, after=coverage_after)),
        ("root-cause.json", diagnostics),
        ("raw-corrections.json", corrections),
        ("projection-counts.json", counts),
        ("removed-slots.json", removed),
        (
            "source-reviews.json",
            [r.model_dump(mode="json") for r in eps_reviews + correction_reviews],
        ),
        ("snapshots.json", [d.model_dump(mode="json") for d in descriptors]),
        (
            "catalog.json",
            [
                catalog.select(d.document_id, d.snapshot_id).candidates[0].model_dump(mode="json")
                for d in descriptors
            ],
        ),
    ):
        save(output / name, value)
    assert before_hashes == manifest(root)
    summary = dict(
        baseline_observations=len(baseline_facts),
        corrected_observations=len(corrected_facts),
        removed_by_role=dict(Counter(r["role"] for r in removed)),
        added_eps_slots=len(eps),
        raw_corrections=len(corrections),
        coverage_before=coverage_before["status"],
        coverage_after=coverage_after["status"],
        baseline_metrics_ready=sum(
            e["preparation_ready_metrics"]
            for e in prior_catalog
            if not e["descriptor"]["parent_snapshot_id"]
        ),
        d04_recovery_ready=sum(
            e["preparation_ready_metrics"]
            for e in prior_catalog
            if e["descriptor"]["parent_snapshot_id"]
        ),
        baseline_lineages_exact=15,
        baseline_graph_exact=True,
        baseline_exact_lookups=len(accepted_facts),
        corrected_restart_exact=True,
        input_hashes=len(before_hashes),
        input_hashes_unchanged=True,
        gateway_attempts=len(load(output / "gateway-usage.json")),
        usage=raw_recovery["response"]["usage"],
        financial_fact_verified=False,
        scope="targeted source checks only; no full-PDF accuracy/restatement approval",
    )
    save(output / "hashes-after.json", manifest(root))
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def review_persisted(root, source, output):
    """Reconcile exact slots and revalidate cached evidence; zero live calls/writes to inputs."""
    if output.exists():
        raise ValueError("Use a new review output directory")
    output.mkdir(parents=True)
    before = manifest(root)
    assert before == load(source / "hashes-before.json") == load(source / "hashes-after.json")
    source_hashes = {
        p.relative_to(source).as_posix(): digest(p) for p in source.rglob("*") if p.is_file()
    }
    base = root / "artifacts/evidence/D-01/evaluation"
    inventory = load(base.parent / "inventory.json")
    source_inventory = SourceRowInventory(**load(source / "source-inventory.json"))
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(source / "source-reviews.json")
    ]
    removed, added, kept, counts, facts, evidence, new_facts, new_evidence = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for entry in inventory:
        year = entry["year"]
        assert digest(root / entry["pdf"]) == entry["sha256"]
        old = load(base / str(year) / "normalized-result.json")
        new = load(source / str(year) / "normalized-result.json")
        old_facts = CanonicalFactRepository(base / str(year) / "canonical").list_by_document(
            old["document_id"], old["attempt_id"]
        )
        selected_facts = CanonicalFactRepository(source / str(year) / "canonical").list_by_document(
            new["document_id"], new["attempt_id"]
        )
        assert len(old_facts) == len(old["quality"]["items"])
        assert (
            new["parent_snapshot_id"] == old["attempt_id"]
            and new["attempt_id"] != old["attempt_id"]
        )
        old_index = {f.local_observation_id: f for f in old_facts}
        new_index = {f.local_observation_id: f for f in selected_facts}
        assert len(old_index) == len(old_facts) and len(new_index) == len(selected_facts)
        before_counts, after_counts = Counter(), Counter()
        for prior, current in zip(old["records"], new["records"], strict=True):
            page = prior["source"]["page"]["page"]
            bound = run_automated_pdf(
                root / entry["pdf"],
                symbol=prior["source"]["page"]["symbol"],
                year=prior["source"]["page"]["year"],
                pages=[page],
                cached_records={page: current},
                source_inventories={page: source_inventory}
                if (old["document_id"], page)
                == (source_inventory.document_id, source_inventory.pdf_page)
                else None,
            )[0]
            assert bound["extraction"] == current["extraction"], "cached_projection_drift"
            assert current["source"] == prior["source"]
            original_response = current["response"] == prior["response"]
            assert (
                original_response
                or current["response"] == load(source / "recovery-extraction.json")["response"]
            )

            def slots(record):
                result = {}
                for index, link in enumerate(record["extraction"]["links"]):
                    key = (link["table"], link["row"], link["column"])
                    assert key not in result
                    result[key] = (index, link)
                return result

            old_slots, new_slots = slots(prior), slots(current)

            def category(key, current=current):
                table, row, column = key
                structure = current["extraction"]["structure"]
                col_role = next(
                    (
                        s["role"]
                        for s in structure
                        if s.get("table") == table and s.get("column") == column
                    ),
                    "unknown",
                )
                role = (
                    col_role
                    if col_role != "financial_value"
                    else next(
                        (
                            s["role"]
                            for s in structure
                            if s.get("table") == table and s.get("row") == row
                        ),
                        "unknown",
                    )
                )
                return (
                    "financial"
                    if role in {"financial_item", "subtotal"}
                    else "note"
                    if role == "note_reference"
                    else "header"
                    if role == "column_header"
                    else "structural"
                ), role

            for key, (index, link) in old_slots.items():
                group, role = category(key)
                before_counts[group] += 1
                original = old_index[f"{old['document_id']}/page/{page}/link/{index}"]
                identity = original.observation_identity().model_dump(mode="json")
                if key not in new_slots:
                    assert group != "financial", "removed_financial_slot"
                    removed.append(
                        dict(
                            year=year,
                            pdf_page=page,
                            observation=identity,
                            table=key[0],
                            row=key[1],
                            column=key[2],
                            role=role,
                            category=group,
                            raw_label=link["raw_label"],
                            raw_header=link["raw_header"],
                            raw_value=link["raw_value"],
                            source_item_code=link["source_item_code"],
                            source_selectors=[s.reference.source_pointer for s in original.sources],
                        )
                    )
                else:
                    updated = new_index[
                        f"{new['document_id']}/page/{page}/link/{new_slots[key][0]}"
                    ]
                    assert updated.value.normalized_value == original.value.normalized_value
                    assert updated.context.period == original.context.period
                    assert updated.source_item_code == original.source_item_code
                    assert updated.context.raw_item_label == original.context.raw_item_label
                    assert updated.raw_header == original.raw_header
                    assert [s.reference for s in updated.sources] == [
                        s.reference for s in original.sources
                    ]
                    assert updated.canonical_item_id == original.canonical_item_id
                    assert updated.value.unit == original.value.unit or (
                        original.source_item_code == "70" and updated.value.unit == "VND/share"
                    )
                    kept.append(
                        dict(
                            before=identity,
                            after=updated.observation_identity().model_dump(mode="json"),
                        )
                    )
            for key, (index, _) in new_slots.items():
                after_counts[category(key)[0]] += 1
                if key not in old_slots:
                    fact = new_index[f"{new['document_id']}/page/{page}/link/{index}"]
                    assert fact.source_item_code == "70" and fact.context.statement_type == "B02"
                    review = next(
                        r for r in reviews if r.observation == fact.observation_identity()
                    )
                    assert (
                        bind_source_review(
                            fact,
                            review.model_dump(
                                exclude={
                                    "sources",
                                    "value_selector",
                                    "label_selector",
                                    "header_selector",
                                }
                            ),
                            extraction_payload(current),
                        )
                        == review
                    )
                    added.append(
                        dict(
                            observation=fact.observation_identity().model_dump(mode="json"),
                            pdf_page=page,
                            label=fact.context.raw_item_label,
                            code=fact.source_item_code,
                            period=fact.context.period,
                            raw_header=fact.raw_header,
                            value=fact.value.model_dump(mode="json"),
                            review=review.model_dump(mode="json"),
                        )
                    )
        assert (
            assess_evidence_for_task(evidence_from_automated_records(new["records"])).model_dump(
                mode="json"
            )
            == new["quality"]
        )
        counts.append(dict(year=year, before=dict(before_counts), after=dict(after_counts)))
        facts.extend(old_facts)
        evidence.extend(evidence_from_persisted_result(old))
        new_facts.extend(selected_facts)
        stored_evidence = DocumentEvidenceRepository(
            source / str(year) / "document-evidence"
        ).list_by_document(new["document_id"], new["attempt_id"])
        assert stored_evidence == evidence_from_persisted_result(new)
        new_evidence.extend(stored_evidence)
    assert len(facts) == 981 and len(new_facts) == 910 and len(kept) == 908
    assert len(removed) == 73 and len(added) == 2
    assert sorted(
        (a["period"], a["value"]["normalized_value"], a["value"]["unit"]) for a in added
    ) == [("2023", "917", "VND/share"), ("2024", "1032", "VND/share")]
    verified_corrections = []
    new_index = {f.observation_identity(): f for f in new_facts}
    for correction in load(source / "raw-corrections.json"):
        review = next(
            r
            for r in reviews
            if r.pdf_sha256 == correction["document_id"].removeprefix("sha256:")
            and r.value_selector == correction["selector"]
            and r.pdf_page == correction["pdf_page"]
        )
        fact = new_index[review.observation]
        assert source_review_status(fact, reviews) == "value_row_verified"
        assert fact.value.raw_value == "-" and fact.value.normalized_value is None
        original = next(
            r
            for r in load(base / "2023/normalized-result.json")["records"]
            if r["source"]["page"]["page"] == correction["pdf_page"]
        )
        corrected = next(
            r
            for r in load(source / "2023/normalized-result.json")["records"]
            if r["source"]["page"]["page"] == correction["pdf_page"]
        )
        assert original["response"] == corrected["response"]
        assert (
            json.loads(original["response"]["output"]["raw_text"])
            == original["response"]["output"]["payload"]
        )
        assert original["response"]["request_id"] == correction["request_id"]
        assert digest(source / review.review_reference) == review.review_image_sha256
        assert (
            bind_source_review(
                fact,
                review.model_dump(
                    exclude={"sources", "value_selector", "label_selector", "header_selector"}
                ),
                extraction_payload(corrected),
            )
            == review
        )
        verified_corrections.append(
            dict(
                correction=correction,
                observation=review.observation.model_dump(mode="json"),
                raw_label=review.raw_label,
                raw_header=review.raw_header,
                period=review.period,
                value_selector=review.value_selector,
                label_selector=review.label_selector,
                header_selector=review.header_selector,
                original_response_preserved=True,
                normalized_value=None,
            )
        )
    assert len(verified_corrections) == 5
    for review in reviews:
        assert digest(source / review.review_reference) == review.review_image_sha256
        assert source_review_status(new_index[review.observation], reviews) == "value_row_verified"
    previous = root / "artifacts/evidence/D-04-review"
    descriptors = [SnapshotDescriptor(**d) for d in load(previous / "snapshots.json")]
    target = next(d for d in descriptors if d.parent_snapshot_id)
    facts.extend(
        CanonicalFactRepository(previous / "canonical").list_by_document(
            target.document_id, target.snapshot_id
        )
    )
    evidence.extend(
        DocumentEvidenceRepository(previous / "document-evidence").list_by_document(
            target.document_id, target.snapshot_id
        )
    )
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m))
        for path in (base / "metrics.json", previous / "metrics.json")
        for m in load(path)
    ]
    accepted_reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for path in (
            root / "artifacts/evidence/D-02/source-reviews.json",
            root / "artifacts/evidence/D-02/recovery-source-reviews.json",
            previous / "source-reviews.json",
        )
        for r in load(path)
    ]
    bases = [
        AccountingBasisReview(**b)
        for path in (
            root / "artifacts/evidence/D-02/accounting-basis-reviews.json",
            previous / "accounting-basis-reviews.json",
        )
        for b in load(path)
    ]
    policy = load(root / "configs/d02-analytical-policies.json")
    graph = build_graph(facts, evidence, metrics)
    assert graph == EvidenceGraph.model_validate_json(
        (previous / "graph.json").read_text(encoding="utf-8")
    )
    catalog = SnapshotCatalog(
        descriptors,
        facts,
        evidence,
        metrics,
        graph=graph,
        source_reviews=accepted_reviews,
        accounting_bases=bases,
        approval=PreparationApproval(**policy["preparation_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in policy["formula_policies"]],
    )
    entries = [
        catalog.select(d.document_id, d.snapshot_id).candidates[0].model_dump(mode="json")
        for d in descriptors
    ]
    assert entries == load(previous / "catalog.json")
    assert [
        trace_metric_lineage(m, graph, facts, evidence, expected_formula=m.definition).model_dump(
            mode="json"
        )
        for m in metrics[:15]
    ] == load(base / "lineages.json")
    assert [
        catalog.reviewed_lineage(target, m.metric_id).model_dump(mode="json") for m in metrics[15:]
    ] == load(previous / "lineages.json")
    all_descriptors = [SnapshotDescriptor(**d) for d in load(source / "snapshots.json")]
    combined = SnapshotCatalog(
        all_descriptors,
        facts + new_facts,
        evidence + new_evidence,
        metrics,
        graph=graph,
        source_reviews=accepted_reviews + reviews,
    )
    for descriptor in all_descriptors:
        assert combined.select(descriptor.document_id).status == "ambiguous"
        assert combined.select(descriptor.document_id, descriptor.snapshot_id).status == "selected"
    assert manifest(root) == before
    assert source_hashes == {
        p.relative_to(source).as_posix(): digest(p) for p in source.rglob("*") if p.is_file()
    }
    summary = dict(
        original=981,
        financial_retained=908,
        removed=73,
        added=2,
        corrected=910,
        net_decrease=71,
        counts=counts,
        baseline_preparation_ready=sum(
            e["preparation_ready_metrics"]
            for e in entries
            if not e["descriptor"]["parent_snapshot_id"]
        ),
        recovery_preparation_ready=sum(
            e["preparation_ready_metrics"] for e in entries if e["descriptor"]["parent_snapshot_id"]
        ),
        baseline_lineages_exact=15,
        recovery_lineages_exact=3,
        graph_exact=True,
        catalog_exact=True,
        cached_pages_revalidated=20,
        source_reviews_exact=7,
        original_responses_unchanged=True,
        input_hashes_unchanged=len(before),
        d05_input_files_unchanged=len(source_hashes),
        gateway_attempts=0,
    )
    assert (
        summary["baseline_preparation_ready"] == 15 and summary["recovery_preparation_ready"] == 3
    )
    for name, value in (
        ("summary.json", summary),
        ("removed-observations.json", removed),
        ("retained-bindings.json", kept),
        ("eps-proof.json", added),
        ("raw-correction-proof.json", verified_corrections),
        ("catalog.json", entries),
        ("hashes-before.json", before),
        ("hashes-after.json", manifest(root)),
        ("d05-input-hashes.json", source_hashes),
    ):
        save(output / name, value)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-05-review"))
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--recover-live", action="store_true")
    parser.add_argument("--review-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / args.output).resolve().is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    if args.review_output:
        review_output = (root / args.review_output).resolve()
        if not review_output.is_relative_to(root / "artifacts/evidence"):
            raise ValueError("Review output must stay under artifacts/evidence")
        review_persisted(root, root / args.output, review_output)
    elif args.prepare:
        prepare(root, root / args.output)
    elif args.recover_live:
        recover(root, root / args.output)
    else:
        evaluate(root, root / args.output)
