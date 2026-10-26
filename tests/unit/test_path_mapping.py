"""Fixtures synthetic; không đọc dataset hoặc kiểm tra file tồn tại."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.document_processing.contracts import (
    OCRPageMetadata,
    OCRTable,
    PathMappingIssue,
    PathMappingRequest,
    PathMappingResult,
    PathMappingStructuralError,
    RawPageIdentity,
    SourceAnchor,
    map_path_lexically,
    parse_path_mapping_request,
    parse_path_mapping_result,
    path_mapping_json_schema,
    validate_path_mapping_result,
)


@pytest.fixture
def payload():
    return {
        "contract_version": "path_mapping_v1",
        "reference": {
            "original_path": "/synthetic/drive/Financial_Report_OCR/CTY/2025/ảnh gốc #1.png",
            "category": "ocr_crop",
            "source_ref": "synthetic-run/page.json",
            "source_location": ["elements", 0, "crop"],
        },
        "mappings": [
            {
                "mapping_id": "ocr",
                "source_root": "/synthetic/drive/Financial_Report_OCR",
                "path_style": "posix",
                "destination_root_key": "FINANCIAL_OCR_DIR",
                "category": "ocr_crop",
                "containment_policy": "lexical_then_runtime",
            }
        ],
    }


def test_request_round_trip(payload):
    model = parse_path_mapping_request(payload)
    assert model.export_result() == payload
    assert (
        PathMappingRequest.model_validate_json(
            model.model_dump_json(exclude_unset=True)
        ).export_result()
        == payload
    )


@pytest.mark.parametrize("key", ["contract_version", "reference", "mappings"])
def test_required_fields(payload, key):
    del payload[key]
    with pytest.raises(PathMappingStructuralError) as caught:
        parse_path_mapping_request(payload)
    assert caught.value.issues[0].path == (key,)
    assert caught.value.payload == payload


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("original_path", 12),
        ("category", "crop"),
        ("source_ref", None),
        ("source_location", [True]),
    ],
)
def test_strict_reference(payload, key, value):
    payload["reference"][key] = value
    with pytest.raises(PathMappingStructuralError) as caught:
        parse_path_mapping_request(payload)
    assert caught.value.issues[0].path[:2] == ("reference", key)
    payload["reference"][key] = "modified"
    assert caught.value.payload["reference"][key] == value


@pytest.mark.parametrize("location", ["root", "reference", "mapping"])
def test_extra_fields(payload, location):
    target = {
        "root": payload,
        "reference": payload["reference"],
        "mapping": payload["mappings"][0],
    }[location]
    target["unknown"] = 1
    with pytest.raises(PathMappingStructuralError):
        parse_path_mapping_request(payload)


@pytest.mark.parametrize("field", ["anchor", "crop_view", "candidate_page_image"])
def test_missing_and_null(payload, field):
    assert field not in parse_path_mapping_request(payload).export_result()["reference"]
    payload["reference"][field] = None
    assert parse_path_mapping_request(payload).export_result() == payload


@pytest.mark.parametrize(
    "status", ["not_checked", "resolved", "missing", "ambiguous", "unsafe", "unmapped"]
)
def test_result_status_serialization(payload, status):
    data = {
        "contract_version": "path_mapping_v1",
        "reference": payload["reference"],
        "status": status,
        "candidate_targets": [],
        "existence_check": "not_checked",
        "containment_check": "not_checked",
        "issues": [],
    }
    # Structural parse không thay thế quality/status validation.
    assert PathMappingResult.model_validate(data).export_result() == data
    data["status"] = "invented"
    with pytest.raises(ValidationError):
        PathMappingResult.model_validate(data)


def test_version_and_mapping_types(payload):
    bad = deepcopy(payload)
    bad["contract_version"] = "path_mapping_v2"
    with pytest.raises(PathMappingStructuralError):
        parse_path_mapping_request(bad)
    payload["mappings"][0]["mapping_id"] = 1
    with pytest.raises(PathMappingStructuralError) as caught:
        parse_path_mapping_request(payload)
    assert caught.value.issues[0].path == ("mappings", 0, "mapping_id")


def test_schema_sync():
    artifact = Path(__file__).resolve().parents[2] / "schemas/path_mapping_v1.schema.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == path_mapping_json_schema()


def mapped(payload):
    return map_path_lexically(parse_path_mapping_request(payload))


def test_colab_candidate_preserves_context(payload):
    payload["reference"]["original_path"] = (
        "/content/drive/synthetic/Financial_Report_OCR/A/2025/crops/ảnh #1.png"
    )
    payload["mappings"][0]["source_root"] = "/content/drive/synthetic/Financial_Report_OCR"
    payload["reference"]["anchor"] = {
        "page": {"symbol": "SYN", "year": "2025", "page": 1, "image": "page.png"},
        "table_id": "t1",
        "cell_id": "c1",
        "observed_bbox": [1, 2, 20, 30],
        "status": "unresolved",
    }
    payload["reference"]["crop_view"] = "red"
    payload["reference"]["candidate_page_image"] = "synthetic/page.png"
    before = deepcopy(payload)
    result = mapped(payload)
    assert result.status == "not_checked"
    assert result.confirmed_target is None
    assert result.existence_check == result.containment_check == "not_checked"
    assert result.reference.export_result() == payload["reference"]
    assert result.candidate_targets[0].relative_suffix == "A/2025/crops/ảnh #1.png"
    assert result.candidate_targets[0].root_key == "FINANCIAL_OCR_DIR"
    assert validate_path_mapping_result(result) == []
    assert payload == before


@pytest.mark.parametrize(
    ("style", "root", "source"),
    [
        ("posix", "local/ocr", "local/ocr/A/2025/page.png"),
        ("posix", "/local/ocr", "/local/ocr/A/2025/page.png"),
        ("windows", r"Q:\synthetic\ocr", r"Q:\synthetic\ocr\A\2025\page.png"),
        ("windows", r"local\ocr", r"local\ocr\A\2025\page.png"),
        (
            "windows",
            r"\\synthetic-server\share\ocr",
            r"\\synthetic-server\share\ocr\A\2025\page.png",
        ),
        ("windows", r"\\synthetic-server\share", r"\\synthetic-server\share\A\2025\page.png"),
    ],
)
def test_cross_platform_local_paths(payload, style, root, source):
    payload["mappings"][0].update(source_root=root, path_style=style)
    payload["reference"]["original_path"] = source
    result = mapped(payload)
    assert result.status == "not_checked"
    assert result.candidate_targets[0].relative_suffix == "A/2025/page.png"
    assert validate_path_mapping_result(result) == []


@pytest.mark.parametrize(
    "source",
    [
        "/unknown/path.png",
        "/synthetic/drive/Financial_Report_OCR_Backup/page.png",
        "/synthetic/drive/Financial_Report_OCR2/page.png",
        "/elsewhere/Financial_Report_OCR/page.png",
    ],
)
def test_component_root_no_marker_search(payload, source):
    payload["reference"]["original_path"] = source
    result = mapped(payload)
    assert result.status == "unmapped"
    assert result.issues[0].code == "unknown_source_root"
    assert not result.candidate_targets
    assert result.reference.original_path == source


@pytest.mark.parametrize(
    ("suffix", "code"),
    [
        ("../secret", "path_traversal"),
        (r"..\secret", "path_traversal"),
        ("a/../../secret", "path_traversal"),
        (r"a/..\secret", "path_traversal"),
        (r"a\b.png", "invalid_separators"),
        ("/etc/passwd", "invalid_separators"),
        ("Q:/secret", "absolute_path_injection"),
        (r"Q:\secret", "invalid_separators"),
        (r"\\server\share\secret", "invalid_separators"),
        ("%2e%2e/secret", "unsupported_path_format"),
        ("%252e%252e/secret", "unsupported_path_format"),
        ("a%2fb.png", "unsupported_path_format"),
        ("./page.png", "unsafe_segment"),
        ("a//page.png", "invalid_separators"),
        ("a/", "invalid_separators"),
        ("a/hidden\x00.png", "unsafe_segment"),
        ("a/hidden\n.png", "unsafe_segment"),
        ("a/hidden\u202e.png", "unsafe_segment"),
        ("a/CON.png", "unsafe_segment"),
        ("a/LPT1.png", "unsafe_segment"),
        ("a/COM¹.png", "unsafe_segment"),
        ("a/file.png:stream", "absolute_path_injection"),
        ("a/file.", "unsafe_segment"),
        ("a/file ", "unsafe_segment"),
    ],
)
def test_unsafe_suffixes_fail_closed(payload, suffix, code):
    source = payload["mappings"][0]["source_root"] + "/" + suffix
    payload["reference"]["original_path"] = source
    result = mapped(payload)
    assert result.status == "unsafe"
    assert result.issues[0].code == code
    assert result.issues[0].path == ["reference", "original_path"]
    assert result.reference.original_path == source
    assert result.candidate_targets == []


@pytest.mark.parametrize("source", ["", "  ", "\t"])
def test_empty_path_quality_not_structural(payload, source):
    payload["reference"]["original_path"] = source
    result = mapped(payload)
    assert result.status == "unsafe"
    assert result.issues[0].code == "empty_path"
    assert result.reference.original_path == source


@pytest.mark.parametrize(
    "source", ["https://example.invalid/file", "file:///tmp/file", "~/file", "//server/share"]
)
def test_unsupported_source_formats(payload, source):
    payload["reference"]["original_path"] = source
    assert mapped(payload).status == "unsafe"


@pytest.mark.parametrize(
    "suffix", [r"..\escape", r"Q:\escape", r"\\server\share\escape", r"a/b", r"\escape"]
)
def test_windows_suffix_injections(payload, suffix):
    payload["mappings"][0].update(source_root=r"Q:\synthetic\ocr", path_style="windows")
    payload["reference"]["original_path"] = "Q:\\synthetic\\ocr\\" + suffix
    assert mapped(payload).status == "unsafe"


def test_overlapping_rules_ambiguous_order_independent(payload):
    second = deepcopy(payload["mappings"][0])
    second.update(mapping_id="nested", source_root=second["source_root"] + "/CTY")
    payload["mappings"].append(second)
    first = mapped(payload)
    payload["mappings"].reverse()
    second_result = mapped(payload)
    assert first == second_result
    assert first.status == "ambiguous"
    assert len(first.candidate_targets) == 2
    assert first.confirmed_target is None
    assert first.issues[0].code == "ambiguous_root_matching"
    assert validate_path_mapping_result(first) == []


def test_duplicate_mapping_ids_fail_closed(payload):
    payload["mappings"].append(deepcopy(payload["mappings"][0]))
    result = mapped(payload)
    assert result.status == "unsafe"
    assert result.issues[0].code == "duplicate_mapping_identifier"
    assert result.issues[0].path == ["mappings", 1, "mapping_id"]


def test_no_basename_fallback(payload):
    prefix = payload["mappings"][0]["source_root"]
    payload["reference"]["original_path"] = prefix + "/A/2024/ocr_crops/same.png"
    first = mapped(payload).candidate_targets[0]
    payload["reference"]["original_path"] = prefix + "/B/2025/ocr_crops/same.png"
    second = mapped(payload).candidate_targets[0]
    assert first != second
    assert first.relative_suffix == "A/2024/ocr_crops/same.png"
    assert second.relative_suffix == "B/2025/ocr_crops/same.png"


def test_category_separates_same_source_roots(payload):
    payload["reference"]["category"] = "raw_page_image"
    assert mapped(payload).issues[0].code == "mismatched_source_category"
    assert mapped(payload).status == "unmapped"
    second = deepcopy(payload["mappings"][0])
    second.update(
        mapping_id="raw", category="raw_page_image", destination_root_key="FINANCIAL_REPORT_DIR"
    )
    payload["mappings"].append(second)
    assert mapped(payload).candidate_targets[0].mapping_id == "raw"


@pytest.mark.parametrize("category", ["raw_page_image", "ocr_page_json", "ocr_crop"])
def test_all_resource_categories(payload, category):
    payload["reference"]["category"] = payload["mappings"][0]["category"] = category
    assert mapped(payload).status == "not_checked"


def test_empty_mappings_still_validates_source(payload):
    payload["mappings"] = []
    assert mapped(payload).status == "unmapped"
    payload["reference"]["original_path"] = "../escape"
    assert mapped(payload).status == "unsafe"


@pytest.mark.parametrize(
    ("key", "value", "code"),
    [
        ("source_root", "/root/../escape", "path_traversal"),
        ("source_root", "", "empty_path"),
        ("mapping_id", " ", "empty_mapping_id"),
        ("destination_root_key", "../secret", "invalid_root_key"),
    ],
)
def test_invalid_configuration(payload, key, value, code):
    payload["mappings"][0][key] = value
    result = mapped(payload)
    assert result.status == "unsafe"
    assert result.issues[0].code == code
    assert result.issues[0].path == ["mappings", 0, key]


def test_source_equal_to_root_is_not_file(payload):
    payload["reference"]["original_path"] = payload["mappings"][0]["source_root"]
    assert mapped(payload).issues[0].code == "empty_relative_suffix"


@pytest.mark.parametrize(
    ("key", "value"),
    [("source_ref", " "), ("source_location", []), ("source_location", [-1]), ("crop_view", "red")],
)
def test_context_quality(payload, key, value):
    if key == "crop_view":
        payload["reference"]["category"] = "raw_page_image"
    payload["reference"][key] = value
    assert mapped(payload).status == "unsafe"


@pytest.mark.parametrize("status", ["resolved", "missing"])
def test_runtime_evidence_required(payload, status):
    result = mapped(payload)
    result.status = status
    assert any(i.code == "status_conflict" for i in validate_path_mapping_result(result))
    result.containment_check = "verified"
    if status == "resolved":
        result.existence_check = "exists"
        result.confirmed_target = result.candidate_targets[0].model_copy(deep=True)
    else:
        result.existence_check = "missing"
        result.issues.append(
            PathMappingIssue(
                code="missing_target",
                path=["candidate_targets", 0],
                message="Runtime reported absent target",
            )
        )
    before = result.export_result()
    assert validate_path_mapping_result(result) == []
    assert result.export_result() == before


@pytest.mark.parametrize(
    "suffix", ["/escape", "../escape", r"Q:\escape", r"\\server\share\escape", "a//b"]
)
def test_result_candidate_suffix_validation(payload, suffix):
    result = mapped(payload)
    result.candidate_targets[0].relative_suffix = suffix
    assert validate_path_mapping_result(result)


def test_confirmed_target_must_match_candidate(payload):
    result = mapped(payload)
    result.status = "resolved"
    result.existence_check = "exists"
    result.containment_check = "verified"
    result.confirmed_target = result.candidate_targets[0].model_copy(update={"root_key": "OTHER"})
    assert validate_path_mapping_result(result)[0].path == ["confirmed_target"]


def test_raw_and_understanding_integration(payload):
    metadata = OCRPageMetadata(
        symbol="SYN",
        year="2025",
        page=1,
        image="synthetic/page.png",
        width=100,
        height=100,
        dpi=300,
    )
    raw_table = OCRTable(
        id="t1",
        type="table",
        bbox=[0, 0, 50, 50],
        name="synthetic",
        crop=payload["reference"]["original_path"],
        cells=[],
    )
    before = raw_table.model_dump(mode="json", exclude_unset=True)
    identity = RawPageIdentity(
        symbol=metadata.symbol,
        year=metadata.year,
        page=metadata.page,
        image=metadata.image,
        source_ref=payload["reference"]["source_ref"],
    )
    anchor = SourceAnchor(
        page=identity,
        element_id=raw_table.id,
        table_id=raw_table.id,
        observed_bbox=raw_table.bbox,
        status="unresolved",
    )
    payload["reference"].update(original_path=raw_table.crop, anchor=anchor.export_result())
    result = mapped(payload)
    assert result.reference.anchor == anchor
    assert result.reference.original_path == raw_table.crop
    assert raw_table.model_dump(mode="json", exclude_unset=True) == before


def test_result_structural_parser_and_copy(payload):
    data = mapped(payload).export_result()
    assert parse_path_mapping_result(data).export_result() == data
    data["candidate_targets"][0]["relative_suffix"] = 1
    with pytest.raises(PathMappingStructuralError) as caught:
        parse_path_mapping_result(data)
    assert caught.value.issues[0].path == ("candidate_targets", 0, "relative_suffix")
    data["candidate_targets"].clear()
    assert caught.value.payload["candidate_targets"][0]["relative_suffix"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_targets", []),
        ("confirmed_target", {}),
        ("existence_check", "exists"),
        ("containment_check", "verified"),
        ("status", "resolved"),
        ("status", "missing"),
        ("status", "unmapped"),
        ("status", "ambiguous"),
        ("status", "unsafe"),
    ],
)
def test_status_quality_conflicts(payload, field, value):
    result = mapped(payload)
    if field == "confirmed_target":
        value = result.candidate_targets[0].model_copy()
    setattr(result, field, value)
    before = result.export_result()
    assert validate_path_mapping_result(result)
    assert result.export_result() == before


@pytest.mark.parametrize("suffix", ["Báo cáo/ảnh #1.png", "Ba\u0301o ca\u0301o/a+b(1).png"])
def test_unicode_not_normalized(payload, suffix):
    payload["reference"]["original_path"] = payload["mappings"][0]["source_root"] + "/" + suffix
    result = mapped(payload)
    assert result.candidate_targets[0].relative_suffix == suffix
    assert parse_path_mapping_result(result.export_result()) == result


def test_exact_case_policy(payload):
    payload["reference"]["original_path"] = payload["reference"]["original_path"].lower()
    assert mapped(payload).status == "unmapped"


def test_duplicate_result_candidates(payload):
    result = mapped(payload)
    result.status = "ambiguous"
    result.candidate_targets.append(result.candidate_targets[0].model_copy())
    assert validate_path_mapping_result(result)[0].code == "duplicate_mapping_identifier"


@pytest.mark.parametrize("status", ["not_checked", "resolved", "missing"])
def test_result_cannot_claim_safe_mapping_for_traversal_source(payload, status):
    result = mapped(payload)
    result.reference.original_path = "../escape"
    result.status = status
    assert any(i.code == "path_traversal" for i in validate_path_mapping_result(result))


def test_missing_requires_machine_readable_issue(payload):
    result = mapped(payload)
    result.status = "missing"
    result.existence_check = "missing"
    result.containment_check = "verified"
    assert validate_path_mapping_result(result)[0].code == "missing_target"
