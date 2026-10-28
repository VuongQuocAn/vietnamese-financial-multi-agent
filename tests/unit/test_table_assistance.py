"""Targeted synthetic evidence/transport/reuse tests; không financial ground truth."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors
from vietnamese_financial_multi_agent.core.data_config import load_data_config
from vietnamese_financial_multi_agent.document_processing.checkpoints import (
    CheckpointRequest,
    CheckpointStore,
)
from vietnamese_financial_multi_agent.document_processing.classification_pilot import (
    MeteredModels,
    PilotStop,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
)
from vietnamese_financial_multi_agent.document_processing.ocr_loader import LoadedOCRPage
from vietnamese_financial_multi_agent.document_processing.table_assistance import (
    AssistanceConfig,
    TableReconstructor,
)
from vietnamese_financial_multi_agent.document_processing.table_pilot import (
    compose_tables,
    table_arguments,
)

from .test_classification import loaded
from .test_classification_pilot import policy, sdk_args, sdk_response
from .test_raw_ocr_contracts import payload as payload
from .test_table_reconstruction import page as page


def prediction():
    return dict(
        disposition="supported",
        rows=2,
        cols=2,
        cells=[
            dict(source_id=f"c{r}{c}", row=r, col=c, rowspan=1, colspan=1, placeholder_ids=[])
            for r in range(2)
            for c in range(2)
        ],
    )


class Harness:
    def __init__(self, page, tmp_path):
        mapping = loaded().mapping_result.model_copy(deep=True)
        mapping.reference.anchor.page = RawPageIdentity(
            **{k: getattr(page.page, k) for k in ("symbol", "year", "page", "image")},
            source_ref=mapping.reference.source_ref,
        )
        self.loaded = LoadedOCRPage(page, mapping, (), True)
        # Edge overlap used to block deterministic, but centers + same-row band support grid.
        page.elements[0].cells[0].bbox[2] = 21
        self.client = Mock()
        self.client.models.generate_content.return_value = sdk_response(prediction())
        self.service, self.guard, self.meter = compose_tables(
            self.client,
            policy().model_copy(
                update={"quota_limits": policy().quota_limits.model_copy(update={"rpd": 15})}
            ),
            sleep=lambda _: None,
        )
        config = load_data_config(
            {"FINANCIAL_REPORT_DIR": "raw", "FINANCIAL_OCR_DIR": "ocr"},
            project_root=tmp_path,
        )
        self.store = CheckpointStore(tmp_path / "checkpoints", data_config=config)
        self.data_config = config

    def run(self, config=None, store=True, **changes):
        args = table_arguments(self.loaded, "synthetic-credential")
        args.update(changes)
        return TableReconstructor(
            self.service, config=config, checkpoints=self.store if store else None
        ).reconstruct(
            self.loaded,
            "t",
            **args,
        )


@pytest.fixture
def harness(page, tmp_path):
    return Harness(page, tmp_path)


def codes(result):
    return {i.code for i in result.table.issues}


def test_supported_grid_layout_policy_and_source_immutability(harness):
    before = harness.loaded.page.export_source()
    result = harness.run()
    assert result.deterministic.status == "unresolved"
    assert result.table.status == "resolved"
    assert "reviewed_metadata_bbox_conflict" in codes(result)
    assert harness.loaded.page.export_source() == before
    assert [(c.id, c.text) for c in result.table.cells] == [
        (c.id, c.text) for c in harness.loaded.page.elements[0].cells
    ]
    assert all(
        c.anchors[0].observed_bbox == raw.bbox
        for c, raw in zip(result.table.cells, harness.loaded.page.elements[0].cells, strict=True)
    )


def test_deterministic_resolved_short_circuits_sdk(harness):
    harness.loaded.page.elements[0].cells[0].bbox[2] = 20
    result = harness.run()
    assert result.table.status == "resolved"
    assert result.table == result.deterministic
    assert result.prediction is None and harness.meter.requests == 0


def test_colspan_supported_by_other_row_and_placeholder_source(harness):
    raw = harness.loaded.page.elements[0]
    raw.cells[0].bbox = [0, 0, 40, 20]
    raw.cells[1].bbox = list(raw.bbox)
    raw.cells[1].text = ""
    p = prediction()
    p["cells"][0].update(colspan=2, placeholder_ids=["c01"])
    del p["cells"][1]
    harness.client.models.generate_content.return_value = sdk_response(p)
    result = harness.run()
    assert result.table.status == "resolved"
    assert len(result.table.cells) == 3
    assert [a.cell_id for a in result.table.cells[0].anchors] == ["c00", "c01"]
    assert result.table.cells[0].colspan == 2


def test_rowspan_supported_by_other_column(harness):
    raw = harness.loaded.page.elements[0]
    raw.cells[0].bbox = [0, 0, 20, 40]
    raw.cells[2].bbox = list(raw.bbox)
    raw.cells[2].text = ""
    p = prediction()
    p["cells"][0].update(rowspan=2, placeholder_ids=["c10"])
    del p["cells"][2]
    harness.client.models.generate_content.return_value = sdk_response(p)
    result = harness.run()
    assert result.table.status == "resolved"
    assert result.table.cells[0].rowspan == 2


def test_schema_rejects_model_text_or_value_invention(harness):
    p = prediction()
    p["cells"][0]["value"] = "fake-999"
    harness.client.models.generate_content.return_value = sdk_response(p)
    assert harness.run().table.status == "unresolved"
    assert list(harness.store.output_root.glob("*.json")) == []


@pytest.mark.parametrize("change", ["invent", "drop", "duplicate", "placeholder-data"])
def test_exact_raw_cell_coverage_rejects_hallucination_and_deletion(harness, change):
    p = prediction()
    if change == "invent":
        p["cells"][0]["source_id"] = "invented"
    if change == "drop":
        p["cells"].pop()
    if change == "duplicate":
        p["cells"][1]["source_id"] = "c00"
    if change == "placeholder-data":
        p["cells"][0].update(colspan=2, placeholder_ids=["c01"])
        del p["cells"][1]
    harness.client.models.generate_content.return_value = sdk_response(p)
    result = harness.run()
    assert result.table.status == "unresolved"
    assert {"invalid_cell_coverage", "invalid_placeholder"} & codes(result)
    assert len(result.table.cells) == 4


@pytest.mark.parametrize(
    "change,code",
    [
        ("collision", "grid_collision"),
        ("gap", "missing_grid_positions"),
        ("bounds", "span_out_of_bounds"),
        ("merge", "unsupported_merge"),
        ("reverse", "layout_order_conflict"),
        ("insufficient", "insufficient_structure_evidence"),
    ],
)
def test_grid_and_layout_evidence_rejection(harness, change, code):
    p = prediction()
    if change == "collision":
        p["cells"][0]["col"] = 1
    if change == "gap":
        p["cols"] = 3
    if change == "bounds":
        p["cells"][0]["colspan"] = 3
    if change == "merge":
        p["rows"] = 3
        p["cells"][0]["rowspan"] = 2
        p["cells"][1]["rowspan"] = 2
        p["cells"][2]["row"] = p["cells"][3]["row"] = 2
    if change == "reverse":
        p["cells"][0]["col"], p["cells"][1]["col"] = 1, 0
    if change == "insufficient":
        p["disposition"] = "insufficient"
    harness.client.models.generate_content.return_value = sdk_response(p)
    result = harness.run()
    assert result.table.status == "unresolved" and code in codes(result)


def test_metadata_containment_warning_does_not_remove_page_geometry_guard(harness):
    harness.loaded.page.elements[0].bbox = [1, 1, 40, 40]
    assert harness.run().table.status == "resolved"
    harness.loaded.page.elements[0].cells[0].bbox[0] = -1
    assert "source_geometry_failed" in codes(harness.run())
    assert harness.meter.requests == 1


def test_source_binding_and_duplicate_ids_stop_before_sdk(harness):
    assert "source_binding_failed" in codes(harness.run(source_ref="other-run"))
    raw = harness.loaded.page.elements[0]
    raw.cells[1].id = raw.cells[0].id
    assert "source_preflight_failed" in codes(harness.run())
    assert harness.meter.requests == 0


def test_cache_and_checkpoint_hits_revalidate_without_api(harness):
    first = harness.run()
    harness.meter.allow_new_requests = False
    cache = harness.run(store=False)
    checkpoint = harness.run()
    assert cache.llm_result.cache_hit
    assert checkpoint.checkpoint_status == "HIT"
    assert checkpoint.table == cache.table == first.table
    assert harness.meter.requests == 1


def test_checkpoint_invalid_prediction_uses_validated_cache(harness):
    first = harness.run()
    artifact = json.loads(next(harness.store.output_root.glob("*.json")).read_text())
    bad = prediction()
    bad["cells"][0]["source_id"] = "absent"
    harness.store.save_verified(
        CheckpointRequest.model_validate(artifact["request"]), bad, verified=True
    )
    result = harness.run()
    assert result.checkpoint_status == "INVALID"
    assert result.llm_result.cache_hit and result.table == first.table


@pytest.mark.parametrize(
    "field",
    ["model", "prompt_revision", "policy_revision", "processing_version", "max_output_tokens"],
)
def test_config_invalidation_never_reuses_checkpoint_or_cache(harness, field):
    harness.run()
    value = 8192 if field == "max_output_tokens" else "changed-revision"
    result = harness.run(config=AssistanceConfig(**{field: value}))
    assert result.checkpoint_status == "STALE"
    assert result.llm_result is not None and not result.llm_result.cache_hit


def test_raw_input_and_schema_fingerprint_invalidation(harness, monkeypatch):
    harness.run()
    harness.loaded.page.elements[0].cells[0].text += " source-revision"
    result = harness.run()
    assert result.checkpoint_status == "STALE" and not result.llm_result.cache_hit
    from vietnamese_financial_multi_agent.document_processing import table_assistance as module

    original = module.table_schema_registry

    def changed():
        registry = original()
        key = module.SCHEMA_REF.to_json()
        registry._schemas[key]["description"] = "revised-schema"
        return registry

    monkeypatch.setattr(module, "table_schema_registry", changed)
    result = harness.run()
    assert result.checkpoint_status == "STALE" and not result.llm_result.cache_hit


def test_provider_error_keeps_unresolved_and_unverified(harness):
    harness.client.models.generate_content.side_effect = errors.ClientError(
        429, {"error": {"message": "private"}}
    )
    result = harness.run()
    assert result.table.status == "unresolved"
    assert harness.meter.requests == 1 and harness.meter.failures == 1
    assert list(harness.store.output_root.glob("*.json")) == []


def test_table_meter_caps_sdk_calls_at_fifteen_including_failure():
    models = Mock()
    models.generate_content.return_value = sdk_response()
    meter = MeteredModels(models, request_limit=15, output_cap=16384, sleep=lambda _: None)
    for _ in range(15):
        meter.generate_content(**sdk_args())
    with pytest.raises(PilotStop):
        meter.generate_content(**sdk_args())
    assert meter.requests == models.generate_content.call_count == 15
    assert meter.input_token_budget is None


def test_runner_persists_results_and_probes_without_new_requests(harness, tmp_path):
    from vietnamese_financial_multi_agent.document_processing.table_pilot import run_tables

    prepared = SimpleNamespace(
        units=((harness.loaded, "t"),),
        root=tmp_path / "pilot",
        config=harness.data_config,
        verify=lambda: None,
    )
    stats, records = run_tables(prepared, harness.service, harness.meter, "synthetic-credential")
    assert stats["baseline"] == {"unresolved": 1}
    assert stats["assisted"] == {"resolved": 1}
    assert stats["cache_hits"] == stats["checkpoint_hits"] == 1
    assert stats["requests"] == 1 and stats["validated_anchors"] == 5
    assert records[0]["result"]["status"] == "resolved"
