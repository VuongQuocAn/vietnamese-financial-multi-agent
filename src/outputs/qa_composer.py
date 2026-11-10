"""Read-only M7 QA: catalog matching → verified retrieval → protected text slots.

The model can reorder selected slots, never write financial prose. This local
gate covers this composer only, not the general M7-05 Information Firewall.
"""

import json
import re
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
from ..tools.question_understanding import (
    EXTRA_ALIASES,
    FORMULA_ALIASES,
    ITEM_RULES,
    natural_formula,
    normalize,
    understand,
)
from ..verification.ledger import VerifiedClaimLedger
from ..verification.ledger_contracts import VerifiedClaim, VerifiedClaimQuery
from .qa_contracts import (
    GroundedSegment,
    QAClaimContext,
    QACompositionProposal,
    QARequirement,
    QAValidationResult,
    VietnameseQARequest,
    VietnameseQAResponse,
)
from .qa_explanation import explanation_text, metric_explanation

INTRODUCTIONS = {
    "verified": "Theo các nội dung đã được xác minh trong ledger:",
    "by_requirement": "Các nội dung có căn cứ cho từng yêu cầu:",
}
STATUS_TEXT = {
    "answered": "",
    "partial": "Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.",
    "clarification_required": "Cần làm rõ chỉ tiêu, tài liệu, snapshot hoặc kỳ báo cáo.",
    "abstained": "Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger.",
    "unsupported": "Yêu cầu vượt quá khả năng QA đã được hỗ trợ.",
}
SCOPE_CAVEAT = "Phạm vi báo cáo chưa được xác nhận trong claim đã chọn."
DOCUMENT_LEDGER_LIMIT = "Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu."
LEDGER_LIMIT = "Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF."


def _unique(values):
    return list(dict.fromkeys(values))


def _citations(values):
    return list({c.model_dump_json(): c for c in values}.values())


def claim_scope(entry: VerifiedClaim):
    """Use source-backed scope from an admitted calculation or exact fact context.

    Caller intent/batch context and a document year do not confirm filing scope.
    Fact proofs without a resolved, available M6 source context retain unknown scope.
    """
    if entry.identity.kind == "document":
        return None
    calc = entry.accepted_claim.calculation
    scope = calc.evidence.reporting_scope if calc and calc.evidence else None
    if (
        scope
        and scope.status == "resolved"
        and scope.evidence_status == "confirmed"
        and (scope.document_id, scope.snapshot_id)
        == (entry.identity.document_id, entry.identity.snapshot_id)
    ):
        return scope.reporting_scope
    if entry.identity.kind == "fact" and entry.decision.evidence:
        contexts = [
            ctx
            for ctx in entry.decision.evidence.evidence
            if ctx.reference in entry.accepted_claim.fact_references
            and ctx.reference.kind == "fact"
        ]
        if (
            contexts
            and all(
                ctx.available
                and ctx.reporting_scope_status == "resolved"
                and (ctx.document_id, ctx.snapshot_id)
                == (entry.identity.document_id, entry.identity.snapshot_id)
                and ctx.reporting_scope in {"separate", "consolidated"}
                for ctx in contexts
            )
            and len({ctx.reporting_scope for ctx in contexts}) == 1
        ):
            return contexts[0].reporting_scope
    return None


def _segment(entry):
    claim, decision = entry.accepted_claim, entry.decision
    scope = claim_scope(entry)
    if entry.identity.kind == "document":
        from ..evidence.document_claim_support import OCR_CAVEAT, SOURCE_LIMIT

        return GroundedSegment(
            segment_id=entry.identity.verified_claim_id,
            content=entry.content,
            verified_claim_ids=[entry.identity.verified_claim_id],
            citations=entry.citations,
            context=QAClaimContext(
                company_id=entry.identity.company_id,
                document_id=claim.source_document_id,
                snapshot_id=entry.identity.snapshot_id,
                period=None,
            ),
            caveats=_unique([OCR_CAVEAT, *entry.caveats]),
            limitations=[SOURCE_LIMIT]
            + (
                ["Trích đoạn liên quan; chưa bao phủ toàn bộ thuyết minh."]
                if claim.requirement.kind == "source_excerpt"
                else []
            ),
        )
    caveats = _unique(
        entry.caveats
        + claim.caveats
        + [c for e in claim.supporting_evidence for c in e.caveats]
        + [c for citation in entry.citations for c in citation.limitations]
        + ([SCOPE_CAVEAT] if scope is None else [])
    )
    return GroundedSegment(
        segment_id=entry.identity.verified_claim_id,
        content=entry.content,
        verified_claim_ids=[entry.identity.verified_claim_id],
        citations=entry.citations,
        context=QAClaimContext(
            **{
                k: getattr(entry.identity, k)
                for k in ("company_id", "document_id", "snapshot_id", "period")
            },
            reporting_scope=scope,
        ),
        caveats=caveats,
        limitations=_unique(
            decision.limitations + decision.unresolved_blockers + claim.missing_information
        ),
    )


def _segments(entries, requirements=()):
    """Coalesce identical display text; retain every selected identity and caveat."""
    grouped = {}
    for entry in entries:
        slot = _segment(entry)
        aspects = [
            r.aspect
            for r in requirements
            if r.kind == "explanation" and entry.identity.verified_claim_id in r.verified_claim_ids
        ]
        if aspects:
            slot.explanation = metric_explanation(entry, aspects)
            if slot.explanation:
                slot.content += "\n" + explanation_text(slot.explanation)
        key = (slot.content, slot.context.model_dump_json())
        if key not in grouped:
            grouped[key] = slot
        else:
            existing = grouped[key]
            existing.verified_claim_ids += slot.verified_claim_ids
            existing.citations = _citations(existing.citations + slot.citations)
            existing.caveats = _unique(existing.caveats + slot.caveats)
            existing.limitations = _unique(existing.limitations + slot.limitations)
    return list(grouped.values())


def _assertion_signature(entry):
    """Compare typed accepted premises, never interpret/paraphrase the claim text.

    Different wording of numeric-only ACCEPTs is allowed only for the same exact
    value/unit/scale, source references, calculation identity, period and scope.
    Interpretations still require verbatim content equality.
    """
    claim = entry.accepted_claim
    if entry.identity.kind == "document":
        return (claim.claim_type, claim.requirement.target, entry.content)
    return financial_assertion_signature(claim, claim_scope(entry))


def financial_assertion_signature(claim, reporting_scope=None):
    calc = claim.calculation
    return json.dumps(
        dict(
            context=dict(
                company_id=claim.company_id,
                document_id=claim.document_id,
                snapshot_id=claim.snapshot_id,
                period=claim.period,
                reporting_scope=reporting_scope,
            ),
            kind=claim.kind,
            interpretation=claim.content if claim.kind == "supported_interpretation" else None,
            evidence=[
                dict(
                    kind=e.kind,
                    reference=e.reference.model_dump(mode="json"),
                    value=e.value,
                    unit=e.unit,
                    scale=e.scale,
                    item=e.canonical_item_id,
                    period=e.period,
                )
                for e in claim.supporting_evidence
            ],
            metric=dict(
                id=calc.metric_id,
                formula=calc.formula_id,
                digest=calc.formula_digest,
                result=calc.result,
                unit=calc.output_unit,
            )
            if calc
            else None,
        ),
        sort_keys=True,
    )


def _targets(text):
    """Longest non-overlapping matches over the existing public catalog/aliases."""
    aliases = [("metric", key, names) for key, names in FORMULA_ALIASES.items()]
    aliases += [
        ("fact", key, (*rule.aliases, key, *EXTRA_ALIASES.get(key, ())))
        for key, rule in ITEM_RULES.items()
    ]
    aliases += [("fact", key, names) for key, names in QA_ALIASES.items()]
    spans = []
    for kind, key, names in aliases:
        for name in names:
            for match in re.finditer(r"(?<!\w)" + re.escape(normalize(name)) + r"(?!\w)", text):
                spans.append((match.start(), match.end(), kind, key))
    targets = _unique(
        (kind, key)
        for start, end, kind, key in sorted(spans)
        if not any(a <= start and end <= b and b - a > end - start for a, b, _, _ in spans)
    )
    if inferred := natural_formula(text):
        targets = [(kind, key) for kind, key in targets if key != "b02.net_revenue"]
        if ("metric", inferred) not in targets:
            targets.append(("metric", inferred))
    return targets


# QA paraphrases of existing catalog items, not new financial definitions.
QA_ALIASES = {
    "b02.profit_after_tax": ("lợi nhuận sau thuế", "lnst"),
    "b03.operating_cash_flow": ("dòng tiền kinh doanh", "cfo"),
}
INTERPRETATION_TERMS = (
    "nhan dinh",
    "dien giai",
    "phan tich",
    "noi len dieu gi",
    "cho thay dieu gi",
    "phan anh dieu gi",
    "nhan xet",
    "danh gia",
    "y nghia",
    "chat luong loi nhuan",
    "tot khong",
    "tot hay xau",
    "an toan",
    "lanh manh",
)
CAUSAL_TERMS = (
    "vi sao",
    "tai sao",
    "nguyen nhan",
    "do dau",
    "chung to",
    "nen dau tu",
    "du bao",
    "du doan",
    "tang bao nhieu",
    "giam bao nhieu",
    "gap doi",
    "gap ba",
    "cao hon",
    "thap hon",
)


def understand_requirements(question):
    """Catalog requests plus dependent explanation/interpretation obligations.

    Sentence intent is shared by its conjuncts. A targetless follow-up inherits
    explicit prior targets; explanation requires one uniquely identified metric.
    Unknown expressions stay bounded, never become computed metrics.
    """
    requirements, values = [], {}
    recent_metrics = []
    question_metrics = [
        target for kind, target in _targets(normalize(question)) if kind == "metric"
    ]

    def append(**kwargs):
        requirement = QARequirement(requirement_id=f"r{len(requirements) + 1}", **kwargs)
        requirements.append(requirement)
        return requirement

    for sentence in re.split(r"[.!?;\n]+", question):
        if not sentence.strip():
            continue
        text = normalize(sentence)
        sentence_interpretation = any(w in text for w in INTERPRETATION_TERMS)
        sentence_values = []
        fragments = re.split(r"\s+và\s+|,|\s*đồng thời\s+", sentence, flags=re.I)
        explanation_fragments = []
        for fragment in fragments:
            if not fragment.strip():
                continue
            t = normalize(fragment)
            targets = _targets(t)
            _, issues = understand(fragment)
            formula = any(w in t for w in ("cong thuc", "cach tinh"))
            operands = any(
                w in t
                for w in (
                    "so lieu su dung",
                    "so lieu dung",
                    "so lieu nao",
                    "nhung so lieu",
                    "du lieu dau vao",
                    "dau vao",
                    "toan hang",
                    "tu so",
                    "mau so",
                    "cach tinh",
                )
            )
            limitations = any(w in t for w in ("han che", "gioi han", "caveat"))
            # A causal question alone is outside the accepted bounded QA contract.
            causal = any(w in t for w in CAUSAL_TERMS)
            invalid = [i for i in issues if i != "multiple_or_ambiguous_targets"]
            if invalid or causal:
                append(
                    text=fragment,
                    kind="unsupported",
                    reason=invalid[0] if invalid else "unsupported_inference",
                )
                continue
            for kind, target in targets:
                key = (kind, target)
                if key not in values:
                    values[key] = append(text=fragment, kind=kind, target_id=target)
                if values[key] not in sentence_values:
                    sentence_values.append(values[key])
            if formula or operands:
                explanation_fragments.append((fragment, targets, formula, operands))
            if limitations:
                append(text=fragment, kind="limitations")
            if not targets and not (formula or operands or limitations):
                broad = any(
                    w in t
                    for w in (
                        "loi nhuan",
                        "sinh loi",
                        "co cau no",
                        "tinh hinh no",
                        "hieu qua kinh doanh",
                    )
                )
                followup = sentence_interpretation or "giai thich" in t
                if broad or not followup:
                    append(
                        text=fragment,
                        kind="ambiguous" if broad else "unsupported",
                        reason="specify_catalog_target" if broad else "unsupported_question",
                    )
        metric_values = [v for v in sentence_values if v.kind == "metric"]
        for fragment, targets, formula, operands in explanation_fragments:
            explicit = [values[(kind, target)] for kind, target in targets if kind == "metric"]
            parents = explicit or metric_values or recent_metrics
            if not parents and len(question_metrics) == 1:
                target = question_metrics[0]
                key = ("metric", target)
                if key not in values:
                    values[key] = append(text=question, kind="metric", target_id=target)
                parents = [values[key]]
            if len(parents) != 1:
                append(text=fragment, kind="ambiguous", reason="specify_explanation_target")
                continue
            parent = parents[0]
            for aspect, requested in (("formula", formula), ("operands", operands)):
                if requested and not any(
                    r.kind == "explanation"
                    and r.target_id == parent.target_id
                    and r.aspect == aspect
                    for r in requirements
                ):
                    append(
                        text=fragment,
                        kind="explanation",
                        target_id=parent.target_id,
                        aspect=aspect,
                        depends_on=[parent.requirement_id],
                    )
        if metric_values:
            recent_metrics = metric_values
        # A generic explanation follow-up continues the preceding request;
        # it does not introduce another independent unknown target.
        if sentence_interpretation:
            parents = sentence_values or list(values.values())
            topic = (
                "earnings_quality"
                if "chat luong loi nhuan" in text
                else (
                    "unbounded"
                    if any(w in text for w in ("tot khong", "tot hay xau", "an toan", "lanh manh"))
                    else "metric_meaning"
                )
            )
            for parent in parents:
                if not any(
                    r.interpretation
                    and r.target_id == parent.target_id
                    and r.interpretation_topic == topic
                    for r in requirements
                ):
                    append(
                        text=sentence,
                        kind=parent.kind,
                        target_id=parent.target_id,
                        interpretation=True,
                        interpretation_topic=topic,
                        depends_on=[parent.requirement_id],
                    )
    return requirements


def planned_requirements(question, proposal):
    """Materialize only user goals; old proposals use question parsing, never tools."""
    requirements = (
        [
            QARequirement(requirement_id=f"adaptive-{i}", text=question, **target.model_dump())
            for i, target in enumerate(proposal.user_requested_targets)
        ]
        if proposal.user_requested_targets
        else understand_requirements(question)
    )
    # Explicit lexical goals cannot disappear from a model-authored inventory.
    for explicit in understand_requirements(question):
        if explicit.kind not in {"fact", "metric", "explanation", "limitations"}:
            continue
        if not any(
            (r.kind, r.target_id, r.interpretation, r.aspect)
            == (explicit.kind, explicit.target_id, explicit.interpretation, explicit.aspect)
            for r in requirements
        ):
            requirements.append(
                explicit.model_copy(update={"requirement_id": f"adaptive-{len(requirements)}"})
            )
    # Explain a requested calculation from its own admitted metadata, never by
    # turning its internal operands into independent fact obligations. Keep the
    # generic M7 protected-slot default unchanged for historical direct callers.
    for metric in [r for r in requirements if r.kind == "metric" and not r.interpretation]:
        for aspect in ("formula", "operands"):
            if not any(
                r.kind == "explanation" and r.target_id == metric.target_id and r.aspect == aspect
                for r in requirements
            ):
                requirements.append(
                    QARequirement(
                        requirement_id=f"support-{len(requirements)}",
                        text=question,
                        kind="explanation",
                        target_id=metric.target_id,
                        period=metric.period,
                        aspect=aspect,
                        depends_on=[metric.requirement_id],
                    )
                )
    for requirement in requirements:
        if requirement.kind == "explanation":
            requirement.depends_on = [
                r.requirement_id
                for r in requirements
                if r.kind == "metric"
                and not r.interpretation
                and r.target_id == requirement.target_id
            ]
        if requirement.interpretation_topic == "earnings_quality":
            requirement.required_indicators = sorted(
                set(requirement.required_indicators)
                | {"b02.profit_after_tax", "b03.operating_cash_flow"}
            )
    if not requirements:
        return understand_requirements(question)
    # A relational goal's fact anchor is a representation choice. Equivalent
    # anchors do not create independent obligations; distinct premises/periods do.
    unique, aliases = {}, {}
    relation_periods = {
        r.period for r in requirements if r.interpretation_topic == "earnings_quality" and r.period
    }
    for requirement in requirements:
        if (
            requirement.interpretation_topic == "earnings_quality"
            and requirement.period is None
            and len(relation_periods) == 1
        ):
            requirement.period = next(iter(relation_periods))
        key = (
            (
                "relation",
                requirement.interpretation_topic,
                requirement.period,
                tuple(sorted(requirement.required_indicators)),
            )
            if requirement.interpretation_topic == "earnings_quality" and requirement.interpretation
            else (
                requirement.kind,
                requirement.target_id,
                requirement.period,
                requirement.interpretation,
                requirement.interpretation_topic,
                requirement.aspect,
                tuple(sorted(requirement.required_indicators)),
            )
        )
        if key in unique:
            aliases[requirement.requirement_id] = unique[key].requirement_id
        else:
            unique[key] = requirement
    for requirement in unique.values():
        requirement.depends_on = list(
            dict.fromkeys(aliases.get(key, key) for key in requirement.depends_on)
        )
    return list(unique.values())


def matches_financial_target(claim, requirement, logic=None):
    """Shared coverage predicate for native M6 records and admitted M7 claims."""
    if requirement.period and claim.period != requirement.period:
        return False
    expected = (
        "supported_interpretation"
        if requirement.interpretation
        else ("fact" if requirement.kind == "fact" else "approved_metric")
    )
    if claim.kind != expected:
        return False
    indicators = {e.canonical_item_id for e in claim.supporting_evidence if e.kind == "fact"}
    if claim.kind == "approved_metric" and claim.calculation and claim.calculation.evidence:
        indicators.update(
            match.record.canonical_item_id
            for operand in claim.calculation.evidence.operands
            for match in operand.facts.matches
        )
    if not set(requirement.required_indicators) <= indicators:
        return False
    if requirement.interpretation:
        if requirement.interpretation_topic == "unbounded":
            return False
        if requirement.interpretation_topic == "earnings_quality":
            from ..verification.logic_rules import assertion_category

            if assertion_category(claim.content) == "EVIDENCE_LIMITATION":
                return False
            # Prefer the already verified Critic purpose. Legacy proofs can also
            # express the relation directly without a prescribed topic sentence.
            typed = any(
                finding.status == "consistent"
                and "earnings_quality_context" in finding.required_premises
                for finding in getattr(logic, "assertions", [])
            )
            text = normalize(claim.content)
            predicate = r"(?:vuot|cao hon|thap hon|ho tro|bao dam|chuyen hoa|chuyen doi|tuong xung|chenh lech)"
            relation = re.search(
                rf"\b(dong tien|cfo)\b[^.;]*\b{predicate}\b[^.;]*\b(loi nhuan|pat)\b", text
            ) or re.search(
                rf"\b(loi nhuan|pat)\b[^.;]*\b{predicate}\b[^.;]*\b(dong tien|cfo|bang tien)\b",
                text,
            )
            if not (typed or relation):
                return False
    if requirement.kind == "fact":
        return any(
            e.kind == "fact" and e.canonical_item_id == requirement.target_id
            for e in claim.supporting_evidence
        )
    return bool(claim.calculation and claim.calculation.formula_id == requirement.target_id)


def _matches_target(entry, requirement):
    if requirement.period and entry.identity.period != requirement.period:
        return False
    if requirement.kind == "source_context":
        return (
            entry.verification_status == "verified"
            and entry.decision.decision == "ACCEPT"
            and bool(entry.citations)
        )
    if requirement.kind == "document":
        return (
            entry.identity.kind == "document"
            and entry.accepted_claim.requirement.target == requirement.target_id
        )
    if entry.identity.kind == "document":
        return False
    claim = entry.accepted_claim
    if entry.verification_status != "verified" or entry.decision.decision != "ACCEPT":
        return False
    if requirement.kind == "explanation" and not requirement.interpretation:
        return bool(
            entry.identity.kind == "approved_metric"
            and claim.calculation
            and claim.calculation.formula_id == requirement.target_id
            and metric_explanation(entry, [requirement.aspect])
        )
    return matches_financial_target(claim, requirement, getattr(entry.decision, "logic", None))


def _answer_text(response):
    parts = [INTRODUCTIONS[response.introduction]] if response.grounded_segments else []
    for segment in response.grounded_segments:
        # Separate context and text: no rewriting or numerical formatting of accepted content.
        ctx = segment.context
        parts.append(f"Kỳ {ctx.period} — {segment.content}" if ctx.period else segment.content)
    if STATUS_TEXT[response.status]:
        parts.append(STATUS_TEXT[response.status])
    if response.unanswered_requirements:
        # Reflect requirement labels only; never echo untrusted financial assertions.
        parts.append(
            "Các yêu cầu chưa đáp ứng: "
            + ", ".join(_requirement_label(r) for r in response.unanswered_requirements)
            + "."
        )
    if response.caveats:
        notes = _public_notes(response.caveats)
        if notes:
            parts.append("Lưu ý: " + "; ".join(notes))
    if response.limitations:
        notes = _public_notes(response.limitations)
        if notes:
            parts.append("Giới hạn: " + "; ".join(notes))
    return "\n".join(parts)


def _public_notes(notes):
    """Keep diagnostic codes in the wire trace, expose bounded source caveats."""
    result = []
    for note in notes:
        if note.startswith(("PLANNER_TASK:", "specialist_annotation:")):
            continue
        if re.search(r"\b[a-zA-Z]+_[a-zA-Z_]+\b", note):
            if any(
                word in note.lower() for word in ("failed", "failure", "error", "invalid_proposal")
            ):
                note = "Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh."
            else:
                note = "Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh."
        result.append(note)
    return _unique(result)


def _requirement_label(requirement):
    """Only bounded catalog labels and reason templates, never the user prose."""
    from ..tools.question_understanding import FORMULA_LABELS

    if requirement.target_id is None and requirement.reason is None:
        return requirement.requirement_id
    if requirement.kind == "document":
        return f"{requirement.text} (chưa có nguồn đủ căn cứ)"
    if requirement.reason == "unsupported_causal_inference":
        return "nguyên nhân biến động (chưa đủ bằng chứng để xác định quan hệ nhân quả)"
    target = requirement.target_id
    name = FORMULA_LABELS.get(target) or (
        ITEM_RULES[target].aliases[0] if target in ITEM_RULES else "yêu cầu chưa xác định"
    )
    if requirement.interpretation:
        name = "nhận định về " + name
    elif requirement.kind == "explanation":
        name = ("công thức của " if requirement.aspect == "formula" else "toán hạng của ") + name
    reason = {
        "no_verified_claim": "chưa có nội dung đã xác minh",
        "no_supported_interpretation": "chưa có nhận định được xác minh phù hợp",
        "insufficient_admitted_calculation_metadata": "bằng chứng tính toán chưa đủ để giải thích",
    }.get(requirement.reason, "chưa đủ căn cứ hoặc cần làm rõ")
    return f"{name} ({reason})"


def _ledger_limit(requirements):
    return (
        DOCUMENT_LEDGER_LIMIT if any(r.kind == "document" for r in requirements) else LEDGER_LIMIT
    )


def validate_qa_response(response, retrieved):
    """Compare complete protected slots, not numeric regex or model attestations."""
    entries = {e.identity.verified_claim_id: e for e in retrieved}
    errors = []
    ids = response.used_verified_claim_ids
    if len(set(ids)) != len(ids) or any(key not in entries for key in ids):
        errors.append("invalid_verified_claim_reference")
    if [key for s in response.grounded_segments for key in s.verified_claim_ids] != ids:
        errors.append("segment_selection_mismatch")
    if all(key in entries for key in ids):
        if response.grounded_segments != _segments(
            [entries[key] for key in ids], response.plan.requirements
        ):
            errors.append("protected_slot_mismatch")
    for segment in response.grounded_segments:
        ctx = segment.context
        if any(
            (c.document_id, c.snapshot_id) != (ctx.document_id, ctx.snapshot_id)
            or (c.source.document_id, c.source.snapshot_id) != (ctx.document_id, ctx.snapshot_id)
            for c in segment.citations
        ):
            errors.append("citation_context_mismatch")
    if response.citations != _citations(c for s in response.grounded_segments for c in s.citations):
        errors.append("citation_projection_mismatch")
    if response.caveats != _unique(c for s in response.grounded_segments for c in s.caveats):
        errors.append("caveat_projection_mismatch")
    expected_limits = _unique(c for s in response.grounded_segments for c in s.limitations)
    if response.unanswered_requirements:
        expected_limits = _unique(
            expected_limits + [_ledger_limit(response.unanswered_requirements)]
        )
    if response.limitations != expected_limits:
        errors.append("limitation_projection_mismatch")
    answered = [r for r in response.plan.requirements if r.verified_claim_ids]
    unanswered = [r for r in response.plan.requirements if not r.verified_claim_ids]
    if (
        response.answered_requirements != answered
        or response.unanswered_requirements != unanswered
        or set(ids) != {key for r in answered for key in r.verified_claim_ids}
        or set(ids) != set(response.plan.selected_verified_claim_ids)
    ):
        errors.append("requirement_coverage_mismatch")
    for requirement in answered:
        if (
            len(
                {
                    _assertion_signature(entries[key])
                    for key in requirement.verified_claim_ids
                    if key in entries
                }
            )
            > 1
            and requirement.kind not in {"limitations", "source_context"}
            and not (
                requirement.kind == "document"
                and all(
                    entries[key].accepted_claim.requirement.kind == "source_excerpt"
                    for key in requirement.verified_claim_ids
                    if key in entries
                )
            )
        ):
            errors.append("conflicting_requirement_assertions")
        for key in requirement.verified_claim_ids:
            if key not in entries or (
                requirement.kind != "limitations" and not _matches_target(entries[key], requirement)
            ):
                errors.append("requirement_target_mismatch")
    if ids and response.status != ("partial" if unanswered else "answered"):
        errors.append("status_coverage_mismatch")
    if not ids and response.status in ("answered", "partial"):
        errors.append("empty_answer")
    contexts = {
        (
            s.context.company_id,
            s.context.document_id if s.context.period else None,
            s.context.snapshot_id if s.context.period else None,
        )
        for s in response.grounded_segments
    }
    from ..agents.fusion_contracts import is_mixed

    if len(contexts) > 1 and not is_mixed(response.question):
        errors.append("mixed_contexts")
    if (
        is_mixed(response.question)
        and len({s.context.company_id for s in response.grounded_segments}) > 1
    ):
        errors.append("mixed_companies")
    if len({s.context.period[:4] for s in response.grounded_segments if s.context.period}) > 1:
        errors.append("mixed_reporting_years")
    if response.answer_vi != _answer_text(response):
        errors.append("unapproved_display_text")
    return QAValidationResult(valid=not errors, errors=_unique(errors))


def qa_claim_query(request, parsed):
    from ..agents.fusion_contracts import is_mixed

    if is_mixed(request.question):
        return VerifiedClaimQuery(company_id=request.company_id, document_id=request.document_id)
    document = request.composition_id is not None
    return VerifiedClaimQuery(
        company_id=request.company_id,
        document_id=request.document_id,
        snapshot_id=request.snapshot_id,
        period=None if document else request.period or parsed.period,
        kind="document" if document else None,
        composition_id=request.composition_id,
        composition_sha256=request.composition_sha256,
    )


def retrieve_qa_claims(ledger, request, parsed):
    from ..agents.fusion_contracts import is_mixed

    if not is_mixed(request.question):
        return ledger.find_claims(qa_claim_query(request, parsed)).claims
    entries = ledger.find_claims(
        VerifiedClaimQuery(
            company_id=request.company_id,
            document_id=request.document_id,
            snapshot_id=request.snapshot_id,
            period=request.period or parsed.period,
        )
    ).claims
    entries += ledger.find_claims(
        VerifiedClaimQuery(
            company_id=request.company_id,
            document_id=request.document_id,
            kind="document",
            composition_id=request.composition_id,
            composition_sha256=request.composition_sha256,
        )
    ).claims
    return [
        e
        for e in entries
        if (
            e.identity.kind == "document"
            and e.identity.composition_id == request.composition_id
            and e.identity.composition_sha256 == request.composition_sha256
            and e.identity.snapshot_id in request.document_snapshots
        )
        or (
            e.identity.kind != "document"
            and e.identity.snapshot_id == request.snapshot_id
            and (request.period is None or e.identity.period == request.period)
        )
    ]


class VietnameseQAComposer:
    def __init__(self, ledger: VerifiedClaimLedger, gateway: SharedLLMGateway | None = None):
        self._ledger, self._gateway = ledger, gateway

    def compose(self, request: VietnameseQARequest) -> VietnameseQAResponse:
        request = VietnameseQARequest.model_validate_json(request.model_dump_json())
        # Local import avoids a module cycle; both consumers recompute the same
        # inventory from their own trusted request and admitted retrieval.
        from .firewall_qa_binding import request_inventory

        plan, status = request_inventory(request, [])
        response = VietnameseQAResponse(
            question=request.question, status="abstained", answer_vi="", plan=plan
        )
        if status in ("unsupported", "clarification_required"):
            return self._finish(response, [], status)
        parsed, _ = understand(request.question)
        try:
            retrieved = retrieve_qa_claims(self._ledger, request, parsed)
        except (ValueError, OSError):
            plan.reasons.append("ledger_read_failed")
            return self._finish(response, [], "abstained")
        if any(
            any(
                value is not None and getattr(e.identity, field) != value
                for field, value in (
                    ("company_id", request.company_id),
                    ("document_id", request.document_id),
                    ("snapshot_id", None if request.document_snapshots else request.snapshot_id),
                    ("period", None if request.composition_id else request.period or parsed.period),
                )
            )
            or e.verification_status != "verified"
            or e.decision.decision != "ACCEPT"
            for e in retrieved
        ):
            plan.reasons.append("retrieval_context_mismatch")
            return self._finish(response, [], "abstained")
        response.plan, status = request_inventory(request, retrieved)
        ids = response.plan.selected_verified_claim_ids
        if not ids:
            return self._finish(response, retrieved, status)
        order = self._propose(request, response, retrieved) if request.allow_gateway else ids
        by_id = {e.identity.verified_claim_id: e for e in retrieved}
        response.grounded_segments = _segments(
            [by_id[key] for key in order], response.plan.requirements
        )
        return self._finish(response, retrieved, status)

    def _propose(self, request, response, retrieved):
        metadata, ids = response.llm_metadata, response.plan.selected_verified_claim_ids
        if self._gateway is None:
            metadata.status, metadata.reason = "fallback", "gateway_unavailable"
            return ids
        projection = [
            dict(
                verified_claim_id=e.identity.verified_claim_id,
                content=e.content,
                context=_segment(e).context.model_dump(mode="json"),
                citation_handles=[c.anchor_id for c in e.citations],
                caveats=_segment(e).caveats,
                limitations=_segment(e).limitations,
                interpretation_boundary="Render accepted content verbatim; no added assertion.",
            )
            for e in retrieved
            if e.identity.verified_claim_id in ids
        ]
        prompt = json.dumps(
            dict(
                instruction="Chỉ sắp xếp các protected slots. Xuất JSON theo schema; claim_order "
                "là hoán vị đầy đủ các verified_claim_id. Không xuất prose, số mới, "
                "citations hay caveats; backend giữ nguyên mọi nội dung và giới hạn.",
                schema=QACompositionProposal.model_json_schema(),
                selected_claims=projection,
            ),
            ensure_ascii=False,
        )
        if len(prompt.encode("utf-8")) > 24000:
            metadata.status, metadata.reason = "fallback", "projection_budget_exceeded"
            return ids
        metadata.calls, metadata.model = 1, request.model
        result = self._gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id=str(uuid4()),
                model=request.model,
                messages=[Message(role="user", content=prompt)],
                generation=GenerationParameters(temperature=0, max_output_tokens=1600),
                output_spec=OutputSpec(format="json"),
                constraints=RequestConstraints(timeout_seconds=45),
            )
        )
        metadata.usage, metadata.cost = result.usage, result.cost
        metadata.provenance, metadata.error = result.provenance, result.error
        try:
            if result.status != "success" or not isinstance(result.output, JSONOutput):
                raise ValueError("provider_or_structured_output_failure")
            proposal = QACompositionProposal.model_validate(result.output.payload)
            if len(proposal.claim_order) != len(ids) or set(proposal.claim_order) != set(ids):
                raise ValueError("invalid_claim_permutation")
        except (ValidationError, ValueError):
            metadata.status, metadata.reason = "fallback", "invalid_composition_proposal"
            return ids
        metadata.status = "accepted"
        response.introduction = proposal.introduction
        return proposal.claim_order

    @staticmethod
    def _finish(response, retrieved, status=None):
        response.answered_requirements = [
            r for r in response.plan.requirements if r.verified_claim_ids
        ]
        response.unanswered_requirements = [
            r for r in response.plan.requirements if not r.verified_claim_ids
        ]
        response.status = status or ("partial" if response.unanswered_requirements else "answered")
        response.used_verified_claim_ids = [
            key for s in response.grounded_segments for key in s.verified_claim_ids
        ]
        response.citations = _citations(c for s in response.grounded_segments for c in s.citations)
        response.caveats = _unique(c for s in response.grounded_segments for c in s.caveats)
        response.limitations = _unique(c for s in response.grounded_segments for c in s.limitations)
        if response.unanswered_requirements:
            response.limitations = _unique(
                response.limitations + [_ledger_limit(response.unanswered_requirements)]
            )
        response.missing_information = response.plan.missing_information.copy()
        response.reasons = _unique(
            response.plan.reasons + [r.reason for r in response.unanswered_requirements if r.reason]
        )
        response.answer_vi = _answer_text(response)
        response.validation_result = validate_qa_response(response, retrieved)
        if not response.validation_result.valid:
            # Retain the failure codes, but expose no financial slots/references.
            errors = response.validation_result.errors
            for r in response.plan.requirements:
                r.verified_claim_ids = []
            response.plan.selected_verified_claim_ids = []
            response.plan.reasons.extend(errors)
            response.grounded_segments = []
            return VietnameseQAComposer._finish(response, [], "abstained")
        return VietnameseQAResponse.model_validate_json(response.model_dump_json())
