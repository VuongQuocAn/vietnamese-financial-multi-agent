"""Fixtures synthetic; không đọc dataset hoặc đánh giá chất lượng tài chính."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.data_config import (
    DataConfig,
    DataConfigError,
    default_project_root,
    load_data_config,
)


@pytest.fixture
def environment():
    return {
        "FINANCIAL_REPORT_DIR": "data/raw/Financial_Report",
        "FINANCIAL_OCR_DIR": "data/processed/Financial_Report_OCR",
    }


def test_required_roots_and_optional_outputs(environment, tmp_path):
    config = load_data_config(environment, project_root=tmp_path)
    assert config.project_root == tmp_path
    assert config.financial_report_dir == tmp_path / environment["FINANCIAL_REPORT_DIR"]
    assert config.financial_ocr_dir == tmp_path / environment["FINANCIAL_OCR_DIR"]
    assert config.normalized_data_dir is None
    assert config.canonical_data_dir is None


@pytest.mark.parametrize("key", ["NORMALIZED_DATA_DIR", "CANONICAL_DATA_DIR"])
def test_optional_root_configured_and_missing(key, environment, tmp_path):
    with pytest.raises(DataConfigError, match=f"{key}: root is not configured"):
        load_data_config(environment, project_root=tmp_path).get_root(key)
    environment[key] = "data/" + key.lower()
    config = load_data_config(environment, project_root=tmp_path)
    assert config.get_root(key) == tmp_path / environment[key]


@pytest.mark.parametrize("key", ["FINANCIAL_REPORT_DIR", "FINANCIAL_OCR_DIR"])
def test_missing_required_key(key, environment, tmp_path):
    del environment[key]
    with pytest.raises(DataConfigError, match=f"{key}: required"):
        load_data_config(environment, project_root=tmp_path)


@pytest.mark.parametrize("key", list(DataConfig.ROOT_FIELDS))
@pytest.mark.parametrize("value", ["", "   ", "\t", None, 1, False, [], Path("data")])
def test_invalid_environment_values(key, value, environment, tmp_path):
    environment[key] = value
    with pytest.raises(DataConfigError, match=key):
        load_data_config(environment, project_root=tmp_path)


def test_absolute_unicode_and_spaces(environment, tmp_path):
    root = tmp_path / "báo cáo 2026"
    environment["FINANCIAL_REPORT_DIR"] = str(root)
    assert load_data_config(environment, project_root=str(tmp_path)).financial_report_dir == root
    assert not root.exists()


def test_relative_policy_and_cwd_independence(environment, tmp_path, monkeypatch):
    import vietnamese_financial_multi_agent.core.data_config as module

    checkout = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(module, "__file__", str(checkout / "src/core/data_config.py"))
    environment["FINANCIAL_REPORT_DIR"] = "../external/reports"
    expected = tmp_path.parent / "external/reports"
    first = load_data_config(environment, project_root=tmp_path)
    default = load_data_config(environment)
    monkeypatch.chdir(tmp_path)
    assert load_data_config(environment, project_root=tmp_path) == first
    assert load_data_config(environment) == default
    assert first.financial_report_dir == expected
    assert default.project_root == checkout


@pytest.mark.parametrize("base", ["relative", "", " ", 1, False, [], "https://host/data"])
def test_invalid_project_root(base, environment):
    with pytest.raises(DataConfigError, match="project_root"):
        load_data_config(environment, project_root=base)


def test_installed_package_requires_explicit_root(environment, tmp_path, monkeypatch):
    import vietnamese_financial_multi_agent.core.data_config as module

    monkeypatch.setattr(module, "__file__", str(tmp_path / "package/core/data_config.py"))
    with pytest.raises(DataConfigError, match="supply an absolute base"):
        default_project_root()
    assert load_data_config(environment, project_root=tmp_path).project_root == tmp_path


def test_injected_environment_isolated(environment, tmp_path, monkeypatch):
    monkeypatch.setenv("NORMALIZED_DATA_DIR", "ignored-process-output")
    before = dict(os.environ)
    original = dict(environment)
    config = load_data_config(environment, project_root=tmp_path)
    assert dict(os.environ) == before
    assert environment == original
    assert config.normalized_data_dir is None
    with pytest.raises(DataConfigError, match="required"):
        load_data_config({}, project_root=tmp_path)


def test_process_environment(environment, tmp_path, monkeypatch):
    for key in DataConfig.ROOT_FIELDS:
        monkeypatch.delenv(key, raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    assert load_data_config(project_root=tmp_path) == load_data_config(
        environment, project_root=tmp_path
    )


@pytest.mark.parametrize("value", [[], "environment", 0, False])
def test_invalid_environment_mapping(value, tmp_path):
    with pytest.raises(DataConfigError, match="expected a mapping"):
        load_data_config(value, project_root=tmp_path)


@pytest.mark.parametrize(
    "key", ["UNKNOWN", "DATA_DIR", "RAW_DATA_DIR", "file.png", "/tmp", "../data", "", None, []]
)
def test_unknown_root_key(key, environment, tmp_path):
    with pytest.raises(DataConfigError, match="Unknown data root key"):
        load_data_config(environment, project_root=tmp_path).get_root(key)


@pytest.mark.parametrize(
    "value",
    ["https://host/data", "s3://bucket/data", "~/data", "bad\x00path", "bad\npath", "C:relative"],
)
def test_unsupported_runtime_path(value, environment, tmp_path):
    environment["FINANCIAL_REPORT_DIR"] = value
    with pytest.raises(DataConfigError, match="FINANCIAL_REPORT_DIR") as error:
        load_data_config(environment, project_root=tmp_path)
    assert value not in str(error.value)


def test_foreign_absolute_paths_are_not_reinterpreted(environment, tmp_path):
    value = "/srv/reports" if os.name == "nt" else r"C:\reports"
    environment["FINANCIAL_REPORT_DIR"] = value
    with pytest.raises(DataConfigError):
        load_data_config(environment, project_root=tmp_path)


def test_native_absolute_unc_or_posix(environment, tmp_path):
    value = r"\\server\share\reports" if os.name == "nt" else "/srv/reports"
    environment["FINANCIAL_REPORT_DIR"] = value
    assert load_data_config(environment, project_root=tmp_path).financial_report_dir == Path(value)


@pytest.mark.skipif(os.name != "nt", reason="Native Windows runtime syntax")
@pytest.mark.parametrize(
    "value", [r"\\?\C:\data", r"\\.\pipe\data", r"C:\CON\data", "bad*name/data", r"\data"]
)
def test_invalid_windows_runtime_paths(value, environment, tmp_path):
    environment["FINANCIAL_REPORT_DIR"] = value
    with pytest.raises(DataConfigError, match="FINANCIAL_REPORT_DIR"):
        load_data_config(environment, project_root=tmp_path)


@pytest.mark.parametrize(
    "output",
    [
        "data/raw/Financial_Report",
        "data/raw/Financial_Report/nested",
        "data",
        "data/processed/Financial_Report_OCR",
    ],
)
def test_conflicting_output_input(output, environment, tmp_path):
    environment["NORMALIZED_DATA_DIR"] = output
    with pytest.raises(ValidationError, match="disjoint"):
        load_data_config(environment, project_root=tmp_path)


def test_conflicting_outputs_and_absolute_dot_segments(environment, tmp_path):
    environment.update(NORMALIZED_DATA_DIR="output", CANONICAL_DATA_DIR="output/nested")
    with pytest.raises(ValidationError, match="disjoint"):
        load_data_config(environment, project_root=tmp_path)
    environment.pop("CANONICAL_DATA_DIR")
    environment["NORMALIZED_DATA_DIR"] = str(tmp_path / "other/../data/raw/Financial_Report")
    with pytest.raises(ValidationError, match="disjoint"):
        load_data_config(environment, project_root=tmp_path)


def test_model_is_strict_frozen_and_rejects_relative_paths(environment, tmp_path):
    config = load_data_config(environment, project_root=tmp_path)
    with pytest.raises(ValidationError):
        config.financial_report_dir = tmp_path
    values = config.model_dump()
    for value in ["relative", Path("relative"), 12]:
        with pytest.raises(ValidationError):
            DataConfig(**(values | {"financial_report_dir": value}))
    with pytest.raises(ValidationError):
        DataConfig(**values, unknown="field")


def test_no_dataset_io_or_creation(environment, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Configuration must not access dataset filesystem")

    for method in ("stat", "exists", "is_dir", "mkdir", "open", "resolve", "glob", "iterdir"):
        monkeypatch.setattr(Path, method, forbidden)
    environment.update(
        NORMALIZED_DATA_DIR="outputs/normalized", CANONICAL_DATA_DIR="outputs/canonical"
    )
    config = load_data_config(environment, project_root=tmp_path)
    assert config.get_root("FINANCIAL_REPORT_DIR") == tmp_path / environment["FINANCIAL_REPORT_DIR"]


@pytest.mark.parametrize(
    ("category", "key"),
    [
        ("raw_page_image", "FINANCIAL_REPORT_DIR"),
        ("ocr_page_json", "FINANCIAL_OCR_DIR"),
        ("ocr_crop", "FINANCIAL_OCR_DIR"),
    ],
)
def test_path_mapping_boundary(category, key, environment, tmp_path, monkeypatch):
    from vietnamese_financial_multi_agent.document_processing.contracts import (
        PathMappingRequest,
        PathReference,
        PathRootMapping,
        map_path_lexically,
    )

    request = PathMappingRequest(
        contract_version="path_mapping_v1",
        reference=PathReference(
            original_path="/synthetic/source/BBS/2024/page.png",
            category=category,
            source_ref="synthetic-run",
            source_location=["page", "image"],
        ),
        mappings=[
            PathRootMapping(
                mapping_id="fixture",
                source_root="/synthetic/source",
                path_style="posix",
                destination_root_key=key,
                category=category,
                containment_policy="lexical_then_runtime",
            )
        ],
    )
    result = map_path_lexically(request)
    original = result.export_result()
    config = load_data_config(environment, project_root=tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Root lookup must not perform existence checks")

    monkeypatch.setattr(Path, "stat", forbidden)
    target = result.candidate_targets[0]
    assert config.get_root(target.root_key) == tmp_path / environment[key]
    assert target.relative_suffix == "BBS/2024/page.png"
    assert config.get_root(target.root_key).name != "page.png"
    assert result.export_result() == original
    assert result.status == "not_checked"
    assert result.existence_check == "not_checked"


@pytest.mark.parametrize("key", ["UNKNOWN", "NORMALIZED_DATA_DIR"])
def test_path_target_unknown_or_unconfigured(key, environment, tmp_path):
    from vietnamese_financial_multi_agent.document_processing.contracts import PathTarget

    target = PathTarget(mapping_id="fixture", root_key=key, relative_suffix="page.png")
    config = load_data_config(environment, project_root=tmp_path)
    with pytest.raises(DataConfigError):
        config.get_root(target.root_key)


def test_lookup_does_not_use_basename_or_join_suffix(environment, tmp_path):
    from vietnamese_financial_multi_agent.document_processing.contracts import PathTarget

    config = load_data_config(environment, project_root=tmp_path)
    # Configuration lookup không diễn giải/validate suffix, đó là trách nhiệm resolver.
    for suffix in ("A/2024/page.png", "B/2025/page.png", "../unsafe.png", "/absolute.png"):
        target = PathTarget(
            mapping_id="fixture", root_key="FINANCIAL_OCR_DIR", relative_suffix=suffix
        )
        assert config.get_root(target.root_key) == config.financial_ocr_dir


def test_core_has_no_reverse_imports():
    import ast

    source = Path(__file__).resolve().parents[2] / "src/core/data_config.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any("document_processing" in name for name in imports)


def test_public_api_and_whitelist_agree():
    from typing import get_args

    from vietnamese_financial_multi_agent.core import DataConfig as PublicDataConfig
    from vietnamese_financial_multi_agent.core import DataRootKey

    assert PublicDataConfig is DataConfig
    assert set(get_args(DataRootKey)) == set(DataConfig.ROOT_FIELDS)
