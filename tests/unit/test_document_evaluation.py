"""Synthetic engineering fixtures; không phải benchmark tài chính."""

import hashlib
import json

import pytest
from vietnamese_financial_multi_agent.document_processing.evaluation import (
    distance,
    evaluate,
    load_inputs,
    normalize_text,
    normalize_value,
)


def fixture():
    identity = {"source_ref": "synthetic", "page": 1}
    b = {
        "files": {"image": {"sha256": "hash"}},
        "pages": [{"id": "p", "image": "image", "identity": identity}],
        "pipelines": {"A": {"pages": ["p"]}, "B": {"pages": ["p"]}},
        "labels": [
            {
                "id": "l",
                "page": "p",
                "image_sha256": "hash",
                "verification": "direct_image_review",
                "region": "synthetic",
                "kind": "financial",
                "expected": "1.000",
                "position": [0, 1],
                "bindings": {
                    "A": {
                        "file": "a",
                        "pointer": ["cell"],
                        "source_pointer": ["page"],
                        "cell_id": "c",
                    }
                },
            }
        ],
    }
    return b, {
        "a": {
            "page": identity,
            "cell": {"text": "1000", "id": "c", "row": 0, "col": 1, "status": "unresolved"},
        }
    }


def test_normalization_is_conservative():
    assert normalize_value("1.234.567") == "1234567"
    assert normalize_value("-1.000") == "-1000"
    for value in ["1,000", "1.23", "-", "1 000", "(1000)"]:
        assert normalize_value(value) is None
    assert normalize_text(" A\n B ") == "A B"


def test_edit_distance():
    assert distance("kitten", "sitting") == 3
    assert distance([], ["word"]) == 1


def test_raw_normalized_and_acceptance_are_independent():
    b, d = fixture()
    r = evaluate(b, d)["pipelines"]["A"]
    assert r["common"]["financial_raw"]["rate"] == 0
    assert r["common"]["financial_normalized"]["rate"] == 1
    assert r["common"]["cell_alignment"]["rate"] == 1
    assert r["structure_accepted"]["rate"] is None


def test_missing_output_stays_in_denominator():
    b, d = fixture()
    r = evaluate(b, d)["pipelines"]["B"]["common"]
    assert r["coverage"]["rate"] == 0
    assert r["financial_normalized"]["total"] == 1
    assert r["cer"]["rate"] == 1


def test_sample_intersection_is_explicit():
    b, d = fixture()
    b["pipelines"]["B"]["pages"] = []
    r = evaluate(b, d)
    assert r["common_pages"] == []
    assert r["pipelines"]["A"]["common"]["text_em"]["rate"] is None
    assert r["pipelines"]["A"]["available"]["labels"] == 1


def test_candidate_or_duplicate_labels_are_rejected():
    b, d = fixture()
    b["labels"][0]["verification"] = "candidate"
    with pytest.raises(ValueError, match="unverified_label"):
        evaluate(b, d)
    b["labels"] *= 2
    with pytest.raises(ValueError, match="duplicate_label"):
        evaluate(b, d)


def test_grounding_does_not_follow_content_or_status():
    b, d = fixture()
    d["a"]["page"] = {"source_ref": "other", "page": 1}
    r = evaluate(b, d)["pipelines"]["A"]["common"]
    assert r["financial_normalized"]["rate"] == 1
    assert r["grounding"]["rate"] == 0


def test_frozen_files_and_root_guard(tmp_path):
    data = b"{}"
    (tmp_path / "out.json").write_bytes(data)
    b = {"files": {"x": {"path": "out.json", "sha256": hashlib.sha256(data).hexdigest()}}}
    assert load_inputs(b, tmp_path) == {"x": json.loads(data)}
    (tmp_path / "out.json").write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match="snapshot_mismatch"):
        load_inputs(b, tmp_path)
    b["files"]["x"]["path"] = "../outside.json"
    with pytest.raises(ValueError, match="input_outside_root"):
        load_inputs(b, tmp_path)
