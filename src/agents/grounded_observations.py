"""Bounded observational candidates; M6 retains all verification authority.

No thresholds, causes, forecasts or corpus-absence assertions. Unknown questions,
ambiguous periods and missing inputs stay with the existing specialist generator.
"""

from decimal import Decimal

from ..tools.question_understanding import normalize
from .specialist_common import AnalysisProposal


def observation_proposal(requirements, evidence, question):
    if not requirements or any(r.answer_goal == "value" for r in requirements):
        return None
    text = normalize(question)
    if any(term in text for term in ("nguyen nhan", "vi sao", "tai sao", "kiem toan")):
        return None
    facts = {}
    for source in evidence:
        if source.kind == "fact":
            facts.setdefault(source.canonical_item_id, []).append(source)

    def single(item):
        matches = facts.get(item, [])
        return matches[0] if len(matches) == 1 else None

    def value(source):
        return Decimal(source.value) * Decimal(source.scale)

    cfo = single("b03.operating_cash_flow")
    if not cfo or len(cfo.period) != 4:
        return None
    sign = "dương" if value(cfo) > 0 else "âm" if value(cfo) < 0 else "bằng không"
    cash = f"Dòng tiền kinh doanh cả năm {cfo.period} {sign}."
    if "thanh khoan" in text:
        assets = single("b01.current_assets")
        debt = single("b01.short_term_liabilities")
        limitation = (
            "Hai chỉ tiêu từ số dư cuối kỳ phản ánh thanh khoản tại ngày đó, còn dòng tiền "
            "phản ánh cả kỳ; dòng tiền kinh doanh không tự bảo đảm khả năng thanh toán tương lai."
        )
        prefix = "Tài sản ngắn hạn"
        debt_label = "nợ ngắn hạn"
        selected = [assets, debt, cfo]
    elif "suc khoe tai chinh" in text:
        assets = single("b01.total_assets")
        debt = single("b01.total_liabilities")
        revenues = sorted(facts.get("b02.net_revenue", []), key=lambda s: s.period)
        if len(revenues) != 2 or revenues[-1].period != cfo.period:
            return None
        prior, current = revenues
        if len(prior.period) != 4 or prior.period == current.period:
            return None
        direction = (
            "tăng"
            if value(current) > value(prior)
            else "giảm"
            if value(current) < value(prior)
            else "không đổi"
        )
        cash = (
            f"Doanh thu thuần năm {current.period} {direction} so với năm {prior.period}. " + cash
        )
        limitation = (
            "Tăng trưởng doanh thu, cơ cấu nợ tại cuối năm và dòng tiền cả năm phản ánh "
            "các khía cạnh khác nhau; không thể dùng riêng một chỉ tiêu để kết luận toàn bộ "
            "sức khỏe tài chính hoặc suy ra xu hướng dài hạn."
        )
        # Order the liability first so the relation reads naturally.
        assets, debt = debt, assets
        prefix, debt_label = "Tổng nợ phải trả", "tổng tài sản"
        selected = [*revenues, assets, debt, cfo]
    else:
        return None
    if any(s is None for s in selected):
        return None
    if assets.period != debt.period or assets.period != cfo.period + "-12-31":
        return None
    if len({(s.company_id, s.document_id, s.snapshot_id, s.unit) for s in selected}) != 1:
        return None
    required = {item for r in requirements for item in r.required_indicators}
    if not required <= {s.canonical_item_id for s in selected}:
        return None
    relation = (
        "nhỏ hơn"
        if value(assets) < value(debt)
        else "lớn hơn"
        if value(assets) > value(debt)
        else "bằng"
    )
    return AnalysisProposal(
        statement=f"{prefix} {relation} {debt_label} tại ngày {assets.period}. {cash} {limitation}",
        evidence_ids=[s.evidence_id for s in selected],
        goal=requirements[-1].text,
        claim_type="reasoned_conclusion",
    )
