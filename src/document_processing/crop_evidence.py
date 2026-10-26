"""Allowlisted aggregate projection; never publish private manifests verbatim."""

from .crop_audit import CropError

COUNT_FIELDS = (
    "target_pages",
    "pages_audited",
    "references_audited",
    "missing_references",
    "unique_missing_paths",
    "contextual_missing_paths",
    "eligible_candidates",
    "requires_review",
    "baseline_missing_occurrences",
    "baseline_selected",
    "pilot_selected",
    "output_validations",
    "source_json_files_hashed",
    "source_image_files_hashed",
)
MAPPING_FIELDS = (
    "source_root_candidates",
    "mappings_verified",
    "mappings_rejected",
    "ambiguous_prefixes",
    "positive_controls",
    "negative_controls",
    "image_bindings_verified",
    "discovery_failures",
)
STATUSES = {"existing", "missing", "unmapped", "ambiguous", "unsafe"}
ELIGIBILITY = {
    "not_needed",
    "requires_review",
    "eligible_candidate",
    "unsupported_view",
    "invalid_bbox",
    "source_image_missing",
}
RECOVERY = {
    "dry_run",
    "recovered",
    "already_recovered",
    "output_conflict",
    "ineligible",
    "pilot_cap_reached",
    "source_changed",
    "io_error",
    "output_validation_failed",
}
ISSUES = {
    "missing_target",
    "run_identity_unverified",
    "unverified_color_transformation",
    "unverified_crop_region",
    "source_identity_mismatch",
    "source_identity_unverified",
    "source_image_missing",
    "requires_review",
    "coordinate_dimensions_mismatch",
    "invalid_bbox",
    "image_decode_failed",
    "oversized_file",
    "oversized_image",
    "unsupported_image_mode",
}
TYPES = {
    f"{kind}.{field}"
    for kind in ("table", "signature", "seal", "seal_signature_region", "checkbox", "red_mark")
    for field in ("crop", "ink_view_crop", "black_view_crop", "red_view_crop", "blue_view_crop")
}


def count(value):
    if type(value) is not int or value < 0:
        raise CropError("unsafe_public_statistics")
    return value


def counts(value, allowed):
    if type(value) is not dict or not set(value).issubset(allowed):
        raise CropError("unsafe_public_statistics")
    return {key: count(n) for key, n in sorted(value.items())}


def public_statistics(summary):
    """Only fixed keys, strict integers/booleans and known enum keys cross boundary.

    Private paths, bindings, per-file hashes, text and arbitrary strings have no
    output channel. Unknown issue/type keys fail closed instead of being echoed.
    """
    result = {key: count(summary[key]) for key in COUNT_FIELDS}
    result["mapping"] = {key: count(summary["mapping"][key]) for key in MAPPING_FIELDS}
    for key, allowed in (
        ("mapping_status", STATUSES),
        ("eligibility", ELIGIBILITY),
        ("dry_run_status", RECOVERY),
        ("recovery_status", RECOVERY),
        ("rerun_status", RECOVERY),
        ("issue_counts", ISSUES),
        ("missing_types", TYPES),
        ("reference_types", TYPES),
    ):
        result[key] = counts(summary[key], allowed)
    result["mapping"]["image_failure_counts"] = counts(
        summary["mapping"]["image_failure_counts"], ISSUES
    )
    for key in (
        "source_json_unchanged",
        "source_image_unchanged",
        "output_validation_passed",
        "execute",
    ):
        if type(summary[key]) is not bool:
            raise CropError("unsafe_public_statistics")
        result[key] = summary[key]
    return result


def public_expansion_statistics(summary):
    """Fixed numeric/boolean projection for M1-03f; no source strings or hashes."""
    result = {
        key: count(summary[key])
        for key in (
            "pages_audited",
            "references_audited",
            "original_missing",
            "existing_original",
            "existing_original_tables",
            "original_table_missing",
            "eligible",
            "prior_reconstructed",
            "reconstructed_available",
            "missing_unrecovered",
            "conflicts",
            "unsupported_views",
            "non_table_requires_review",
            "new_outputs",
        )
    }
    for key in ("human_approved", "source_unchanged"):
        if type(summary[key]) is not bool:
            raise CropError("unsafe_public_statistics")
        result[key] = summary[key]
    result["dry_run_status"] = counts(summary["dry_run_status"], RECOVERY)
    return result
