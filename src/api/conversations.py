"""Thin, deterministic conversation binding; financial authority stays in QA/M6/M7."""

import re
from threading import RLock
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.document_qa_contracts import document_intent
from ..evidence.composition import payload_sha256
from ..tools.question_understanding import (
    EXTRA_ALIASES,
    FORMULA_LABELS,
    ITEM_RULES,
    normalize,
    understand,
)
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
        text = normalize(request.question)
        parsed, _ = understand(request.question)
        old = state.selected_context
        values = old.model_dump()
        explicit = {
            k: v
            for k, v in request.model_dump().items()
            if k in values and v is not None and v != []
        }
        companies = {
            d.company_id
            for d in self.pipeline.documents
            if any(
                re.search(r"(?<!\w)" + re.escape(normalize(a)) + r"(?!\w)", text)
                for a in [d.company_id, *d.company_aliases]
            )
        }
        known_aliases = {
            normalize(a)
            for d in self.pipeline.documents
            for a in [d.company_id, *d.company_aliases]
        }
        unknown_tickers = {
            word
            for word in re.findall(r"\b[A-Z]{2,8}\b", request.question)
            if normalize(word) not in known_aliases
            and word not in {"ROE", "ROA", "EBITDA", "VND", "PDF", "QA", "AI"}
        }
        if unknown_tickers:
            return (
                None,
                old,
                [],
                [],
                [],
                "Chưa xác định được công ty trong câu hỏi. Bạn muốn chọn công ty nào?",
            )
        if len(companies) > 1 or (
            companies and request.company_id and companies != {request.company_id}
        ):
            return None, old, [], [], [], "Bạn muốn hỏi công ty nào trong lượt này?"
        if companies:
            explicit["company_id"] = next(iter(companies))
        if parsed.reporting_year:
            if request.period and request.period[:4] != str(parsed.reporting_year):
                return (
                    None,
                    old,
                    [],
                    [],
                    [],
                    "Năm trong câu hỏi khác kỳ đã chọn. Bạn muốn dùng kỳ nào?",
                )
            explicit["period"] = parsed.period or str(parsed.reporting_year)
        if parsed.reporting_scope:
            if request.reporting_scope and parsed.reporting_scope != request.reporting_scope:
                return None, old, [], [], [], "Bạn muốn dùng báo cáo riêng hay hợp nhất?"
            explicit["reporting_scope"] = parsed.reporting_scope
        # A supplied document is a deliberate selection; resolve only declared metadata.
        if request.document_id:
            docs = [d for d in self.pipeline.documents if d.document_id == request.document_id]
            if len(docs) == 1:
                if explicit.get("company_id", docs[0].company_id) != docs[0].company_id:
                    return None, old, [], [], [], "Công ty và tài liệu đã chọn không khớp."
                explicit["company_id"] = docs[0].company_id
        switched = any(
            k in explicit and explicit[k] != values[k]
            for k in ("company_id", "document_id", "period")
        )
        if switched:
            for key in (
                "document_id",
                "snapshot_id",
                "composition_id",
                "composition_sha256",
                "document_snapshots",
            ):
                values[key] = [] if key == "document_snapshots" else None
        values.update(explicit)
        context = ConversationContext(**values)
        changed = [k for k, v in values.items() if v != getattr(old, k)]
        inherited = [k for k, v in values.items() if v and k not in explicit and k not in changed]
        topics = []
        if parsed.formula_id:
            topics.append(FORMULA_LABELS[parsed.formula_id])
        elif parsed.canonical_item_id:
            topics.append(
                EXTRA_ALIASES.get(
                    parsed.canonical_item_id, ITEM_RULES[parsed.canonical_item_id].aliases
                )[-1]
            )
        kind, specs = document_intent(request.question)
        topics.extend(s.label for s in specs)
        relative = "nam truoc" in text
        comparison = relative and any(p in text for p in ("so voi", "so sanh", "tang", "giam"))
        if relative:
            if not context.period:
                return None, context, inherited, changed, [], "Năm trước là so với năm nào?"
            if parsed.reporting_year is None and not comparison:
                context.period = str(int(context.period[:4]) - 1)
                context.document_id = context.snapshot_id = None
                context.composition_id = context.composition_sha256 = None
                context.document_snapshots = []
                changed.append("period")
        question = request.question
        expanded = False
        if (
            request.execution_mode == "auto"
            and not topics
            and not switched
            and state.reference_question
            and state.verified_claim_ids
            and re.fullmatch(
                r"(?:noi dung do |doan do |nguon cua noi dung do |nguon |no )?(?:o dau|o trang nao|trang nao)(?:\?)?",
                text,
            )
        ):
            document = document_intent(state.reference_question)[0] == "document"
            bound = request.model_copy(
                update={
                    **context.model_dump(),
                    "question": state.reference_question,
                    "force_refresh": False,
                    "allow_gateway": False,
                    "period": None if document else context.period,
                }
            )
            if not document:
                bound.composition_id = bound.composition_sha256 = None
                bound.document_snapshots = []
            return (
                bound,
                context,
                inherited + ["exact_verified_source_lookup"],
                changed,
                list(state.topics),
                None,
            )
        if comparison:
            target = parsed.canonical_item_id
            if target == "b02.net_revenue" or (
                not topics and [normalize(t) for t in state.topics] == ["doanh thu thuan"]
            ):
                question = "Tăng trưởng doanh thu"
                topics = [FORMULA_LABELS["revenue_yoy"]]
            else:
                return (
                    None,
                    context,
                    inherited,
                    changed,
                    [],
                    "Bạn muốn so sánh chỉ tiêu nào? Hiện chỉ hỗ trợ tăng trưởng doanh thu qua công thức đã duyệt.",
                )
        elif not topics:
            if (
                request.execution_mode != "deterministic"
                and request.allow_gateway
                and self.pipeline.gateway
                and context.company_id
                and context.period
            ):
                # Keep the actual analytical follow-up for the LLM Planner.
                # Only exact declared metadata is inherited; prior prose is context,
                # never new financial evidence.
                bound = request.model_copy(
                    update={
                        **context.model_dump(),
                        "question": request.question + f" cho năm {context.period[:4]}",
                        "period": context.period,
                        "composition_id": None,
                        "composition_sha256": None,
                        "document_snapshots": [],
                        "conversation_context": [
                            dict(
                                question=t.original_question,
                                resolved_question=t.resolved_question,
                                answer=t.response.answer_vi[:1600],
                                verified_claim_ids=t.response.used_verified_claim_ids,
                            )
                            for t in state.turns[-2:]
                        ],
                    }
                )
                return (
                    bound,
                    context,
                    inherited + ["conversation_context"],
                    changed,
                    list(state.topics),
                    None,
                )
            followup = bool(
                re.search(
                    r"\b(no|chi so nay|khoan muc do|nam do|nam truoc|con|cong thuc|o dau|trang nao|nguon|noi dung do|thuyet minh do)\b",
                    text,
                )
            )
            if not followup or len(state.topics) != 1:
                return (
                    None,
                    context,
                    inherited,
                    changed,
                    [],
                    "Bạn muốn hỏi chỉ tiêu hoặc nội dung nào? Hãy nêu rõ công ty và năm nếu chưa chọn.",
                )
            topics = list(state.topics)
            expanded = True
            if document_intent(state.reference_question or "")[0] == "document":
                question = f"Thuyết minh về {topics[0]} ở đâu?"
            elif "cong thuc" in text:
                question = f"Công thức tính {topics[0]} là gì?"
            elif any(p in text for p in ("nguon", "trang nao", "o dau")):
                question = f"Nguồn số liệu {topics[0]} ở đâu?"
            elif any(p in text for p in ("y nghia", "la gi", "giai thich")):
                question = f"Ý nghĩa của {topics[0]} là gì?"
            else:
                question = topics[0]
            inherited.append("topic")
        if not context.company_id or not context.period:
            return None, context, inherited, changed, topics, "Bạn muốn hỏi công ty và năm nào?"
        # Never carry a prior fiscal year into an explicit new period question.
        if relative:
            question = re.sub(r"năm trước", "", question, flags=re.I)
        question = question.rstrip(" ?.!;\n")
        if not parsed.reporting_year or comparison or expanded:
            # "ở đâu năm ..." would be misread by the existing parser as "đầu năm".
            question += f" cho năm {context.period[:4]}"
        if not companies or expanded:
            question += f" {context.company_id}"
        if context.reporting_scope and not parsed.reporting_scope:
            question += " hợp nhất" if context.reporting_scope == "consolidated" else " riêng"
        bound = request.model_copy(update={**context.model_dump(), "question": question})
        # Document periods live in the declared reporting year, not financial fact
        # period filters. Annual financial questions also let QA derive B01/B02 dates.
        if kind == "document" or document_intent(question)[0] == "document":
            bound.period = None
            if not request.snapshot_id:
                bound.snapshot_id = None
        elif context.period and len(context.period) == 4:
            bound.period = None
        if document_intent(question)[0] == "other":
            # Financial-only M7 contracts intentionally reject document composition
            # filters. Keep the session's provenance, but bind only the active lane.
            for key in ("composition_id", "composition_sha256", "document_snapshots"):
                if key not in explicit:
                    setattr(bound, key, [] if key == "document_snapshots" else None)
        changed = [
            key
            for key in ConversationContext.model_fields
            if getattr(context, key) != getattr(old, key)
        ]
        inherited = [
            key
            for key in inherited
            if key == "topic" or (getattr(context, key) and key not in changed)
        ]
        return bound, context, inherited, changed, topics, None

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
                # Partial coverage can leave several requested targets unresolved.
                state.topics = topics if response.status != "partial_verified_coverage" else []
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
            if not successful:
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
