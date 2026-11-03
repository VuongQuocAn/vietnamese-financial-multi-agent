"""B01 facts and approved Debt-to-Assets arithmetic candidates; never M6 verification."""

import re
import unicodedata
from time import perf_counter
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import ModelIdentity
from ..core.llm_gateway import SharedLLMGateway
from ..tools.question_understanding import normalize, understand
from .contracts import SPECIALIST_BOUNDARIES
from .query_planner import _explicit_constraints
from .specialist_common import (
    ClaimKind,
    SpecialistResult,
    SpecialistTrace,
    _number,
    generate_candidates,
    select_evidence,
    with_assignment,
)
from .supervisor import SupervisorResult

PROMPT_VERSION = "liquidity_leverage_v1"
ITEM_LABELS = {
    "b01.total_assets": "Tổng tài sản",
    "b01.total_liabilities": "Tổng nợ phải trả",
    "b01.total_equity": "Vốn chủ sở hữu",
    "b01.short_term_receivables": "Các khoản phải thu ngắn hạn",
}
METRIC_LABELS = {"debt_to_assets": "Tỷ lệ nợ phải trả trên tổng tài sản"}
UNSUPPORTED = (
    r"\b(?:current ratio|quick ratio|cash ratio|debt to equity|interest coverage|"
    r"working capital|ty (?:le|so) thanh toan (?:hien hanh|nhanh|tien mat)|"
    r"he so thanh toan (?:hien hanh|nhanh|tien mat)|von luu dong|"
    r"no (?:phai tra )?tren von chu so huu|kha nang thanh toan lai vay)\b"
)
INDEPENDENT = r"tong tai san|tong no phai tra|von chu so huu|phai thu ngan han|debt to assets|no phai tra tren tong tai san"


class LiquidityLeverageProposal(FinancialModel):
    evidence_id: str
    kind: ClaimKind
    meaning: Literal["fact_value", "metric_value", "liabilities_per_100_assets"]
    period: str
    statement: str | None = Field(default=None, max_length=700)


def _render(proposal, evidence):
    if proposal.period != evidence.period:
        raise ValueError("wrong_period")
    value = _number(evidence.value)
    if proposal.kind == evidence.kind == "fact" and proposal.meaning == "fact_value":
        text = f"{evidence.label} tại ngày {evidence.period} là {value} {evidence.unit}"
        if evidence.scale != "1":
            text += f" (hệ số đơn vị {evidence.scale})"
        text += "."
    elif (
        proposal.kind == "approved_metric"
        and proposal.meaning == "metric_value"
        and evidence.calculation
    ):
        text = f"{evidence.label} tại ngày {evidence.period} là {value}%."
    elif (
        proposal.kind == "supported_interpretation"
        and proposal.meaning == "liabilities_per_100_assets"
        and evidence.calculation
        and evidence.calculation.formula_id == "debt_to_assets"
    ):
        # Full sentence arithmetic semantics: total liabilities, NOT interest-bearing
        # borrowing, liquidity/solvency judgments, causes or an unapproved ratio.
        patterns = [
            r"(?:tai thoi diem bao cao(?: ngay \{period\})?,? )?"
            r"(?:cu|voi moi|tren moi) 100 dong tong tai san "
            r"(?:tai thoi diem bao cao )?tuong ung(?: khoang)? \{value\} dong no phai tra"
            r"(?: tai thoi diem bao cao)?[.]?",
            r"no phai tra tuong ung(?: khoang)? \{value\} dong "
            r"tren (?:moi )?100 dong tong tai san tai thoi diem bao cao[.]?",
        ]
        statement = unicodedata.normalize("NFC", proposal.statement or "")
        folded = unicodedata.normalize("NFD", statement.casefold().replace("đ", "d"))
        folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
        for pattern in patterns:
            replacements = {"value": value, "period": evidence.period}
            for key, replacement in replacements.items():
                options = ["{" + key + "}", replacement]
                if key == "value":
                    options.append(evidence.value)
                pattern = pattern.replace(
                    re.escape("{" + key + "}"),
                    f"(?P<{key}>" + "|".join(re.escape(v) for v in options) + ")",
                )
            matched = re.fullmatch(pattern, folded)
            if matched:
                text = statement
                for key in sorted(
                    matched.groupdict(), key=lambda k: matched.start(k), reverse=True
                ):
                    start, end = matched.span(key)
                    if start >= 0:
                        text = text[:start] + replacements[key] + text[end:]
                return text
        raise ValueError("unsupported_or_numeric_prose")
    else:
        raise ValueError("kind_or_meaning_mismatch")
    if proposal.statement not in (None, text):
        raise ValueError("fact_or_metric_text_mismatch")
    return text


def _debt_semantics_error(calc, bundle):
    """Check accepted policy/operand meaning without calculating a new metric."""
    if not calc.trace or not calc.evidence:
        return "metric_trace_or_lineage_incomplete"
    trace, match = calc.trace, calc.evidence
    expected = {"liabilities": "b01.total_liabilities", "assets": "b01.total_assets"}
    if {o.role for o in trace.operands} != set(expected):
        return "debt_operand_roles_mismatch"
    facts = {f.reference.observation: f.record for f in bundle.facts}
    for operand in trace.operands:
        fact = facts.get(operand.observation)
        if not fact or fact.canonical_item_id != expected[operand.role]:
            return "debt_operand_semantics_mismatch"
        if fact.context.statement_type != "B01" or fact.context.period_type != "as_of":
            return "debt_operand_period_type_mismatch"
    if (
        len({o.context.period for o in trace.operands}) != 1
        or len({(o.unit, o.context.currency, str(o.context.scale)) for o in trace.operands}) != 1
        or trace.formula.expression != "liabilities / assets"
        or trace.formula.denominator_role != "assets"
        or trace.formula.period_relation != "same"
        or {o.role: o.canonical_item_id for o in trace.formula.operands} != expected
        or calc.request.metric_id != calc.metric_id
        or calc.request.document_id not in (None, calc.document_id)
        or calc.request.snapshot_id not in (None, calc.snapshot_id)
        or match.selected_snapshot.document_id != calc.document_id
        or match.selected_snapshot.snapshot_id != calc.snapshot_id
    ):
        return "debt_policy_or_context_mismatch"
    policy = (match.closure.readiness or {}).get("formula_policy", {})
    if (
        policy.get("execution_approved") is not True
        or policy.get("definition_sha256") != calc.formula_digest
        or policy.get("approval_reference") != trace.approval.decision_reference
    ):
        return "debt_formula_not_approved"
    return None


class LiquidityLeverageSpecialist:
    boundary = next(b for b in SPECIALIST_BOUNDARIES if b.role == "liquidity_and_leverage")

    def __init__(self, gateway: SharedLLMGateway, *, model: ModelIdentity | None = None):
        self._gateway = gateway
        self._model = model or ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)

    def _select(self, upstream, result):
        # Filter invalid policies before shared period extraction; original inputs
        # were copied by analyze. Conflicting fact variants remain for shared gates.
        calculations = []
        for calc in upstream.evidence_bundle.calculations:
            if calc.formula_id != "debt_to_assets":
                continue
            error = _debt_semantics_error(calc, upstream.evidence_bundle)
            if error:
                result.missing_evidence.append(error)
                result.trace.append(
                    SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
                )
            else:
                calculations.append(calc)
        upstream.evidence_bundle.calculations = calculations
        select_evidence(
            upstream,
            result,
            item_labels=ITEM_LABELS,
            metric_labels=METRIC_LABELS,
            period_roles={"debt_to_assets": "assets"},
            balance_sheet=True,
        )
        # A completed upstream result never resolves conflicting snapshot choices.
        snapshots = {}
        for evidence in result.supporting_evidence:
            snapshots.setdefault(evidence.document_id, set()).add(evidence.snapshot_id)
        if any(len(v) > 1 for v in snapshots.values()):
            result.supporting_evidence.clear()
            result.missing_evidence.append("ambiguous_snapshot")

    def _prompt(self, result):
        digest = []
        for evidence in result.supporting_evidence:
            item = evidence.model_dump(exclude={"citations", "calculation", "reference"})
            if evidence.calculation:
                calc = evidence.calculation
                item.update(
                    formula_id=calc.formula_id,
                    formula_version=calc.formula_version,
                    expression=calc.trace.formula.expression,
                    operands=[
                        dict(
                            role=o.role,
                            value=o.value,
                            unit=o.unit,
                            scale=str(o.context.scale),
                            period=o.context.period,
                        )
                        for o in calc.trace.operands
                    ],
                )
            digest.append(item)
        return dict(
            prompt_version=PROMPT_VERSION,
            instruction=(
                "Bạn là Liquidity and Leverage Specialist. Chọn evidence liên quan câu hỏi. "
                "Xuất JSON {claims: [...], missing_information: [string]}, mỗi claim theo schema. "
                "fact/fact_value hoặc approved_metric/metric_value: statement=null để backend "
                "render số chính xác. Mỗi chỉ tiêu được hỏi có evidence phải có một fact riêng. "
                "Với Debt-to-Assets: tạo approved_metric VÀ supported_interpretation, meaning="
                "liabilities_per_100_assets. Diễn giải tiếng Việt theo một trong hai câu mẫu: "
                "'Cứ 100 đồng tổng tài sản tại thời điểm báo cáo tương ứng khoảng {value} đồng nợ phải trả.' "
                "hoặc 'Nợ phải trả tương ứng khoảng {value} đồng trên mỗi 100 đồng tổng tài sản tại thời điểm báo cáo.' "
                "Có thể thay 'Cứ' bằng 'Với mỗi' hoặc 'Trên mỗi'; giữ {value} để backend điền. "
                "period phải đúng nguyên chuỗi ngày ISO trong evidence. Không thêm mệnh đề. "
                "Total liabilities là tổng nợ phải trả, không riêng nợ vay có lãi. Không kết luận "
                "cao/thấp/an toàn/mất khả năng thanh toán/phá sản/tốt/xấu, không nguyên nhân hoặc so ngành. "
                "Chỉ dùng debt_to_assets approved; không tự tính Current/Quick/Cash Ratio, Debt-to-Equity, "
                "Interest Coverage hoặc Working Capital. Thiếu/unsupported ghi missing_information; "
                "nhánh thiếu không chặn facts độc lập được hỏi. Không tạo citations hoặc financial values "
                "ngoài evidence, không comparison liên tài liệu D03-B10, không xác minh claims."
            ),
            schema=LiquidityLeverageProposal.model_json_schema(),
            boundary=self.boundary.model_dump(),
            evidence=digest,
            upstream_status=result.upstream_status,
            missing_evidence=result.missing_evidence,
            limitations=result.limitations,
        )

    def analyze(self, *, question: str, supervisor_result: SupervisorResult) -> SpecialistResult:
        start = perf_counter()
        result = SpecialistResult(
            version="liquidity_leverage_specialist_v1",
            role="liquidity_and_leverage",
            question=question,
            upstream_status=supervisor_result.status,
            risks=supervisor_result.risk_signals,
            limitations=list(supervisor_result.evidence_bundle.limitations)
            + [
                "Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi.",
                "Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán.",
            ],
            missing_evidence=list(supervisor_result.evidence_bundle.missing_requirement_ids),
        )
        try:
            upstream = SupervisorResult.model_validate_json(supervisor_result.model_dump_json())
            if upstream.status in {"blocked", "failed"}:
                result.missing_evidence.append("upstream_" + upstream.status)
                return result
            plan = upstream.final_plan_state
            if (plan and plan.query.cross_document_comparison) or any(
                r.blocking
                and r.code in {"ambiguous_snapshot", "cross_document_compatibility_unresolved"}
                for r in result.risks
            ):
                result.missing_evidence.append("snapshot_or_D03-B10_blocked")
                return result
            question_text = normalize(question)
            # Use M5-02's contextual scope rules. M4 understand() below is retained
            # for period/formula parsing only; its broad "rieng" rule is not a gate.
            _, explicit_scopes, _, _ = _explicit_constraints(question)
            if len(explicit_scopes) > 1:
                result.missing_evidence.append("ambiguous_reporting_scope")
                return result
            parsed, period_reasons = understand(question)
            if any(
                reason in period_reasons
                for reason in (
                    "invalid_period",
                    "multiple_periods_unsupported",
                    "cross_document_comparison_blocked_D03_B10",
                )
            ):
                result.missing_evidence.extend(period_reasons)
                return result
            unsupported = re.findall(UNSUPPORTED, question_text)
            result.missing_evidence.extend("unsupported_capability:" + name for name in unsupported)
            # Remove unsupported phrases before detecting an independently asked fact.
            independent = re.search(INDEPENDENT, re.sub(UNSUPPORTED, "", question_text))
            if not unsupported or independent:
                self._select(upstream, result)
            requested_scope = (
                explicit_scopes[0]
                if explicit_scopes
                else plan.query.reporting_scope
                if plan
                else None
            )
            kept = []
            for evidence in result.supporting_evidence:
                match = next(
                    (
                        f
                        for f in upstream.evidence_bundle.facts
                        if f.reference == evidence.reference
                    ),
                    None,
                )
                scope = (
                    match.reporting_scope
                    if match
                    else evidence.calculation.evidence.reporting_scope
                )
                selectors = plan.query.selectors if plan else []
                if (parsed.period and evidence.period != parsed.period) or (
                    selectors
                    and not any(
                        s.document_id in (None, evidence.document_id)
                        and s.snapshot_id in (None, evidence.snapshot_id)
                        for s in selectors
                    )
                ):
                    result.missing_evidence.append("question_or_selector_context_mismatch")
                elif match and (
                    match.record.context.statement_type != "B01"
                    or match.record.context.period_type != "as_of"
                ):
                    result.missing_evidence.append("balance_sheet_context_mismatch")
                elif requested_scope and (
                    scope.status != "resolved" or scope.reporting_scope != requested_scope
                ):
                    result.missing_evidence.append("reporting_scope_unresolved_or_mismatched")
                else:
                    kept.append(evidence)
            result.supporting_evidence = kept
            if (
                parsed.formula_id == "debt_to_assets"
                or "debt to assets" in question_text
                or (plan and "debt_to_assets" in plan.query.requested_formula_ids)
            ) and not any(e.kind == "metric" for e in kept):
                result.missing_evidence.append("missing_approved_debt_to_assets_evidence")
            if not kept:
                result.missing_evidence.append("no_usable_liquidity_leverage_evidence")
            generate_candidates(
                gateway=self._gateway,
                model=self._model,
                result=result,
                prompt=with_assignment(self._prompt(result), upstream),
                proposal_type=LiquidityLeverageProposal,
                render=_render,
                prefix="liquidity-leverage",
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
