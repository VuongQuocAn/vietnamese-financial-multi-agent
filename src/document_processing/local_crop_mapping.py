"""Verified local bindings for a bounded inventory run; no Drive identity claim."""

import json
from collections import Counter, defaultdict

from .contracts.path_mapping import PathRootMapping
from .contracts.path_mapping_validation import map_path_lexically
from .crop_audit import CROP_FIELDS, CropError, digest, read_image, reference_request
from .ocr_loader import load_ocr_page
from .path_resolver import resolve_path

MARKERS = {
    "raw_page_image": ("Financial_Report", "FINANCIAL_REPORT_DIR"),
    "ocr_crop": ("Financial_Report_OCR", "FINANCIAL_OCR_DIR"),
}


def candidate_mapping(original: str, category: str) -> PathRootMapping:
    """Extract one full exact root; marker discovery alone grants no approval."""
    marker, key = MARKERS[category]
    parts = original.split("/")
    indices = [i for i, part in enumerate(parts) if part in {m[0] for m in MARKERS.values()}]
    if len(indices) != 1 or parts[indices[0]] != marker:
        raise CropError("unknown_or_ambiguous_root")
    root = "/".join(parts[: indices[0] + 1])
    mapping = PathRootMapping(
        mapping_id="local-" + digest([category, root])[:16],
        source_root=root,
        path_style="posix",
        destination_root_key=key,
        category=category,
        containment_policy="lexical_then_runtime",
    )
    result = map_path_lexically(
        reference_request(original, category, "local-verification", ["reference"], [mapping])
    )
    if result.status != "not_checked":
        raise CropError("unsafe_source_reference")
    return mapping


def manifest_mapping() -> PathRootMapping:
    return PathRootMapping(
        mapping_id="development-manifest-local-binding",
        source_root="processed/Financial_Report_OCR",
        path_style="posix",
        destination_root_key="FINANCIAL_OCR_DIR",
        category="ocr_page_json",
        containment_policy="lexical_then_runtime",
    )


def page_request(row):
    return reference_request(
        row["source"], "ocr_page_json", "M1-01/page_manifest", ["source"], [manifest_mapping()]
    )


def expected_suffix(row, category):
    symbol, year, number = row["symbol"], row["year"], row["page"]
    if category == "raw_page_image":
        return f"{symbol}/{year}/page_{number}.png"
    return f"{symbol}/{year}/ocr_crops/page_{number}/"


def verify_local_mappings(rows, config):
    """Verify exact inventory/metadata/relative identity, containment and dimensions.

    All observed references in a prefix must pass contextual checks, with at least
    one existing positive control. Cross-prefix target collisions fail closed.
    Individual image bindings additionally require decoded dimensions to match.
    Returns private evidence; callers must keep it in ignored local artifacts.
    """
    groups = defaultdict(list)
    failures, page_checks, source_snapshots = [], [], {}
    for row in rows:
        request = page_request(row)
        loaded = load_ocr_page(request, config)
        page = loaded.page
        identity = (row["symbol"], row["year"], row["page"])
        # The inventory source context is independent of the OCR page metadata.
        expected_source = (
            f"processed/Financial_Report_OCR/{identity[0]}/{identity[1]}"
            f"/ocr_json/page_{identity[2]}.json"
        )
        if (
            row["source"] != expected_source
            or (page.page.symbol, page.page.year, page.page.page) != identity
        ):
            failures.append({"source": row["source"], "code": "source_identity_mismatch"})
            continue
        refs = [(page.page.image, "raw_page_image")]
        refs.extend(
            (value, "ocr_crop")
            for element in page.elements
            for field in CROP_FIELDS
            if isinstance(value := element.model_dump(exclude_unset=True).get(field), str)
        )
        for original, category in refs:
            try:
                mapping = candidate_mapping(original, category)
            except CropError as error:
                failures.append({"source": row["source"], "code": error.code})
                continue
            req = reference_request(original, category, row["source"], ["reference"], [mapping])
            result = resolve_path(req, config)
            suffix = original[len(mapping.source_root) + 1 :]
            expected = expected_suffix(row, category)
            context_ok = (
                suffix == expected
                if category == "raw_page_image"
                else (suffix.startswith(expected) and len(suffix) > len(expected))
            )
            entry = dict(
                original=original,
                category=category,
                identity=identity,
                source=row["source"],
                suffix=suffix,
                mapping=mapping,
                status=result.status,
                context_ok=context_ok,
            )
            groups[mapping.mapping_id].append(entry)
        page_checks.append((row, page))

    colliding = set()
    targets = defaultdict(set)
    for mapping_id, entries in groups.items():
        for entry in entries:
            targets[(entry["category"], entry["suffix"])].add(mapping_id)
    for ids in targets.values():
        if len(ids) > 1:
            colliding.update(ids)
    verified, evidence = [], []
    for mapping_id, entries in sorted(groups.items()):
        positives = [e for e in entries if e["status"] == "resolved" and e["context_ok"]]
        accepted = (
            bool(positives)
            and mapping_id not in colliding
            and all(e["context_ok"] and e["status"] in {"resolved", "missing"} for e in entries)
        )
        mapping = entries[0]["mapping"]
        evidence.append(
            dict(
                mapping_id=mapping_id,
                verified_local_mapping=accepted,
                positive_controls=len(positives),
                positive_groups=sorted({e["identity"][:2] for e in positives}),
                collision=mapping_id in colliding,
            )
        )
        if accepted:
            verified.append(mapping)
    bindings, image_evidence = {}, []
    for row, page in page_checks:
        identity = (row["symbol"], row["year"], row["page"])
        original = page.page.image
        req = reference_request(
            original, "raw_page_image", row["source"], ["page", "image"], verified
        )
        result = resolve_path(req, config)
        code = "source_identity_unverified"
        if result.status == "missing":
            code = "source_image_missing"
        elif result.status == "resolved":
            target = result.confirmed_target
            if target.relative_suffix == expected_suffix(row, "raw_page_image"):
                path = config.get_root(target.root_key) / target.relative_suffix
                before = path.stat()
                try:
                    image, hashed = read_image(req, config)
                    with image:
                        matches = image.size == (page.page.width, page.page.height)
                    if matches:
                        bindings[original] = identity
                        code = "verified_local_page_identity"
                    else:
                        code = "coordinate_dimensions_mismatch"
                    source_snapshots[original] = dict(
                        size=before.st_size,
                        mtime_ns=before.st_mtime_ns,
                        inode=before.st_ino,
                        sha256=hashed,
                        root_key=target.root_key,
                        relative_suffix=target.relative_suffix,
                    )
                except CropError as error:
                    code = error.code
        image_evidence.append(dict(source=row["source"], image=original, code=code))
    # Negative controls use foreign symbol/year while preserving the basename and
    # remaining suffix. They query only exact targets, never search for a match.
    negative = []
    for mapping in verified:
        control = next(e for e in groups[mapping.mapping_id] if e["status"] == "resolved")
        parts = control["suffix"].split("/")
        for index, replacement in ((0, "M1_03E_NEGATIVE_CONTROL"), (1, "0000")):
            changed = parts.copy()
            changed[index] = replacement
            original = mapping.source_root + "/" + "/".join(changed)
            result = resolve_path(
                reference_request(
                    original, mapping.category, "negative-control", ["reference"], verified
                ),
                config,
            )
            negative.append(result.status == "missing")
    if negative and not all(negative):
        raise CropError("negative_control_failed")
    return dict(
        mappings=[m.model_dump() for m in verified],
        image_bindings=bindings,
        mapping_evidence=evidence,
        image_evidence=image_evidence,
        discovery_failures=failures,
        source_snapshots=source_snapshots,
        verification_level="verified_local_page_identity",
        original_drive_identity_verified=False,
        run_identity=None,
        statistics=dict(
            source_root_candidates=len(groups),
            mappings_verified=len(verified),
            mappings_rejected=len(groups) - len(verified),
            ambiguous_prefixes=len(colliding),
            positive_controls=sum(
                e["positive_controls"] for e in evidence if e["verified_local_mapping"]
            ),
            negative_controls=len(negative),
            image_bindings_verified=len(bindings),
            discovery_failures=len(failures),
            image_failure_counts=dict(
                Counter(
                    e["code"] for e in image_evidence if e["code"] != "verified_local_page_identity"
                )
            ),
        ),
    )


def save_private_bindings(path, bindings):
    """Idempotent exclusive artifact; changed evidence requires a new location."""
    content = json.dumps(bindings, ensure_ascii=False, sort_keys=True, indent=2).encode()
    if path.exists():
        if path.read_bytes() != content:
            raise CropError("local_bindings_conflict")
        return "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
    return "created"
