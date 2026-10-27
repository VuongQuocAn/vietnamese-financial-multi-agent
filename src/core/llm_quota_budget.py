"""Quota/budget wrapper một process; explicit project selection, không I/O/retry ngầm."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from threading import Lock
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .llm_contracts import ErrorCategory, GatewayError, LLMRequest, LLMResponse, parse_llm_request
from .llm_gateway import SharedLLMGateway

Alias = Annotated[
    str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
]
Count = Annotated[int, Field(gt=0)]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class PolicyModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class QuotaLimits(PolicyModel):
    rpm: Count
    tpm: Count
    rpd: Count


class BudgetLimit(PolicyModel):
    amount: Money
    currency: Currency


class ProjectPolicy(PolicyModel):
    account_ref: Alias
    project_ref: Alias
    credential_refs: tuple[Alias, ...] = Field(min_length=1)
    provider: Alias
    model: Alias
    tier: Alias
    quota_limits: QuotaLimits
    verification_source: Alias
    mapping_confirmed: bool = False
    budget: BudgetLimit | None = None


class Reservation(PolicyModel):
    token_upper_bound: Count
    token_basis: Literal["caller_attested_upper_bound"]
    spending_upper_bound: Money | None = None
    currency: Currency | None = None
    spending_basis: Literal["approved_upper_bound"] | None = None

    @model_validator(mode="after")
    def complete_spending_bound(self) -> "Reservation":
        fields = (self.spending_upper_bound, self.currency, self.spending_basis)
        if any(v is not None for v in fields) and not all(v is not None for v in fields):
            raise ValueError("Spending bound requires currency and approval basis")
        return self


@dataclass(frozen=True)
class GatewayBinding:
    account_ref: str
    project_ref: str
    credential_ref: str
    provider: str
    model: str
    gateway: SharedLLMGateway = field(repr=False)


class ProjectRegistry:
    def __init__(self, policies: list[ProjectPolicy]) -> None:
        self._policies: dict[tuple[str, str, str], ProjectPolicy] = {}
        owners, projects = {}, {}
        for item in policies:
            policy = ProjectPolicy.model_validate(item)
            key = (policy.project_ref, policy.provider, policy.model)
            identity = (policy.account_ref, policy.budget)
            if (
                key in self._policies
                or len(set(policy.credential_refs)) != len(policy.credential_refs)
                or (policy.project_ref in projects and projects[policy.project_ref] != identity)
            ):
                raise ValueError("Conflicting project configuration")
            projects[policy.project_ref] = identity
            for credential in policy.credential_refs:
                owner = (policy.account_ref, policy.project_ref, policy.provider)
                if credential in owners and owners[credential] != owner:
                    raise ValueError("Conflicting credential mapping")
                owners[credential] = owner
            self._policies[key] = policy

    def policy_for(self, project_ref: str, provider: str, model: str) -> ProjectPolicy | None:
        return self._policies.get((project_ref, provider, model))


@dataclass
class _Charge:
    started: datetime
    tokens: int
    pending: bool = True
    completed: datetime | None = None


@dataclass
class _Bucket:
    day: date | None = None
    daily_count: int = 0
    charges: list[_Charge] = field(default_factory=list)
    unavailable: str | None = None
    retry_at: datetime | None = None
    unknown_usage_count: int = 0


@dataclass
class _MoneyState:
    used_known: Decimal = Decimal(0)
    reserved: Decimal = Decimal(0)
    unknown_cost_count: int = 0
    breached: bool = False


@dataclass(frozen=True)
class GuardResult:
    admitted: bool
    reason: str
    response: LLMResponse | None = None
    error: GatewayError | None = None
    retry_at: datetime | None = None

    @property
    def automatic_retry(self) -> bool:
        return False


def manual_retry_eligible(error: GatewayError) -> bool:
    """Chỉ decision metadata; caller vẫn phải admission mới, cùng explicit project."""
    return error.retryability == "retryable" and error.category in (
        "rate_limit",
        "network",
        "timeout",
        "provider_unavailable",
    )


def _blocked(reason: str, category: ErrorCategory, retry_at: datetime | None = None) -> GuardResult:
    return GuardResult(
        False,
        reason,
        error=GatewayError(
            category=category, code=category, origin="gateway", retryability="not_retryable"
        ),
        retry_at=retry_at,
    )


class QuotaBudgetGuard:
    def __init__(
        self,
        registry: ProjectRegistry,
        bindings: list[GatewayBinding],
        *,
        overall_budget: BudgetLimit | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._registry = registry
        self._bindings = {}
        for binding in bindings:
            key = (binding.project_ref, binding.credential_ref, binding.provider, binding.model)
            if key in self._bindings:
                raise ValueError("Duplicate gateway binding")
            self._bindings[key] = binding
        self._overall_limit = BudgetLimit.model_validate(overall_budget) if overall_budget else None
        currencies = {p.budget.currency for p in registry._policies.values() if p.budget}
        if overall_budget:
            currencies.add(overall_budget.currency)
        if len(currencies) > 1:
            raise ValueError("Mixed budget currencies unsupported")
        self._currency = next(iter(currencies), None)
        self._clock, self._lock = clock, Lock()
        self._zone = ZoneInfo("America/Los_Angeles")
        self._buckets: dict[tuple[str, str, str], _Bucket] = {}
        self._money: dict[str, _MoneyState] = {}
        self._overall_money = _MoneyState()
        self._initialized = False
        self._last_time: datetime | None = None

    def initialize(self, *, confirmed_fresh_scope: bool = False) -> None:
        """Ứng dụng xác nhận scope exclusive chưa có prior usage; không reset sau restart."""
        with self._lock:
            if confirmed_fresh_scope is not True or self._initialized:
                raise ValueError("Fresh accounting scope must be explicitly confirmed once")
            self._now()
            self._initialized = True

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Clock must be timezone aware")
        now = now.astimezone(UTC)
        if self._last_time is not None and now < self._last_time:
            raise ValueError("Clock moved backwards")
        self._last_time = now
        return now

    def _roll(self, bucket: _Bucket, now: datetime) -> None:
        day = now.astimezone(self._zone).date()
        if bucket.day != day:
            bucket.day = day
            bucket.daily_count = sum(c.pending for c in bucket.charges)
        cutoff = now - timedelta(seconds=60)
        bucket.charges[:] = [c for c in bucket.charges if c.pending or c.completed > cutoff]
        if (
            bucket.unavailable in ("provider_rate_limit", "provider_quota")
            and bucket.retry_at is not None
            and now >= bucket.retry_at
        ):
            bucket.unavailable, bucket.retry_at = None, None

    def _midnight(self, now: datetime) -> datetime:
        day = now.astimezone(self._zone).date() + timedelta(days=1)
        return datetime.combine(day, time.min, self._zone).astimezone(UTC)

    @staticmethod
    def _money_snapshot(state: _MoneyState, limit: BudgetLimit | None, enabled: bool) -> dict:
        if not enabled:
            return {
                "status": "NOT_CONFIGURED",
                "used_known": None,
                "reserved": None,
                "remaining": None,
                "unknown_cost_count": None,
            }
        remaining = limit.amount - state.used_known - state.reserved if limit else None
        return {
            "status": "UNAVAILABLE"
            if state.breached
            else "EXHAUSTED"
            if remaining is not None and remaining <= 0
            else "AVAILABLE",
            "used_known": state.used_known,
            "reserved": state.reserved,
            "remaining": remaining,
            "unknown_cost_count": state.unknown_cost_count,
        }

    def snapshot(self, project_ref: str, provider: str, model: str) -> dict:
        with self._lock:
            now = self._now()
            policy = self._registry.policy_for(project_ref, provider, model)
            if policy is None:
                raise ValueError("Project policy not found")
            bucket = self._buckets.setdefault((project_ref, provider, model), _Bucket())
            self._roll(bucket, now)
            cutoff = now - timedelta(seconds=60)
            money = self._money.setdefault(project_ref, _MoneyState())
            return {
                "initialized": self._initialized,
                "rpm_used": sum(c.pending or c.started > cutoff for c in bucket.charges),
                "tpm_charged": sum(c.tokens for c in bucket.charges),
                "rpd_used": bucket.daily_count,
                "pending": sum(c.pending for c in bucket.charges),
                "unknown_usage_count": bucket.unknown_usage_count,
                "unavailable": bucket.unavailable,
                "retry_at": bucket.retry_at,
                "daily_reset_at": self._midnight(now),
                "project_budget": self._money_snapshot(
                    money,
                    policy.budget,
                    policy.budget is not None or self._overall_limit is not None,
                ),
                "overall_budget": self._money_snapshot(
                    self._overall_money, self._overall_limit, self._overall_limit is not None
                ),
            }

    def clear_provider_unavailable(
        self, project_ref: str, provider: str, model: str, *, confirmed_available: bool = False
    ) -> None:
        with self._lock:
            bucket = self._buckets.get((project_ref, provider, model))
            if (
                confirmed_available is not True
                or bucket is None
                or bucket.unavailable not in ("provider_rate_limit", "provider_quota")
            ):
                raise ValueError("Provider availability must be explicitly confirmed")
            bucket.unavailable, bucket.retry_at = None, None

    def generate(
        self,
        request: LLMRequest,
        *,
        project_ref: str,
        credential_ref: str,
        reservation: Reservation,
    ) -> GuardResult:
        request = parse_llm_request(request).model_copy(deep=True)
        reservation = Reservation.model_validate(reservation)
        key = (project_ref, request.model.provider, request.model.model)
        policy = self._registry.policy_for(*key)
        binding = self._bindings.get((project_ref, credential_ref, *key[1:]))
        if (
            policy is None
            or not policy.mapping_confirmed
            or credential_ref not in policy.credential_refs
            or binding is None
            or binding.account_ref != policy.account_ref
        ):
            return _blocked("mapping_unconfirmed", "invalid_configuration")
        cap = request.generation.max_output_tokens
        if cap is None or reservation.token_upper_bound < cap:
            return _blocked("token_bound_required", "invalid_request")
        if reservation.token_upper_bound > policy.quota_limits.tpm:
            return _blocked("token_bound_exceeds_limit", "invalid_request")
        money_enabled = policy.budget is not None or self._overall_limit is not None
        if money_enabled and (
            reservation.spending_upper_bound is None or reservation.currency != self._currency
        ):
            return _blocked("spending_bound_required", "invalid_configuration")
        with self._lock:
            try:
                now = self._now()
            except ValueError:
                return _blocked("clock_invalid", "invalid_configuration")
            if not self._initialized:
                return _blocked("accounting_not_initialized", "invalid_configuration")
            bucket = self._buckets.setdefault(key, _Bucket())
            self._roll(bucket, now)
            if bucket.unavailable:
                return _blocked(
                    bucket.unavailable,
                    "rate_limit"
                    if bucket.unavailable == "provider_rate_limit"
                    else "quota_exceeded",
                    bucket.retry_at,
                )
            cutoff = now - timedelta(seconds=60)
            rpm = [c for c in bucket.charges if c.pending or c.started > cutoff]
            if len(rpm) >= policy.quota_limits.rpm:
                retry_at = (
                    None
                    if any(c.pending for c in rpm)
                    else min(c.started for c in rpm) + timedelta(seconds=60)
                )
                return _blocked("rpm", "rate_limit", retry_at)
            if (
                sum(c.tokens for c in bucket.charges) + reservation.token_upper_bound
                > policy.quota_limits.tpm
            ):
                retry_at = (
                    None
                    if any(c.pending for c in bucket.charges)
                    else max(
                        (c.completed + timedelta(seconds=60) for c in bucket.charges), default=None
                    )
                )
                return _blocked("tpm", "rate_limit", retry_at)
            if bucket.daily_count >= policy.quota_limits.rpd:
                retry_at = None if any(c.pending for c in bucket.charges) else self._midnight(now)
                return _blocked("rpd", "quota_exceeded", retry_at)
            money = self._money.setdefault(project_ref, _MoneyState())
            targets = [(money, policy.budget)] if money_enabled else []
            if self._overall_limit is not None:
                targets.append((self._overall_money, self._overall_limit))
            ceiling = reservation.spending_upper_bound if money_enabled else Decimal(0)
            for state, limit in targets:
                if state.breached or (
                    limit
                    and (
                        state.used_known + state.reserved >= limit.amount
                        or state.used_known + state.reserved + ceiling > limit.amount
                    )
                ):
                    return _blocked("budget", "quota_exceeded")
            for state, _ in targets:
                state.reserved += ceiling
            charge = _Charge(now, reservation.token_upper_bound)
            bucket.charges.append(charge)
            bucket.daily_count += 1
        # Không giữ lock qua gateway/network; mỗi invocation có reservation riêng.
        response = None
        try:
            response = binding.gateway.generate(request)
        except Exception:
            pass  # Request có thể đã gửi; không refund hoặc xuất raw exception.
        with self._lock:
            try:
                completed = self._now()
            except ValueError:
                completed = self._last_time
                bucket.unavailable = "clock_invalid"
            self._roll(bucket, completed)
            charge.completed, charge.pending = completed, False
            total = (
                response.usage.total_tokens
                if response is not None and response.usage.source == "provider_reported"
                else None
            )
            if total is None:
                bucket.unknown_usage_count += 1
            else:
                charge.tokens = total
                if total > reservation.token_upper_bound:
                    bucket.unavailable = "token_bound_exceeded"
            for state, _ in targets:
                cost = response.cost if response is not None else None
                if (
                    cost is None
                    or cost.status != "available"
                    or cost.currency != self._currency
                    or cost.source != "provider_reported"
                ):
                    state.unknown_cost_count += 1  # ceiling vẫn reserved, không unknown → zero.
                    if (
                        cost is not None
                        and cost.status == "available"
                        and cost.currency != self._currency
                    ):
                        state.breached = True
                else:
                    state.reserved -= ceiling
                    state.used_known += cost.amount
                    if cost.amount > ceiling:
                        state.breached = True
            error = (
                response.error
                if response is not None
                else GatewayError(
                    category="internal", code="internal", origin="gateway", retryability="unknown"
                )
            )
            if (
                error is not None
                and error.category in ("rate_limit", "quota_exceeded")
                and bucket.unavailable in (None, "provider_rate_limit", "provider_quota")
            ):
                previous, previous_retry = bucket.unavailable, bucket.retry_at
                bucket.unavailable = (
                    "provider_rate_limit" if error.category == "rate_limit" else "provider_quota"
                )
                bucket.retry_at = (
                    completed + timedelta(seconds=error.retry_after_seconds)
                    if error.retry_after_seconds is not None
                    else None
                )
                if previous is not None:
                    if previous == "provider_quota":
                        bucket.unavailable = previous
                    bucket.retry_at = (
                        max(previous_retry, bucket.retry_at)
                        if previous_retry is not None and bucket.retry_at is not None
                        else None
                    )
            return GuardResult(
                True,
                "completed" if response is not None else "gateway_failed",
                response=response,
                error=error,
            )
