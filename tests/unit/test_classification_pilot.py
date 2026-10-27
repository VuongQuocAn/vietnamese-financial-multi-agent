"""Synthetic runner/SDK only; không credentials hoặc real financial data."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors, types
from vietnamese_financial_multi_agent.core.data_config import load_data_config
from vietnamese_financial_multi_agent.core.llm_quota_budget import ProjectPolicy, QuotaLimits
from vietnamese_financial_multi_agent.document_processing import classification_pilot as pilot

from .test_classification import loaded, prediction
from .test_extraction_pilot import config as config
from .test_extraction_pilot import payload as payload
from .test_extraction_pilot import prepare as extraction_prepare
from .test_extraction_pilot import sample as sample


def policy(**changes):
    values = dict(
        account_ref="synthetic-account",
        project_ref="synthetic-project",
        credential_refs=("synthetic-credential",),
        provider="gemini",
        model="gemini-3.5-flash-lite",
        tier="free",
        mapping_confirmed=True,
        verification_source="synthetic-test",
        quota_limits=QuotaLimits(rpm=5, tpm=250_000, rpd=20),
    )
    values.update(changes)
    return ProjectPolicy(**values)


def sdk_response(payload=None, *, usage=True):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    parts=[
                        types.Part(text=json.dumps(prediction() if payload is None else payload))
                    ]
                ),
                finish_reason="STOP",
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100,
            candidates_token_count=20,
            total_token_count=120,
        )
        if usage
        else None,
    )


def setup(tmp_path, *, pages=None, raw=None):
    config = load_data_config(
        {"FINANCIAL_REPORT_DIR": "data/raw", "FINANCIAL_OCR_DIR": "data/processed"},
        project_root=tmp_path,
    )
    prepared = SimpleNamespace(
        pages=pages or (loaded(),),
        config=config,
        root=tmp_path / "artifacts/pilot",
        verify=Mock(),
        statistics=lambda: dict(selected_pages=len(pages or (loaded(),))),
    )
    client = Mock()
    client.models.generate_content.return_value = raw or sdk_response()
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    service, guard, meter = pilot.compose_pilot(client, policy(), clock=lambda: now[0], sleep=sleep)
    return prepared, client, service, guard, meter


def test_smoke_then_resolved_checkpoint_resume(tmp_path, capsys):
    prepared, client, service, guard, meter = setup(tmp_path)
    result = pilot.run_pilot(prepared, service, meter, credential_ref="synthetic-credential")
    assert result["smoke_passed"] and result["resolved"] == 1
    assert result["api_requests"] == 2 and result["real_api_requests"] == 1
    assert result["input_tokens"] == 200 and result["total_tokens"] == 240
    assert result["checkpoint_hits"] == 1 and result["source_unchanged"]
    calls = meter.requests
    resumed = pilot.run_pilot(
        prepared, service, meter, credential_ref="synthetic-credential", smoke=False
    )
    assert resumed["checkpoint_hits"] == 2 and meter.requests == calls
    assert not capsys.readouterr().out
    public = json.dumps(result)
    assert str(tmp_path) not in public and "SYNTHETIC" not in public
    assert client.models.generate_content.call_count == 2
    assert guard.snapshot("synthetic-project", "gemini", policy().model)["rpd_used"] == 2


def test_unresolved_response_cache_reuse(tmp_path):
    args = setup(tmp_path, raw=sdk_response(prediction(None, "insufficient", [])))
    prepared, client, service, _, meter = args
    result = pilot.run_pilot(prepared, service, meter, credential_ref="synthetic-credential")
    assert result["unresolved"] == 1 and result["cache_hits"] == 1
    assert result["checkpoint_hits"] == 0 and client.models.generate_content.call_count == 2


@pytest.mark.parametrize("failure", ["auth", "quota", "schema", "unknown_usage"])
def test_smoke_failure_never_sends_real_data(tmp_path, failure):
    prepared, client, service, _, meter = setup(tmp_path)
    if failure in {"auth", "quota"}:
        client.models.generate_content.side_effect = errors.ClientError(
            401 if failure == "auth" else 429, {"error": {"message": "private-provider-payload"}}
        )
    elif failure == "schema":
        client.models.generate_content.return_value = sdk_response({"unexpected": "private"})
    else:
        client.models.generate_content.return_value = sdk_response(usage=False)
    result = pilot.run_pilot(prepared, service, meter, credential_ref="synthetic-credential")
    assert result["processed_pages"] == 0 and result["api_requests"] == 1
    assert result["real_api_requests"] == 0 and result["stop_reason"]
    assert client.models.generate_content.call_count == 1
    assert "private" not in json.dumps(result)
    assert result["schema_errors"] == (1 if failure == "schema" else 0)


def sdk_args(text="Synthetic"):
    return dict(
        model=policy().model,
        contents=[types.Content(parts=[types.Part(text=text)])],
        config=types.GenerateContentConfig(max_output_tokens=512),
    )


def test_meter_paces_and_caps_failed_attempts_without_retry():
    models = Mock()
    models.generate_content.return_value = sdk_response()
    now, starts = [0.0], []

    def sleep(n):
        now[0] += n

    meter = pilot.MeteredModels(models, clock=lambda: now[0], sleep=sleep)
    for _ in range(20):
        meter.generate_content(**sdk_args())
        starts.append(now[0])
    assert all(b - a >= 12.09 for a, b in zip(starts, starts[1:], strict=False))
    with pytest.raises(pilot.PilotStop, match="request_limit"):
        meter.generate_content(**sdk_args())
    assert models.generate_content.call_count == 20


def test_input_bound_denied_before_send_and_unknown_usage_stops():
    models = Mock()
    meter = pilot.MeteredModels(models)
    with pytest.raises(pilot.PilotStop, match="input_token_limit"):
        meter.generate_content(**sdk_args("s" * 20_000))
    models.generate_content.assert_not_called()
    meter = pilot.MeteredModels(models)
    models.generate_content.return_value = sdk_response(usage=False)
    meter.generate_content(**sdk_args())
    assert meter.input_charged > 0 and meter.unknown_usage == 1
    with pytest.raises(pilot.PilotStop, match="pilot_stopped"):
        meter.generate_content(**sdk_args())
    assert models.generate_content.call_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        dict(tier="paid"),
        dict(mapping_confirmed=False),
        dict(model="other-model"),
        dict(credential_refs=("a", "b")),
        dict(quota_limits=QuotaLimits(rpm=6, tpm=250_000, rpd=20)),
    ],
)
def test_policy_rejects_paid_unconfirmed_rotation_or_high_rate(changes):
    client = Mock()
    with pytest.raises(pilot.PilotStop, match="invalid_pilot_policy"):
        pilot.compose_pilot(client, policy(**changes))
    client.models.generate_content.assert_not_called()


def test_source_change_stops_before_gateway(tmp_path):
    prepared, client, service, _, meter = setup(tmp_path)
    prepared.verify.side_effect = pilot.PilotStop("source_changed")
    with pytest.raises(pilot.PilotStop, match="source_changed"):
        pilot.run_pilot(prepared, service, meter, credential_ref="synthetic-credential")
    client.models.generate_content.assert_not_called()


def test_verified_manifest_dry_run_and_source_change(sample, monkeypatch):
    from vietnamese_financial_multi_agent.document_processing import extraction_pilot

    paths = extraction_prepare(sample, pages=10)
    # Fixture tạo frozen parent có 10 pages trong cùng stratum, không đổi selector production.
    monkeypatch.setattr(
        extraction_pilot,
        "select_sample",
        lambda rows, _: ([dict(row=r, group="coverage", reasons=["synthetic"]) for r in rows], {}),
    )
    parent = extraction_pilot.build_manifest(sample.config, *paths)
    path = extraction_pilot.freeze_manifest(parent, sample.config)
    prepared = pilot.prepare_pilot(sample.config, path, limit=10)
    assert len(prepared.pages) == 10
    assert all(page.identity_checked for page in prepared.pages)
    assert all(
        page.mapping_result.reference.source_ref == page.mapping_result.reference.original_path
        for page in prepared.pages
    )
    assert prepared.manifest == pilot.prepare_pilot(sample.config, path, limit=10).manifest
    sample.source.write_bytes(sample.source.read_bytes() + b" ")
    with pytest.raises(pilot.PilotStop, match="source_changed"):
        prepared.verify()


def test_probe_miss_never_calls_provider():
    models = Mock()
    meter = pilot.MeteredModels(models)
    meter.allow_new_requests = False
    with pytest.raises(pilot.PilotStop, match="reuse_probe_miss"):
        meter.generate_content(**sdk_args())
    models.generate_content.assert_not_called()
    assert meter.requests == 0


def test_local_token_denial_is_not_provider_error_or_completed_page(tmp_path):
    prepared, client, service, _, meter = setup(tmp_path)
    meter.input_charged = 19_999
    result = pilot.run_pilot(
        prepared, service, meter, credential_ref="synthetic-credential", smoke=False
    )
    assert result["stop_reason"] == "input_token_limit"
    assert result["attempted_pages"] == 1 and result["processed_pages"] == 0
    assert result["budget_denials"] == 1 and result["provider_errors"] == 0
    assert result["resolved"] == result["unresolved"] == 0
    assert result["api_requests"] == 0
    client.models.generate_content.assert_not_called()
