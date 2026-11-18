"""Thin, deterministic conversation binding; financial authority stays in QA/M6/M7."""

from threading import RLock
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.composition import payload_sha256
from .qa_pipeline_contracts import FinancialQARequest, FinancialQAResponse, PipelineTrace


class ConversationMessage(FinancialQARequest):
    execution_mode: Literal["auto", "gemini", "deterministic"] = "auto"


class ConversationContext(FinancialModel):
    company_id: str | None = None
    document_id: str | None = None
    snapshot_id: str | None = None
    composition_id: str | None = None
    composition_sha256: str | None = None
    document_snapshots: list[str] = Field(default_factory=list)
    period: str | None = None
    reporting_scope: str | None = None


class ConversationTurn(FinancialModel):
    conversation_id: str
    turn_id: int
    original_question: str
    resolved_question: str | None = None
    context: ConversationContext
    inherited: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    resolution_latency_ms: float
    total_latency_ms: float
    response: FinancialQAResponse


class ConversationState(FinancialModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    turn_id: int = 0
    # Explicit selections are intent, not claims or successful evidence binding.
    selected_context: ConversationContext = Field(default_factory=ConversationContext)
    resolved_context: ConversationContext | None = None
    topics: list[str] = Field(default_factory=list)
    reference_question: str | None = None
    verified_claim_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    turns: list[ConversationTurn] = Field(default_factory=list)


class ConversationService:
    """In-process sessions, lost on restart. Inject the existing FinancialQAPipeline.

    One lock serializes local turns and pipeline catalog preparation. Copies returned
    to callers cannot mutate stored state. No model calls are made by this layer.
    """

    def __init__(self, pipeline, *, history_limit=40):
        if history_limit < 1:
            raise ValueError("history_limit_must_be_positive")
        self.pipeline = pipeline
        self.history_limit = history_limit
        self._sessions = {}
        self._lock = RLock()

    def create(self):
        with self._lock:
            state = ConversationState()
            self._sessions[state.conversation_id] = state
            return state.model_copy(deep=True)

    def history(self, conversation_id):
        with self._lock:
            return self._sessions[conversation_id].model_copy(deep=True)

    def _resolve(self, state, request):
        """Keep explicit UI selections and original turns for semantic resolution by the Coordinator."""
        old = state.selected_context
        values = old.model_dump()
        explicit = {
            k: v
            for k, v in request.model_dump().items()
            if k in values and v is not None and v != []
        }
        if any(k in explicit and explicit[k] != values[k] for k in ("company_id", "document_id")):
            values = ConversationContext().model_dump()
        values.update(explicit)
        context = ConversationContext(**values)
        changed = [k for k in values if getattr(context, k) != getattr(old, k)]
        inherited = [k for k, v in values.items() if v and k not in explicit]
        bound = request.model_copy(update=context.model_dump())
        bound.conversation_context = [
            dict(
                question=t.original_question,
                answer=t.response.answer_vi,
                verified_claim_ids=t.response.used_verified_claim_ids,
                citation_ids=[c.citation_id for c in t.response.citations],
            )
            for t in state.turns[-8:]
            if t.context.company_id == context.company_id
            and t.context.document_id == context.document_id
        ]
        return bound, context, inherited, changed, [], None

    def send(self, conversation_id, request: FinancialQARequest):
        request = FinancialQARequest.model_validate(request)
        with self._lock:
            state = self._sessions[conversation_id]
            start = perf_counter()
            bound, context, inherited, changed, topics, clarification = self._resolve(
                state, request
            )
            resolution_ms = (perf_counter() - start) * 1000
            if clarification:
                response = FinancialQAResponse(
                    status="clarification_required",
                    mode="CLARIFICATION_REQUIRED",
                    answer_vi=clarification,
                    trace=PipelineTrace(request_id=request.request_id),
                )
            else:
                response = self.pipeline.run(bound)
            successful = response.status in {
                "completed",
                "completed_with_caveats",
                "partial_verified_coverage",
            }
            successful = successful and bool(
                response.used_verified_claim_ids and response.citations
            )
            if successful:
                # The trace reports the identities actually resolved by existing QA.
                for key in ("company_id", "document_id", "snapshot_id"):
                    value = getattr(response.trace, key)
                    if value:
                        setattr(context, key, value)
                manifests = [
                    m
                    for m in self.pipeline.compositions
                    if m.logical_document_id == context.document_id
                    and (not context.composition_id or m.composition_id == context.composition_id)
                ]
                if len(manifests) == 1:
                    context.document_snapshots = sorted(
                        {
                            source.descriptor.snapshot_id
                            for source in manifests[0].sources
                            if source.status == "verified"
                        }
                    )
                    context.composition_id = manifests[0].composition_id
                    context.composition_sha256 = payload_sha256(
                        manifests[0].model_dump(mode="json")
                    )
                state.selected_context = context.model_copy(deep=True)
                state.resolved_context = context.model_copy(deep=True)
                # Several partial targets are ambiguous; one verified topic
                # remains a valid referent even when its analysis is incomplete.
                state.topics = (
                    topics
                    if response.status != "partial_verified_coverage" or len(topics) == 1
                    else []
                )
                state.reference_question = bound.question
                state.verified_claim_ids = list(response.used_verified_claim_ids)
                state.citation_ids = [c.citation_id for c in response.citations]
                state.summary = f"{context.company_id}; {context.period}; {'; '.join(state.topics)}"
            elif changed:
                # Keep explicit user selections, never promote failed inferred targets.
                state.selected_context = context.model_copy(deep=True)
                state.resolved_context = None
                state.topics = []
                state.reference_question = None
                state.verified_claim_ids = []
                state.citation_ids = []
                state.summary = ""
            if not successful and not (
                response.status in {"internal_error", "provider_unavailable"} and not changed
            ):
                # A failed current target cannot leave an older target looking like
                # the referent of "this metric". Successful evidence remains in QA.
                state.topics = []
                state.reference_question = None
            state.turn_id += 1
            turn = ConversationTurn(
                conversation_id=conversation_id,
                turn_id=state.turn_id,
                original_question=request.question,
                resolved_question=bound.question if bound else None,
                context=context,
                inherited=inherited,
                changed=changed,
                resolution_latency_ms=resolution_ms,
                total_latency_ms=(perf_counter() - start) * 1000,
                response=response,
            )
            state.turns.append(turn)
            state.turns = state.turns[-self.history_limit :]
            return turn.model_copy(deep=True)
