"""Synthetic focused tests; không phải financial ground truth."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    GatewayBinding,
    ProjectRegistry,
    QuotaBudgetGuard,
    QuotaLimits,
)
from vietnamese_financial_multi_agent.document_processing.classification_pilot import MeteredModels
from vietnamese_financial_multi_agent.document_processing.ocr_correction import (
    OCRCorrector,
    correction_schema_registry,
)

from .test_classification import loaded
from .test_classification_pilot import policy, sdk_args, sdk_response


def proposal(**changes):
    value = dict(
        element_id="e0", cell_id=None, original="Báo cá0", proposed="Báo cáo", reason="0/o"
    )
    value.update(changes)
    return value


@pytest.fixture
def harness():
    page = loaded(texts=["Báo cá0", "1.234.56O"])
    client = Mock()
    client.models.generate_content.return_value = sdk_response(
        dict(disposition="assessed", corrections=[proposal()])
    )
    schemas = correction_schema_registry()
    adapter = GeminiAdapter(client, schema_registry=schemas)
    gateway = SharedLLMGateway({"gemini": adapter}, schema_registry=schemas)
    p = policy(quota_limits=QuotaLimits(rpm=15, tpm=250_000, rpd=500))
    guard = QuotaBudgetGuard(
        ProjectRegistry([p]),
        [
            GatewayBinding(
                p.account_ref, p.project_ref, p.credential_refs[0], p.provider, p.model, gateway
            )
        ],
    )
    guard.initialize(confirmed_fresh_scope=True)
    service = CachedLLMService(
        guard,
        tenant_ref="test",
        project_ref=p.project_ref,
        credential_refs=frozenset(p.credential_refs),
        configuration_revision="test",
        scope_confirmed=True,
        schema_registry=schemas,
    )

    def run():
        return (
            OCRCorrector(service)
            .correct(page, source_ref="synthetic-doc/run-A", credential_ref="synthetic-credential")
            .view
        )

    return SimpleNamespace(page=page, client=client, run=run)


def test_valid_anchor_raw_immutable_and_complete_structured_context(harness):
    before = harness.page.page.export_source()
    view = harness.run()
    correction = view.corrections[0]
    assert correction.status == "proposed"
    assert correction.source_anchor.element_id == "e0"
    assert correction.source_anchor.observed_bbox == before["elements"][0]["bbox"]
    assert harness.page.page.export_source() == before
    assert view.texts[0].effective_text == "Báo cá0" and view.texts[0].proposed == "Báo cáo"
    args = harness.client.models.generate_content.call_args.kwargs
    assert args["model"] == "gemini-3.5-flash-lite"
    assert args["config"].response_mime_type == "application/json"
    assert args["config"].response_json_schema
    assert json.loads(args["contents"][0].parts[0].text)["raw"] == before


@pytest.mark.parametrize("change", [dict(element_id="fake"), dict(original="Báo cáo")])
def test_source_mismatch_rejected(harness, change):
    harness.client.models.generate_content.return_value = sdk_response(
        dict(disposition="assessed", corrections=[proposal(**change)])
    )
    view = harness.run()
    assert view.status == "unresolved" and view.corrections == []
    assert "source_id_or_original_mismatch" in view.issues
    assert all(t.effective_text == t.original for t in view.texts)


def test_financial_number_never_confirmed_by_model_reason(harness):
    harness.client.models.generate_content.return_value = sdk_response(
        dict(
            disposition="assessed",
            corrections=[
                proposal(
                    element_id="e1",
                    original="1.234.56O",
                    proposed="1.234.560",
                    reason="Accounting balances prove it",
                )
            ],
        )
    )
    view = harness.run()
    assert view.corrections[0].status == "proposed"
    assert view.corrections[0].issues == ["independent_evidence_required"]
    assert view.texts[1].effective_text == "1.234.56O"


@pytest.mark.parametrize("failure", ["schema", "provider"])
def test_errors_return_unresolved_without_invented_corrections(harness, failure):
    if failure == "schema":
        harness.client.models.generate_content.return_value = sdk_response({"bad": True})
    else:
        harness.client.models.generate_content.side_effect = errors.ClientError(
            429, {"error": {"message": "private"}}
        )
    view = harness.run()
    assert view.status == "unresolved" and not view.corrections
    assert all(t.status == "unresolved" and t.effective_text == t.original for t in view.texts)
    assert harness.client.models.generate_content.call_count == 1


def test_clean_page_needs_no_correction(harness):
    harness.client.models.generate_content.return_value = sdk_response(
        dict(disposition="assessed", corrections=[])
    )
    view = harness.run()
    assert view.status == "assessed" and view.corrections == []
    assert all(t.status == "unchanged" for t in view.texts)


def test_conflicting_candidates_remain_unresolved(harness):
    harness.client.models.generate_content.return_value = sdk_response(
        dict(disposition="assessed", corrections=[proposal(), proposal(proposed="Báo cao")])
    )
    view = harness.run()
    assert all(c.status == "unresolved" for c in view.corrections)
    assert view.texts[0].status == "unresolved" and view.texts[0].proposed is None


def test_source_preflight_stops_api_for_ambiguous_ids_or_binding(harness):
    harness.page.mapping_result.reference.source_ref = "other-run"
    assert "source_binding_failed" in harness.run().issues
    harness.page.mapping_result.reference.source_ref = "synthetic-doc/run-A"
    harness.page.page.elements[1].id = "e0"
    assert "ambiguous_source_ids" in harness.run().issues
    harness.client.models.generate_content.assert_not_called()


def test_cell_anchor_is_scoped_to_its_table(harness):
    from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRTable

    harness.page.page.elements.append(
        OCRTable(
            id="table",
            type="table",
            bbox=[1, 1, 190, 90],
            name="Synthetic",
            crop="synthetic.png",
            cells=[
                dict(id="e0", row=0, col=0, bbox=[1, 1, 90, 20], text="1.O", line_count=0, lines=[])
            ],
        )
    )
    harness.client.models.generate_content.return_value = sdk_response(
        dict(
            disposition="assessed",
            corrections=[
                proposal(element_id="table", cell_id="e0", original="1.O", proposed="1.0")
            ],
        )
    )
    view = harness.run()
    anchor = view.corrections[0].source_anchor
    assert (anchor.element_id, anchor.table_id, anchor.cell_id) == ("table", "table", "e0")
    assert view.texts[-1].effective_text == "1.O"


def test_meter_uses_selected_rpm_without_total_input_cap():
    client = Mock()
    client.generate_content.return_value = sdk_response()
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    meter = MeteredModels(client, rpm=15, clock=lambda: now[0], sleep=sleep)
    meter.generate_content(**sdk_args())
    meter.generate_content(**sdk_args())
    assert 4.0 <= now[0] < 5.0
    assert meter.requests == 2 and meter.input_token_budget is None
