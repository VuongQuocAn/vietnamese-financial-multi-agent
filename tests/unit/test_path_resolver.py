"""Synthetic metadata tests; không đọc dataset hoặc đánh giá chất lượng tài chính."""

import errno
import os
import stat
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.core import DataConfig
from vietnamese_financial_multi_agent.document_processing import path_resolver, resolve_path
from vietnamese_financial_multi_agent.document_processing.contracts import (
    PathMappingRequest,
    validate_path_mapping_result,
)


@pytest.fixture
def config(tmp_path):
    raw, ocr = tmp_path / "raw", tmp_path / "ocr"
    raw.mkdir()
    ocr.mkdir()
    return DataConfig(project_root=tmp_path, financial_report_dir=raw, financial_ocr_dir=ocr)


def request(category="ocr_crop", suffix="CTY/2025/crop.png", key="FINANCIAL_OCR_DIR"):
    return PathMappingRequest.model_validate(
        {
            "contract_version": "path_mapping_v1",
            "reference": {
                "original_path": f"/synthetic/source/{suffix}",
                "category": category,
                "source_ref": "synthetic-run/page.json",
                "source_location": ["elements", 0, "crop"],
                "crop_view": "red" if category == "ocr_crop" else None,
                "candidate_page_image": "/synthetic/page.png",
                "anchor": {
                    "page": {
                        "symbol": "CTY",
                        "year": "2025",
                        "page": 1,
                        "image": "/synthetic/page.png",
                    },
                    "element_id": "synthetic-element",
                    "observed_bbox": [1, 2, 30, 40],
                    "status": "resolved",
                },
            },
            "mappings": [
                {
                    "mapping_id": "approved-source",
                    "source_root": "/synthetic/source",
                    "path_style": "posix",
                    "destination_root_key": key,
                    "category": category,
                    "containment_policy": "lexical_then_runtime",
                }
            ],
        }
    )


def create_file(config, req):
    suffix = req.reference.original_path.removeprefix("/synthetic/source/")
    target = config.get_root(req.mappings[0].destination_root_key) / suffix
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"synthetic placeholder, deliberately not decoded")
    return target


def checked(req, config, status, code=None):
    snapshot = req.export_result()
    result = resolve_path(req, config)
    assert result.status == status
    assert req.export_result() == snapshot
    assert result.reference.export_result() == req.reference.export_result()
    assert not validate_path_mapping_result(result)
    if code:
        assert code in {issue.code for issue in result.issues}
    return result


@pytest.mark.parametrize(
    ("category", "suffix", "key"),
    [
        ("raw_page_image", "CTY/2025/page.png", "FINANCIAL_REPORT_DIR"),
        ("ocr_page_json", "CTY/2025/page.json", "FINANCIAL_OCR_DIR"),
        ("ocr_crop", "CTY/2025/ảnh gốc #1.png", "FINANCIAL_OCR_DIR"),
    ],
)
def test_existing_resources(config, category, suffix, key):
    req = request(category, suffix, key)
    target = create_file(config, req)
    original = target.read_bytes()
    result = checked(req, config, "resolved")
    assert result.confirmed_target == result.candidate_targets[0]
    assert result.confirmed_target.root_key == key
    assert result.confirmed_target.relative_suffix == suffix
    assert result.existence_check == "exists"
    assert result.containment_check == "verified"
    assert target.read_bytes() == original


@pytest.mark.parametrize("category", ["ocr_crop", "raw_page_image", "ocr_page_json"])
def test_missing_resource_preserves_provenance(config, category):
    req = request(category)
    result = checked(req, config, "missing", "missing_target")
    assert result.candidate_targets[0].mapping_id == "approved-source"
    assert result.candidate_targets[0].root_key == "FINANCIAL_OCR_DIR"
    assert result.candidate_targets[0].relative_suffix == "CTY/2025/crop.png"
    assert result.confirmed_target is None
    assert not (config.financial_ocr_dir / "CTY").exists()


@pytest.mark.parametrize("key", ["UNKNOWN_ROOT", "NORMALIZED_DATA_DIR", "CANONICAL_DATA_DIR"])
def test_unknown_or_unconfigured_root(config, key):
    checked(request(key=key), config, "unsafe", "root_binding_error")


def test_unmapped(config):
    req = request()
    req.mappings = []
    checked(req, config, "unmapped", "unknown_source_root")


def test_ambiguous(config):
    req = request()
    rule = req.mappings[0].model_copy(deep=True)
    rule.mapping_id = "second-approved"
    req.mappings.append(rule)
    assert len(checked(req, config, "ambiguous").candidate_targets) == 2


def test_lexical_unsafe(config):
    checked(request(suffix="../escape.png"), config, "unsafe", "path_traversal")


def test_directory_is_not_file(config):
    target = create_file(config, request())
    target.unlink()
    target.mkdir()
    checked(request(), config, "unsafe", "target_not_regular_file")


def test_no_basename_or_other_root_fallback(config):
    (config.financial_ocr_dir / "crop.png").write_bytes(b"synthetic")
    create_file(config, request(key="FINANCIAL_REPORT_DIR"))
    checked(request(), config, "missing", "missing_target")


def test_results_are_independent(config):
    req = request()
    result = checked(req, config, "missing")
    result.reference.source_location.append("changed")
    assert req.reference.source_location == ["elements", 0, "crop"]
    snapshot = deepcopy(req.export_result())
    checked(req, config, "missing")
    assert req.export_result() == snapshot


def symlink(link, destination, *, directory=False):
    try:
        link.symlink_to(destination, target_is_directory=directory)
    except OSError as error:
        if (
            error.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS}
            or getattr(error, "winerror", None) == 1314
        ):
            pytest.skip("Runner không cấp quyền/hỗ trợ tạo symlink")
        raise


@pytest.mark.parametrize("location", ["inside", "outside", "broken", "loop", "chain"])
def test_target_symlink_rejected(config, tmp_path, location):
    req = request(suffix="link.png")
    target = config.financial_ocr_dir / "link.png"
    destination = config.financial_ocr_dir / "actual.png"
    if location == "outside":
        destination = tmp_path / "outside.png"
    if location == "loop":
        destination = target
    elif location != "broken":
        destination.write_bytes(b"synthetic")
    if location == "chain":
        intermediate = config.financial_ocr_dir / "intermediate.png"
        symlink(intermediate, destination)
        destination = intermediate
    symlink(target, destination)
    result = checked(req, config, "unsafe", "symlink_or_reparse_point")
    assert result.containment_check == "rejected"
    assert result.confirmed_target is None


@pytest.mark.parametrize("outside", [True, False])
def test_parent_symlink_rejected(config, tmp_path, outside):
    destination = tmp_path / "outside" if outside else config.financial_ocr_dir / "actual"
    destination.mkdir()
    (destination / "crop.png").write_bytes(b"synthetic")
    symlink(config.financial_ocr_dir / "linked", destination, directory=True)
    checked(request(suffix="linked/crop.png"), config, "unsafe", "symlink_or_reparse_point")


@pytest.mark.parametrize("ancestor", [False, True])
def test_root_symlink_or_ancestor_rejected(config, tmp_path, ancestor):
    linked = tmp_path / "linked"
    symlink(linked, config.financial_ocr_dir, directory=True)
    root = linked / "nested" if ancestor else linked
    if ancestor:
        (config.financial_ocr_dir / "nested").mkdir()
    changed = config.model_copy(update={"financial_ocr_dir": root})
    checked(request(suffix="crop.png"), changed, "unsafe", "symlink_or_reparse_point")


@pytest.mark.skipif(os.name != "nt", reason="Junction chỉ có trên native Windows")
@pytest.mark.parametrize("location", ["parent", "root", "root_ancestor"])
def test_native_windows_junction(config, tmp_path, location):
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "crop.png").write_bytes(b"synthetic")
    link = config.financial_ocr_dir / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
        check=True,
        capture_output=True,
    )
    req = request(suffix="junction/crop.png")
    if location == "root":
        config = config.model_copy(update={"financial_ocr_dir": link})
        req = request(suffix="crop.png")
    elif location == "root_ancestor":
        (destination / "nested").mkdir()
        config = config.model_copy(update={"financial_ocr_dir": link / "nested"})
        req = request(suffix="crop.png")
    checked(req, config, "unsafe", "symlink_or_reparse_point")


def test_other_reparse_point_is_rejected(config, monkeypatch):
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == config.financial_ocr_dir / "reparse.png":
            return SimpleNamespace(
                st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    checked(request(suffix="reparse.png"), config, "unsafe", "symlink_or_reparse_point")


@pytest.mark.parametrize("kind", ["same", "nested", "parent"])
def test_overlapping_roots_keep_selected_binding(config, kind):
    raw = config.financial_report_dir
    if kind == "same":
        root = raw
    elif kind == "nested":
        root = raw / "nested"
        root.mkdir()
    else:
        root = raw.parent
    changed = config.model_copy(update={"financial_ocr_dir": root})
    req = request(suffix="selected.png")
    create_file(changed, req)
    result = checked(req, changed, "resolved")
    assert result.confirmed_target.root_key == "FINANCIAL_OCR_DIR"
    assert ("shared_root_identity" in {i.code for i in result.issues}) == (kind == "same")


def test_configured_optional_root_is_bound_without_fallback(config, tmp_path):
    output = tmp_path / "normalized"
    output.mkdir()
    config = config.model_copy(update={"normalized_data_dir": output})
    req = request(key="NORMALIZED_DATA_DIR")
    create_file(config, req)
    result = checked(req, config, "resolved")
    assert result.confirmed_target.root_key == "NORMALIZED_DATA_DIR"


@pytest.mark.parametrize(
    "suffix",
    [
        "../escape.png",
        "a/../../escape.png",
        "/etc/file.png",
        "C:\\evil.png",
        "C:/evil.png",
        "\\\\server\\share\\evil.png",
        "x.png:stream",
        "%2e%2e/x.png",
    ],
)
def test_source_injection_stops_before_binding(config, monkeypatch, suffix):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe lexical input must stop before root lookup")

    monkeypatch.setattr(DataConfig, "get_root", forbidden)
    checked(request(suffix=suffix), config, "unsafe")


@pytest.mark.parametrize("state", ["unsafe", "ambiguous", "unmapped"])
def test_nonunique_lexical_status_has_no_filesystem_io(config, monkeypatch, state):
    req = request(suffix="../x.png" if state == "unsafe" else "x.png")
    if state == "ambiguous":
        second = req.mappings[0].model_copy(deep=True)
        second.mapping_id = "second"
        req.mappings.append(second)
    elif state == "unmapped":
        req.mappings = []

    def forbidden(*args, **kwargs):
        pytest.fail("Lexical terminal statuses must not touch filesystem")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", forbidden)
        patch.setattr(Path, "stat", forbidden)
        patch.setattr(Path, "resolve", forbidden)
        checked(req, config, state)


@pytest.mark.parametrize("error_type", [PermissionError, OSError, NotADirectoryError])
@pytest.mark.parametrize("location", ["root", "target", "parent"])
def test_filesystem_errors_are_not_missing(config, monkeypatch, error_type, location):
    req = request()
    target = create_file(config, req)
    failing = {"root": config.financial_ocr_dir, "parent": target.parent, "target": target}[
        location
    ]
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == failing:
            raise error_type("synthetic filesystem failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", lstat)
        code = "permission_denied" if error_type is PermissionError else "filesystem_error"
        result = checked(req, config, "unsafe", code)
        assert result.existence_check != "missing"


def test_inaccessible_file(config, monkeypatch):
    req = request()
    create_file(config, req)
    monkeypatch.setattr(path_resolver.os, "access", lambda *args: False)
    checked(req, config, "unsafe", "target_inaccessible")


@pytest.mark.parametrize("location", ["root", "target"])
@pytest.mark.parametrize("kind", ["outside", "io_error", "loop"])
def test_resolve_failures(config, tmp_path, monkeypatch, location, kind):
    req = request()
    target = create_file(config, req)
    original = Path.resolve
    failing = config.financial_ocr_dir if location == "root" else target

    def resolve(path, *args, **kwargs):
        if path == failing:
            if kind == "io_error":
                raise OSError("synthetic resolve failure")
            if kind == "loop":
                raise RuntimeError("synthetic symlink loop")
            return tmp_path / "outside.png"
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", resolve)
        expected = "runtime_containment_failed" if kind == "outside" else "filesystem_error"
        checked(req, config, "unsafe", expected)


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_root_is_unsafe(config, tmp_path, kind):
    root = tmp_path / "not-a-directory"
    if kind == "file":
        root.write_bytes(b"synthetic")
    changed = config.model_copy(update={"financial_ocr_dir": root})
    code = "root_unavailable" if kind == "missing" else "root_not_directory"
    checked(request(), changed, "unsafe", code)


def test_parent_is_file(config):
    (config.financial_ocr_dir / "parent").write_bytes(b"synthetic")
    checked(request(suffix="parent/crop.png"), config, "unsafe", "parent_not_directory")


@pytest.mark.parametrize("category", ["raw_page_image", "ocr_crop", "ocr_page_json"])
def test_wrong_extension(config, category):
    req = request(category, "wrong.txt")
    create_file(config, req)
    checked(req, config, "unsafe", "resource_extension_mismatch")


def test_case_sensitive_filesystem_missing(config):
    req = request(suffix="case.png")
    create_file(config, req)
    if (config.financial_ocr_dir / "CASE.PNG").exists():
        pytest.skip("Filesystem hiện tại không phân biệt case")
    checked(request(suffix="CASE.PNG"), config, "missing")


def test_no_content_open_scan_or_write(config, monkeypatch):
    req = request()
    create_file(config, req)

    def forbidden(*args, **kwargs):
        pytest.fail("Resolver must only inspect metadata")

    with monkeypatch.context() as patch:
        for method in ("open", "iterdir", "glob", "rglob", "mkdir", "write_bytes", "write_text"):
            patch.setattr(Path, method, forbidden)
        patch.setattr(path_resolver.os, "scandir", forbidden)
        patch.setattr(path_resolver.os, "open", forbidden)
        checked(req, config, "resolved")


def test_result_is_snapshot_not_durable_file_handle(config):
    req = request()
    target = create_file(config, req)
    result = checked(req, config, "resolved")
    target.unlink()
    assert result.status == "resolved"
    checked(req, config, "missing")


@pytest.mark.parametrize("location", ["root", "ancestor", "parent", "target"])
@pytest.mark.parametrize("reparse", [False, True])
def test_link_metadata_policy_without_symlink_privileges(config, monkeypatch, location, reparse):
    req = request()
    target = create_file(config, req)
    failing = {
        "root": config.financial_ocr_dir,
        "ancestor": config.financial_ocr_dir.parent,
        "parent": target.parent,
        "target": target,
    }[location]
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == failing:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR if reparse else stat.S_IFLNK,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if reparse else 0,
            )
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", lstat)
        checked(req, config, "unsafe", "symlink_or_reparse_point")


@pytest.mark.skipif(os.name == "nt", reason="FIFO không được os.mkfifo hỗ trợ trên Windows")
def test_fifo_is_not_regular_file(config):
    os.mkfifo(config.financial_ocr_dir / "pipe.png")
    checked(request(suffix="pipe.png"), config, "unsafe", "target_not_regular_file")


def test_other_root_unavailable_does_not_change_binding(config, tmp_path):
    changed = config.model_copy(update={"financial_report_dir": tmp_path / "absent"})
    req = request()
    create_file(config, req)
    checked(req, changed, "resolved")


def test_empty_context_fails_closed_and_preserves_source(config):
    req = request()
    req.reference.source_ref = ""
    result = resolve_path(req, config)
    assert result.status == "unsafe"
    assert result.reference == req.reference
    assert "empty_source_context" in {i.code for i in result.issues}


def test_reference_missing_fields_remain_missing(config):
    payload = request().export_result()
    for key in ("anchor", "crop_view", "candidate_page_image"):
        del payload["reference"][key]
    req = PathMappingRequest.model_validate(payload)
    result = checked(req, config, "missing")
    assert result.reference.export_result() == payload["reference"]
