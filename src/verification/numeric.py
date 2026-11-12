"""Small grammar for accepted M5 Vietnamese assertions, never a general NLP parser."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from ..accounting.item_mapping import ITEM_CATALOG
from ..agents.cash_flow_earnings_quality_specialist import ITEM_LABELS as FLOW_LABELS
from ..agents.liquidity_leverage_specialist import ITEM_LABELS as BALANCE_LABELS
from ..agents.liquidity_leverage_specialist import METRIC_LABELS as DEBT_LABELS
from ..agents.profitability_specialist import ITEM_LABELS, METRIC_LABELS


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d").replace("−", "-"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip()


# Keep punctuation/signs; unlike question normalization, numeric parsing needs them.
def _text(text: str) -> str:
    return re.sub(r"\s+", " ", fold(text))


NUMBER = r"[+-]?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[,.]\d+)?)"
PERIOD = r"\d{4}(?:-\d{2}-\d{2})?"


def parse_number(text: str) -> Decimal | None:
    text = text.strip().replace("−", "-")
    if not re.fullmatch(NUMBER, text):
        return None
    if "," in text:
        integer, fraction = text.split(",")
        if "." in integer and not re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", integer):
            return None
        return Decimal(integer.replace(".", "") + "." + fraction)
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", text):
        return Decimal(text.replace(".", ""))
    return Decimal(text) if text.count(".") <= 1 else None


@dataclass(frozen=True)
class NumericAssertion:
    target: str
    value: Decimal
    unit: str
    scale: Decimal
    period: str | None = None
    period_type: str | None = None
    prior_period: str | None = None


def extract_assertion(content: str) -> NumericAssertion | None:
    text = _text(content)
    # Source table labels may retain a row ordinal. It is not part of the
    # financial quantity or identity; only strip a leading list marker.
    text = re.sub(r"^(?:\d+|[ivxlcdm]+)[.)]\s+", "", text)
    labels = [
        (k, _text(v))
        for d in (ITEM_LABELS, FLOW_LABELS, BALANCE_LABELS, METRIC_LABELS, DEBT_LABELS)
        for k, v in d.items()
    ]
    labels += [
        ("b02.net_revenue", "doanh thu"),
        ("gross_margin", "gross margin"),
        ("debt_to_assets", "debt to assets"),
        ("revenue_yoy", "revenue yoy"),
    ]
    labels += [
        (rule.canonical_item_id, re.sub(r"^(?:\d+|[ivxlcdm]+)[.)]\s+", "", _text(alias)))
        for rule in ITEM_CATALOG
        for alias in rule.aliases
    ]
    assertions = set()
    for target, label in sorted(set(labels), key=lambda entry: -len(entry[1])):
        pattern = (
            re.escape(label)
            + rf"(?:(?: cua)? (?P<ptype>trong ky|tai ngay|ky|nam) (?P<period>{PERIOD}))?"
            + rf" (?:la|dat) (?P<value>{NUMBER})\s*"
            + r"(?:(?P<mult>nghin|ngan|trieu|ty) )?(?P<unit>vnd|usd|dong|%|phan tram)"
            + rf"(?: \(he so don vi (?P<scale>{NUMBER})\))?"
            + r"(?=$|[.,; ])"
        )
        matched = re.match(pattern, text)
        if not matched:
            continue
        # Another number or an explicit negation makes a single-value binding unsafe.
        tail = text[matched.end() :]
        if re.search(r"\d", tail) or re.search(r"\b(?:khong|chua)\b", text[: matched.start()]):
            return None
        number = parse_number(matched["value"])
        scale = parse_number(matched["scale"] or "1")
        if number is None or scale is None or scale <= 0:
            return None
        multiplier = {"nghin": "1000", "ngan": "1000", "trieu": "1000000", "ty": "1000000000"}.get(
            matched["mult"], "1"
        )
        if matched["mult"] and matched["scale"]:
            return None
        unit = {"vnd": "VND", "dong": "VND", "usd": "USD", "%": "percent", "phan tram": "percent"}[
            matched["unit"]
        ]
        with localcontext(Context(prec=50)):
            scale *= Decimal(multiplier)
        assertions.add(
            NumericAssertion(
                target,
                number,
                unit,
                scale,
                matched["period"],
                "as_of"
                if matched["ptype"] == "tai ngay"
                else "fiscal_year"
                if matched["period"]
                else None,
            )
        )
    if assertions:
        # Shared labels (e.g. gross/net inventory) cannot select an accounting
        # identity on wording alone. Never pick the first catalog entry.
        return next(iter(assertions)) if len(assertions) == 1 else None
    # Accepted arithmetic paraphrases: only the numerical assertion is checked.
    matched = re.fullmatch(
        rf"(?:trong ky (?P<period>{PERIOD}),? )?(?:cu|voi moi|tren moi) 100 dong "
        rf"(?P<base>doanh thu thuan|tong tai san) "
        rf"(?:tuong ung|tao ra|doanh nghiep thu duoc)(?: khoang)? (?P<value>{NUMBER}) dong "
        r"(?P<part>loi nhuan gop|no phai tra)\.?",
        text,
    )
    if matched and (matched["base"], matched["part"]) in {
        ("doanh thu thuan", "loi nhuan gop"),
        ("tong tai san", "no phai tra"),
    }:
        value = parse_number(matched["value"])
        if value is None:
            return None
        return NumericAssertion(
            "gross_margin" if matched["part"] == "loi nhuan gop" else "debt_to_assets",
            value,
            "percent",
            Decimal(1),
            matched["period"],
        )
    matched = re.fullmatch(
        rf"(?:trong cung (?:mot )?bao cao,? )?doanh thu thuan (?:ky|nam) "
        rf"(?P<period>{PERIOD}) (?P<direction>tang|giam|khong doi o muc) "
        rf"(?P<value>{NUMBER})% so voi (?:ky|nam) (?P<prior>{PERIOD})\.?",
        text,
    )
    if matched:
        value = parse_number(matched["value"])
        if value is not None and value >= 0:
            return NumericAssertion(
                "revenue_yoy",
                -value if matched["direction"] == "giam" else value,
                "percent",
                Decimal(1),
                matched["period"],
                "fiscal_year",
                matched["prior"],
            )
    return None
