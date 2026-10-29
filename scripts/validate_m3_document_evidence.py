"""Read-only targeted real-artifact validation; không chạy M1/M2 pipeline hoặc LLM.

Chi tiết nguồn/output nằm trong artifacts ignored. PDF visual review là bước riêng,
script này không được tự gọi provenance/accuracy PASS từ JSON selectors.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedDocument,
)
from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    EvidenceConflict,
    evidence_from_persisted_result,
    evidence_from_unified_page,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer_value(payload, pointer):
    value = payload
    for key in pointer.lstrip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    hashes, inventory, groups, failures = {}, [], [], []

    def read(path):
        hashes[path.relative_to(root).as_posix()] = digest(path)
        return json.loads(path.read_text(encoding="utf-8-sig"))

    pdf = root / "data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf"
    hashes[pdf.relative_to(root).as_posix()] = digest(pdf)
    raw_pages = {}
    for path in sorted(
        (root / "data/processed/Financial_Report_OCR/BBS/2025/ocr_json").glob("*.json")
    ):
        raw = read(path)
        raw_pages[raw["page"]["page"]] = raw
        inventory.append(
            dict(
                source=path.relative_to(root).as_posix(),
                family="raw_ocr",
                content=True,
                page=raw["page"]["page"],
                texts=sum(e["type"] == "text" for e in raw["elements"]),
                tables=sum(e["type"] == "table" for e in raw["elements"]),
                adapter="unsupported_direct_input_inventory_only",
            )
        )
    native_sources = {}
    for path in sorted((root / "artifacts/gemini-ingestion/M1-15/pdf").glob("page-*.json")):
        raw = read(path)
        payload = (raw.get("response") or {}).get("output", {}).get("payload")
        number = int(path.stem.split("-")[-1])
        native_sources[number] = payload
        inventory.append(
            dict(
                source=path.relative_to(root).as_posix(),
                family="m1_native_raw",
                page=number,
                content=isinstance(payload, dict),
                texts=len((payload or {}).get("text_elements", [])),
                tables=len((payload or {}).get("tables", [])),
                adapter="via_existing_unified_export_only",
            )
        )
    for name in ("existing", "native"):
        path = root / f"artifacts/document-understanding/M1-16/{name}.json"
        raw = read(path)
        document = UnifiedDocument.model_validate_json(json.dumps(raw))
        pages, evidence = [], []
        for page in document.pages:
            # Native export có PDF fingerprint; existing OCR chỉ manifest pointer,
            # chưa có document binding: giữ None/quarantine, không gán PDF identity.
            document_id = page.identity.source_ref if name == "native" else None
            try:
                converted = evidence_from_unified_page(
                    page, document_id=document_id, snapshot_id=path.relative_to(root).as_posix()
                )
                evidence.extend(converted)
                source = (
                    raw_pages[page.identity.page]
                    if name == "existing"
                    else native_sources[page.identity.page]
                )
                pages.append((page, converted, source))
            except Exception as error:
                failures.append(
                    dict(
                        source=str(path.relative_to(root)),
                        page=page.identity.page,
                        stage="conversion",
                        error=type(error).__name__,
                    )
                )
        inventory.append(
            dict(
                source=path.relative_to(root).as_posix(),
                family="unified",
                content=True,
                pages=[p.identity.page for p in document.pages],
                texts=sum(len(p.text_regions) for p in document.pages),
                tables=sum(len(p.tables) for p in document.pages),
            )
        )
        groups.append((f"m1-{name}", evidence, pages))
    for family in ("storage", "fresh-storage"):
        paths = sorted((root / f"artifacts/w07/{family}").rglob("result.json"))
        for path in paths:
            raw = read(path)
            inventory.append(
                dict(
                    source=path.relative_to(root).as_posix() + "#/inventory",
                    family="discovery_inventory",
                    content=False,
                    pages=len(raw["inventory"]),
                    notes_pages=sum(p.get("statement_type") == "B09" for p in raw["inventory"]),
                )
            )
            try:
                evidence = evidence_from_persisted_result(raw)
            except Exception as error:
                failures.append(
                    dict(
                        source=str(path.relative_to(root)),
                        stage="conversion",
                        error=type(error).__name__,
                    )
                )
                evidence = []
            inventory.append(
                dict(
                    source=path.relative_to(root).as_posix(),
                    family="web_snapshot",
                    content=True,
                    records=len(raw["records"]),
                    pages=[r["source"]["page"]["page"] for r in raw["records"]],
                    texts=sum(
                        len(r["response"]["output"]["payload"]["context"]) for r in raw["records"]
                    ),
                    tables=sum(
                        len(r["response"]["output"]["payload"]["tables"]) for r in raw["records"]
                    ),
                )
            )
            groups.append((f"w07-{family}", evidence, raw))
        for path in sorted((root / f"artifacts/w07/{family}").rglob("document.json")):
            raw = read(path)
            inventory.append(
                dict(
                    source=path.relative_to(root).as_posix(),
                    family="document_metadata",
                    content=False,
                    keys=list(raw),
                )
            )

    # Inventory bổ sung: không tính copies/caches thành evidence mới đã convert.
    extra_paths = [
        *root.glob("artifacts/**/result.json"),
        *root.glob("artifacts/item-mapping/M2-04b/*/page-*.json"),
        *root.glob("artifacts/evaluation/M2-09/extraction/page-*.json"),
    ]
    for path in sorted(extra_paths):
        if path.relative_to(root).as_posix() in hashes:
            continue
        raw = read(path)
        records = raw.get("records", [raw] if "response" in raw else [])
        inventory.append(
            dict(
                source=path.relative_to(root).as_posix(),
                family="financial_inventory_only",
                content=bool(records),
                records=len(records),
                texts=sum(
                    len(
                        r.get("response", {})
                        .get("output", {})
                        .get("payload", {})
                        .get("context", [])
                    )
                    for r in records
                ),
                tables=sum(
                    len(
                        r.get("response", {}).get("output", {}).get("payload", {}).get("tables", [])
                    )
                    for r in records
                ),
            )
        )
    quality_path = root / "artifacts/quality/M2-07/review/quality.json"
    quality = read(quality_path)
    inventory.append(
        dict(
            source=quality_path.relative_to(root).as_posix(),
            family="financial_quality_projection",
            content=False,
            observations=len(quality["direct"]["items"]),
        )
    )
    counts = Counter()
    levels, issues, group_results, identities = Counter(), Counter(), [], set()
    for name, evidence, source_data in groups:
        repo = DocumentEvidenceRepository(output / name)
        local = Counter()
        quarantine = []
        for item in evidence:
            local["converted"] += 1
            local[item.kind] += 1
            identity = item.evidence_identity()
            if identity is not None:
                if identity in identities:
                    failures.append(dict(group=name, stage="identity", error="duplicate_identity"))
                identities.add(identity)
            else:
                quarantine.append(item)
            sources = [*item.sources, *getattr(item, "member_sources", [])]
            for source in sources:
                ref = source.reference
                levels[ref.provenance_level] += 1
                local["references"] += 1
                local["uncertain_references"] += ref.anchor.status != "resolved"
                local["missing_raw_anchor_ids"] += not any(
                    (
                        ref.anchor.element_id,
                        ref.anchor.table_id,
                        ref.anchor.cell_id,
                        ref.anchor.line_id,
                    )
                )
                unsupported = ref.provenance_level == "cell" and not (
                    ref.anchor.table_id and ref.anchor.cell_id
                )
                unsupported |= ref.provenance_level == "element" and not (
                    ref.anchor.element_id or ref.anchor.table_id or ref.anchor.line_id
                )
                local["unsupported_level"] += unsupported
                try:
                    if name.startswith("w07"):
                        record = source_data["records"][item.source_metadata["record_index"]]
                        payload = record["response"]["output"]["payload"]
                        page = record["source"]["page"]
                    else:
                        selected = next(p for p in source_data if item in p[1])
                        payload, page = selected[2], selected[0].identity.model_dump(mode="json")
                    value = pointer_value(payload, ref.source_pointer)
                    assert ref.anchor.page.model_dump(mode="json") == page
                    if item.kind == "text":
                        assert item.raw_text == (
                            value.get("text") if isinstance(value, dict) else value
                        )
                    if name == "m1-existing":
                        if ref.anchor.cell_id:
                            assert ref.anchor.cell_id == value["id"]
                        elif ref.anchor.table_id or ref.anchor.element_id:
                            assert (ref.anchor.table_id or ref.anchor.element_id) == value["id"]
                    local["source_selector_resolved"] += 1
                except Exception as error:
                    failures.append(
                        dict(
                            group=name,
                            identity=identity.model_dump() if identity else None,
                            stage="source_selector",
                            pointer=ref.source_pointer,
                            error=type(error).__name__,
                        )
                    )
            issues.update(item.resolution_issues)
            if item.kind == "table":
                issues.update(item.structural_issues)
            try:
                outcome = repo.put(item)
                local[outcome] += 1
                expected = "quarantined" if identity is None else "idempotent"
                assert repo.put(item) == expected
                local["duplicate_payload_preserved"] += 1
                if identity is not None:
                    restored = DocumentEvidenceRepository(repo.root).get(identity)
                    assert restored.model_dump_json() == item.model_dump_json()
                    local["indexed_restart_exact"] += 1
            except Exception as error:
                failures.append(dict(group=name, stage="persistence", error=type(error).__name__))
            try:
                pointer = item.sources[0].reference.source_pointer
                if name.startswith("w07"):
                    payload = source_data["records"][item.source_metadata["record_index"]][
                        "response"
                    ]["output"]["payload"]
                    original = pointer_value(payload, pointer)
                    assert (
                        item.raw_text
                        if item.kind == "text"
                        else item.structure.model_dump(mode="json")
                    ) == original
                else:
                    original_page = next(p[0] for p in source_data if item in p[1])
                    if item.kind == "table":
                        original = next(
                            t for t in original_page.tables if t.source_pointer == pointer
                        )
                        assert item.structure.model_dump_json() == original.model_dump_json()
                    else:
                        original = next(
                            t for t in original_page.text_regions if t.source_pointer == pointer
                        )
                        assert item.source_metadata["unified_region"] == original.model_dump(
                            mode="json"
                        )
                local["source_representation_exact"] += 1
            except Exception as error:
                failures.append(
                    dict(group=name, stage="source_representation", error=type(error).__name__)
                )
        restored_quarantine = DocumentEvidenceRepository(repo.root).list_quarantine()
        assert [e.model_dump_json() for e in restored_quarantine] == [
            e.model_dump_json() for e in quarantine
        ]
        local["quarantine_restart_exact"] = len(quarantine)
        for document_id in {e.document_id for e in evidence if e.document_id}:
            for snapshot_id in {e.snapshot_id for e in evidence if e.document_id == document_id}:
                expected = [
                    e
                    for e in evidence
                    if (e.document_id, e.snapshot_id) == (document_id, snapshot_id)
                ]
                assert (
                    DocumentEvidenceRepository(repo.root).list_by_document(document_id, snapshot_id)
                    == expected
                )
                local["list_retrieved"] += len(expected)
        for kind in ("text", "table"):
            original = next((e for e in evidence if e.kind == kind and e.evidence_identity()), None)
            if original is not None:
                altered = original.model_copy(deep=True)
                altered.source_metadata["validation_conflict_probe"] = True
                try:
                    repo.put(altered)
                    failures.append(dict(group=name, stage="conflict", error="silent_overwrite"))
                except EvidenceConflict:
                    assert repo.get(original.evidence_identity()) == original
                    local["conflict_rejected"] += 1
        counts.update(local)
        group_results.append(dict(group=name, counts=dict(local)))
        print(name, dict(local), flush=True)
    for relative, before in hashes.items():
        assert digest(root / relative) == before, relative
    report = dict(
        inventory=inventory,
        hashes=hashes,
        groups=group_results,
        counts=dict(counts),
        provenance_levels=dict(levels),
        issue_counts=dict(issues),
        failures=failures,
        sources_unchanged=True,
        pdf_grounded_validation="NOT_VERIFIED_BY_THIS_SCRIPT",
        evidence_accuracy="NOT_VERIFIED_BY_THIS_SCRIPT",
    )
    (output / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("TOTAL", dict(counts), "failures", len(failures), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.root.resolve(), args.output.resolve())
    raise SystemExit(bool(result["failures"]))
