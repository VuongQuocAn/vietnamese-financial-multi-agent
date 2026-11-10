"""B03 cash flows and B02 profit facts; bounded sign prose, never earnings-quality scoring."""

import re
import unicodedata
from decimal import Decimal
from time import perf_counter
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import ModelIdentity
from ..core.llm_gateway import SharedLLMGateway
from ..tools.question_understanding import normalize
from .contracts import SPECIALIST_BOUNDARIES
from .query_planner import _explicit_constraints
from .specialist_common import (
    SpecialistEvidence,
    SpecialistResult,
    SpecialistTrace,
    _number,
    generate_candidates,
    select_evidence,
    with_assignment,
)
from .supervisor import SupervisorResult

PROMPT_VERSION = "cash_flow_earnings_quality_v2"
ITEM_LABELS = {
    "b03.operating_cash_flow": "Lưu chuyển tiền thuần từ hoạt động kinh doanh",
    "b03.investing_cash_flow": "Lưu chuyển tiền thuần từ hoạt động đầu tư",
    "b03.financing_cash_flow": "Lưu chuyển tiền thuần từ hoạt động tài chính",
    "b03.net_cash_flow": "Lưu chuyển tiền thuần trong kỳ",
    "b03.opening_cash": "Tiền và tương đương tiền đầu kỳ",
    "b03.closing_cash": "Tiền và tương đương tiền cuối kỳ",
    "b02.profit_before_tax": "Lợi nhuận kế toán trước thuế",
    "b02.profit_after_tax": "Lợi nhuận sau thuế",
}
FLOW_ACTIVITIES = {
    "b03.operating_cash_flow": "từ hoạt động kinh doanh",
    "b03.investing_cash_flow": "từ hoạt động đầu tư",
    "b03.financing_cash_flow": "từ hoạt động tài chính",
    "b03.net_cash_flow": "trong kỳ",
}
SIGN_TEMPLATE = (
    "{label} trong kỳ {period} là {value} {unit}, mang giá trị {sign}, "
    "phản ánh dòng tiền {direction} thuần {activity} theo chỉ tiêu được báo cáo."
)
ZERO_TEMPLATE = (
    "{label} trong kỳ {period} là {value} {unit}, phản ánh giá trị dòng tiền thuần "
    "bằng không theo chỉ tiêu được báo cáo."
)
LIMITATIONS = [
    "Đối chiếu lợi nhuận và dòng tiền là tín hiệu trong kỳ, chưa phải đánh giá toàn diện chất lượng lợi nhuận.",
    "Phép tính ad hoc phải nêu định nghĩa và không tự trở thành chỉ tiêu kế toán chuẩn.",
    "Chưa đủ dữ liệu để xác nhận các điều chỉnh dòng tiền hoặc nguyên nhân chênh lệch.",
    "Báo cáo kết quả kinh doanh và lưu chuyển tiền tệ có nguồn riêng; phạm vi báo cáo vẫn chưa được xác nhận.",
]
UNAPPROVED = (
    r"\b(?:cfo (?:net income|tren loi nhuan(?: sau thue)?)|cash conversion ratio|"
    r"accrual ratio|free cash flow|fcf|cfo margin|cash flow coverage|earnings quality score|"
    r"ty (?:le|so) (?:cfo|dong tien(?: hoat dong)? kinh doanh) (?:tren )?loi nhuan|"
    r"dong tien tu do|ty le don tich|diem chat luong loi nhuan)\b"
)
INDEPENDENT_FACT = (
    r"\b(?:cfo|dong tien|luu chuyen tien|loi nhuan truoc thue|loi nhuan sau thue|"
    r"tien va tuong duong tien)\b"
)


class CashFlowEarningsQualityProposal(FinancialModel):
    evidence_id: str
    kind: Literal["fact", "supported_interpretation"]
    meaning: Literal["fact_value", "cash_flow_sign"]
    period: str
    sign: Literal["positive", "negative", "zero"] | None = None
    statement: str | None = Field(default=None, max_length=700)


def _render(proposal: CashFlowEarningsQualityProposal, evidence: SpecialistEvidence):
    if proposal.period != evidence.period:
        raise ValueError("wrong_period")
    scale = f" (hệ số đơn vị {evidence.scale})" if evidence.scale != "1" else ""
    value = _number(evidence.value)
    if proposal.kind == "fact" and proposal.meaning == "fact_value" and proposal.sign is None:
        # Opening/closing cash are B03 balances within the reported fiscal year;
        # their canonical fiscal_year context is never rewritten to as_of.
        text = f"{evidence.label} của kỳ {evidence.period} là {value} {evidence.unit}{scale}."
        if proposal.statement not in (None, text):
            raise ValueError("fact_text_mismatch")
        return text
    if (
        proposal.kind != "supported_interpretation"
        or proposal.meaning != "cash_flow_sign"
        or evidence.canonical_item_id not in FLOW_ACTIVITIES
    ):
        raise ValueError("flow_balance_or_kind_mismatch")
    number = Decimal(evidence.value)
    sign = "positive" if number > 0 else "negative" if number < 0 else "zero"
    if proposal.sign != sign:
        raise ValueError("wrong_cash_flow_sign")
    replacements = dict(
        label=evidence.label,
        period=evidence.period,
        value=value,
        unit=evidence.unit + scale,
        sign="dương" if sign == "positive" else "âm",
        direction="vào" if sign == "positive" else "ra",
        activity=FLOW_ACTIVITIES[evidence.canonical_item_id],
    )
    template = ZERO_TEMPLATE if sign == "zero" else SIGN_TEMPLATE
    text = unicodedata.normalize("NFC", proposal.statement or "")
    # Accept mixed placeholders/literals only when the entire proposition matches
    # the approved semantics. Never strip numeric signs or allow extra clauses.
    for key, replacement in replacements.items():
        text = text.replace("{" + key + "}", replacement)
    expected = template.format(**replacements)
    if text != expected:
        raise ValueError("unsupported_or_numeric_prose")
    return text


class CashFlowEarningsQualitySpecialist:
    boundary = next(b for b in SPECIALIST_BOUNDARIES if b.role == "cash_flow_and_earnings_quality")

    def __init__(
        self, gateway: SharedLLMGateway, *, model: ModelIdentity | None = None, deterministic=False
    ):
        self._deterministic = deterministic
        self._gateway = gateway
        self._model = model or ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)

    def _select(self, upstream, result, years, scopes, periods):
        assigned = upstream.evidence_bundle.claim_fact_references is not None
        select_evidence(
            upstream, result, item_labels=ITEM_LABELS, metric_labels={}, period_roles={}
        )
        plan = upstream.final_plan_state
        requested_scope = scopes[0] if scopes else plan.query.reporting_scope if plan else None
        matches = {f.reference.observation: f for f in upstream.evidence_bundle.facts}
        kept = []
        for evidence in result.supporting_evidence:
            match = matches[evidence.reference.observation]
            context = match.record.context
            selectors = plan.query.selectors if plan else []
            error = None
            if (
                context.statement_type != evidence.canonical_item_id[:3].upper()
                or context.period_type != "fiscal_year"
                or context.mapped_item_code != evidence.canonical_item_id
            ):
                error = "cash_flow_or_profit_statement_period_mismatch"
            # Canonical monetary item_unit() preserves currency as unit and
            # scale separately; do not reinterpret a mismatched unit or rescale.
            elif (
                not context.currency
                or match.record.value.unit != context.currency
                or context.scale <= 0
            ):
                error = "currency_unit_or_scale_mismatch"
            elif (
                (not assigned and years and evidence.period not in {str(y) for y in years})
                or periods  # A calendar date is not a B03 fiscal_year fact.
                or (
                    plan
                    and plan.query.reporting_periods
                    and evidence.period not in plan.query.reporting_periods
                )
                or (
                    selectors
                    and not any(
                        s.document_id in (None, evidence.document_id)
                        and s.snapshot_id in (None, evidence.snapshot_id)
                        and s.company_id in (None, evidence.company_id)
                        and s.period in (None, evidence.period)
                        for s in selectors
                    )
                )
            ):
                error = "question_or_selector_context_mismatch"
            elif requested_scope and (
                match.reporting_scope.status != "resolved"
                or match.reporting_scope.reporting_scope != requested_scope
                or context.reporting_scope not in (None, requested_scope)
            ):
                error = "reporting_scope_unresolved_or_mismatched"
            if error:
                result.missing_evidence.append(error)
                result.trace.append(
                    SpecialistTrace(
                        stage="selection",
                        outcome="excluded",
                        evidence_id=evidence.evidence_id,
                        reasons=[error],
                    )
                )
            else:
                # _fact_error owns source-review lookup eligibility. A found
                # lookup may explicitly report unverified row review (accepted
                # BBS B03 baseline); retain that limit, never upgrade it.
                evidence.caveats = sorted(
                    set(
                        evidence.caveats
                        + [
                            "source_review_status:" + view.status
                            for view in match.source_review.matches
                        ]
                    )
                )
                kept.append(evidence)
        # Do not choose a preferred filing/snapshot or pair incompatible statements.
        contexts = {
            (
                e.company_id,
                e.document_id,
                e.snapshot_id,
                e.period,
                e.unit,
                e.scale,
                matches[e.reference.observation].record.context.currency,
                matches[e.reference.observation].record.context.reporting_scope,
                matches[e.reference.observation].reporting_scope.reporting_scope,
            )
            for e in kept
        }
        if len(contexts) > 1:
            kept.clear()
            result.missing_evidence.append("incompatible_cash_flow_profit_context_or_snapshot")
        result.supporting_evidence = kept
        if plan:
            available = {e.canonical_item_id for e in kept}
            result.missing_evidence.extend(
                "missing_fact:" + item
                for item in plan.query.required_indicators
                if item in ITEM_LABELS and item not in available
            )

    def _prompt(self, result, upstream):
        contexts = {
            f.reference.observation: f.record.context for f in upstream.evidence_bundle.facts
        }
        return dict(
            prompt_version=PROMPT_VERSION,
            instruction=(
                "Bạn là Cash Flow and Earnings Quality Specialist. Chọn bằng chứng liên quan "
                "câu hỏi; xuất JSON {claims: [...], missing_information: [string]}. "
                "Mỗi chỉ tiêu được hỏi có nguồn phải có một claim fact/fact_value, sign=null, "
                "statement=null; backend render exact value/unit/scale. CFO và lợi nhuận B02 "
                "phải là hai factual claims riêng, mỗi claim dùng evidence_id của chính nó. "
                "CHỈ khi câu hỏi yêu cầu diễn giải dấu hoặc ý nghĩa dòng tiền, tạo thêm supported_interpretation/"
                "cash_flow_sign, sign=positive/negative/zero theo exact value. "
                "statement phải COPY NGUYÊN VĂN sign_template hoặc zero_template dưới đây, "
                "bao gồm tất cả dấu ngoặc nhọn và placeholders. KHÔNG điền bất kỳ placeholder "
                "nào: không điền raw number vào {value}, không điền enum positive/negative vào "
                "{sign}, không tự rút gọn {activity}. Backend sẽ điền số format tiếng Việt, "
                "{sign} thành dương/âm, {direction} thành vào/ra và {activity} thành đúng "
                "'từ hoạt động kinh doanh/đầu tư/tài chính'. Trường sign là enum metadata, "
                "khác placeholder {sign} trong câu. Không thêm mệnh đề. Chỉ flow được diễn giải "
                "vào/ra thuần; opening_cash/closing_cash là balances B03, profit là B02. "
                "period giữ nguyên chuỗi trong evidence; không đổi fiscal_year sang as_of. "
                "Trong schema claims cũ không tính CFO/Net Income, cash conversion, accrual, FCF, CFO margin, coverage, "
                "earnings quality score hoặc chênh lệch. Không kết luận chất lượng lợi nhuận "
                "cao/thấp, thao túng, mất khả năng trả nợ, dòng tiền bền vững, dự báo hoặc nguyên "
                "nhân do phải thu/tồn kho/khấu hao. Không khẳng định closing=opening+net cash flow "
                "vì chưa đủ đối chiếu điều chỉnh/tỷ giá. Với câu hỏi vượt evidence, ghi rõ giới "
                "hạn vào missing_information và vẫn trình bày facts độc lập có nguồn nếu phù hợp. "
                "Không sinh financial values/citations mới hoặc xác minh claims; D03-B10 blocked."
            ),
            sign_template=SIGN_TEMPLATE,
            zero_template=ZERO_TEMPLATE,
            sign_proposal_example=dict(
                evidence_id="<ID từ evidence>",
                kind="supported_interpretation",
                meaning="cash_flow_sign",
                period="<period từ evidence>",
                sign="positive",
                statement=SIGN_TEMPLATE,
            ),
            schema=CashFlowEarningsQualityProposal.model_json_schema(),
            boundary=self.boundary.model_dump(),
            evidence=[
                dict(
                    **e.model_dump(exclude={"citations", "calculation", "reference"}),
                    period_type="fiscal_year",
                    currency=contexts[e.reference.observation].currency,
                    reporting_scope=contexts[e.reference.observation].reporting_scope,
                    semantic_type="flow"
                    if e.canonical_item_id in FLOW_ACTIVITIES
                    else "cash_balance"
                    if e.canonical_item_id.startswith("b03.")
                    else "profit",
                )
                for e in result.supporting_evidence
            ],
            upstream_status=result.upstream_status,
            risks=[r.model_dump(mode="json") for r in result.risks],
            missing_evidence=result.missing_evidence,
            limitations=result.limitations,
        )

    def analyze(self, *, question: str, supervisor_result: SupervisorResult) -> SpecialistResult:
        start = perf_counter()
        result = SpecialistResult(
            version="cash_flow_earnings_quality_specialist_v1",
            role="cash_flow_and_earnings_quality",
            question=question,
            upstream_status=supervisor_result.status,
            risks=supervisor_result.risk_signals,
            limitations=list(supervisor_result.evidence_bundle.limitations) + LIMITATIONS,
            missing_evidence=list(supervisor_result.evidence_bundle.missing_requirement_ids),
        )
        try:
            upstream = SupervisorResult.model_validate_json(supervisor_result.model_dump_json())
            plan = upstream.final_plan_state
            if upstream.status in {"blocked", "failed"}:
                result.missing_evidence.append("upstream_" + upstream.status)
                return result
            if (plan and plan.query.cross_document_comparison) or any(
                r.blocking
                and r.code in {"ambiguous_snapshot", "cross_document_compatibility_unresolved"}
                for r in result.risks
            ):
                result.missing_evidence.append("snapshot_or_D03-B10_blocked")
                return result
            years, scopes, _, periods = _explicit_constraints(question)
            reasoning_assignment = (
                upstream.evidence_bundle.claim_fact_references is not None
                and any(
                    note.startswith("PLANNER_TASK:")
                    for note in upstream.evidence_bundle.limitations
                )
            )
            if len(scopes) > 1:
                result.missing_evidence.append("ambiguous_reporting_scope")
                return result
            if len(years) > 1 and not reasoning_assignment:
                result.missing_evidence.append("cross_document_comparison_blocked_D03_B10")
                return result
            if re.search(r"\b(?:quy|thang|ban nien)\b", normalize(question)):
                result.missing_evidence.append("non_annual_period_unsupported")
                return result
            text = normalize(question)
            unsupported = [] if reasoning_assignment else re.findall(UNAPPROVED, text)
            result.missing_evidence.extend("unsupported_capability:" + name for name in unsupported)
            if not reasoning_assignment and re.search(
                r"chat luong loi nhuan|thao tung|ben vung|nguyen nhan|cash bridge", text
            ):
                result.missing_evidence.append("earnings_quality_or_reconciliation_not_established")
            if not unsupported or re.search(INDEPENDENT_FACT, re.sub(UNAPPROVED, "", text)):
                self._select(upstream, result, years, scopes, periods)
            if not result.supporting_evidence:
                result.missing_evidence.append("no_usable_cash_flow_profit_evidence")
                return result
            generate_candidates(
                gateway=self._gateway,
                deterministic=self._deterministic,
                model=self._model,
                result=result,
                prompt=with_assignment(self._prompt(result, upstream), upstream),
                proposal_type=CashFlowEarningsQualityProposal,
                render=_render,
                prefix="cash-flow-earnings-quality",
            )
        except (ValueError, ValidationError):
            result.status = "failed"
            result.trace.append(
                SpecialistTrace(
                    stage="generation", outcome="failed", reasons=["invalid_proposal_schema"]
                )
            )
        finally:
            result.missing_evidence = sorted(set(result.missing_evidence))
            result.latency_ms = (perf_counter() - start) * 1000
        return result
