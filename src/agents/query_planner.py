"""Evidence-aware planning: một proposal call, catalog materialization, zero execution."""

import json
import re
from copy import deepcopy
from datetime import date
from time import perf_counter
from uuid import uuid4

from pydantic import ValidationError

from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_gateway import SharedLLMGateway
from ..evidence.snapshots import SnapshotCatalog
from ..tools.financial_qa import QADocument
from ..tools.question_understanding import (
    EXTRA_ALIASES,
    FORMULA_ALIASES,
    ITEM_RULES,
    _matches,
    natural_formula,
    normalize,
)
from .contracts import (
    SPECIALIST_BOUNDARIES,
    TOOL_CONTRACTS,
    EvidencePlan,
    EvidenceRequirement,
    EvidenceSelector,
    InputBinding,
    PlanStep,
    QuerySpecification,
    RiskSignal,
    validate_plan,
)
from .planner_contracts import (
    PlannerContext,
    PlannerOperation,
    PlannerProposal,
    PlannerResult,
    PlannerTrace,
)

STOP_CONDITIONS = [
    "all_required_evidence_resolved",
    "missing_required_inputs",
    "unresolved_ambiguity",
    "conflicting_evidence",
    "unsupported_operation",
    "compatibility_gate_blocked",
    "execution_limit_reached",
]

# Cách gọi ngắn ở tầng question, không thay item mapping/accounting semantics M4.
PLANNER_ALIASES = {
    "b02.profit_before_tax": ("lợi nhuận trước thuế",),
    "b02.profit_after_tax": ("lợi nhuận sau thuế",),
    "b03.operating_cash_flow": ("dòng tiền kinh doanh", "CFO"),
}

DOMAIN_ALIASES = {
    "profitability": ("khả năng sinh lời", "sinh lời"),
    "liquidity_and_leverage": ("tình hình nợ", "đòn bẩy", "thanh khoản"),
    "cash_flow_and_earnings_quality": ("dòng tiền", "chất lượng lợi nhuận"),
}
UNSUPPORTED_ALIASES = {
    "roe": ("roe", "return on equity"),
    "roa": ("roa", "return on assets"),
    "ebitda": ("ebitda",),
    "forecast": ("dự báo", "dự đoán"),
    "current_ratio": ("thanh toán hiện hành",),
    "quick_ratio": ("thanh toán nhanh",),
}


def _question_targets(question):
    # Match facts and formulas together: a metric phrase must not turn its
    # embedded operand names into additional independent factual requests.
    aliases = {
        key: (*rule.aliases, key, *EXTRA_ALIASES.get(key, ()), *PLANNER_ALIASES.get(key, ()))
        for key, rule in ITEM_RULES.items()
    }
    aliases.update(FORMULA_ALIASES)
    targets = _matches(normalize(question), aliases)
    if inferred := natural_formula(normalize(question)):
        targets.add(inferred)
        targets.discard("b02.net_revenue")
    return sorted(targets & FORMULA_ALIASES.keys()), sorted(targets & ITEM_RULES.keys())


def _explicit_constraints(question):
    text = normalize(question)
    scopes = []
    if re.search(r"\b(?:bao cao(?: tai chinh)?|bctc|pham vi) rieng\b|\brieng le\b|\brieng$", text):
        scopes.append("separate")
    if "hop nhat" in text:
        scopes.append("consolidated")
    years = sorted({int(y) for y in re.findall(r"\b(?:19|20|21)\d{2}\b", text)})
    origins = [
        s
        for s, word in (("recovery", "recovery"), ("original_extraction", "original"))
        if word in text
    ]
    if (
        any(word in text for word in ("ban goc", "snapshot goc"))
        and "original_extraction" not in origins
    ):
        origins.append("original_extraction")
    periods = re.findall(r"\b(?:19|20|21)\d{2}-\d{2}-\d{2}\b", question)
    periods.extend(
        f"{y}-{int(m):02d}-{int(d):02d}"
        for d, m, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/((?:19|20|21)\d{2})\b", question)
    )
    if "dau nam" in text and len(years) == 1:
        periods.append(f"{years[0]}-01-01")
    return years, scopes, origins, sorted(set(periods))


def _ordered_operations(proposal):
    operations = {o.operation_id: o for o in proposal.operations}
    if len(operations) != len(proposal.operations):
        raise ValueError("duplicate_proposal_operation")
    ordered, active, visited = [], set(), set()

    def visit(key):
        if key not in operations:
            raise ValueError("unknown_proposal_dependency")
        if key in active:
            raise ValueError("proposal_dependency_cycle")
        if key in visited:
            return
        active.add(key)
        for dependency in operations[key].dependencies:
            visit(dependency)
        active.remove(key)
        visited.add(key)
        ordered.append(operations[key])

    for key in operations:
        visit(key)
    return ordered


class EvidenceAwareQueryPlanner:
    def __init__(
        self, catalog: SnapshotCatalog, documents=(), gateway: SharedLLMGateway | None = None
    ):
        self._catalog = deepcopy(catalog)
        self._documents = [QADocument.model_validate(d).model_copy(deep=True) for d in documents]
        known = {d.document_id for d in catalog.descriptors}
        if len({d.document_id for d in self._documents}) != len(self._documents) or any(
            d.document_id not in known for d in self._documents
        ):
            raise ValueError("invalid_planner_document_metadata")
        self._gateway = gateway

    @staticmethod
    def plan_document(requirements, manifest, snapshot_id):
        from .document_qa import document_operations

        return document_operations(requirements, manifest, snapshot_id)

    def _prompt(self, context):
        return {
            "instruction": (
                "Lập kế hoạch phân tích tài chính tiếng Việt, không thực thi hoặc trả số liệu. "
                "Xuất duy nhất JSON theo schema. Không xuất document/snapshot/metric IDs, values, "
                "PDF citations, approval hoặc verified facts. Nhận diện nhiều mục tiêu và paraphrases. "
                "reporting_years chỉ là năm filing được yêu cầu; period=null nếu chỉ nêu năm. "
                "Không suy scope; reporting_scope=null nếu không nêu riêng/hợp nhất. "
                "snapshot_origin=null nếu không nêu original/recovery. Thiếu metadata ghi missing_information. "
                "D03-B10 chặn so sánh liên tài liệu, không được chia nhỏ để lách gate. "
                "revenue_yoy dùng hai kỳ đã bind trong cùng filing, không cần hai filing. "
                "Không giới hạn nhận diện nhu cầu vào ba metrics: ROE/ROA và capability khác phải "
                "ghi unsupported_capabilities; chỉ intent=unsupported nếu không có phần supported. "
                "Giữ targets/operations supported khi yêu cầu chỉ được hỗ trợ một phần. "
                "Không chọn metric gần giống. Ba specialist_boundaries đều có sẵn; hai/ba lĩnh vực "
                "đồng thời được hỗ trợ, không ghi role/capability đã đăng ký vào unsupported_capabilities. "
                "Với mục tiêu phân tích tổng quát, tự chọn các chỉ tiêu đã đăng ký phù hợp mục tiêu; "
                "chỉ hỏi lại khi company/filing hoặc yêu cầu thực sự mơ hồ. "
                "Không tự chọn ROA/ROE/EBITDA hoặc một ratio đại diện cho domain. "
                "Thiếu evidence không phải unsupported capability; backend kiểm tra readiness. "
                "Mọi direct fact dùng find_financial_facts và get_evidence_sources phụ thuộc fact đó. "
                "QUY TẮC INTENT: direct_fact chỉ có MỘT chỉ tiêu độc lập. Hai hoặc nhiều chỉ tiêu "
                "độc lập trong câu hỏi phải là multi_step_analysis, kể cả chỉ truy xuất/đối chiếu "
                "mà không tính ratio. Bắt buộc thêm prepare_bundle phụ thuộc tất cả source outputs. "
                "Hai operands nội bộ của một metric không phải hai mục tiêu độc lập. "
                "Yêu cầu kiểm tra/giải thích nguồn, công thức, cách tính hoặc các kỳ đầu vào "
                "của một metric là evidence_explanation, dù có từ tính trong câu hỏi. "
                "Metric dùng calculate_financial_metric/formula_id, rồi get_metric_evidence_lineage "
                "phụ thuộc calculation (lineage đã bao gồm citations). Backend tự mở rộng calculation "
                "thành operand retrieval + formula/compatibility gates; không cần lặp operands thành "
                "fact operations trừ khi câu hỏi cũng yêu cầu chúng. required_indicators gồm operands. "
                "get_evidence_sources chỉ phụ thuộc đúng một find_financial_facts; "
                "get_metric_evidence_lineage chỉ phụ thuộc đúng một calculation. "
                "Các facts độc lập không phụ thuộc nhau. prepare_bundle phụ thuộc tất cả outputs "
                "cần tổng hợp và bắt buộc cho multi_step_analysis. operation_id tùy chọn, dependencies "
                "tham chiếu operation_id. Mỗi operation chỉ có item_id cho facts hoặc formula_id cho "
                "calculation; các operation khác hai field null. "
                "evidence_needs: fact/citations cho facts; fact/formula/compatibility/metric/lineage/"
                "citations cho metrics; analysis_bundle cho multi-step. Unknown scope cho phép direct "
                "facts và approved same-filing calculation với caveats; usable_with_caveat không là verified. "
                "ADAPTIVE: reasoning_required=false cho truy xuất/công thức đơn giản; assignments=[] "
                "để tool-only. Phân tích quan hệ/đánh giá cần reasoning_required=true và assignments "
                "chọn đúng specialists, task cụ thể, indicators/formulas và depends_on theo role hoặc operation_id đã khai báo. "
                "Chất lượng lợi nhuận cần PAT/CFO và ít nhất profitability cùng cash_flow_and_earnings_quality. "
                "Không gọi mọi specialist mặc định. selection_reason giải thích lựa chọn; completion_conditions "
                "nêu khi đủ evidence, không suy nguyên nhân không có nguồn. "
                "Nếu feedback có mặt: chỉ sửa operations/assignments bị ảnh hưởng; giữ phần còn hợp lệ "
                "trong previous_proposal/reusable_results. Bổ sung evidence thiếu hoặc bỏ claim vượt nguồn; "
                "nếu không có hướng mới đặt stop_reason. Không đổi company, filing, snapshot hay scope."
                " So sánh trong cùng filing dùng reporting_years=[năm filing], cross_document_comparison=false; "
                "mỗi find_financial_facts có period riêng (YYYY cho B02/B03, YYYY-12-31 cho B01). "
                "Chỉ dùng những kỳ được nêu hoặc có trong filing đã chọn; không lấy từ tài liệu khác."
            ),
            "schema": PlannerProposal.model_json_schema(),
            "canonical_indicators": {
                key: dict(
                    aliases=list(
                        dict.fromkeys(
                            (*r.aliases, *EXTRA_ALIASES.get(key, ()), *PLANNER_ALIASES.get(key, ()))
                        )
                    ),
                    statement=r.statement_type,
                    period_types=r.period_types,
                )
                for key, r in ITEM_RULES.items()
            },
            "approved_formula_candidates": [
                p.model_dump(mode="json") for p in self._catalog.policies
            ],
            "allowed_M4_tools": list(TOOL_CONTRACTS),
            "specialist_boundaries": [b.model_dump(mode="json") for b in SPECIALIST_BOUNDARIES],
            "companies": sorted({a for d in self._documents for a in d.company_aliases}),
            "context": context.model_dump(
                mode="json", exclude={"model", "document_id", "snapshot_id"}
            ),
        }

    def _gemini(self, question, context, result):
        if self._gateway is None:
            raise ValueError("gateway_unavailable")
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="planner-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(
                    role="system", content=json.dumps(self._prompt(context), ensure_ascii=False)
                ),
                Message(role="user", content=question),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=3000),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=context.provider_timeout_seconds),
        )
        start = perf_counter()
        attempts = self._gateway.generate_with_recovery(
            request, max_attempts=context.provider_attempt_limit
        )
        if not attempts:
            raise ValueError("provider_timeout_budget_exhausted")
        response = attempts[-1].response
        meta = result.llm
        meta.attempts = attempts
        meta.calls, meta.model = len(attempts), context.model
        meta.latency_ms = (perf_counter() - start) * 1000
        meta.status, meta.usage, meta.cost = response.status, response.usage, response.cost
        meta.provenance, meta.error = response.provenance, response.error
        if isinstance(response.output, JSONOutput):
            result.raw_proposal = response.output.payload
        if response.status != "success" or not isinstance(response.output, JSONOutput):
            raise ValueError(
                response.error.category if response.error else "gateway_response_failed"
            )
        return result.raw_proposal

    def _deterministic(self, question):
        """Catalog alias mode để tiết kiệm quota; không dùng single-target M4 parser."""
        text = normalize(question)
        years, scopes, origins, periods = _explicit_constraints(question)
        formulas, items = _question_targets(question)
        unsupported = sorted(_matches(text, UNSUPPORTED_ALIASES))
        company = next(
            (
                a
                for d in self._documents
                for a in d.company_aliases
                if re.search(r"\b" + re.escape(normalize(a)) + r"\b", text)
            ),
            None,
        )
        explanation = bool(formulas) and any(
            p in text
            for p in (
                "cong thuc",
                "tu dau",
                "nhung so lieu",
                "can so lieu",
                "nguon goc",
                "bang chung",
            )
        )
        multiple = len(items) + len(formulas) > 1
        intent = (
            "unsupported"
            if not (formulas or items)
            else (
                "multi_step_analysis"
                if multiple
                else "evidence_explanation"
                if explanation
                else "calculated_metric"
                if formulas
                else "direct_fact"
            )
        )
        proposal = PlannerProposal(
            intent=intent,
            company_alias=company,
            reporting_years=years,
            reporting_scope=scopes[0] if len(scopes) == 1 else None,
            snapshot_origin=origins[0] if len(origins) == 1 else None,
            period=periods[0] if len(periods) == 1 else None,
            formula_ids=formulas,
            required_indicators=items,
            unsupported_capabilities=unsupported,
            cross_document_comparison=len(years) > 1,
        )
        if intent == "unsupported":
            return proposal.model_dump(mode="json")
        terminals = []
        for i, item in enumerate(items):
            key = f"fact_{i}"
            proposal.operations.extend(
                [
                    PlannerOperation(
                        operation_id=key, operation="find_financial_facts", canonical_item_id=item
                    ),
                    PlannerOperation(
                        operation_id=f"sources_{i}",
                        operation="get_evidence_sources",
                        dependencies=[key],
                    ),
                ]
            )
            terminals.append(f"sources_{i}")
        for i, formula in enumerate(formulas):
            key = f"metric_{i}"
            proposal.operations.extend(
                [
                    PlannerOperation(
                        operation_id=key, operation="calculate_financial_metric", formula_id=formula
                    ),
                    PlannerOperation(
                        operation_id=f"lineage_{i}",
                        operation="get_metric_evidence_lineage",
                        dependencies=[key],
                    ),
                ]
            )
            terminals.append(f"lineage_{i}")
        proposal.evidence_needs = ["fact", "citations"]
        if formulas:
            proposal.evidence_needs.extend(["formula", "compatibility", "metric", "lineage"])
        if multiple:
            proposal.operations.append(
                PlannerOperation(
                    operation_id="bundle", operation="prepare_bundle", dependencies=terminals
                )
            )
            proposal.evidence_needs.append("analysis_bundle")
        return proposal.model_dump(mode="json")

    def _semantic_policy(self, question, proposal, result):
        """Bounded alias checks; never choose a representative domain metric."""
        effective = proposal.model_copy(deep=True)
        lexical = PlannerProposal.model_validate(self._deterministic(question))
        formulas, items = set(lexical.formula_ids), set(lexical.required_indicators)
        registered = {
            normalize(name)
            for boundary in SPECIALIST_BOUNDARIES
            for name in (
                boundary.role,
                boundary.responsibility,
                *boundary.capabilities,
                *DOMAIN_ALIASES[boundary.role],
            )
        }
        removed = [
            name for name in proposal.unsupported_capabilities if normalize(name) in registered
        ]
        effective.unsupported_capabilities = [
            name for name in proposal.unsupported_capabilities if name not in removed
        ]
        for name in lexical.unsupported_capabilities:
            if normalize(name) not in {normalize(n) for n in effective.unsupported_capabilities}:
                effective.unsupported_capabilities.append(name)
        reasons = ["registered_capability_misclassified:" + name for name in removed]
        domains = _matches(normalize(question), DOMAIN_ALIASES)
        target_roles = set()
        for prefix, role in (
            ("b02.", "profitability"),
            ("b01.", "liquidity_and_leverage"),
            ("b03.", "cash_flow_and_earnings_quality"),
        ):
            if any(i.startswith(prefix) for i in items):
                target_roles.add(role)
        if formulas & {"gross_margin", "revenue_yoy"}:
            target_roles.add("profitability")
        if "debt_to_assets" in formulas:
            target_roles.add("liquidity_and_leverage")
        unclear = domains - target_roles
        if unclear or (
            removed and not (formulas or items) and not effective.unsupported_capabilities
        ):
            effective.intent = "ambiguous"
            effective.missing_information = [
                "explicit_target_for:" + role for role in sorted(unclear)
            ] or ["analysis_target"]
            effective.operations = []
            effective.formula_ids = sorted(formulas)
            effective.required_indicators = sorted(items)
            reasons.append("supported_domain_requires_explicit_targets")
        elif lexical.unsupported_capabilities and not (formulas or items):
            effective.intent = "unsupported"
            effective.formula_ids, effective.required_indicators, effective.operations = [], [], []
            reasons.append("unsupported_target_cannot_be_substituted")
        elif proposal.intent == "ambiguous" or proposal.missing_information:
            # An intentionally empty DAG awaiting clarification is not an omitted
            # target. Preserve the model's question instead of inventing a plan.
            reasons.append("proposal_clarification_preserved")
        elif (
            (formulas or items)
            and (proposal.intent == "unsupported" or not proposal.operations)
            and not proposal.missing_information
        ):
            # Only exact catalog aliases. All original metadata/constraints remain
            # on effective; materialization and accounting gates still run below.
            for field in (
                "intent",
                "formula_ids",
                "required_indicators",
                "operations",
                "evidence_needs",
            ):
                setattr(effective, field, getattr(lexical, field))
            reasons.append("explicit_catalog_targets_recovered")
        elif formulas - set(proposal.formula_ids) or items - {
            op.canonical_item_id
            for op in proposal.operations
            if op.operation == "find_financial_facts"
        }:
            effective.intent = "ambiguous"
            effective.missing_information = ["proposal_omits_explicit_target"]
            reasons.append("explicit_targets_not_covered_by_proposal")
        if reasons:
            result.trace.append(
                PlannerTrace(stage="semantic_policy", outcome=effective.intent, reasons=reasons)
            )
        else:
            result.trace.append(PlannerTrace(stage="semantic_policy", outcome="consistent"))
        return effective

    def plan(self, question: str, context: PlannerContext | None = None) -> PlannerResult:
        context = PlannerContext.model_validate_json(
            (context or PlannerContext()).model_dump_json()
        )
        result = PlannerResult(
            question=question,
            query=QuerySpecification(
                original_question=question, intent="unsupported", analysis_type="pending"
            ),
            status="failed",
        )
        start, stage = perf_counter(), "understanding"
        try:
            payload = (
                self._gemini(question, context, result)
                if context.mode != "deterministic"
                else self._deterministic(question)
            )
            result.raw_proposal = payload
            result.trace.append(PlannerTrace(stage=stage, outcome=context.mode))
            stage = "proposal_schema"
            proposal = PlannerProposal.model_validate(payload)
            result.proposal = proposal
            result.trace.append(PlannerTrace(stage=stage, outcome="validated"))
            stage = "semantic_policy"
            # LLM owns semantic planning in auto. Catalog/typed plan validation below
            # still controls IDs, accounting capabilities and exact source binding.
            if context.mode != "auto":
                proposal = self._semantic_policy(question, proposal, result)
            else:
                proposal = proposal.model_copy(deep=True)
            result.effective_proposal = proposal
            result.query = QuerySpecification(
                original_question=question,
                intent=proposal.intent,
                company_alias=proposal.company_alias,
                required_indicators=proposal.required_indicators,
                requested_formula_ids=proposal.formula_ids,
                reporting_periods=[proposal.period] if proposal.period else [],
                reporting_year=proposal.reporting_years[0]
                if len(proposal.reporting_years) == 1
                else None,
                reporting_scope=proposal.reporting_scope,
                analysis_type=proposal.intent,
                cross_document_comparison=proposal.cross_document_comparison,
                missing_information=proposal.missing_information,
            )
            # Chuẩn hóa nhãn route cho yêu cầu evidence tường minh. Targets và DAG
            # vẫn từ Gemini; raw/validated proposal giữ nguyên để chấm understanding.
            if proposal.intent == "calculated_metric" and any(
                phrase in normalize(question)
                for phrase in ("kiem tra nguon", "giai thich nguon", "cach tinh")
            ):
                result.query.intent = "evidence_explanation"
                result.trace.append(
                    PlannerTrace(
                        stage="understanding",
                        outcome="explicit_evidence_intent_normalized",
                        reasons=["original_proposal_intent_preserved"],
                    )
                )
            stage = "catalog_resolution"
            scope = self._resolve(question, context, proposal, result)
            if scope is not None:
                result.trace.append(PlannerTrace(stage=stage, outcome="resolved"))
                stage = "materialization"
                result.plan = self._materialize(scope, context, proposal, result)
                result.trace.append(PlannerTrace(stage=stage, outcome="materialized"))
                stage = "validation"
                result.validation = validate_plan(result.plan, catalog=self._catalog)
                result.risks.extend(result.validation.risks)
                result.status = "planned" if result.validation.execution_eligible else "blocked"
                result.reasons.extend(result.validation.errors)
                result.reasons.extend(r.reason for r in result.validation.risks if r.blocking)
                result.trace.append(
                    PlannerTrace(stage=stage, outcome=result.validation.disposition)
                )
        except ValidationError as error:
            result.status = "failed"
            result.reasons.append("invalid_" + stage + "_schema")
            result.trace.append(
                PlannerTrace(
                    stage=stage,
                    outcome="failed",
                    reasons=[e["msg"] for e in error.errors(include_input=False)],
                )
            )
        except ValueError as error:
            result.status = (
                "unsupported"
                if str(error) == "metric_missing_or_ambiguous_in_selected_filing"
                else "failed"
            )
            result.reasons.append(str(error))
            result.trace.append(PlannerTrace(stage=stage, outcome="failed", reasons=[str(error)]))
        result.latency_ms = (perf_counter() - start) * 1000
        return result

    def _resolve(self, question, context, proposal, result):
        query = result.query

        def stop(status, reason, *, missing=None, risk=None):
            result.status = status
            result.reasons.append(reason)
            if missing:
                result.missing_information.append(missing)
                if missing not in query.missing_information:
                    query.missing_information.append(missing)
            if risk:
                result.risks.append(RiskSignal(code=risk, reason=reason))
            result.trace.append(
                PlannerTrace(stage="catalog_resolution", outcome=status, reasons=[reason])
            )

        years, scopes, origins, periods = _explicit_constraints(question)
        if len(scopes) > 1 or len(periods) > 1:
            stop(
                "clarification_required",
                "conflicting_explicit_constraints",
                missing="reporting_scope/snapshot/period",
            )
            return None
        if any(y not in years and y != context.reporting_year for y in proposal.reporting_years):
            raise ValueError("proposal_invented_reporting_year")
        explicit_scope = scopes[0] if scopes else context.reporting_scope
        if scopes and context.reporting_scope and scopes[0] != context.reporting_scope:
            stop(
                "clarification_required",
                "question_context_scope_conflict",
                missing="reporting_scope",
            )
            return None
        if proposal.reporting_scope not in (None, explicit_scope):
            raise ValueError("proposal_invented_or_changed_scope")
        if (
            years
            and context.reporting_year
            and len(years) == 1
            and years[0] != context.reporting_year
        ):
            stop(
                "clarification_required", "question_context_year_conflict", missing="reporting_year"
            )
            return None
        query.reporting_scope = explicit_scope
        if proposal.snapshot_origin and proposal.snapshot_origin not in origins:
            raise ValueError("proposal_invented_snapshot_origin")
        period = periods[0] if periods else context.period
        # A provider may echo the explicitly requested filing year into period.
        # Preserve the raw proposal, but let statement types materialize their own
        # annual/as-of periods rather than treating the same year as invented.
        if (
            period is None
            and proposal.period
            and proposal.period in {str(y) for y in (*years, context.reporting_year)}
        ):
            proposal.period = None
        if proposal.period not in (None, period):
            raise ValueError("proposal_invented_period")
        proposal.period = period
        if period:
            try:
                if not re.fullmatch(r"(?:19|20|21)\d{2}", period):
                    date.fromisoformat(period)
            except ValueError:
                stop("unsupported", "invalid_explicit_period")
                return None
        # Hai operand years trong cùng filing không phải hai documents. Chỉ mở
        # đường cho approved YoY, có filing year explicit/context; periods còn
        # phải khớp chính xác persisted bindings ở materializer.
        same_filing = any(
            p in normalize(question)
            for p in ("cung bao cao", "chinh bao cao", "theo bao cao", "bao cao nam")
        )
        if (
            len(years) > 1
            and same_filing
            and (proposal.formula_ids == ["revenue_yoy"] or context.mode == "auto")
        ):
            filing_years = set(
                re.findall(r"\bbao cao(?: nam)? ((?:19|20|21)\d{2})\b", normalize(question))
            )
            if not filing_years and context.reporting_year:
                filing_years.add(str(context.reporting_year))
            if len(filing_years) != 1:
                stop(
                    "clarification_required", "same_filing_year_required", missing="reporting_year"
                )
                return None
            years = [int(next(iter(filing_years)))]
            query.cross_document_comparison = False
            result.trace.append(
                PlannerTrace(stage="catalog_resolution", outcome="explicit_same_filing_comparison")
            )
        if (
            len(years) > 1
            or query.cross_document_comparison
            or "lien tai lieu" in normalize(question)
        ):
            query.cross_document_comparison = True
            stop(
                "blocked",
                "D03-B10:cross_document_execution_not_approved",
                risk="cross_document_compatibility_unresolved",
            )
            return None
        if re.search(r"\b(quy|thang|ban nien)\b", normalize(question)):
            stop("unsupported", "non_annual_period_unsupported")
            return None
        if proposal.intent == "unsupported" or (
            proposal.unsupported_capabilities and not proposal.operations
        ):
            stop(
                "unsupported",
                ";".join(proposal.unsupported_capabilities) or "unsupported_analysis_capability",
            )
            return None
        if proposal.unsupported_capabilities:
            result.caveats.extend(
                "unsupported_portion:" + name for name in proposal.unsupported_capabilities
            )
        if proposal.intent == "ambiguous" or proposal.missing_information:
            stop(
                "clarification_required",
                "proposal_requires_clarification",
                missing=";".join(proposal.missing_information) or "analysis_target",
            )
            return None
        if any(i not in ITEM_RULES for i in proposal.required_indicators) or any(
            f not in {p.formula_id for p in self._catalog.policies} for f in proposal.formula_ids
        ):
            stop("unsupported", "indicator_or_formula_not_supported", risk="formula_not_approved")
            return None
        aliases = {
            normalize(a)
            for d in self._documents
            for a in d.company_aliases
            if re.search(r"\b" + re.escape(normalize(a)) + r"\b", normalize(question))
        }
        bound_aliases = {
            normalize(a)
            for d in self._documents
            if context.company_id and d.company_id == context.company_id
            for a in d.company_aliases
        }
        if proposal.company_alias and normalize(proposal.company_alias) not in (
            aliases or bound_aliases
        ):
            raise ValueError("proposal_invented_company")
        year = years[0] if years else context.reporting_year
        if years and context.reporting_year and year != context.reporting_year:
            stop(
                "clarification_required", "question_context_year_conflict", missing="reporting_year"
            )
            return None
        query.reporting_year = year
        candidates = [
            d
            for d in self._documents
            if (not context.document_id or d.document_id == context.document_id)
            and (not context.company_id or d.company_id == context.company_id)
            and (not aliases or any(normalize(a) in aliases for a in d.company_aliases))
            and (year is None or d.reporting_year == year)
        ]
        if not (aliases or context.company_id or context.document_id):
            stop("clarification_required", "company_required", missing="company")
            return None
        if year is None and not context.document_id:
            stop("clarification_required", "reporting_year_required", missing="reporting_year")
            return None
        if len(candidates) != 1:
            stop(
                "clarification_required" if candidates else "blocked",
                "document_missing_or_ambiguous",
                missing="document_id",
            )
            return None
        document = candidates[0]
        query.reporting_year = document.reporting_year
        # Nhắc cả original/recovery là lựa chọn chưa giải quyết, không chọn một bản.
        origin = origins[0] if len(origins) == 1 else None
        descriptors = [
            d
            for d in self._catalog.descriptors
            if d.document_id == document.document_id
            and (not context.snapshot_id or d.snapshot_id == context.snapshot_id)
            and (not origin or d.origin == origin)
        ]
        result.snapshot_candidates = [d.model_copy(deep=True) for d in descriptors]
        if len(descriptors) != 1:
            stop(
                "clarification_required" if descriptors else "blocked",
                "snapshot_selection_required" if descriptors else "snapshot_not_found",
                missing="snapshot_id",
                risk="ambiguous_snapshot" if descriptors else "missing_evidence",
            )
            return None
        descriptor = descriptors[0]
        query.selectors = [
            EvidenceSelector(
                document_id=document.document_id,
                snapshot_id=descriptor.snapshot_id,
                reporting_scope=explicit_scope,
            )
        ]
        result.caveats.extend(
            self._catalog.select(document.document_id, descriptor.snapshot_id)
            .candidates[0]
            .known_limitations
        )
        result.trace.append(
            PlannerTrace(
                stage="catalog_resolution",
                outcome="metadata_bound",
                reasons=["period_from_explicit_request_or_canonical_statement_type"],
            )
        )
        return dict(document_id=document.document_id, snapshot_id=descriptor.snapshot_id)

    def _materialize(self, scope, context, proposal, result):
        ordered = _ordered_operations(proposal)
        if not ordered:
            raise ValueError("proposal_has_no_operations")
        query = result.query
        selector = EvidenceSelector(**scope, reporting_scope=query.reporting_scope)
        requirements = [
            EvidenceRequirement(
                requirement_id="snapshot", evidence_type="snapshot", selector=selector
            )
        ]
        steps = [
            PlanStep(
                step_id="snapshot",
                step_type="resolve_snapshot",
                selector=selector,
                output_evidence_ids=["snapshot"],
                expected_result_type="SnapshotSelection",
            )
        ]
        op_steps, op_evidence, types, fact_cache, covered_items, covered_formulas = (
            {},
            {},
            {},
            {},
            set(),
            set(),
        )

        def requirement(key, kind, selected=selector, dependencies=(), **kwargs):
            requirements.append(
                EvidenceRequirement(
                    requirement_id=key,
                    evidence_type=kind,
                    selector=selected,
                    dependencies=list(dependencies),
                    **kwargs,
                )
            )

        def tool(
            key, name, selected, arguments, dependencies, inputs, output, bindings=(), formula=None
        ):
            steps.append(
                PlanStep(
                    step_id=key,
                    step_type="tool",
                    tool=name,
                    selector=selected,
                    arguments=arguments,
                    prerequisite_step_ids=list(dict.fromkeys(dependencies)),
                    required_evidence_ids=list(dict.fromkeys(inputs)),
                    output_evidence_ids=[output],
                    input_bindings=list(bindings),
                    formula_id=formula,
                    expected_result_type=TOOL_CONTRACTS[name][1].__name__,
                )
            )

        def fact(item, period, key):
            if item not in ITEM_RULES:
                raise ValueError("proposal_unknown_indicator")
            covered_items.add(item)
            cache_key = item, period
            if cache_key in fact_cache:
                return fact_cache[cache_key]
            rule = ITEM_RULES[item]
            selected = EvidenceSelector(
                **scope,
                canonical_item_id=item,
                period=period,
                statement_type=rule.statement_type,
                period_type=rule.period_types[0],
                reporting_scope=query.reporting_scope,
            )
            found = self._catalog.api.find_facts(
                selected.model_copy(update={"reporting_scope": None})
            )
            caveats = list(
                dict.fromkeys(
                    c for m in found.matches for q in m.record.quality_context for c in q.caveats
                )
            )
            requirement(
                key, "fact", selected, ["snapshot"], canonical_item_id=item, caveats=caveats
            )
            result.caveats.extend(caveats)
            tool(
                key,
                "find_financial_facts",
                selected,
                selected.model_dump(exclude_none=True),
                ["snapshot"],
                ["snapshot"],
                key,
            )
            fact_cache[cache_key] = key
            if period not in query.reporting_periods:
                query.reporting_periods.append(period)
            return key

        operations = {o.operation_id: o for o in ordered}
        for i, operation in enumerate(ordered):
            key = f"op_{i}"
            deps = [op_steps[d] for d in operation.dependencies]
            inputs = [op_evidence[d] for d in operation.dependencies]
            kind = operation.operation
            if kind != "find_financial_facts" and operation.canonical_item_id:
                raise ValueError("proposal_unexpected_indicator_binding")
            if kind != "calculate_financial_metric" and operation.formula_id:
                raise ValueError("proposal_unexpected_formula_binding")
            if kind == "find_financial_facts":
                item = operation.canonical_item_id
                if item not in ITEM_RULES or operation.dependencies:
                    raise ValueError("fact_operation_requires_known_independent_target")
                period = (
                    operation.period
                    or proposal.period
                    or context.period
                    or (
                        f"{query.reporting_year}-12-31"
                        if ITEM_RULES[item].statement_type == "B01"
                        else str(query.reporting_year)
                    )
                )
                if operation.period and operation.period[:4] not in {
                    str(y)
                    for y in (*_explicit_constraints(result.question)[0], query.reporting_year)
                }:
                    raise ValueError("operation_period_not_requested")
                key = fact(item, period, key)
                types[operation.operation_id] = "fact"
            elif kind == "calculate_financial_metric":
                formula = operation.formula_id
                policies = [p for p in self._catalog.policies if p.formula_id == formula]
                if len(policies) != 1:
                    raise ValueError("proposal_formula_not_supported")
                covered_formulas.add(formula)
                metrics = [
                    m
                    for m in self._catalog.metrics
                    if m.definition.name == formula
                    and m.request.document_id == scope["document_id"]
                    and m.request.snapshot_id == scope["snapshot_id"]
                    and (
                        not (proposal.period or context.period)
                        or (proposal.period or context.period)
                        == m.request.operand_periods[policies[0].operands[0].role]
                    )
                ]
                if len(metrics) != 1:
                    raise ValueError("metric_missing_or_ambiguous_in_selected_filing")
                metric = metrics[0]
                requested_years = _explicit_constraints(result.question)[0]
                if (
                    formula == "revenue_yoy"
                    and len(requested_years) > 1
                    and {str(y) for y in requested_years}
                    != set(metric.request.operand_periods.values())
                ):
                    raise ValueError("requested_comparative_periods_not_bound_in_filing")
                operands = [
                    fact(
                        o.canonical_item_id,
                        metric.request.operand_periods[o.role],
                        f"{key}_operand_{n}",
                    )
                    for n, o in enumerate(policies[0].operands)
                ]
                requirement(key + "_formula", "formula", dependencies=operands, formula_id=formula)
                requirement(
                    key + "_compatible", "compatibility", dependencies=operands, formula_id=formula
                )
                gate = key + "_gate"
                steps.append(
                    PlanStep(
                        step_id=gate,
                        step_type="check_compatibility",
                        selector=selector,
                        formula_id=formula,
                        prerequisite_step_ids=list(dict.fromkeys(operands + deps)),
                        required_evidence_ids=list(dict.fromkeys(operands + inputs)),
                        output_evidence_ids=[key + "_formula", key + "_compatible"],
                        expected_result_type="MetricSnapshotClosure",
                    )
                )
                requirement(
                    key,
                    "metric",
                    dependencies=[key + "_formula", key + "_compatible"],
                    formula_id=formula,
                )
                tool(
                    key,
                    kind,
                    selector,
                    {**scope, "metric_id": metric.metric_id},
                    [gate],
                    [key + "_formula", key + "_compatible"],
                    key,
                    formula=formula,
                )
                types[operation.operation_id] = "metric"
            elif kind in {"get_evidence_sources", "get_metric_evidence_lineage"}:
                expected = "fact" if kind == "get_evidence_sources" else "metric"
                if len(operation.dependencies) != 1 or types[operation.dependencies[0]] != expected:
                    raise ValueError("evidence_operation_requires_single_typed_producer")
                producer = deps[0]
                evidence_type = "citations" if expected == "fact" else "lineage"
                requirement(key, evidence_type, dependencies=inputs)
                tool(
                    key,
                    kind,
                    selector,
                    scope,
                    deps,
                    inputs,
                    key,
                    [
                        InputBinding(
                            argument="reference" if expected == "fact" else "metric_id",
                            source_step_id=producer,
                            output_path="matches.0.reference"
                            if expected == "fact"
                            else "metric_id",
                        )
                    ],
                )
                if expected == "metric":
                    requirement(key + "_citations", "citations", dependencies=[key])
                    steps[-1].output_evidence_ids.append(key + "_citations")
                types[operation.operation_id] = evidence_type
            else:
                if not inputs:
                    raise ValueError("analysis_bundle_requires_dependencies")
                requirement(key, "analysis_bundle", dependencies=inputs)
                steps.append(
                    PlanStep(
                        step_id=key,
                        step_type="prepare_bundle",
                        selector=selector,
                        prerequisite_step_ids=deps,
                        required_evidence_ids=inputs,
                        output_evidence_ids=[key],
                        expected_result_type="candidate_claim_inputs_for_M6",
                    )
                )
                types[operation.operation_id] = "analysis_bundle"
            op_steps[operation.operation_id] = op_evidence[operation.operation_id] = key
        if (
            not set(proposal.required_indicators) <= covered_items
            or set(proposal.formula_ids) != covered_formulas
        ):
            raise ValueError("proposal_targets_not_covered")
        if proposal.intent == "direct_fact" and (len(covered_items) != 1 or covered_formulas):
            raise ValueError("proposal_intent_target_mismatch")
        produced = {r.evidence_type for r in requirements}
        expected = {"fact", "citations"}
        if covered_formulas:
            expected |= {"formula", "compatibility", "metric", "lineage"}
        if proposal.intent == "multi_step_analysis":
            expected.add("analysis_bundle")
            bundles = [o for o in ordered if o.operation == "prepare_bundle"]
            ancestors = set()

            def collect(key):
                if key not in ancestors:
                    ancestors.add(key)
                    for dep in operations[key].dependencies:
                        collect(dep)

            for bundle in bundles:
                collect(bundle.operation_id)
            if set(operations) - ancestors:
                raise ValueError("analysis_bundle_omits_required_operation")
        if not expected <= produced or not set(proposal.evidence_needs) <= produced:
            raise ValueError("proposal_evidence_needs_not_covered")
        # Mỗi fact target cần nguồn riêng; không dùng nguồn một fact thay tất cả.
        sourced = {
            op_steps[o.dependencies[0]] for o in ordered if o.operation == "get_evidence_sources"
        }
        metric_operands = {
            d for r in requirements if r.evidence_type == "formula" for d in r.dependencies
        }
        if any(key not in sourced and key not in metric_operands for key in fact_cache.values()):
            raise ValueError("fact_missing_source_operation")
        explained = {
            op_steps[o.dependencies[0]]
            for o in ordered
            if o.operation == "get_metric_evidence_lineage"
        }
        if any(
            op_steps[o.operation_id] not in explained
            for o in ordered
            if o.operation == "calculate_financial_metric"
        ):
            raise ValueError("metric_missing_lineage_operation")
        query.required_indicators = sorted(covered_items)
        roles = set()
        if any(i.startswith("b02.") for i in covered_items):
            roles.add("profitability")
        if any(i.startswith("b01.") for i in covered_items):
            roles.add("liquidity_and_leverage")
        if any(i.startswith("b03.") for i in covered_items):
            roles.add("cash_flow_and_earnings_quality")
        result.caveats = sorted(set(result.caveats))
        return EvidencePlan(
            plan_id="plan-" + uuid4().hex,
            query=query.model_copy(deep=True),
            requirements=requirements,
            steps=steps,
            stop_conditions=STOP_CONDITIONS,
            evidence_limitations=result.caveats,
            specialist_roles=sorted(roles),
            execution_limit=len(steps),
        )
