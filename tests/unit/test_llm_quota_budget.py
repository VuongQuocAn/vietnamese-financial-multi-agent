"""Synthetic quota/budget tests với fake clock; không key thật/live quota calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Event, Lock
from unittest.mock import Mock

import pytest
from google.genai import types
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    GatewayError,
    SchemaReference,
    Usage,
    parse_llm_request,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    BudgetLimit,
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
    QuotaLimits,
    Reservation,
    manual_retry_eligible,
)
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry


class Clock:
    def __init__(self, value="2026-10-27T12:00:00+00:00"):
        self.now = datetime.fromisoformat(value)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def policy(project="project_a", credentials=("credential_a", "credential_b"), **changes):
    values = dict(
        account_ref=f"account_{project}",
        project_ref=project,
        credential_refs=credentials,
        provider="gemini",
        model="gemini-3.5-flash-lite",
        tier="free",
        quota_limits=QuotaLimits(rpm=15, tpm=250000, rpd=500),
        verification_source="synthetic_test",
        mapping_confirmed=True,
    )
    values.update(changes)
    return ProjectPolicy(**values)


def request(request_id="synthetic-1", model="gemini-3.5-flash-lite", cap=32):
    return parse_llm_request(
        {
            "contract_version": "llm_gateway_v1",
            "request_id": request_id,
            "model": {"provider": "gemini", "model": model},
            "messages": [{"role": "user", "content": "Synthetic request"}],
            "generation": {} if cap is None else {"max_output_tokens": cap},
        }
    )


def reserve(tokens=100, spend=None):
    return Reservation(
        token_upper_bound=tokens,
        token_basis="caller_attested_upper_bound",
        **(
            {
                "spending_upper_bound": Decimal(spend),
                "currency": "USD",
                "spending_basis": "approved_upper_bound",
            }
            if spend is not None
            else {}
        ),
    )


def budget(value):
    return BudgetLimit(amount=Decimal(value), currency="USD")


def build(*, policies=None, handler=None, clock=None, overall=None, initialized=True):
    policies = policies or [policy()]
    calls = []

    def transport(req):
        calls.append(req.request_id)
        return handler(req) if handler else FakeLLMTransport()(req)

    gateway = SharedLLMGateway({"gemini": transport})
    bindings = [
        GatewayBinding(p.account_ref, p.project_ref, c, p.provider, p.model, gateway)
        for p in policies
        for c in p.credential_refs
    ]
    clock = clock or Clock()
    guard = QuotaBudgetGuard(
        ProjectRegistry(policies), bindings, overall_budget=overall, clock=clock
    )
    if initialized:
        guard.initialize(confirmed_fresh_scope=True)
    return guard, clock, calls


def run(guard, *, project="project_a", credential="credential_a", reservation=None, req=None):
    return guard.generate(
        req or request(),
        project_ref=project,
        credential_ref=credential,
        reservation=reservation or reserve(),
    )


def snapshot(guard, project="project_a", model="gemini-3.5-flash-lite"):
    return guard.snapshot(project, "gemini", model)


def test_projects_independent_credentials_share_bucket_and_provenance():
    a = policy(
        quota_limits=QuotaLimits(rpm=1, tpm=250000, rpd=500),
        verification_source="ai_studio_screenshot_2026_10_27",
    )
    b = policy("project_b", ("credential_c",), verification_source="user_reported")
    guard, _, calls = build(policies=[a, b])
    assert run(guard).admitted
    assert run(guard, credential="credential_b").reason == "rpm"
    assert run(guard, project="project_b", credential="credential_c").admitted
    assert snapshot(guard)["rpd_used"] == snapshot(guard, "project_b")["rpd_used"] == 1
    assert len(calls) == 2
    registry = ProjectRegistry([a, b])
    assert (
        registry.policy_for("project_b", "gemini", b.model).verification_source == "user_reported"
    )


def test_models_have_separate_quota_but_shared_project_budget():
    a = policy(budget=budget("3"))
    b = policy(model="another-model", budget=budget("3"))
    guard, _, calls = build(policies=[a, b])
    assert run(guard, reservation=reserve(spend="2")).admitted
    assert run(guard, req=request(model=b.model), reservation=reserve(spend="2")).reason == "budget"
    assert snapshot(guard, model=b.model)["rpd_used"] == 0
    assert len(calls) == 1


def test_rpm_sliding_window_and_boundary():
    guard, clock, calls = build(
        policies=[policy(quota_limits=QuotaLimits(rpm=1, tpm=1000, rpd=500))]
    )
    assert run(guard).admitted
    blocked = run(guard)
    assert blocked.retry_at == clock.now + timedelta(seconds=60)
    clock.advance(59.9)
    assert not run(guard).admitted
    clock.advance(0.1)
    assert run(guard).admitted and len(calls) == 2


@pytest.mark.parametrize(
    "start,reset,hours",
    [
        ("2026-03-08T08:00:00+00:00", "2026-03-09T07:00:00+00:00", 23),
        ("2026-11-01T07:00:00+00:00", "2026-11-02T08:00:00+00:00", 25),
    ],
)
def test_rpd_pacific_midnight_handles_dst(start, reset, hours):
    clock = Clock(start)
    guard, _, _ = build(
        clock=clock, policies=[policy(quota_limits=QuotaLimits(rpm=15, tpm=1000, rpd=1))]
    )
    assert run(guard).admitted
    assert run(guard).retry_at == datetime.fromisoformat(reset)
    clock.advance(hours * 3600 - 1)
    assert run(guard).reason == "rpd"
    clock.advance(1)
    assert run(guard).admitted
    assert snapshot(guard)["rpd_used"] == 1


@pytest.mark.parametrize(
    "usage,charged,unknown",
    [
        (Usage(status="unknown", source="unknown"), 100, 1),
        (Usage(status="available", source="provider_reported", input_tokens=1), 100, 1),
        (Usage(status="available", source="provider_reported", total_tokens=40), 40, 0),
        (Usage(status="available", source="provider_reported", total_tokens=0), 0, 0),
    ],
)
def test_tpm_reconciliation_unknown_is_not_zero(usage, charged, unknown):
    def transport(req):
        result = FakeLLMTransport()(req)
        result.usage = usage
        return result

    guard, clock, _ = build(
        handler=transport, policies=[policy(quota_limits=QuotaLimits(rpm=15, tpm=150, rpd=500))]
    )
    result = run(guard)
    assert result.response.usage == usage
    state = snapshot(guard)
    assert state["tpm_charged"] == charged and state["unknown_usage_count"] == unknown
    assert run(guard).admitted == (charged <= 50)
    clock.advance(60)
    assert run(guard).admitted


@pytest.mark.parametrize("scope", ["quota", "budget"])
def test_pending_reservations_do_not_expire_and_do_not_hold_network_lock(scope):
    entered, release, lock = Event(), Event(), Lock()
    count = 0
    denied_done, denied_count = Event(), 0

    def transport(req):
        nonlocal count
        with lock:
            count += 1
            if count == 3:
                entered.set()
        assert release.wait(5)
        return FakeLLMTransport()(req)

    guard, clock, _ = build(
        handler=transport,
        policies=[
            policy(
                quota_limits=QuotaLimits(rpm=3, tpm=300, rpd=500)
                if scope == "quota"
                else QuotaLimits(rpm=16, tpm=1600, rpd=500),
                budget=budget("3") if scope == "budget" else None,
            )
        ],
    )
    reservation = reserve(spend="1") if scope == "budget" else reserve()

    def submit_request(index):
        nonlocal denied_count
        result = run(guard, req=request(f"concurrent-{index}"), reservation=reservation)
        if not result.admitted:
            with lock:
                denied_count += 1
                if denied_count == 13:
                    denied_done.set()
        return result

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(submit_request, i) for i in range(16)]
        try:
            assert entered.wait(3)
            assert denied_done.wait(3)
            clock.advance(120)
            state = snapshot(guard)
            assert state["pending"] == state["rpm_used"] == 3
            assert state["tpm_charged"] == 300
            assert run(guard, reservation=reservation).reason == (
                "rpm" if scope == "quota" else "budget"
            )
        finally:
            release.set()
        results = [f.result() for f in futures]
    assert sum(r.admitted for r in results) == count == 3


def test_inflight_request_counts_on_new_pacific_day():
    clock = Clock("2026-10-27T06:59:59+00:00")

    def transport(req):
        clock.advance(2)
        return FakeLLMTransport()(req)

    guard, _, _ = build(
        clock=clock,
        handler=transport,
        policies=[policy(quota_limits=QuotaLimits(rpm=15, tpm=1000, rpd=1))],
    )
    assert run(guard).admitted
    clock.advance(60)
    assert run(guard).reason == "rpd"


@pytest.mark.parametrize("scope", ["project", "overall"])
def test_budget_admission_atomic_with_explicit_spending_ceiling(scope):
    policies = [
        policy(budget=budget("3") if scope == "project" else None),
        policy("project_b", ("credential_c",)),
    ]
    guard, _, calls = build(policies=policies, overall=budget("3") if scope == "overall" else None)
    assert run(guard).reason == "spending_bound_required"
    assert run(guard, reservation=reserve(spend="2")).admitted
    result = run(
        guard,
        project="project_b" if scope == "overall" else "project_a",
        credential="credential_c" if scope == "overall" else "credential_a",
        reservation=reserve(spend="2"),
    )
    assert result.reason == "budget" and len(calls) == 1
    money = snapshot(guard)["project_budget" if scope == "project" else "overall_budget"]
    assert money["used_known"] == 0 and money["reserved"] == Decimal("2")
    assert money["remaining"] == 1 and money["unknown_cost_count"] == 1


@pytest.mark.parametrize(
    "cost,used,reserved,unknown",
    [
        (Cost(status="unknown", source="unknown"), "0", "0.20", 1),
        (
            Cost(
                status="available",
                source="provider_reported",
                amount="0",
                currency="USD",
                price_source="synthetic",
            ),
            "0",
            "0",
            0,
        ),
        (
            Cost(
                status="available",
                source="provider_reported",
                amount="0.012",
                currency="USD",
                price_source="synthetic",
            ),
            "0.012",
            "0",
            0,
        ),
    ],
)
def test_cost_unknown_zero_decimal_and_response_unchanged(cost, used, reserved, unknown):
    returned = []

    def transport(req):
        result = FakeLLMTransport()(req)
        result.cost = cost
        returned.append(result.export())
        return result

    guard, _, _ = build(handler=transport, policies=[policy(budget=budget("1.00"))])
    result = run(guard, reservation=reserve(spend="0.20"))
    assert result.response.export() == returned[0]
    money = snapshot(guard)["project_budget"]
    assert money["used_known"] == Decimal(used) and money["reserved"] == Decimal(reserved)
    assert money["unknown_cost_count"] == unknown


def test_money_enforcement_not_configured_and_restart_requires_initialization():
    guard, _, calls = build(initialized=False)
    assert run(guard).reason == "accounting_not_initialized"
    with pytest.raises(ValueError):
        guard.initialize()
    guard.initialize(confirmed_fresh_scope=True)
    assert run(guard).admitted
    state = snapshot(guard)["project_budget"]
    assert state["status"] == "NOT_CONFIGURED" and state["used_known"] is None
    with pytest.raises(ValueError):
        guard.initialize(confirmed_fresh_scope=True)
    restarted, _, _ = build(initialized=False)
    assert run(restarted).reason == "accounting_not_initialized"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "category,hint", [("rate_limit", None), ("quota_exceeded", None), ("rate_limit", 5.0)]
)
def test_provider_exhaustion_blocks_without_rotation_or_invented_reset(category, hint):
    def transport(req):
        result = FakeLLMTransport()(req)
        result.status, result.output, result.finish_reason = "error", None, "error"
        result.error = GatewayError(
            category=category,
            code=category,
            origin="provider",
            retryability="unknown",
            retry_after_seconds=hint,
        )
        return result

    guard, clock, calls = build(handler=transport)
    first = run(guard)
    assert first.admitted and not first.automatic_retry
    blocked = run(guard, credential="credential_b")
    assert not blocked.admitted and len(calls) == 1
    assert blocked.retry_at == (clock.now + timedelta(seconds=5) if hint else None)
    clock.advance(60)
    if hint is None:
        assert not run(guard).admitted and len(calls) == 1
        guard.clear_provider_unavailable(
            "project_a", "gemini", "gemini-3.5-flash-lite", confirmed_available=True
        )
    assert run(guard).admitted and len(calls) == 2


@pytest.mark.parametrize(
    "category,retryability,eligible",
    [
        ("authentication", "retryable", False),
        ("authorization", "retryable", False),
        ("invalid_request", "retryable", False),
        ("schema_mismatch", "retryable", False),
        ("safety", "retryable", False),
        ("quota_exceeded", "unknown", False),
        ("timeout", "unknown", False),
        ("rate_limit", "retryable", True),
    ],
)
def test_safe_retry_decision_only(category, retryability, eligible):
    error = GatewayError(
        category=category, code=category, origin="provider", retryability=retryability
    )
    assert manual_retry_eligible(error) is eligible


@pytest.mark.parametrize("failure", ["missing", "unconfirmed", "account", "model"])
def test_mapping_fail_closed(failure):
    p = policy(mapping_confirmed=failure != "unconfirmed")
    gateway = SharedLLMGateway({"gemini": FakeLLMTransport()})
    binding = GatewayBinding(
        "wrong" if failure == "account" else p.account_ref,
        p.project_ref,
        "credential_a",
        p.provider,
        p.model,
        gateway,
    )
    guard = QuotaBudgetGuard(
        ProjectRegistry([p]), [] if failure == "missing" else [binding], clock=Clock()
    )
    guard.initialize(confirmed_fresh_scope=True)
    result = run(guard, req=request(model="wrong") if failure == "model" else None)
    assert result.reason == "mapping_unconfirmed" and not result.admitted


def test_conflicting_registry_credentials_and_budget_rejected():
    with pytest.raises(ValueError, match="Conflicting credential mapping"):
        ProjectRegistry([policy(), policy("project_b")])
    with pytest.raises(ValueError, match="Conflicting project configuration"):
        ProjectRegistry([policy(), policy(model="other", budget=budget("1"))])


def test_missing_output_cap_and_invalid_clock_block_before_transport():
    guard, clock, calls = build()
    assert run(guard, req=request(cap=None)).reason == "token_bound_required"
    assert run(guard, reservation=reserve(tokens=10)).reason == "token_bound_required"
    assert run(guard, reservation=reserve(tokens=300000)).reason == "token_bound_exceeds_limit"
    clock.advance(-1)
    assert run(guard).reason == "clock_invalid" and not calls


@pytest.mark.parametrize("kind", ["tokens", "cost"])
def test_actual_usage_exceeds_bound_marks_unavailable(kind):
    def transport(req):
        result = FakeLLMTransport()(req)
        if kind == "tokens":
            result.usage = Usage(status="available", source="provider_reported", total_tokens=101)
        else:
            result.cost = Cost(
                status="available",
                source="provider_reported",
                amount="0.30",
                currency="USD",
                price_source="synthetic",
            )
        return result

    guard, _, calls = build(handler=transport, policies=[policy(budget=budget("1"))])
    assert run(guard, reservation=reserve(spend="0.20")).admitted
    blocked = run(guard, reservation=reserve(spend="0.20"))
    assert blocked.reason == ("token_bound_exceeded" if kind == "tokens" else "budget")
    assert len(calls) == 1


def test_transport_exception_retains_quota_and_money_without_secrets(caplog, capsys):
    def transport(req):
        raise RuntimeError("synthetic-private-exception")

    guard, _, calls = build(handler=transport, policies=[policy(budget=budget("1"))])
    result = run(guard, reservation=reserve(spend="0.20"))
    state = snapshot(guard)
    assert result.error.category == "provider_unavailable" and len(calls) == 1
    assert state["rpd_used"] == 1 and state["tpm_charged"] == 100
    assert state["project_budget"]["reserved"] == Decimal("0.20")
    assert "synthetic-private-exception" not in result.response.to_json() + caplog.text + str(
        capsys.readouterr()
    )


def test_explicit_credential_binding_and_gemini_trusted_validation_integration():
    # Resolver thuộc application composition, fake value không vào policy/accounting.
    resolver = Mock(return_value="synthetic-private-credential")
    factory = Mock(return_value=Mock())
    client = factory(api_key=resolver("credential_b"))
    client.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                finish_reason="STOP",
                content=types.Content(parts=[types.Part(text='{"synthetic":true}')]),
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(total_token_count=12),
    )
    reference = SchemaReference(
        schema_id="urn:synthetic:guard",
        name="guard",
        version="v1",
        dialect="https://json-schema.org/draft/2020-12/schema",
    )
    schemas = LocalSchemaRegistry(
        [
            (
                reference,
                {
                    "type": "object",
                    "required": ["synthetic"],
                    "properties": {"synthetic": {"const": True}},
                    "additionalProperties": False,
                },
            )
        ]
    )
    gateway = SharedLLMGateway(
        {"gemini": GeminiAdapter(client, schema_registry=schemas)}, schema_registry=schemas
    )
    p = policy()
    guard = QuotaBudgetGuard(
        ProjectRegistry([p]),
        [
            GatewayBinding(
                p.account_ref, p.project_ref, "credential_b", p.provider, p.model, gateway
            )
        ],
        clock=Clock(),
    )
    guard.initialize(confirmed_fresh_scope=True)
    assert run(guard, credential="credential_a").reason == "mapping_unconfirmed"
    req = request()
    from vietnamese_financial_multi_agent.core.llm_contracts import OutputSpec

    req.output_spec = OutputSpec(format="json", schema_ref=reference)
    result = run(guard, credential="credential_b", req=req)
    assert result.response.output.validation_status == "schema_valid"
    assert result.response.usage.total_tokens == 12
    resolver.assert_called_once_with("credential_b")
    assert factory.call_args.kwargs["api_key"] == "synthetic-private-credential"
    assert "synthetic-private-credential" not in str(snapshot(guard)) + result.response.to_json()
    client.models.generate_content.assert_called_once()
