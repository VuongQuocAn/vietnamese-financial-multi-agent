"""Publication boundary uses numeric allowlists, never path-pattern redaction."""

import json

import pytest
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.crop_evidence import (
    COUNT_FIELDS,
    MAPPING_FIELDS,
    public_expansion_statistics,
    public_statistics,
)


@pytest.fixture
def summary():
    return dict(
        **dict.fromkeys(COUNT_FIELDS, 0),
        mapping=dict(**dict.fromkeys(MAPPING_FIELDS, 0), image_failure_counts={}),
        mapping_status={"missing": 1},
        eligibility={"eligible_candidate": 1},
        dry_run_status={"dry_run": 1},
        recovery_status={"recovered": 1},
        rerun_status={"already_recovered": 1},
        issue_counts={"run_identity_unverified": 1},
        reference_types={"table.crop": 1},
        missing_types={"table.crop": 1},
        source_json_unchanged=True,
        source_image_unchanged=True,
        output_validation_passed=True,
        execute=True,
    )


def test_private_fields_have_no_public_channel(summary):
    summary.update(
        original_path="/content/drive/private-id/Financial_Report/x",
        image_bindings={"C:/Users/PRIVATE/file": "private"},
        api_key="SECRET-EXAMPLE",
        ocr_text="private-cell-value",
        sha256="private-hash",
    )
    exported = json.dumps(public_statistics(summary))
    for sensitive in ("/content", "private", "SECRET", "Users", "api_key", "sha256", "ocr_text"):
        assert sensitive not in exported


@pytest.mark.parametrize(
    "value", ["/content/drive/secret", "SECRET-EXAMPLE", "C:/Users/private", -1, True, 1.5, None]
)
def test_injected_statistic_fails_closed(summary, value):
    summary["references_audited"] = value
    with pytest.raises(CropError, match="unsafe_public_statistics"):
        public_statistics(summary)


@pytest.mark.parametrize(
    "field", ["issue_counts", "mapping_status", "recovery_status", "reference_types"]
)
def test_unknown_enum_cannot_leak_path_or_secret(summary, field):
    summary[field]["/content/drive/SECRET-EXAMPLE"] = 1
    with pytest.raises(CropError, match="unsafe_public_statistics"):
        public_statistics(summary)


def test_boolean_is_strict(summary):
    summary["source_json_unchanged"] = "private-path"
    with pytest.raises(CropError):
        public_statistics(summary)


@pytest.fixture
def expansion_summary():
    return dict(
        pages_audited=193,
        references_audited=1557,
        original_missing=572,
        existing_original=985,
        existing_original_tables=180,
        original_table_missing=199,
        eligible=199,
        prior_reconstructed=12,
        reconstructed_available=12,
        missing_unrecovered=187,
        conflicts=0,
        unsupported_views=288,
        non_table_requires_review=85,
        new_outputs=0,
        human_approved=False,
        source_unchanged=True,
        dry_run_status={"already_recovered": 12, "dry_run": 187},
    )


def test_expansion_projection_cannot_publish_private_payload(expansion_summary):
    expansion_summary.update(
        bindings={"/content/drive/private": "secret"},
        recovery_id="private-per-file-hash",
        ocr_text="financial text",
    )
    public = json.dumps(public_expansion_statistics(expansion_summary))
    assert all(s not in public for s in ("private", "financial text", "secret", "drive"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("eligible", "private-path"),
        ("eligible", True),
        ("eligible", -1),
        ("human_approved", "secret"),
        ("dry_run_status", {"/private-path": 1}),
    ],
)
def test_expansion_projection_injection_fails_closed(expansion_summary, field, value):
    expansion_summary[field] = value
    with pytest.raises(CropError, match="unsafe_public_statistics"):
        public_expansion_statistics(expansion_summary)
