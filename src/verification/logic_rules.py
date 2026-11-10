"""Bounded Vietnamese reasoning grammar; no financial formulas or industry thresholds."""

import re
from decimal import Decimal, InvalidOperation

from .numeric import extract_assertion, fold


def _has(text, pattern):
    return re.search(pattern, text) is not None


_EVIDENCE_NOUN = r"(?:co so|can cu|bang chung|du lieu|thong tin)"
_SHORTAGE = r"(?:(?:chua|khong)(?: co)? du|chua co|khong co|thieu)"
_EPISTEMIC_ACTION = r"(?:tinh(?: toan)?|ket luan|khang dinh|xac nhan|danh gia|chung minh)"
_LIMITATION_PREDICATE = re.compile(
    rf"\b(?:{_SHORTAGE} {_EVIDENCE_NOUN}|"
    rf"{_EVIDENCE_NOUN}(?: (?:hien co|hien tai|duoc cung cap|nay|van|hien|con))* "
    rf"(?:chua|khong)(?: co)? du|(?:chua|khong) the)(?: de)? {_EPISTEMIC_ACTION}\b"
)
_SCOPE_BOUNDARY = re.compile(
    r"[.;!?,]|\b(?:nhung|tuy nhien|song|vi vay|do do|boi vi|"
    r"va thuc te|dong thoi)\b|"
    # A new subject + asserted predicate is outside the preceding epistemic
    # complement, even when linked by a plain conjunction rather than punctuation.
    r"\b(?:va|hoac) (?=(?:ty le|ty so|he so|doanh thu|loi nhuan|cfo|dong tien) "
    r"(?:(?:nay|do) )?(?:(?:da|dang|van) )?(?:tang|giam|cai thien|vuot|cao hon|thap hon)\b)"
)


def _limitation_remainder(text):
    """Remove only governed epistemic complements, retaining independent clauses.

    Handles evidence-first and deficiency-first word orders. Negation of the
    deficiency itself is not a limitation. This grants no semantic support: every
    retained or governed assertion is still assessed by the independent critics.
    """
    limitation, remainder = False, []
    for clause in _SCOPE_BOUNDARY.split(text):
        match = _LIMITATION_PREDICATE.search(clause)
        if match is None or re.search(r"\bkhong(?: phai)?\s*$", clause[: match.start()]):
            remainder.append(clause)
            continue
        limitation = True
        remainder.append(clause[: match.start()])
        # Causes of evidence insufficiency stay within that limitation. A causal
        # financial assertion starts a new scope and cannot inherit its negation.
        governed = clause[match.end() :]
        escape = re.search(r"\b(?:nen|vi|do)\b(?! thieu\b)", governed)
        if escape:
            remainder.append(governed[escape.start() :])
    return limitation, " ".join(" ".join(remainder).split())


def assertion_category(content):
    """Conservative assertion scope; limitation complements never authorize a value.

    A limitation must have an evidence-deficiency predicate governing a conclusion
    or calculation. Contrast/independent clauses remain outside that scope. All
    digits/percentages and positive quantitative assertions keep numeric gates.
    This is routing to semantic assessment, never an evidence-support verdict.
    """
    text = fold(content)
    if re.search(r"\d|%", text):
        return "NUMERIC_ASSERTION"
    limitation, positive = _limitation_remainder(text)
    if re.search(
        r"\b(?:ty le|ty so|he so|ratio|margin|gap (?:doi|ba|bon)|lon hon|nho hon|cao hon|thap hon|vuot)\b",
        positive,
    ):
        return "NUMERIC_ASSERTION"
    if re.search(r"\b(?:chu yeu do|nguyen nhan|dan den|nho .+ nen|do .+ nen)\b", positive):
        return "UNSUPPORTED_CAUSAL_CLAIM"
    if limitation and not positive.strip():
        return "EVIDENCE_LIMITATION"
    if limitation and re.fullmatch(
        r"\s*(?:(?:trong ky nay )?(?:bao cao|doanh nghiep) ghi nhan .*)?", positive
    ):
        return "EVIDENCE_LIMITATION"
    return "QUALITATIVE_FINANCIAL_INTERPRETATION" if positive.strip() else "UNKNOWN_OR_AMBIGUOUS"


def assertion_spans(content):
    # Split coordinated propositions, while retaining noun phrases and the M5
    # sign/paraphrase template as a single assertion.
    return [
        s.strip()
        for s in re.split(
            r"(?<=[.!?;])\s+|(?:,\s*|\s+và\s+)(?=(?:doanh thu(?: thuần)?|lợi nhuận|"
            r"dòng tiền(?: từ hoạt động (?:kinh doanh|đầu tư|tài chính))?)\s+(?:tăng|giảm|dương|âm)\b)",
            content,
            flags=re.IGNORECASE,
        )
        if s.strip()
    ]


def classify(content, claim, checks):
    """Return (status, reason, required premises), or None for semantic assessment.

    Rules that disprove implications (e.g. CFO => loss) do not assert the opposite
    financial outcome. Complex negation, hypothetical or quoted statements defer.
    """
    text = fold(content)
    proof = getattr(claim, "reasoning", None)
    if proof is not None:
        if not _has(text, r"\b(?:khong|chua|neu|gia su|co the)\b") and _has(
            text, r"(?:chu yeu do|nguyen nhan|dan den|nho .+ nen|do .+ nen|vi .+ nen)"
        ):
            return "insufficient_context", "causal_evidence_missing", ["causal_evidence"]
        if proof.claim_type == "derived_fact":
            valid = all(
                any(c.check_id == key and c.status == "pass" for c in checks)
                for key in ("dynamic_calculation", "derived_statement")
            )
            return (
                "consistent" if valid else "insufficient_context",
                "replayed_derived_fact" if valid else "derived_proof_missing",
                ["comparison"],
            )
        # Structured inferences go to Critics after source/arithmetic validation.
        return None
    if _has(text, r'\b(?:khong|chua|neu|gia su|co the|khong han)\b|["“”]'):
        return None
    parsed = extract_assertion(content)
    # Exact numeric restatements (including signed YoY prose) belong to M6-02.
    if parsed:
        from .evidence_critic import _numeric_scope

        _, tail = _numeric_scope(content)
        if not tail:
            return "not_applicable", "numeric_assertion_only", []
    if _has(text, r"(?P<subject>doanh thu|loi nhuan|dong tien) tang dong thoi (?P=subject) giam"):
        return "inconsistent", "mutually_exclusive_directions", []
    if _has(
        text,
        r"(?:(?:dong tien|luu chuyen tien).*kinh doanh|cfo).*\bam\b.*(?:nen|chung to|dong nghia|suy ra).*"
        r"(?:thua lo|loi nhuan am)",
    ):
        return "inconsistent", "cash_flow_is_not_net_income", []
    if _has(text, r"(?:doanh thu|loi nhuan).*dong nghia.*(?:dong tien|tien mat)"):
        return "inconsistent", "accrual_is_not_cash_flow", []
    if _has(text, r"(?:mat kha nang thanh toan|pha san|khung hoang)"):
        return "insufficient_context", "solvency_requires_additional_context", ["liquidity_context"]
    if _has(text, r"(?:chu yeu do|nho .+ nen|do .+ nen|vi .+ nen|nguyen nhan|chung minh|dan den)"):
        return "insufficient_context", "causal_evidence_missing", ["causal_evidence"]
    if _has(text, r"(?:chat luong loi nhuan|loi nhuan chat luong cao)"):
        return (
            "insufficient_context",
            "earnings_quality_requires_context",
            ["earnings_quality_context"],
        )
    if _has(text, r"(?:kha nang thanh toan|rui ro don bay|don bay .+ rui ro)"):
        return "insufficient_context", "liquidity_requires_context", ["liquidity_context"]
    if _has(text, r"dong tien.*dau tu.*\bam\b.*(?:kinh doanh kem|hieu qua kem)"):
        return (
            "insufficient_context",
            "investing_outflow_not_performance_proof",
            ["financial_context"],
        )
    prefix = extract_assertion(claim.content)
    numeric = next((c for c in checks if c.check_id == "numeric"), None)
    value = None
    if numeric and numeric.status == "pass" and prefix:
        try:
            value = Decimal(numeric.expected["value"])
            if not value.is_finite():
                value = None
        except (InvalidOperation, KeyError, TypeError):
            pass
    if prefix and value is not None:
        # Bind directions to the approved revenue_yoy, never to a margin level.
        if prefix.target == "revenue_yoy" and re.fullmatch(
            r"doanh thu(?: thuan)? (?:tang|giam|on dinh)(?: so voi ky truoc)?[.!;]?", text
        ):
            # M4 already computed this numerator. Its sign preserves the true
            # direction even when the displayed YoY rounds to zero or base is negative.
            trace = getattr(getattr(claim, "calculation", None), "trace", None)
            if trace is None:
                return "insufficient_context", "comparison_evidence_required", ["comparison"]
            change = Decimal(trace.numerator)
            increasing = _has(text, r"\btang\b")
            decreasing = _has(text, r"\bgiam\b")
            stable = _has(text, r"\bon dinh\b")
            if sum((increasing, decreasing, stable)) != 1:
                return None
            correct = change > 0 if increasing else change < 0 if decreasing else change == 0
            return (
                "consistent" if correct else "inconsistent",
                "approved_yoy_direction_matches"
                if correct
                else "approved_yoy_direction_contradiction",
                ["comparison"],
            )
        targets = {
            "b03.operating_cash_flow": r"dong tien.*kinh doanh|\bcfo\b",
            "b03.investing_cash_flow": r"dong tien.*dau tu",
            "b03.financing_cash_flow": r"dong tien.*tai chinh",
            "b02.profit_after_tax": r"loi nhuan sau thue|loi nhuan rong",
            "b02.net_revenue": r"doanh thu(?: thuan)?",
            "gross_margin": r"bien loi nhuan gop|gross margin",
        }
        sign_phrase = re.fullmatch(
            r"(?:dong tien (?:tu hoat dong )?(?:kinh doanh|dau tu|tai chinh)|cfo|"
            r"loi nhuan sau thue|loi nhuan rong|doanh thu(?: thuan)?|bien loi nhuan gop|gross margin)"
            r" (?:la )?(?:am|duong)[.!;]?",
            text,
        )
        template = re.fullmatch(
            r"mang gia tri (am|duong), phan anh dong tien (vao|ra) thuan tu hoat dong "
            r"(kinh doanh|dau tu|tai chinh) theo chi tieu duoc bao cao[.!;]?",
            text,
        )
        if (
            prefix.target in targets
            and (sign_phrase or template)
            and (_has(text, targets[prefix.target]) or text.startswith("mang gia tri "))
        ):
            positive, negative = _has(text, r"\bduong\b"), _has(text, r"\bam\b")
            if positive != negative:
                correct = value > 0 if positive else value < 0
                if template:
                    correct &= (template[2] == "vao") == (value > 0)
                    activity = {
                        "kinh doanh": "b03.operating_cash_flow",
                        "dau tu": "b03.investing_cash_flow",
                        "tai chinh": "b03.financing_cash_flow",
                    }[template[3]]
                    if prefix.target != activity:
                        return (
                            "insufficient_context",
                            "financial_item_context_missing",
                            ["financial_context"],
                        )
                return (
                    "consistent" if correct else "inconsistent",
                    "financial_sign_matches" if correct else "financial_sign_contradiction",
                    ["sign_context"],
                )
    if _has(text, r"(?:cai thien|suy giam|on dinh|tot hon|tang|giam|so voi|ky truoc)"):
        return "insufficient_context", "comparison_evidence_required", ["comparison"]
    return None


def semantic_requirements(content, claim):
    """Conservative local minimum; Gemini cannot relabel an unknown inference as numeric."""
    text = fold(content)
    if getattr(claim, "reasoning", None) is not None:
        return {"financial_context"}
    if assertion_category(content) == "EVIDENCE_LIMITATION":
        return {"financial_context"}
    if _has(text, r"(?:dong luc|quyet dinh|nho|chi phi|nguyen nhan)"):
        return {"causal_evidence"}
    if _has(text, r"(?:tien bo|so sanh|tot len|cai thien|suy giam|on dinh)"):
        return {"comparison"}
    prefix = extract_assertion(claim.content)
    if (
        prefix
        and prefix.target
        in {
            "b03.operating_cash_flow",
            "b03.investing_cash_flow",
            "b03.financing_cash_flow",
            "b03.net_cash_flow",
        }
        and _has(
            text,
            r"(?:tien thu vao.*tien chi|tien chi.*tien thu vao|dong tien (?:vao|ra) thuan|chi rong|thu rong)",
        )
    ):
        return {"sign_context"}
    return {"financial_context"}


def mark_explicit_contradictions(findings):
    """Only identical, unqualified propositions in the same claim/context."""
    propositions = {}
    for finding in findings:
        match = re.fullmatch(
            r"(doanh thu(?: thuan)?|loi nhuan|dong tien) (tang|giam)[.!;]?", fold(finding.content)
        )
        if match:
            propositions.setdefault(match[1], []).append((match[2], finding))
    for entries in propositions.values():
        if {direction for direction, _ in entries} == {"tang", "giam"}:
            if any(finding.status == "consistent" for _, finding in entries):
                continue
            for _, finding in entries:
                finding.status = "inconsistent"
                finding.reason_codes = ["mutually_exclusive_assertions"]
                finding.missing_evidence.clear()


def context_gate(claim, validation, evidence):
    """Context gates describe missing comparability, not proven financial falsity."""
    contexts = {(e.document_id, e.snapshot_id) for e in evidence.evidence if e.available}
    refs = [*claim.fact_references, *claim.provenance.supporting_references]
    contexts.update(
        (r.observation.document_id, r.observation.snapshot_id) for r in refs if r.observation
    )
    if len(contexts) > 1 or any(
        c.check_id == "cross_document" and c.status == "undetermined" for c in validation.checks
    ):
        return "D03_B10_cross_document_comparability_blocked"
    if any(
        c.check_id in {"context", "content_period", "reporting_scope"} and c.status == "fail"
        for c in validation.checks
    ):
        return "period_scope_snapshot_mismatch"
    if any(
        c.check_id == "reporting_scope"
        and c.status == "undetermined"
        and c.observed.get("requested_scopes")
        for c in validation.checks
    ):
        return "requested_reporting_scope_unresolved"
    return None


def premise_gate(validation, evidence):
    if any(c.status == "fail" for c in validation.checks):
        return "failed_validation_premise"
    required = {
        "numeric",
        "item",
        "unit_scale",
        "context",
        "provenance",
        "quality",
        "supporting_fact",
        "fact_reference",
        "source_structure",
        "canonical_currency",
        "formula",
        "calculation_result",
        "calculation_request",
        "calculation_trace",
        "calculation_lineage",
        "operand_references",
        "supporting_metric",
    }
    checks = {c.check_id: c for c in validation.checks}
    if (
        "numeric" not in checks
        or checks["numeric"].status != "pass"
        or any(c.check_id in required and c.status == "undetermined" for c in validation.checks)
    ):
        return "validated_numeric_context_missing"
    if not any(a.status == "supported" and a.check_references for a in evidence.assertions):
        return "supported_numeric_premise_missing"
    if (
        any(e.stage != "semantic" for e in evidence.errors)
        or not evidence.evidence
        or any(not e.available for e in evidence.evidence)
    ):
        return "source_context_incomplete"
    return None
