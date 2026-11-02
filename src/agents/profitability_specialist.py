"""M5 candidate generation; bounded arithmetic prose, never M6 claim verification."""

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
from .specialist_common import (
    ClaimKind,
    SpecialistResult,
    SpecialistTrace,
    _number,
    generate_candidates,
    select_evidence,
)

# Legacy public names remain available after moving wire contracts to common.
from .specialist_common import SpecialistCandidate as ProfitabilityCandidate
from .specialist_common import SpecialistEvidence as ProfitabilityEvidence
from .supervisor import SupervisorResult

__all__ = [
    "ProfitabilityCandidate",
    "ProfitabilityEvidence",
    "ProfitabilitySpecialist",
    "SpecialistResult",
    "SpecialistTrace",
]

ITEM_LABELS = {
    "b02.net_revenue": "Doanh thu thuần",
    "b02.cost_of_sales": "Giá vốn hàng bán",
    "b02.gross_profit": "Lợi nhuận gộp",
    "b02.profit_before_tax": "Lợi nhuận trước thuế",
    "b02.profit_after_tax": "Lợi nhuận sau thuế",
}
METRIC_LABELS = {"gross_margin": "Biên lợi nhuận gộp", "revenue_yoy": "Tăng trưởng doanh thu"}
Meaning = Literal["fact_value", "metric_value", "gross_profit_per_100_revenue", "revenue_change"]


class ProfitabilityProposal(FinancialModel):
    evidence_id: str
    kind: ClaimKind
    meaning: Meaning
    period: str
    # Facts/metrics may request exact backend rendering. Interpretations require prose.
    statement: str | None = Field(default=None, max_length=700)


# Full-match semantic grammar, NOT a blacklist: no extra clauses, invented causes,
# industry judgments, periods, numbers or citations can survive. Gemini chooses the
# proposition and writes Vietnamese within these bounded arithmetic paraphrases.
GROSS_PROSE = (
    r"(?:trong ky \{period\},? )?"
    r"(?:cu|voi moi|tren moi) 100 dong doanh thu thuan "
    r"(?:tuong ung|tao ra|doanh nghiep thu duoc)(?: khoang)? "
    r"\{value\} dong loi nhuan gop[.]?"
)
YOY_PROSE = (
    r"(?:trong cung (?:mot )?bao cao,? )?doanh thu thuan "
    r"(?:ky|nam) \{period\} \{direction\} \{value\}% "
    r"so voi (?:ky|nam) \{prior_period\}[.]?"
)


def _render(proposal, evidence):
    if proposal.period != evidence.period:
        raise ValueError("wrong_period")
    value = _number(evidence.value)
    if proposal.meaning == "fact_value" and proposal.kind == evidence.kind == "fact":
        text = f"{evidence.label} kỳ {evidence.period} là {value} {evidence.unit}"
        if evidence.scale != "1":
            text += f" (hệ số đơn vị {evidence.scale})"
        text += "."
    elif (
        proposal.meaning == "metric_value"
        and proposal.kind == "approved_metric"
        and evidence.calculation
    ):
        text = f"{evidence.label} kỳ {evidence.period} đạt {value}%."
    elif proposal.kind == "supported_interpretation" and evidence.calculation:
        calc = evidence.calculation
        statement = unicodedata.normalize("NFC", proposal.statement or "")
        if proposal.meaning == "gross_profit_per_100_revenue" and calc.formula_id == "gross_margin":
            pattern = GROSS_PROSE
        elif proposal.meaning == "revenue_change" and calc.formula_id == "revenue_yoy":
            pattern = YOY_PROSE
        else:
            raise ValueError("unsupported_interpretation")
        replacements = {"period": evidence.period, "value": value}
        if proposal.meaning == "revenue_change":
            replacements.update(
                value=_number(abs(Decimal(evidence.value))),
                direction="tăng"
                if Decimal(evidence.value) > 0
                else "giảm"
                if Decimal(evidence.value) < 0
                else "không đổi ở mức",
                prior_period=evidence.operand_periods["prior_revenue"],
            )
        # Both placeholders and exact accepted numbers are safe. A literal value
        # mismatch cannot match the grammar and is never repaired by guessing.
        for key, replacement in replacements.items():
            options = ["{" + key + "}", replacement]
            if key == "value":
                options.append(
                    str(abs(Decimal(evidence.value)))
                    if proposal.meaning == "revenue_change"
                    else evidence.value
                )
            alternatives = "|".join(
                re.escape(normalize(v) if key == "direction" and v == replacement else v)
                for v in options
            )
            pattern = pattern.replace(re.escape("{" + key + "}"), f"(?P<{key}>{alternatives})")
        folded = unicodedata.normalize("NFD", statement.casefold().replace("đ", "d"))
        folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
        matched = re.fullmatch(pattern, folded)
        if not matched:
            raise ValueError("unsupported_or_numeric_prose")
        text = statement
        for key in sorted(replacements, key=lambda k: matched.start(k), reverse=True):
            start, end = matched.span(key)
            if start >= 0:
                text = text[:start] + replacements[key] + text[end:]
        return text
    else:
        raise ValueError("kind_or_meaning_mismatch")
    if proposal.statement not in (None, text):
        # A structured fact/metric lets the backend render exact values; never fix
        # a conflicting Gemini numeric statement by guessing its intended number.
        raise ValueError("fact_or_metric_text_mismatch")
    return text


class ProfitabilitySpecialist:
    boundary = next(b for b in SPECIALIST_BOUNDARIES if b.role == "profitability")

    def __init__(self, gateway: SharedLLMGateway, *, model: ModelIdentity | None = None):
        self._gateway = gateway
        self._model = model or ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)

    def _select(self, upstream, result):
        select_evidence(
            upstream,
            result,
            item_labels=ITEM_LABELS,
            metric_labels=METRIC_LABELS,
            period_roles={"gross_margin": "revenue", "revenue_yoy": "current_revenue"},
        )

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
                        dict(role=o.role, value=o.value, unit=o.unit, period=o.context.period)
                        for o in calc.trace.operands
                    ],
                )
            digest.append(item)
        return {
            "instruction": (
                "Bạn là Profitability Specialist. Phân tích câu hỏi và chỉ chọn evidence liên quan. "
                "Xuất JSON {claims: [...], missing_information: [string]}. Mỗi claim theo schema. "
                "fact/fact_value và approved_metric/metric_value: statement=null để backend render "
                "số chính xác. Không viết citations hoặc IDs ngoài evidence_id input. "
                "Nếu metric phù hợp, PHẢI thêm supported_interpretation ngoài metric_value. "
                "Diễn giải bằng tiếng Việt trong NGỮ PHÁP SỐ HỌC GIỚI HẠN sau, ưu tiên giữ literal "
                "{period}, {value}, {direction}, {prior_period}; backend thay từ evidence. "
                "gross_profit_per_100_revenue: [Trong kỳ {period}, ] + (cứ|với mỗi|trên mỗi) "
                "100 đồng doanh thu thuần + (tương ứng|tạo ra|doanh nghiệp thu được) + [khoảng ] "
                "+ {value} đồng lợi nhuận gộp. revenue_change: [Trong cùng báo cáo, ] "
                "+ Doanh thu thuần kỳ {period} {direction} {value}% so với kỳ {prior_period}. "
                "Các dấu [] biểu thị thành phần tùy chọn, không in dấu ngoặc. "
                "Chọn cách diễn đạt phù hợp, viết thành câu hoàn chỉnh. Không thêm mệnh đề khác. "
                "Ví dụ câu HOÀN CHỈNH hợp lệ: 'Trong kỳ {period}, với mỗi 100 đồng doanh thu "
                "thuần tương ứng khoảng {value} đồng lợi nhuận gộp.' Chỉ chọn MỘT động từ, "
                "không ghép 'tạo ra doanh nghiệp thu được'. Có thể dùng số thực từ evidence "
                "nhưng phải khớp chính xác. Với câu hỏi nhiều chỉ tiêu, MỖI chỉ tiêu có "
                "evidence phải có fact candidate. Nhánh doanh thu thiếu/conflicted KHÔNG chặn "
                "các facts giá vốn và lợi nhuận gộp độc lập đang có trong digest. "
                "Không nhận xét cao/thấp/tốt/xấu, so ngành, nguyên nhân, hoặc ROE/ROA/NPM "
                "chưa approved. Không tính mới, không comparison liên tài liệu D03-B10. "
                "Thiếu dữ liệu ghi missing_information; không biến thành financial claim. "
                "Không tự xác minh hoặc phê duyệt claims."
            ),
            "schema": ProfitabilityProposal.model_json_schema(),
            "boundary": self.boundary.model_dump(),
            "evidence": digest,
            "upstream_status": result.upstream_status,
            "missing_evidence": result.missing_evidence,
            "limitations": result.limitations,
        }

    def analyze(self, *, question: str, supervisor_result: SupervisorResult) -> SpecialistResult:
        start = perf_counter()
        upstream = SupervisorResult.model_validate_json(supervisor_result.model_dump_json())
        result = SpecialistResult(
            question=question,
            upstream_status=upstream.status,
            risks=upstream.risk_signals,
            limitations=list(upstream.evidence_bundle.limitations),
            missing_evidence=list(upstream.evidence_bundle.missing_requirement_ids),
        )
        try:
            plan = upstream.final_plan_state
            if upstream.status in {"blocked", "failed"}:
                result.missing_evidence.append("upstream_" + upstream.status)
                return result
            if (plan and plan.query.cross_document_comparison) or any(
                r.code == "cross_document_compatibility_unresolved" and r.blocking
                for r in result.risks
            ):
                result.missing_evidence.append("D03-B10_cross_document_blocked")
                return result
            question_text = normalize(question)
            unsupported = re.findall(
                r"\b(?:roe|roa|net profit margin|operating margin|bien loi nhuan rong|bien loi nhuan hoat dong)\b",
                question_text,
            )
            result.missing_evidence.extend("unsupported_capability:" + name for name in unsupported)
            independent = re.search(
                r"doanh thu thuan|gia von|loi nhuan gop|loi nhuan truoc thue|loi nhuan sau thue|gross margin|revenue yoy|tang truong doanh thu",
                question_text,
            )
            if not unsupported or independent:
                self._select(upstream, result)
            if not result.supporting_evidence:
                result.missing_evidence.append("no_usable_profitability_evidence")
            generate_candidates(
                gateway=self._gateway,
                model=self._model,
                result=result,
                prompt=self._prompt(result),
                proposal_type=ProfitabilityProposal,
                render=_render,
                prefix="profitability",
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
