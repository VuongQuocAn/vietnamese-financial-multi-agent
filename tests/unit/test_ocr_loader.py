"""Synthetic loader/security tests; không đo chất lượng OCR hoặc tài chính."""

import errno
import json
import os
import stat
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.document_processing import (
    OCRLoadError,
    load_ocr_page,
    ocr_loader,
)
from vietnamese_financial_multi_agent.document_processing.contracts.validation import (
    RawOCRStructuralError,
)

from .test_path_resolver import config as config
from .test_path_resolver import request as mapping_request
from .test_raw_ocr_contracts import KINDS, element
from .test_raw_ocr_contracts import payload as payload


@pytest.fixture
def sample(config, payload):
    req = mapping_request(category="ocr_page_json", suffix="CTY/2025/page.json")
    req.reference.anchor = None
    req.reference.source_location = ["page"]
    target = config.financial_ocr_dir / "CTY/2025/page.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(config=config, request=req, target=target, payload=payload)


def write(sample):
    sample.target.write_text(json.dumps(sample.payload, ensure_ascii=False), encoding="utf-8")


def failure(sample, code, **kwargs):
    with pytest.raises(OCRLoadError) as raised:
        load_ocr_page(sample.request, sample.config, **kwargs)
    error = raised.value
    assert error.code == code
    assert error.reference.export_result() == sample.request.reference.export_result()
    assert str(sample.target) not in str(error)
    return error


def test_empty_elements_and_provenance(sample):
    before = sample.target.read_bytes(), sample.target.stat()
    request_before = sample.request.export_result()
    result = load_ocr_page(sample.request, sample.config)
    assert result.page.export_source() == sample.payload
    assert result.quality_issues == ()
    assert result.identity_checked is False
    assert result.mapping_result.reference.export_result() == request_before["reference"]
    assert result.mapping_result.confirmed_target.export_result() == {
        "mapping_id": "approved-source",
        "root_key": "FINANCIAL_OCR_DIR",
        "relative_suffix": "CTY/2025/page.json",
    }
    assert sample.request.export_result() == request_before
    assert sample.target.read_bytes() == before[0]
    assert ocr_loader._fingerprint(sample.target.stat()) == ocr_loader._fingerprint(before[1])


@pytest.mark.parametrize("kind", [*KINDS, "all"])
def test_elements_unicode_and_nested_source_preserved(sample, kind):
    sample.payload["elements"] = [element(k) for k in (KINDS if kind == "all" else [kind])]
    sample.payload["extra"] = {"nullable": None, "note": "Nguồn tiếng Việt"}
    write(sample)
    before = sample.target.read_bytes()
    result = load_ocr_page(sample.request, sample.config)
    assert result.page.export_source() == sample.payload
    assert sample.target.read_bytes() == before


@pytest.mark.parametrize(
    ("scenario", "status", "issue"),
    [
        ("missing", "missing", "missing_target"),
        ("unmapped", "unmapped", "unknown_source_root"),
        ("ambiguous", "ambiguous", None),
        ("unsafe", "unsafe", "path_traversal"),
        ("unknown_root", "unsafe", "root_binding_error"),
        ("directory", "unsafe", "target_not_regular_file"),
        ("extension", "unsafe", "resource_extension_mismatch"),
    ],
)
def test_path_failures_never_open(sample, monkeypatch, scenario, status, issue):
    if scenario == "missing":
        sample.target.unlink()
        sample.request.reference.original_path = "/synthetic/source/absent/path/page.json"
    elif scenario == "unmapped":
        sample.request.mappings = []
    elif scenario == "ambiguous":
        rule = sample.request.mappings[0].model_copy(deep=True)
        rule.mapping_id = "another-source"
        sample.request.mappings.append(rule)
    elif scenario == "unsafe":
        sample.request.reference.original_path = "/synthetic/source/../escape.json"
    elif scenario == "unknown_root":
        sample.request.mappings[0].destination_root_key = "UNKNOWN_ROOT"
    elif scenario == "directory":
        sample.target.unlink()
        sample.target.mkdir()
    else:
        renamed = sample.target.with_suffix(".png")
        sample.target.rename(renamed)
        sample.request.reference.original_path = "/synthetic/source/CTY/2025/page.png"
    before = sorted(sample.config.project_root.rglob("*"))

    def forbidden(*args, **kwargs):
        pytest.fail("Path failure must not open content")

    monkeypatch.setattr(ocr_loader.os, "open", forbidden)
    error = failure(sample, "path_failure")
    assert error.mapping_result.status == status
    if issue:
        assert issue in {i.code for i in error.mapping_result.issues}
    assert sorted(sample.config.project_root.rglob("*")) == before


@pytest.mark.parametrize("category", ["ocr_crop", "raw_page_image"])
def test_wrong_category_before_resolution(sample, monkeypatch, category):
    sample.request.reference.category = category
    monkeypatch.setattr(ocr_loader, "resolve_path", lambda *a: pytest.fail("Must reject first"))
    failure(sample, "unsupported_category")


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "empty_file"),
        (b" \r\n\t", "empty_file"),
        (b"\xef\xbb\xbf", "empty_file"),
        (b"\xff", "invalid_utf8"),
        (b"{", "invalid_json"),
        (b'{"x": NaN}', "invalid_json"),
        (b'{"x": Infinity}', "invalid_json"),
        (b'{"x": 1, "x": 2}', "duplicate_json_key"),
        (b'{"nested": {"x": 1, "x": 2}}', "duplicate_json_key"),
        (b"[]", "unsupported_json_root"),
        (b"null", "unsupported_json_root"),
        (b"1", "unsupported_json_root"),
        (b'"text"', "unsupported_json_root"),
        (b"true", "unsupported_json_root"),
    ],
)
def test_decode_failures(sample, content, code):
    sample.target.write_bytes(content)
    failure(sample, code)
    assert sample.target.read_bytes() == content


def test_utf8_bom_and_exact_limit(sample):
    content = b"\xef\xbb\xbf" + sample.target.read_bytes()
    sample.target.write_bytes(content)
    assert load_ocr_page(sample.request, sample.config, max_bytes=len(content)).page
    failure(sample, "oversized_file", max_bytes=len(content) - 1)


def test_deep_array_rejected_portably(sample):
    sample.target.write_bytes(b"[" * 2000 + b"]" * 2000)
    # Decoder depth limit khác giữa Python/platform; root list luôn bị từ chối.
    error = failure_any(sample)
    assert error.code in {"invalid_json", "unsupported_json_root"}


def test_decoder_recursion_error_is_structured(sample, monkeypatch):
    def exhausted(*args, **kwargs):
        raise RecursionError

    monkeypatch.setattr(ocr_loader.json, "loads", exhausted)
    failure(sample, "invalid_json")


@pytest.mark.parametrize("limit", [0, -1, True, False, 1.5, "10", None, sys.maxsize])
def test_invalid_limits(sample, monkeypatch, limit):
    monkeypatch.setattr(ocr_loader, "resolve_path", lambda *a: pytest.fail("Must reject first"))
    failure(sample, "invalid_max_bytes", max_bytes=limit)


@pytest.mark.parametrize("field", ["page", "elements", "provenance"])
def test_missing_required_structure(sample, field):
    del sample.payload[field]
    write(sample)
    error = failure(sample, "structural_failure")
    assert (field,) in {i.path for i in error.issues}
    assert isinstance(error.__cause__, RawOCRStructuralError)
    assert error.__cause__.payload == sample.payload


@pytest.mark.parametrize("change", ["unknown_type", "bbox", "year", "page", "row"])
def test_structural_failure_no_coercion(sample, change):
    sample.payload["elements"] = [element("table")]
    if change == "unknown_type":
        sample.payload["elements"][0]["type"] = "unknown"
    elif change == "bbox":
        sample.payload["elements"][0]["cells"][0]["bbox"] = [1, 2, 3]
    elif change in {"year", "page"}:
        sample.payload["page"][change] = 2025 if change == "year" else "1"
    else:
        sample.payload["elements"][0]["cells"][0]["row"] = "0"
    write(sample)
    error = failure(sample, "structural_failure")
    assert error.issues
    if change == "bbox":
        assert error.issues[0].path == ("elements", 0, "cells", 0, "bbox")


def test_quality_warnings_preserve_page(sample):
    table = element("table")
    cell = table["cells"][0]
    cell.update(text="", bbox=[10, 10, 0, 0])
    table["cells"].append(deepcopy(cell))
    distant = deepcopy(cell)
    distant.update(id="distant", row=2, col=2)
    table["cells"].append(distant)
    checkbox = element("checkbox")
    checkbox.update(confidence=2.0, label_text_ids=["missing-id"])
    sample.payload["elements"] = [table, checkbox]
    write(sample)
    result = load_ocr_page(sample.request, sample.config)
    assert {
        "invalid_bbox_geometry",
        "duplicate_cell_position",
        "sparse_table",
        "empty_cell_text",
        "confidence_out_of_range",
        "unresolved_text_reference",
    } <= {i.code for i in result.quality_issues}
    assert result.page.export_source() == sample.payload


def set_anchor(sample):
    from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
        SourceAnchor,
    )

    sample.request.reference.anchor = SourceAnchor.model_validate(
        {
            "page": {k: sample.payload["page"][k] for k in ("symbol", "year", "page", "image")},
            "status": "unresolved",
        }
    )


def test_expected_identity(sample):
    set_anchor(sample)
    assert load_ocr_page(sample.request, sample.config).identity_checked is True


@pytest.mark.parametrize("field", ["symbol", "year", "page", "image"])
def test_identity_mismatch(sample, field):
    set_anchor(sample)
    setattr(sample.request.reference.anchor.page, field, 2 if field == "page" else "different")
    error = failure(sample, "identity_mismatch")
    assert error.issues[0].path == ("page", field)
    assert json.loads(sample.target.read_bytes()) == sample.payload


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (FileNotFoundError(), "missing_file"),
        (PermissionError(), "permission_denied"),
        (OSError(errno.EIO, "private path"), "io_error"),
        (OSError(errno.ELOOP, "private path"), "unsafe_file"),
    ],
)
def test_open_errors(sample, monkeypatch, error, code):
    def broken(*args):
        raise error

    monkeypatch.setattr(ocr_loader.os, "open", broken)
    failure(sample, code)


def test_disappeared_after_resolver(sample, monkeypatch):
    original = ocr_loader.resolve_path
    calls = 0

    def resolve(*args):
        nonlocal calls
        calls += 1
        result = original(*args)
        if calls == 1:
            sample.target.unlink()
        return result

    monkeypatch.setattr(ocr_loader, "resolve_path", resolve)
    failure(sample, "source_changed")


def test_symlink_swap_after_resolver(sample, monkeypatch):
    other = sample.target.with_name("other.json")
    other.write_bytes(sample.target.read_bytes())
    probe = sample.target.with_name("probe")
    try:
        probe.symlink_to(other)
    except OSError:
        pytest.skip("Runner không cấp quyền/hỗ trợ tạo symlink")
    probe.unlink()
    original = ocr_loader.resolve_path
    calls = 0

    def resolve(*args):
        nonlocal calls
        calls += 1
        result = original(*args)
        if calls == 1:
            sample.target.unlink()
            sample.target.symlink_to(other)
        return result

    monkeypatch.setattr(ocr_loader, "resolve_path", resolve)
    failure(sample, "source_changed")


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO])
def test_read_time_file_type_rejected(sample, monkeypatch, mode):
    original = Path.lstat

    def changed(path, *args, **kwargs):
        metadata = original(path, *args, **kwargs)
        if path == sample.target:
            return SimpleNamespace(st_mode=mode, st_file_attributes=0)
        return metadata

    original_resolve = ocr_loader.resolve_path
    calls = 0

    def resolve(*args):
        nonlocal calls
        calls += 1
        result = original_resolve(*args)
        if calls == 2:
            monkeypatch.setattr(Path, "lstat", changed)
        return result

    monkeypatch.setattr(ocr_loader, "resolve_path", resolve)
    failure(sample, "unsafe_file")


@pytest.mark.parametrize("when", ["open", "read"])
def test_file_growth_bounded(sample, monkeypatch, when):
    limit = sample.target.stat().st_size
    original_open = os.open
    original_fdopen = os.fdopen
    reads = []

    def grow():
        with sample.target.open("ab") as file:
            file.write(b" " * 10000)

    def opening(*args):
        grow()
        return original_open(*args)

    class GrowingReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            assert size > 0
            reads.append(size)
            if len(reads) == 1:
                grow()
            return self.stream.read(size)

    if when == "open":
        monkeypatch.setattr(ocr_loader.os, "open", opening)
        failure(sample, "source_changed", max_bytes=limit)
    else:
        monkeypatch.setattr(
            ocr_loader.os, "fdopen", lambda *a, **k: GrowingReader(original_fdopen(*a, **k))
        )
        failure(sample, "oversized_file", max_bytes=limit)
        assert sum(reads) <= limit + 1


def test_programming_errors_not_hidden(sample, monkeypatch):
    monkeypatch.setattr(ocr_loader, "parse_raw_ocr", lambda *a: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        load_ocr_page(sample.request, sample.config)


@pytest.mark.parametrize("action", ["io_error", "permission", "shrink", "replace", "rewrite"])
def test_changes_or_errors_during_read(sample, monkeypatch, action):
    original_fdopen = os.fdopen
    original_bytes = sample.target.read_bytes()
    streams = []

    class Reader:
        def __init__(self, stream):
            self.stream = stream
            self.changed = False
            streams.append(stream)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            if not self.changed:
                self.changed = True
                if action == "io_error":
                    raise OSError(errno.EIO, "private path")
                if action == "permission":
                    raise PermissionError("private path")
                if action == "shrink":
                    sample.target.write_bytes(b"{}")
                elif action == "rewrite":
                    sample.target.write_bytes(b" " * len(original_bytes))
                    metadata = sample.target.stat()
                    os.utime(
                        sample.target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1000000)
                    )
                elif action == "replace":
                    replacement = sample.target.with_name("replacement.json")
                    replacement.write_bytes(original_bytes)
                    replacement.replace(sample.target)
            return self.stream.read(size)

    monkeypatch.setattr(ocr_loader.os, "fdopen", lambda *a, **k: Reader(original_fdopen(*a, **k)))
    expected = {"io_error": "io_error", "permission": "permission_denied"}.get(
        action, "source_changed"
    )
    # Windows có thể cấm replace file đang mở; fail closed thành permission_denied.
    error = failure_any(sample)
    assert error.code in ({expected, "permission_denied"} if action == "replace" else {expected})
    assert streams and all(stream.closed for stream in streams)


def failure_any(sample):
    with pytest.raises(OCRLoadError) as raised:
        load_ocr_page(sample.request, sample.config)
    return raised.value


def test_readonly_open_flags(sample, monkeypatch):
    original = os.open
    observed = []

    def opening(path, flags):
        observed.append(flags)
        return original(path, flags)

    monkeypatch.setattr(ocr_loader.os, "open", opening)
    load_ocr_page(sample.request, sample.config)
    assert len(observed) == 1
    flags = observed[0]
    assert flags & (os.O_WRONLY | os.O_RDWR | os.O_TRUNC | os.O_CREAT | os.O_APPEND) == 0
    assert flags & getattr(os, "O_NOFOLLOW", 0) == getattr(os, "O_NOFOLLOW", 0)


def test_read_time_reparse_metadata(sample, monkeypatch):
    original = Path.lstat
    resolve = ocr_loader.resolve_path
    calls = 0

    def metadata(path, *a, **k):
        if path == sample.target:
            return SimpleNamespace(
                st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return original(path, *a, **k)

    def resolving(*args):
        nonlocal calls
        calls += 1
        result = resolve(*args)
        if calls == 2:
            monkeypatch.setattr(Path, "lstat", metadata)
        return result

    monkeypatch.setattr(ocr_loader, "resolve_path", resolving)
    failure(sample, "unsafe_file")


@pytest.mark.skipif(os.name != "nt", reason="Junction chỉ có trên native Windows")
def test_native_junction_swap_before_read(sample, monkeypatch):
    alternate = sample.config.project_root / "alternate"
    alternate.mkdir()
    (alternate / "page.json").write_bytes(sample.target.read_bytes())
    original = ocr_loader.resolve_path
    calls = 0

    def resolving(*args):
        nonlocal calls
        calls += 1
        result = original(*args)
        if calls == 1:
            sample.target.unlink()
            sample.target.parent.rmdir()
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(sample.target.parent), str(alternate)],
                check=True,
                capture_output=True,
            )
        return result

    monkeypatch.setattr(ocr_loader, "resolve_path", resolving)
    failure(sample, "source_changed")
