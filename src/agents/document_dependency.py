"""Resolve a downstream search subject only from released verified comparisons."""

import re
from decimal import Decimal

from ..tools.question_understanding import normalize


def comparison_subject(entries, question):
    text = normalize(question)
    if not re.search(r"\b(khoan muc|chi tieu).*(lon hon|nho hon)\b", text):
        return None
    if not re.search(r"\b(doi tuong|khach hang|cong ty|ten rieng)\b", text) or not re.search(
        r"\b(lon nhat|nho nhat)\b", text
    ):
        return None
    found = set()
    for entry in entries:
        claim = entry.accepted_claim
        proof = getattr(claim, "reasoning", None)
        if not proof or not proof.calculation or proof.assumptions:
            continue
        calc = proof.calculation
        step = calc.steps[-1]
        if step.operation.operator not in {"greater", "less"} or len(step.operation.inputs) != 2:
            continue
        operands = [calc.operands.get(key) for key in step.operation.inputs]
        if any(o is None or o.unit != "VND" for o in operands):
            continue
        if len({o.period for o in operands}) != 1 or not operands[0].period.endswith("-12-31"):
            continue
        values = [Decimal(o.value) * Decimal(o.scale) for o in operands]
        if values[0] == values[1]:
            continue
        chooser = min if "nho hon" in text else max
        selected = operands[values.index(chooser(values))]
        labels = {e.label for e in claim.supporting_evidence if e.reference == selected.reference}
        if len(labels) == 1:
            label = re.sub(r"^\s*(?:[IVX]+|\d+)[.)]\s*", "", next(iter(labels)))
            found.add((label, selected.period[:4]))
    if len(found) != 1:
        return None
    label, year = next(iter(found))
    extremum = "nhỏ nhất" if "nho nhat" in text else "lớn nhất"
    return (
        f"Trong thuyết minh {label} cuối năm {year}, "
        f"đối tượng được nêu tên riêng có số dư {extremum} là ai?"
    )
