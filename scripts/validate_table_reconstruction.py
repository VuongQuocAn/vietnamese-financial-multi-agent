"""M1-12: read-only validation, tối đa bốn pages trong frozen M1-04b manifest."""

import argparse
import json
from collections import Counter
from pathlib import Path

from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.checkpoints import fingerprint_json
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    DocumentClassification,
    DocumentUnderstandingResult,
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding_validation import (
    validate_understanding_quality,
)
from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRTable
from vietnamese_financial_multi_agent.document_processing.crop_expansion import write_once
from vietnamese_financial_multi_agent.document_processing.extraction_artifacts import (
    read_local_evidence,
)
from vietnamese_financial_multi_agent.document_processing.extraction_pilot import (
    parse_manifest,
    snapshot,
    verify_bindings,
)
from vietnamese_financial_multi_agent.document_processing.ocr_loader import load_ocr_page
from vietnamese_financial_multi_agent.document_processing.path_resolver import resolve_path
from vietnamese_financial_multi_agent.document_processing.table_reconstruction import (
    reconstruct_table,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/extraction-validation/M1-04b/manifest.json"),
    )
    parser.add_argument("--page-indices", type=int, nargs="+", default=[0, 2, 4, 5])
    args = parser.parse_args()
    indices = args.page_indices
    if not 1 <= len(indices) <= 4 or len(set(indices)) != len(indices) or min(indices) < 0:
        parser.error("Select one to four distinct nonnegative manifest indices")
    config = load_data_config()
    path = args.manifest.absolute()
    manifest_payload = read_local_evidence(path, config)
    manifest = parse_manifest(manifest_payload, config)
    if max(indices) >= len(manifest.pages):
        parser.error("Manifest index out of range")
    verify_bindings(manifest, config)
    expected = {s.path: s.model_dump(mode="json") for s in manifest.snapshots}
    captured = {}
    for evidence_path in manifest.evidence_paths.values():
        current = snapshot(Path(evidence_path), config)
        if current != expected[evidence_path]:
            raise ValueError("Frozen evidence changed")
        captured[evidence_path] = current
    records, statuses, codes, du_codes = [], Counter(), Counter(), Counter()
    for index in indices:
        selected = manifest.pages[index]
        request = selected.request.model_copy(deep=True)
        target = resolve_path(request, config).confirmed_target
        if target is None:
            raise ValueError("Selected source unresolved")
        source = config.get_root(target.root_key) / target.relative_suffix
        current = snapshot(source, config)
        if current != expected.get(str(source)):
            raise ValueError("Frozen source changed")
        captured[str(source)] = current
        request.reference.source_ref = request.reference.original_path
        symbol, year, number = selected.identity
        identity = RawPageIdentity(
            symbol=symbol,
            year=year,
            page=number,
            image=selected.image_reference,
            source_ref=request.reference.source_ref,
        )
        request.reference.anchor = SourceAnchor(page=identity, status="unresolved")
        loaded = load_ocr_page(request, config)
        before = fingerprint_json(loaded.page.export_source())
        results = [
            reconstruct_table(loaded.page, table.id, source_ref=identity.source_ref)
            for table in loaded.page.elements
            if isinstance(table, OCRTable)
        ]
        du = DocumentUnderstandingResult(
            contract_version="document_understanding_v1",
            raw_page=identity,
            classification=DocumentClassification(label=None, status="unresolved", anchors=[]),
            text_regions=[],
            tables=results,
            issues=[],
        )
        quality = validate_understanding_quality(du, raw_page=loaded.page)
        du_codes.update(issue.code for issue in quality)
        statuses.update(table.status for table in results)
        codes.update(issue.code for table in results for issue in table.issues)
        if fingerprint_json(loaded.page.export_source()) != before:
            raise ValueError("In-memory source mutation")
        records.append(
            dict(
                manifest_index=index,
                source_digest=before,
                result=du.export_result(),
                quality_issues=[issue.model_dump(mode="json") for issue in quality],
            )
        )
    summary = dict(
        pages=len(indices),
        tables=sum(statuses.values()),
        statuses=dict(statuses),
        issue_occurrences=dict(codes),
        du_quality_occurrences=dict(du_codes),
        api_requests=0,
        ground_truth="not_supplied",
    )

    def verify():
        if read_local_evidence(path, config) != manifest_payload:
            raise ValueError("Frozen manifest changed")
        for source_path, before in captured.items():
            if snapshot(Path(source_path), config) != before:
                raise ValueError("Selected input changed")

    verify()
    # Fixed ignored destination; same source protection/write-once as approved pilot.
    output = config.project_root / "artifacts/table-reconstruction/M1-12/validation.json"
    for source_root in (config.financial_ocr_dir, config.financial_report_dir):
        if output.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("Output overlaps source root")
    write_once(
        output,
        dict(
            protocol="table_structure_validation_v1",
            source_manifest=manifest.manifest_id,
            snapshots=list(captured.values()),
            summary=summary,
            records=records,
        ),
    )
    verify()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
