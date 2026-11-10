"""One shared call/deadline budget across all agents and child QA lanes."""

from time import perf_counter

from .llm_gateway import SharedLLMGateway, _failure


class RequestGateway:
    generate_with_recovery = SharedLLMGateway.generate_with_recovery

    def __init__(self, gateway, *, max_calls, timeout_seconds):
        self.gateway = gateway
        self.max_calls = max_calls
        self.deadline = perf_counter() + timeout_seconds
        self.events = []
        self.exhausted = False
        self.failure_category = None
        self.judge_calls = 0
        self.revisions_used = 0

    def reserve_revision(self):
        if self.revisions_used >= 2 or self.exhausted or self.failure_category:
            return False
        self.revisions_used += 1
        return True

    def generate(self, request):
        if self.failure_category:
            return _failure(request, self.failure_category)
        remaining = self.deadline - perf_counter()
        is_judge = request.request_id.startswith(("adaptive-judge-", "document-judge-"))
        if is_judge and self.judge_calls >= 3:
            self.exhausted = True
            return _failure(request, "timeout")
        if len(self.events) >= self.max_calls or remaining < 1:
            self.exhausted = True
            return _failure(request, "timeout")
        bound = request.model_copy(deep=True)
        if bound.constraints:
            bound.constraints.timeout_seconds = min(
                bound.constraints.timeout_seconds or remaining, remaining
            )
        started = perf_counter()
        if is_judge:
            self.judge_calls += 1
        response = self.gateway.generate(bound)
        # Invalid output belongs to this call. Keep it unverified, while other
        # critics/Judge may still assess independent claims. Never auto-retry it.
        if (
            response.status != "success"
            and response.error
            and response.error.category not in {"structured_output_invalid", "schema_mismatch"}
        ):
            self.failure_category = response.error.category
        self.events.append(
            dict(
                event="LLM_AGENT_EXECUTED" if response.status == "success" else "PROVIDER_DEGRADED",
                request_id=request.request_id,
                model=request.model.model_dump(mode="json"),
                status=response.status,
                tokens=response.usage.total_tokens,
                usage=response.usage.model_dump(mode="json"),
                cost=response.cost.model_dump(mode="json"),
                error=response.error.code if response.error else None,
                latency_ms=(perf_counter() - started) * 1000,
            )
        )
        return response
