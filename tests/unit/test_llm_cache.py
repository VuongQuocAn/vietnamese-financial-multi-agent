"""Synthetic/offline cache tests; không credentials thật hoặc live API."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService, cache_key
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
)
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry


def request(**changes):
    values = dict(
        contract_version="llm_gateway_v1",
        request_id="synthetic-1",
        model={"provider": "gemini", "model": "gemini-3.5-flash-lite"},
        messages=[{"role": "user", "content": "Synthetic request"}],
        generation={"max_output_tokens": 32},
    )
    values.update(changes)
    return parse_llm_request(values)


def build(*, handler=None, schemas=None, guard_budget=None, **options):
    transport = Mock(side_effect=handler or FakeLLMTransport())
    gateway = SharedLLMGateway({"gemini": transport}, schema_registry=schemas)
    policy = ProjectPolicy(
        account_ref="account",
        project_ref="project",
        credential_refs=("credential",),
        provider="gemini",
        model="gemini-3.5-flash-lite",
        tier="synthetic",
        quota_limits=QuotaLimits(rpm=500, tpm=250000, rpd=500),
        verification_source="synthetic",
        mapping_confirmed=True,
    )
    guard = QuotaBudgetGuard(
        ProjectRegistry([policy]),
        [
            GatewayBinding(
                policy.account_ref,
                policy.project_ref,
                "credential",
                policy.provider,
                policy.model,
                gateway,
            )
        ],
        overall_budget=guard_budget,
    )
    guard.initialize(confirmed_fresh_scope=True)
    guard.generate = Mock(wraps=guard.generate)
    clock = Mock(return_value=0.0)
    config = dict(
        tenant_ref="tenant",
        project_ref="project",
        credential_refs=frozenset({"credential"}),
        configuration_revision="adapter-1-config-1-model-unknown",
        scope_confirmed=True,
        schema_registry=schemas,
        clock=clock,
    )
    config.update(options)
    return CachedLLMService(guard, **config), guard, transport, clock


def run(service, req=None, **changes):
    args = dict(
        credential_ref="credential",
        cache_allowed=True,
        reservation=Reservation(
            token_upper_bound=100,
            token_basis="caller_attested_upper_bound",
        ),
    )
    args.update(changes)
    return service.generate(req or request(), **args)


def key(req=None, **changes):
    args = dict(tenant_ref="tenant", project_ref="project", configuration_revision="revision-1")
    args.update(changes)
    return cache_key(req or request(), **args)


def schema(version="1", **changes):
    reference = SchemaReference(
        schema_id="synthetic",
        name="synthetic",
        version=version,
        dialect="https://json-schema.org/draft/2020-12/schema",
    )
    body = {"type": "object", "properties": {"synthetic": {"type": "boolean"}}}
    body.update(changes)
    return reference, LocalSchemaRegistry([(reference, body)])


def test_hit_rebind_copy_and_no_new_quota_or_historical_billing():
    def handler(req):
        response = FakeLLMTransport()(req)
        response.usage = Usage(status="available", source="provider_reported", total_tokens=7)
        response.cost = Cost(
            status="available",
            source="provider_reported",
            amount=Decimal("0.1"),
            currency="USD",
            price_source="synthetic",
        )
        response.provenance.metadata_source = "provider_reported"
        response.provenance.provider_reported_model = "synthetic-revision"
        response.provider_response_id = "original-provider-id"
        return response

    service, guard, transport, _ = build(handler=handler)
    first = run(service)
    before = guard.snapshot("project", "gemini", request().model.model)
    first.response.output.text = "caller mutation"
    second = run(service, request(request_id="synthetic-2", correlation={"trace_id": "trace-2"}))
    assert first.cache_status == "miss" and second.cache_hit
    assert second.provider_called is False and second.guard_result is None
    assert guard.generate.call_count == transport.call_count == 1
    assert before == guard.snapshot("project", "gemini", request().model.model)
    assert second.response.request_id == "synthetic-2"
    assert second.response.correlation.trace_id == "trace-2"
    assert second.response.output.text == "Synthetic example"
    assert second.response.provenance.provider_reported_model == "synthetic-revision"
    assert second.response.provider_response_id == "original-provider-id"
    assert second.historical_usage.total_tokens == 7
    assert second.historical_cost.amount == Decimal("0.1")
    assert second.response.usage.total_tokens == 0
    assert second.response.usage.source == "calculated"
    assert second.response.cost.status == "not_available"
    second.response.output.text = "second mutation"
    second.historical_usage.total_tokens = 999
    assert run(service).historical_usage.total_tokens == 7
    assert run(service).response.output.text == "Synthetic example"


@pytest.mark.parametrize(
    "changes",
    [
        {"messages": [{"role": "user", "content": "changed"}]},
        {
            "messages": [
                {"role": "system", "content": "instruction"},
                {"role": "user", "content": "Synthetic request"},
            ]
        },
        {"model": {"provider": "other", "model": "gemini-3.5-flash-lite"}},
        {"model": {"provider": "gemini", "model": "other"}},
        {"generation": {"max_output_tokens": 32, "temperature": 0.0}},
        {"generation": {"max_output_tokens": 32, "temperature": None}},
        {"constraints": {"timeout_seconds": 10.0}},
        {"constraints": None},
        {"output_spec": None},
        {"output_spec": {"format": "text"}},
    ],
)
def test_key_and_lookup_separate_inputs(changes):
    assert key() != key(request(**changes))
    service, guard, _, _ = build()
    run(service)
    assert not run(service, request(**changes)).cache_hit
    assert guard.generate.call_count == 2


def test_canonical_order_presence_message_order_and_versions():
    assert key(request(request_id="another", correlation=None)) == key()
    assert key(request(generation={"temperature": None, "max_output_tokens": 32})) != key(
        request(generation={"temperature": 0.0, "max_output_tokens": 32})
    )
    assert key(request(generation={"temperature": 0.0, "max_output_tokens": 32})) == key(
        request(generation={"max_output_tokens": 32, "temperature": 0.0})
    )
    messages = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    assert key(request(messages=messages)) != key(request(messages=messages[::-1]))
    for name in ("tenant_ref", "project_ref", "configuration_revision"):
        assert key(**{name: "other"}) != key()


def test_schema_fingerprint_version_strictness_and_trusted_validation():
    ref, registry = schema()
    req = request(output_spec={"format": "json", "schema_ref": ref.export(), "strict": True})
    service, guard, _, _ = build(schemas=registry)
    assert run(service, req).response.output.validation_status == "schema_valid"
    assert run(service, req).cache_hit
    _, changed = schema(required=["other"])
    assert key(req, schema_registry=registry) != key(req, schema_registry=changed)
    # Thay registry cùng identity không bump version phải miss, không replay output cũ.
    registry._schemas = changed._schemas
    result = run(service, req)
    assert not result.cache_hit and result.response.status == "malformed"
    assert not run(service, req).cache_hit
    ref2, registry2 = schema("2")
    req2 = request(output_spec={"format": "json", "schema_ref": ref2.export()})
    assert key(req, schema_registry=changed) != key(req2, schema_registry=registry2)
    assert guard.generate.call_count == 3
    values = req.export()
    values["output_spec"]["strict"] = None
    assert key(req, schema_registry=changed) != key(
        parse_llm_request(values), schema_registry=changed
    )


def test_missing_registry_and_unverified_schema_bypass():
    ref, _ = schema()
    req = request(output_spec={"format": "json", "schema_ref": ref.export()})
    service, guard, _, _ = build()
    assert run(service, req).response.output.validation_status == "unverified"
    assert run(service, req).cache_status == "bypassed"
    assert guard.generate.call_count == 2
    with pytest.raises(ValueError, match="Local schema"):
        key(req)


def test_ttl_lru_invalidation_and_clear():
    service, _, transport, clock = build(ttl_seconds=10, max_entries=2)
    a, b, c = [request(messages=[{"role": "user", "content": x}]) for x in "abc"]
    run(service, a)
    run(service, b)
    assert run(service, a).cache_hit  # b is now LRU
    run(service, c)
    assert not run(service, b).cache_hit
    assert run(service, c).cache_hit
    clock.return_value = 10
    assert run(service, c).cache_status == "expired"
    assert run(service, c).ttl_remaining_seconds == 10
    service.invalidate(c)
    assert run(service, c).cache_status == "miss"
    service.clear()
    assert run(service, c).cache_status == "miss"
    assert transport.call_count == 7


@pytest.mark.parametrize(
    "options,call_options",
    [
        ({}, {"cache_allowed": False}),
        ({"scope_confirmed": False}, {}),
        ({"credential_refs": frozenset()}, {}),
        ({}, {"credential_ref": "unmapped"}),
    ],
)
def test_eligibility_scope_and_credential_fail_closed(options, call_options):
    service, guard, _, _ = build(**options)
    run(service)
    result = run(service, **call_options)
    assert result.cache_status == "bypassed"
    assert guard.generate.call_count == 2
    if call_options.get("credential_ref") == "unmapped":
        assert not result.guard_result.admitted
        assert result.provider_called is False


def test_default_eligibility_and_scope_instances_do_not_share():
    service, guard, _, _ = build()
    args = dict(
        credential_ref="credential",
        reservation=Reservation(token_upper_bound=100, token_basis="caller_attested_upper_bound"),
    )
    assert service.generate(request(), **args).cache_status == "bypassed"
    assert service.generate(request(), **args).cache_status == "bypassed"
    assert guard.generate.call_count == 2
    run(service)
    for options in ({"tenant_ref": "other"}, {"project_ref": "other"}):
        other, other_guard, _, _ = build(**options)
        assert not run(other).cache_hit
        assert other_guard.generate.call_count == 1


@pytest.mark.parametrize("status", ["error", "partial", "refused", "malformed", "mismatch"])
def test_unsuccessful_or_unbound_never_cached(status):
    def handler(req):
        if status == "malformed":
            return FakeLLMTransport(json_text="{")(req)
        response = FakeLLMTransport()(req)
        if status == "mismatch":
            response.request_id = "wrong"
            return response
        response.status = status
        response.finish_reason = {"error": "error", "partial": "length", "refused": "safety"}[
            status
        ]
        if status != "partial":
            response.output = None
            category = "safety" if status == "refused" else "internal"
            response.error = GatewayError(
                category=category, code=category, origin="provider", retryability="unknown"
            )
        return response

    service, guard, transport, _ = build(handler=handler)
    req = request(output_spec={"format": "json"}) if status == "malformed" else request()
    assert not run(service, req).cache_hit
    assert not run(service, req).cache_hit
    assert guard.generate.call_count == transport.call_count == 2


def test_guard_reject_does_not_write_or_fabricate_response():
    service, guard, transport, _ = build()
    tiny = Reservation(token_upper_bound=1, token_basis="caller_attested_upper_bound")
    for _ in range(2):
        result = run(service, reservation=tiny)
        assert result.response is None and not result.guard_result.admitted
        assert result.guard_result.reason == "token_bound_required"
        assert result.provider_called is False
    assert guard.generate.call_count == 2 and transport.call_count == 0
    assert run(service).cache_status == "miss"


def test_budget_rejection_and_hit_leave_original_reservation_unchanged():
    service, guard, transport, _ = build(
        guard_budget=BudgetLimit(amount=Decimal("1"), currency="USD")
    )
    reservation = Reservation(
        token_upper_bound=100,
        token_basis="caller_attested_upper_bound",
        spending_upper_bound=Decimal("1"),
        currency="USD",
        spending_basis="approved_upper_bound",
    )
    assert run(service, reservation=reservation).guard_result.admitted
    before = guard.snapshot("project", "gemini", request().model.model)
    assert run(service, reservation=reservation).cache_hit
    assert before == guard.snapshot("project", "gemini", request().model.model)
    changed = request(messages=[{"role": "user", "content": "another synthetic request"}])
    result = run(service, changed, reservation=reservation)
    assert result.guard_result.reason == "budget" and result.response is None
    assert run(service, changed, reservation=reservation).guard_result.reason == "budget"
    assert transport.call_count == 1


def test_simultaneous_misses_each_go_through_shared_guard():
    from threading import Barrier

    barrier = Barrier(2)

    def handler(req):
        barrier.wait(timeout=5)
        return FakeLLMTransport()(req)

    service, guard, transport, _ = build(handler=handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda i: run(service, request(request_id=f"id-{i}")), range(2)))
    assert all(r.cache_status == "miss" for r in results)
    assert guard.generate.call_count == transport.call_count == 2
    assert guard.snapshot("project", "gemini", request().model.model)["rpd_used"] == 2
    assert run(service).cache_hit


def test_concurrent_operations_and_clear_during_miss():
    entered, release = Event(), Event()

    def handler(req):
        entered.set()
        assert release.wait(5)
        return FakeLLMTransport()(req)

    service, _, _, _ = build(handler=handler)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = pool.submit(run, service)
        assert entered.wait(5)
        service.clear()
        release.set()
        assert pending.result().response.status == "success"
        assert run(service).cache_status == "miss"  # pending pre-clear write suppressed
        results = list(pool.map(lambda i: run(service, request(request_id=f"id-{i}")), range(32)))
    assert all(r.cache_hit for r in results)
    assert len({r.response.request_id for r in results}) == 32
    assert len({id(r.response) for r in results}) == 32


def test_diagnostics_do_not_expose_content_or_credentials(capsys):
    service, _, _, _ = build()
    marker = "synthetic-private-marker"
    req = request(messages=[{"role": "user", "content": marker}])
    run(service, req)
    result = run(service, req)
    assert marker not in repr(result) and "credential" not in repr(result)
    assert marker not in repr(service._entries)
    assert marker not in key(req)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "options",
    [
        {"ttl_seconds": 0},
        {"ttl_seconds": float("inf")},
        {"max_entries": 0},
        {"configuration_revision": ""},
    ],
)
def test_bounded_configuration(options):
    with pytest.raises(ValueError, match="Invalid cache"):
        build(**options)
