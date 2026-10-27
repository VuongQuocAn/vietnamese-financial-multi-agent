"""Synthetic persistence/integrity tests; không phải financial ground truth."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.data_config import load_data_config
from vietnamese_financial_multi_agent.document_processing.checkpoints import (
    CheckpointRequest,
    CheckpointStore,
    ProcessingUnit,
    fingerprint_json,
)
from vietnamese_financial_multi_agent.document_processing.contracts import (
    parse_document_understanding,
    validate_understanding_quality,
)


@pytest.fixture
def config(tmp_path):
    return load_data_config(
        {"FINANCIAL_REPORT_DIR": "data/raw", "FINANCIAL_OCR_DIR": "data/processed"},
        project_root=tmp_path,
    )


@pytest.fixture
def store(tmp_path, config):
    return CheckpointStore(tmp_path / "checkpoints", data_config=config)


@pytest.fixture
def checkpoint_request():
    return CheckpointRequest(
        unit=ProcessingUnit(source_ref="synthetic-document/run-A"),
        stage="synthetic-stage",
        input_fingerprint=fingerprint_json({"text": "Nguồn 1.234", "provenance": "run-A"}),
        config_fingerprint=fingerprint_json({"threshold": 0.5}),
        processing_version="synthetic-v1",
    )


def artifact_path(store):
    return next(store.output_root.glob("*.json"))


def test_persistence_restart_and_detached_result(store, checkpoint_request, config):
    assert store.lookup(checkpoint_request).status == "MISS"
    payload = {"text": "  Tiếng Việt\n1.234,50 ", "values": [None, True, 3, 1.5]}
    store.save_verified(checkpoint_request, payload, verified=True)
    payload["text"] = "mutated"
    reopened = CheckpointStore(store.output_root, data_config=config)
    hit = reopened.lookup(checkpoint_request)
    assert hit.status == "HIT"
    assert hit.result["text"] == "  Tiếng Việt\n1.234,50 "
    hit.result.clear()
    assert reopened.lookup(checkpoint_request).result["values"] == [None, True, 3, 1.5]
    # Một interpreter mới thực sự đọc artifact; không chỉ reopen object trong RAM.
    code = """
import json, sys
from pathlib import Path
from vietnamese_financial_multi_agent.core.data_config import DataConfig
from vietnamese_financial_multi_agent.document_processing.checkpoints import CheckpointRequest, CheckpointStore
config = DataConfig.model_validate({k: Path(v) if v is not None else None for k, v in json.loads(sys.argv[2]).items()})
store = CheckpointStore(Path(sys.argv[1]), data_config=config)
hit = store.lookup(CheckpointRequest.model_validate(json.loads(sys.argv[3])))
assert hit.status == 'HIT' and hit.result['values'] == [None, True, 3, 1.5]
"""
    subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(store.output_root),
            config.model_dump_json(),
            checkpoint_request.model_dump_json(exclude_unset=True),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def test_null_result_is_a_hit(store, checkpoint_request):
    store.save_verified(checkpoint_request, None, verified=True)
    assert store.lookup(checkpoint_request).status == "HIT"
    assert store.lookup(checkpoint_request).result is None


@pytest.mark.parametrize("field", ["input_fingerprint", "config_fingerprint", "processing_version"])
def test_revision_is_stale(store, checkpoint_request, field):
    store.save_verified(checkpoint_request, {"old": True}, verified=True)
    changed = checkpoint_request.model_dump(exclude_unset=True)
    changed[field] = "v2" if field == "processing_version" else fingerprint_json("changed")
    lookup = store.lookup(CheckpointRequest.model_validate(changed))
    assert lookup.status == "STALE" and lookup.result is None


def test_distinct_units_pages_sources_and_stages(store, checkpoint_request):
    identities = [
        checkpoint_request,
        checkpoint_request.model_copy(update={"stage": "another-stage"}),
        checkpoint_request.model_copy(
            update={"unit": ProcessingUnit(source_ref="other-document/run-A")}
        ),
    ]
    for page, source in [(1, "run-A"), (2, "run-A"), (1, "run-B")]:
        identities.append(
            checkpoint_request.model_copy(
                update={
                    "unit": ProcessingUnit(
                        source_ref="synthetic-document/run-A",
                        page=dict(
                            symbol="SYNTHETIC",
                            year="2025",
                            page=page,
                            image="source/page.png",
                            source_ref=source,
                        ),
                    )
                }
            )
        )
    for index, identity in enumerate(identities):
        assert store.lookup(identity).status == "MISS"
        store.save_verified(identity, index, verified=True)
    assert [store.lookup(identity).result for identity in identities] == list(range(6))


@pytest.mark.parametrize("value", [None, "", " ", "a" * 63, "G" * 64])
def test_missing_or_invalid_fingerprint(checkpoint_request, value):
    payload = checkpoint_request.model_dump()
    payload["input_fingerprint"] = value
    with pytest.raises(ValidationError):
        CheckpointRequest.model_validate(payload)
    del payload["input_fingerprint"]
    with pytest.raises(ValidationError):
        CheckpointRequest.model_validate(payload)


def test_source_binding_required():
    with pytest.raises(ValidationError):
        ProcessingUnit(source_ref=" ")
    with pytest.raises(ValidationError):
        ProcessingUnit(source_ref="doc", page=dict(symbol="S", year="2025", page=1, image="p"))


def test_stable_fingerprint():
    assert fingerprint_json({"a": 1, "b": "Việt"}) == fingerprint_json({"b": "Việt", "a": 1})
    assert fingerprint_json({"a": None}) != fingerprint_json({})
    assert fingerprint_json({"a": 1}) != fingerprint_json({"a": "1"})


@pytest.mark.parametrize("value", [{1: "bad"}, (1, 2), float("nan"), float("inf"), Path("x")])
def test_non_json_rejected_before_publication(store, checkpoint_request, value):
    with pytest.raises(ValueError):
        store.save_verified(checkpoint_request, value, verified=True)
    assert store.lookup(checkpoint_request).status == "MISS"


@pytest.mark.parametrize("verified", [False, None, 1, "true"])
def test_explicit_attestation_required(store, checkpoint_request, verified):
    with pytest.raises(ValueError):
        store.save_verified(checkpoint_request, {}, verified=verified)
    assert store.lookup(checkpoint_request).status == "MISS"


@pytest.mark.parametrize(
    "change",
    ["payload", "format", "missing", "unverified", "metadata", "truncated", "duplicate", "nan"],
)
def test_corrupt_or_incomplete_artifact_is_invalid(store, checkpoint_request, change):
    store.save_verified(checkpoint_request, {"text": "original"}, verified=True)
    path = artifact_path(store)
    body = json.loads(path.read_bytes())
    if change == "payload":
        body["result"]["text"] = "corrupt"
    elif change == "format":
        body["format_version"] = "future"
    elif change == "missing":
        del body["result"]
    elif change == "unverified":
        body["verified"] = False
    elif change == "metadata":
        body["request"]["processing_version"] = "tampered"
    content = json.dumps(body)
    if change == "truncated":
        content = content[:20]
    elif change == "duplicate":
        content = content[:-1] + ', "verified": true}'
    elif change == "nan":
        content = content.replace('"original"', "NaN")
    path.write_text(content, encoding="utf-8")
    lookup = store.lookup(checkpoint_request)
    assert lookup.status == "INVALID" and lookup.result is None


@pytest.mark.parametrize("operation", ["fsync", "replace"])
@pytest.mark.parametrize("existing", [False, True])
def test_interruption_never_publishes_partial_result(
    store, checkpoint_request, operation, existing
):
    if existing:
        store.save_verified(checkpoint_request, "old", verified=True)
    with patch(
        f"vietnamese_financial_multi_agent.document_processing.checkpoints.os.{operation}",
        side_effect=OSError("synthetic failure"),
    ):
        with pytest.raises(OSError):
            store.save_verified(checkpoint_request, "new", verified=True)
    hit = store.lookup(checkpoint_request)
    assert hit.status == ("HIT" if existing else "MISS")
    assert hit.result == ("old" if existing else None)
    assert not list(store.output_root.glob("*.tmp"))


def test_orphan_temp_and_read_error(store, checkpoint_request):
    store.output_root.mkdir()
    (store.output_root / ".checkpoint-interrupted.tmp").write_text('{"verified":')
    assert store.lookup(checkpoint_request).status == "MISS"
    with patch.object(Path, "read_bytes", side_effect=PermissionError("synthetic")):
        with pytest.raises(PermissionError):
            store.lookup(checkpoint_request)


def test_write_failure_cleans_temp(store, checkpoint_request):
    from vietnamese_financial_multi_agent.document_processing import checkpoints

    original = checkpoints.tempfile.NamedTemporaryFile

    def fail_write(content):
        raise OSError("synthetic write failure")

    def broken_stream(**kwargs):
        stream = original(**kwargs)
        stream.write = fail_write
        return stream

    with patch.object(checkpoints.tempfile, "NamedTemporaryFile", side_effect=broken_stream):
        with pytest.raises(OSError):
            store.save_verified(checkpoint_request, "new", verified=True)
    assert store.lookup(checkpoint_request).status == "MISS"
    assert not list(store.output_root.iterdir())


def test_source_roots_protected_and_unchanged(store, checkpoint_request, config):
    config.financial_ocr_dir.mkdir(parents=True)
    raw = config.financial_ocr_dir / "synthetic.json"
    raw.write_bytes(b'{"synthetic":true}')
    before = (raw.read_bytes(), raw.stat().st_mtime_ns)
    for root in [
        config.financial_ocr_dir,
        config.financial_ocr_dir / "checkpoints",
        config.project_root,
        config.project_root / "data/raw",
        config.project_root / "data/recovered_crops",
    ]:
        with pytest.raises(ValueError):
            CheckpointStore(root, data_config=config)
    store.save_verified(checkpoint_request, {"source_ref": "synthetic"}, verified=True)
    assert (raw.read_bytes(), raw.stat().st_mtime_ns) == before


@pytest.mark.integration
def test_document_understanding_v1_round_trip(store, checkpoint_request):
    identity = dict(
        symbol="SYNTHETIC",
        year="2025",
        page=1,
        image="source/page.png",
        source_ref="synthetic-run/page-1",
    )
    payload = dict(
        contract_version="document_understanding_v1",
        raw_page=identity,
        classification=dict(label=None, status="unresolved", anchors=[]),
        text_regions=[
            dict(
                id="text-1",
                text="  Tổng cộng 1.234,50\n",
                status="uncertain",
                anchors=[
                    dict(
                        page=identity,
                        status="unresolved",
                        element_id=None,
                        observed_bbox=[1, 2, 30, 40],
                    )
                ],
            )
        ],
        tables=[],
        issues=[],
    )
    parsed = parse_document_understanding(payload)
    assert validate_understanding_quality(parsed) == []
    checkpoint_request = checkpoint_request.model_copy(
        update={"unit": ProcessingUnit(source_ref="doc/run", page=identity)}
    )
    store.save_verified(checkpoint_request, parsed.export_result(), verified=True)
    hit = store.lookup(checkpoint_request)
    assert hit.status == "HIT"
    restored = parse_document_understanding(hit.result)
    assert validate_understanding_quality(restored) == []
    assert restored.export_result() == payload
