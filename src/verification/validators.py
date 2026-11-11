"""Deterministic, read-only claim checks against an independently hydrated catalog."""

import re
from decimal import Decimal, InvalidOperation

from ..evidence.contracts import assess_fact_consistency
from ..evidence.snapshots import SnapshotCatalog
from ..tools.financial_calculator import (
    CalculateFinancialMetricRequest,
    FinancialCalculator,
    render_dynamic,
)
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
from ..tools.question_understanding import comparison_periods
from .contracts import CandidateClaim, VerificationInput
from .logic_rules import _limitation_remainder, assertion_category
from .numeric import extract_assertion, fold
from .validation_contracts import (
    ClaimValidationResult,
    ValidationCheck,
    ValidationResult,
    verification_input_digest,
)

APPROVED_FORMULAS = {"gross_margin", "debt_to_assets", "revenue_yoy"}
PERIOD_ROLES = {
    "gross_margin": "revenue",
    "debt_to_assets": "assets",
    "revenue_yoy": "current_revenue",
}


def _decimal_equal(left, right):
    try:
        a, b = Decimal(left), Decimal(right)
        return a.is_finite() and b.is_finite() and a == b
    except (InvalidOperation, TypeError):
        return False


def _same_calculation(actual, expected):
    return actual is not None and (
        actual.request.metric_id == expected.metric_id
        and actual.request.document_id in {None, expected.document_id}
        and actual.request.snapshot_id in {None, expected.snapshot_id}
        and actual.model_dump(exclude={"request"}) == expected.model_dump(exclude={"request"})
    )


class DeterministicFinancialValidator:
    """Caller supplies canonical facts/policies/graph, never candidate-derived copies.

    No filesystem/network/Gemini calls. Catalog is isolated on construction; M4
    owns snapshot selection, quality retrieval and approved formula execution.
    Findings describe individual checks, not an ACCEPT/REVISE decision.
    """

    def __init__(self, catalog: SnapshotCatalog):
        from ..evidence.snapshots import isolated_catalog

        self._catalog = isolated_catalog(catalog)
        self._retrieval = FinancialRetrievalTools(self._catalog)
        self._calculator = FinancialCalculator(self._catalog)

    def validate(self, batch: VerificationInput) -> ValidationResult:
        batch = VerificationInput.model_validate_json(batch.model_dump_json())
        output = ValidationResult(
            source_result_sha256=batch.source_result_sha256,
            verification_input_sha256=verification_input_digest(batch),
            conflicts=batch.conflicts,
            caveats=batch.caveats,
        )
        for claim in batch.claims:
            result = ClaimValidationResult(
                candidate_id=claim.candidate_id, claim_kind=claim.kind, caveats=list(claim.caveats)
            )
            self._claim(batch, claim, result)
            result.caveats = sorted(set(result.caveats))
            output.claims.append(result)
        return output

    @staticmethod
    def _check(
        result,
        check_id,
        status,
        reason,
        *,
        kind="missing_evidence",
        refs=(),
        expected=None,
        observed=None,
        citations=(),
        candidate_ids=None,
        conflicts=(),
    ):
        result.checks.append(
            ValidationCheck(
                finding_id=f"{result.candidate_id}:{check_id}:{len(result.checks)}",
                candidate_ids=candidate_ids or [result.candidate_id],
                kind=kind,
                message=reason,
                references=list(refs),
                conflict_ids=list(conflicts),
                check_id=check_id,
                status=status,
                reason_code=reason,
                expected=expected or {},
                observed=observed or {},
                citations=list(citations),
            )
        )

    def _claim(self, batch, claim, result):
        def add(*args, **kw):
            return self._check(result, *args, **kw)

        conflicts = [c for c in batch.conflicts if claim.candidate_id in c.candidate_ids]
        if conflicts:
            for conflict in conflicts:
                add(
                    "candidate_conflict",
                    "undetermined",
                    "candidate_conflict_preserved",
                    kind="conflicting_candidates",
                    candidate_ids=conflict.candidate_ids,
                    conflicts=[conflict.conflict_id],
                )
        else:
            add("candidate_conflict", "not_applicable", "no_candidate_conflict")
        issues = [i for i in batch.issues if i.candidate_id in {None, claim.candidate_id}]
        add(
            "handoff_structure",
            "undetermined" if issues else "pass",
            "handoff_issues_preserved" if issues else "handoff_structure_available",
            observed={"issues": [i.model_dump(mode="json") for i in issues]},
        )
        if not claim.supporting_evidence:
            add("supporting_evidence", "undetermined", "supporting_evidence_missing")
        assertion = extract_assertion(claim.content)
        if claim.kind == "supported_interpretation" and claim.analysis_premises:
            self._analysis(batch, claim, result)
            if not claim.metric_ids and not any(
                c.check_id == "formula" and c.status == "fail" for c in result.checks
            ):
                add("formula", "not_applicable", "fact_interpretation_has_no_formula")
        elif claim.kind == "fact":
            self._fact(batch, claim, result, assertion)
            add("formula", "not_applicable", "fact_has_no_formula")
        elif claim.kind == "approved_metric" or claim.metric_ids or claim.calculation:
            self._metric(batch, claim, result, assertion)
        else:
            self._fact(batch, claim, result, assertion)
            add("formula", "not_applicable", "fact_interpretation_has_no_formula")
        add(
            "semantic_conclusion",
            "undetermined" if claim.kind == "supported_interpretation" else "not_applicable",
            "requires_financial_logic_critic"
            if claim.kind == "supported_interpretation"
            else "no_interpretation_conclusion",
            kind="unsupported_inference",
        )

    def _analysis(self, batch, claim, result):
        if claim.reasoning is not None:
            return self._reasoning(batch, claim, result)
        sources = claim.supporting_evidence
        if re.search(r"\d|%", claim.content):
            self._check(result, "numeric", "fail", "analysis_premise_binding_invalid")
            return
        if assertion_category(claim.content) == "NUMERIC_ASSERTION":
            self._check(result, "formula", "fail", "analysis_requires_approved_calculation")
            return
        if (
            re.search(r"\d|%", claim.content)
            or len(sources) != len(claim.analysis_premises)
            or not sources
            or any(e.kind != "fact" for e in sources)
            or set(r.model_dump_json() for r in claim.fact_references)
            != {e.reference.model_dump_json() for e in sources}
        ):
            self._check(result, "numeric", "fail", "analysis_premise_binding_invalid")
            return
        for index, (source, statement) in enumerate(
            zip(sources, claim.analysis_premises, strict=True)
        ):
            local = claim.model_copy(
                deep=True,
                update=dict(
                    content=statement,
                    kind="fact",
                    analysis_premises=[],
                    supporting_evidence=[source],
                    fact_references=[source.reference],
                    citations=source.citations,
                ),
            )
            sub = ClaimValidationResult(candidate_id=claim.candidate_id, claim_kind=claim.kind)
            self._fact(batch, local, sub, extract_assertion(statement))
            for check in sub.checks:
                check.finding_id += f":premise-{index}"
            result.checks.extend(sub.checks)
            result.caveats.extend(sub.caveats)
        self._citations(
            claim,
            result,
            list({c.model_dump_json(): c for s in sources for c in s.citations}.values()),
            claim.fact_references,
        )

    def _reasoning(self, batch, claim, result):
        """Independently check every source/operation before semantic interpretation.

        Existing wire/proof paths remain unchanged when reasoning is absent.
        A failed branch only blocks this candidate and its dependent conclusion.
        """
        proof, sources = claim.reasoning, claim.supporting_evidence
        if not sources or len(sources) != len(claim.analysis_premises):
            self._check(result, "numeric", "fail", "analysis_premise_binding_invalid")
            return
        expected_refs = {e.reference.model_dump_json() for e in sources if e.kind == "fact"}
        if (
            expected_refs != {r.model_dump_json() for r in claim.fact_references}
            and not claim.metric_ids
        ):
            self._check(result, "numeric", "fail", "analysis_premise_binding_invalid")
            return
        if len({e.evidence_id for e in sources}) != len(sources):
            self._check(result, "numeric", "fail", "analysis_duplicate_evidence_identity")
            return
        if (claim.company_id, claim.document_id, claim.snapshot_id, claim.period) != (
            sources[0].company_id,
            sources[0].document_id,
            sources[0].snapshot_id,
            sources[0].period,
        ):
            self._check(result, "context", "fail", "reasoning_owner_mismatch")
        requested_periods = comparison_periods(batch.question)
        periods = {s.period for s in sources}
        comparative = (
            bool(requested_periods)
            and periods <= requested_periods
            and (not batch.context.period or batch.context.period in requested_periods)
        )
        if requested_periods and not comparative:
            self._check(result, "context", "fail", "reasoning_comparison_period_mismatch")
        if batch.context.period and batch.context.period != claim.period and not comparative:
            self._check(result, "context", "fail", "reasoning_requested_period_mismatch")
        across = proof.calculation and any(
            step.operation.period_relation == "across_periods" for step in proof.calculation.steps
        )
        if len(periods) > 1 and not across:
            self._check(result, "context", "fail", "reasoning_period_relation_missing")
        for index, (source, statement) in enumerate(
            zip(sources, claim.analysis_premises, strict=True)
        ):
            local = claim.model_copy(
                deep=True,
                update=dict(
                    content=statement,
                    kind="approved_metric" if source.calculation else "fact",
                    reasoning=None,
                    analysis_premises=[],
                    supporting_evidence=[source],
                    company_id=source.company_id,
                    document_id=source.document_id,
                    snapshot_id=source.snapshot_id,
                    period=source.period,
                    fact_references=[source.reference]
                    if not source.calculation
                    else [
                        r
                        for r in claim.fact_references
                        if r.observation
                        in {o.observation for o in source.calculation.trace.operands}
                    ],
                    calculation=source.calculation,
                    metric_ids=[source.calculation.metric_id] if source.calculation else [],
                    citations=source.citations,
                ),
            )
            sub = ClaimValidationResult(candidate_id=claim.candidate_id, claim_kind=claim.kind)
            local_batch = batch.model_copy(deep=True)
            if across and (not batch.context.period or comparative):
                local_batch.context.period = None
                local_batch.context.reporting_year = None
            if source.calculation:
                self._metric(local_batch, local, sub, extract_assertion(statement))
            else:
                self._fact(local_batch, local, sub, extract_assertion(statement))
            for check in sub.checks:
                check.finding_id += f":premise-{index}"
            result.checks.extend(sub.checks)
            result.caveats.extend(sub.caveats)
        computation = proof.calculation
        if computation:
            try:
                expected = self._calculator.calculate_dynamic(
                    {s.evidence_id: s.reference for s in sources if s.kind == "fact"},
                    [s.operation for s in computation.steps],
                )
                if computation != expected:
                    raise ValueError("dynamic_replay_mismatch")
                # A change relative to the base uses target first, base second.
                # Bind direct change operands to the same canonical indicator;
                # replay still owns the arithmetic, denominator and source guards.
                by_id = {s.evidence_id: s for s in sources}
                for step in computation.steps:
                    op = step.operation
                    if op.period_relation != "across_periods" or op.operator not in {
                        "subtract",
                        "percentage_change",
                        "relative_difference",
                    }:
                        continue
                    if all(key in by_id for key in op.inputs):
                        target, base = (by_id[key] for key in op.inputs)
                        if target.period != base.period and (
                            target.period < base.period
                            or not target.canonical_item_id
                            or target.canonical_item_id != base.canonical_item_id
                        ):
                            raise ValueError("reasoning_comparison_operand_mismatch")
                self._check(
                    result,
                    "dynamic_calculation",
                    "pass",
                    "dynamic_independent_replay_matches",
                    expected=expected.model_dump(mode="json"),
                )
            except (ValueError, ArithmeticError, TypeError) as error:
                self._check(result, "dynamic_calculation", "fail", str(error))
        if proof.claim_type == "derived_fact":
            exact = (
                bool(computation)
                and not proof.assumptions
                and claim.content
                == render_dynamic(computation, {s.evidence_id: s.label for s in sources})
            )
            self._check(
                result,
                "derived_statement",
                "pass" if exact else "fail",
                "derived_statement_matches" if exact else "derived_statement_mismatch",
            )
        else:
            # Digits in a conclusion must occur in the disclosed inputs/results or
            # periods. Semantic critics still check attribution and interpretation.
            from .numeric import NUMBER, parse_number

            allowed = {Decimal(s.value) for s in sources}
            allowed.update(Decimal(y) for s in sources for y in re.findall(r"\d{4}", s.period))
            if computation:
                allowed.update(Decimal(s.result) for s in computation.steps)
                allowed.update(
                    Decimal(s.result).quantize(Decimal("0.01")) for s in computation.steps
                )
            # Statement identifiers (B02/B03, note IDs) are not monetary values.
            # Still bind a value directly followed by its currency, e.g. 100VND.
            numbers = [parse_number(n) for n in re.findall(r"(?<!\w)" + NUMBER, claim.content)]
            if any(n not in allowed for n in numbers):
                self._check(result, "numeric_binding", "fail", "reasoning_unbound_number")
            units = {s.unit for s in sources} | (
                {s.unit for s in computation.steps} if computation else set()
            )
            if (
                re.search(r"%|phần trăm", claim.content, re.IGNORECASE) and "percent" not in units
            ) or any(unit not in units for unit in re.findall(r"\b(?:VND|USD)\b", claim.content)):
                self._check(result, "numeric_binding", "fail", "reasoning_unbound_unit")
            _, positive = _limitation_remainder(fold(claim.content))
            quantitative_relation = re.search(
                r"\b(?:(?:ty le|ty so|he so|ratio).{0,35}\b(?:la|dat|bang|tang|giam)|lon hon|nho hon|cao hon|thap hon|vuot)\b",
                positive,
            )
            if (
                quantitative_relation
                and not computation
                and not any(s.calculation for s in sources)
            ):
                self._check(result, "dynamic_calculation", "fail", "reasoning_calculation_required")
        if proof.claim_type == "conditional_inference":
            self._check(
                result,
                "conditional_assumptions",
                "undetermined",
                "conditional_inference_is_not_verified_fact",
            )
        self._citations(
            claim,
            result,
            list({c.model_dump_json(): c for s in sources for c in s.citations}.values()),
            claim.fact_references,
        )

    def _context(
        self,
        batch,
        claim,
        result,
        *,
        company,
        document,
        snapshot,
        period,
        period_type,
        scope,
        refs,
        assertion,
        prior=None,
    ):
        def add(*args, **kw):
            return self._check(
                result, *args, kind="context_scope_snapshot_mismatch", refs=refs, **kw
            )

        expected = dict(
            company_id=company,
            document_id=document,
            snapshot_id=snapshot,
            period=period,
            period_type=period_type,
        )
        observed = {
            k: getattr(claim, k) for k in ("company_id", "document_id", "snapshot_id", "period")
        }
        mismatch = [k for k, v in observed.items() if v and expected[k] and v != expected[k]]
        missing = [k for k, v in observed.items() if not v or not expected[k]]
        requested_periods = comparison_periods(batch.question)
        if requested_periods and period not in requested_periods:
            mismatch.append("requested_comparison_period")
        for field in ("company_id", "document_id", "snapshot_id", "period"):
            requested = getattr(batch.context, field)
            if (
                field == "period"
                and period in requested_periods
                and (requested is None or requested in requested_periods)
            ):
                continue
            if (
                requested is not None
                and expected[field] is not None
                and requested != expected[field]
            ):
                mismatch.append("requested_" + field)
        # A batch can legitimately contain several years. The explicit period above
        # is a guard; reporting_year is only a guard for single-year batches.
        years = {c.period[:4] for c in batch.claims}
        if (
            batch.context.reporting_year is not None
            and len(years) == 1
            and period
            and str(batch.context.reporting_year) != period[:4]
        ):
            mismatch.append("requested_reporting_year")
        if assertion:
            if assertion.period and period and assertion.period != period:
                mismatch.append("content_period")
            if assertion.period_type and period_type and assertion.period_type != period_type:
                mismatch.append("content_period_type")
            if assertion.prior_period and assertion.prior_period != prior:
                mismatch.append("content_prior_period")
        add(
            "context",
            "fail" if mismatch else "undetermined" if missing else "pass",
            "context_mismatch" if mismatch else "context_missing" if missing else "context_matches",
            expected=expected,
            observed={
                **observed,
                "mismatches": mismatch,
                "missing": missing,
                "content_period": assertion.period if assertion else None,
            },
        )
        add(
            "content_period",
            "fail"
            if assertion and assertion.period and assertion.period != period
            else "pass"
            if assertion and assertion.period
            else "undetermined",
            "content_period_mismatch"
            if assertion and assertion.period and assertion.period != period
            else "content_period_matches"
            if assertion and assertion.period
            else "content_period_unbound",
            expected={"period": period},
            observed={"period": assertion.period if assertion else None},
        )
        text = fold(claim.content)
        stated = {
            s
            for s, token in (("separate", "rieng le"), ("consolidated", "hop nhat"))
            if token in text
        }
        requested = batch.context.reporting_scope
        if requested:
            stated.add(requested)
        if scope.status == "resolved":
            failed = bool(stated - {scope.reporting_scope})
            add(
                "reporting_scope",
                "fail" if failed else "pass",
                "reporting_scope_mismatch" if failed else "reporting_scope_matches",
                expected={"scope": scope.reporting_scope},
                observed={"scopes": sorted(stated)},
            )
        else:
            result.caveats.extend(["reporting_scope_unresolved", *scope.reasons])
            add(
                "reporting_scope",
                "undetermined",
                "reporting_scope_unresolved",
                observed={"status": scope.status, "requested_scopes": sorted(stated)},
            )
        contexts = {
            (r.observation.document_id, r.observation.snapshot_id) for r in refs if r.observation
        }
        if len(contexts) > 1:
            add("cross_document", "undetermined", "D03_B10_cross_document_comparability_blocked")
        else:
            add("cross_document", "not_applicable", "single_document_context")

    def _citations(self, claim, result, citations, refs):
        def add(*args, **kw):
            return self._check(result, *args, refs=refs, citations=citations, **kw)

        if not claim.citations or not citations:
            add("provenance", "undetermined", "citations_missing")
            return
        bad = [c for c in claim.citations if c not in citations]
        missing = [c for c in citations if c not in claim.citations]
        add(
            "provenance",
            "fail" if bad else "undetermined" if missing else "pass",
            "citation_identity_or_source_mismatch"
            if bad
            else "citation_lineage_incomplete"
            if missing
            else "citation_structure_matches",
            kind="context_scope_snapshot_mismatch",
            observed={"unexpected": len(bad), "missing": len(missing)},
        )
        result.caveats.extend(c for citation in citations for c in citation.limitations)

    def _numeric(self, result, assertion, *, target, value, unit, scale, refs):
        if assertion is None:
            self._check(
                result,
                "numeric",
                "undetermined",
                "numeric_assertion_not_unambiguously_bound",
                refs=refs,
            )
            return
        if target is None:
            self._check(result, "numeric", "undetermined", "canonical_item_unresolved", refs=refs)
            return
        if assertion.target != target:
            self._check(
                result,
                "item",
                "fail",
                "financial_item_mismatch",
                kind="context_scope_snapshot_mismatch",
                refs=refs,
                expected={"target": target},
                observed={"target": assertion.target},
            )
            self._check(
                result, "numeric", "undetermined", "numeric_item_binding_mismatch", refs=refs
            )
            return
        self._check(result, "item", "pass", "financial_item_matches", refs=refs)
        if value is None or unit is None or scale is None:
            self._check(
                result, "numeric", "undetermined", "canonical_numeric_context_missing", refs=refs
            )
            return
        # Values stay in their declared scale. No implicit conversion or rounding of facts.
        units_match = assertion.unit == unit and assertion.scale == scale
        self._check(
            result,
            "unit_scale",
            "pass" if units_match else "fail",
            "unit_scale_matches" if units_match else "currency_unit_scale_mismatch",
            kind="context_scope_snapshot_mismatch",
            refs=refs,
            expected={"unit": unit, "scale": str(scale)},
            observed={"unit": assertion.unit, "scale": str(assertion.scale)},
        )
        matches = assertion.value == value
        self._check(
            result,
            "numeric",
            "pass" if matches else "fail",
            "numeric_matches_independent_source" if matches else "numeric_value_mismatch",
            kind="numeric_value_mismatch",
            refs=refs,
            expected={"value": str(value)},
            observed={"value": str(assertion.value)},
        )

    def _fact(self, batch, claim, result, assertion):
        refs = claim.fact_references

        def add(*args, **kw):
            return self._check(result, *args, refs=refs, **kw)

        if len(refs) != 1 or refs[0].kind != "fact":
            add("fact_reference", "undetermined", "single_fact_reference_required")
            add("numeric", "undetermined", "independent_fact_unavailable")
            if (
                len(
                    {
                        (r.observation.document_id, r.observation.snapshot_id)
                        for r in refs
                        if r.observation
                    }
                )
                > 1
            ):
                add(
                    "cross_document", "undetermined", "D03_B10_cross_document_comparability_blocked"
                )
            return
        identity = refs[0].observation
        retrieved = self._retrieval.get_financial_fact(
            GetFinancialFactRequest(
                document_id=identity.document_id,
                snapshot_id=identity.snapshot_id,
                local_observation_id=identity.local_id,
            )
        )
        result.caveats.extend(retrieved.caveats)
        if retrieved.status != "found" or len(retrieved.matches) != 1:
            add(
                "fact_reference",
                "fail" if retrieved.status == "conflicted" else "undetermined",
                "canonical_fact_conflicted"
                if retrieved.status == "conflicted"
                else "independent_fact_unavailable",
                observed={"reasons": retrieved.reasons},
            )
            add("numeric", "undetermined", "independent_fact_unavailable")
            return
        match = retrieved.matches[0]
        fact = match.record
        add("fact_reference", "pass", "exact_canonical_fact_resolved", citations=match.citations)
        consistency = assess_fact_consistency(fact)
        missing_structure = any(
            i.code
            in {
                "missing_provenance",
                "missing_source_identity",
                "unresolved_source_reference",
                "missing_observation_identity",
            }
            for i in consistency.issues
        )
        add(
            "source_structure",
            "fail"
            if consistency.status == "inconsistent"
            else "undetermined"
            if missing_structure
            else "pass",
            "canonical_source_inconsistent"
            if consistency.status == "inconsistent"
            else "canonical_source_structure_missing"
            if missing_structure
            else "canonical_source_structure_checked",
            observed={"issues": [i.code for i in consistency.issues]},
        )
        currency, unit = fact.context.currency, fact.value.unit
        add(
            "canonical_currency",
            "undetermined" if not currency or not unit else "pass" if currency == unit else "fail",
            "canonical_currency_missing"
            if not currency or not unit
            else "canonical_currency_matches"
            if currency == unit
            else "canonical_currency_conflict",
            kind="context_scope_snapshot_mismatch",
            expected={"currency": currency},
            observed={"unit": unit},
        )
        self._context(
            batch,
            claim,
            result,
            company=fact.company_id,
            document=fact.document_id,
            snapshot=fact.snapshot_id,
            period=fact.context.period,
            period_type=fact.context.period_type,
            scope=match.reporting_scope,
            refs=refs,
            assertion=assertion,
        )
        self._citations(claim, result, match.citations, refs)
        self._numeric(
            result,
            assertion,
            target=fact.canonical_item_id,
            value=fact.value.normalized_value if fact.value.status == "resolved" else None,
            unit=fact.value.unit,
            scale=fact.context.scale,
            refs=refs,
        )
        decisions = [q.decision for q in fact.quality_context if q.task_type == "direct_qa"]
        for q in fact.quality_context:
            result.caveats.extend([q.decision, *q.caveats, *[i.code for i in q.issues]])
        result.caveats.extend(i.code for i in fact.resolution_issues)
        bad = (
            match.display_status != "display_with_caveat"
            or any(d in {"conflicted", "insufficient"} for d in decisions)
            or match.source_review.status != "found"
            or any(
                view.status in {"source_missing", "source_inconsistent"}
                for view in match.source_review.matches
            )
        )
        add(
            "quality",
            "undetermined" if bad or not decisions else "pass",
            "source_quality_insufficient_or_conflicted"
            if bad
            else "source_quality_missing"
            if not decisions
            else "source_quality_caveats_preserved",
            kind="source_quality_limitation",
            observed={"decisions": decisions, "source_review_status": match.source_review.status},
        )
        # Candidate copies are untrusted even if their prose happens to be correct.
        for evidence in claim.supporting_evidence:
            if evidence.kind != "fact" or evidence.reference != refs[0]:
                add("supporting_fact", "fail", "supporting_fact_reference_mismatch")
                continue
            expected = dict(
                company_id=fact.company_id,
                document_id=fact.document_id,
                snapshot_id=fact.snapshot_id,
                period=fact.context.period,
                canonical_item_id=fact.canonical_item_id,
                unit=fact.value.unit,
                scale=str(fact.context.scale) if fact.context.scale is not None else None,
                value=str(fact.value.normalized_value)
                if fact.value.normalized_value is not None
                else None,
            )
            observed = {k: getattr(evidence, k) for k in expected}
            # Decimal representation differences (e.g. 1 vs 1.0) are harmless.
            fields = [
                k
                for k in expected
                if k not in {"value", "scale"}
                and expected[k] is not None
                and expected[k] != observed[k]
            ]
            fields += [
                k
                for k in ("value", "scale")
                if expected[k] is not None and not _decimal_equal(observed[k], expected[k])
            ]
            if evidence.citations != match.citations:
                fields.append("citations")
            add(
                "supporting_fact",
                "fail"
                if fields
                else "undetermined"
                if any(v is None for v in expected.values())
                else "pass",
                "supporting_fact_mismatch"
                if fields
                else "supporting_fact_context_missing"
                if any(v is None for v in expected.values())
                else "supporting_fact_matches_canonical",
                expected=expected,
                observed=observed,
            )

    def _metric(self, batch, claim: CandidateClaim, result, assertion):
        refs = claim.fact_references

        def add(*args, **kw):
            return self._check(result, *args, refs=refs, **kw)

        if len(claim.metric_ids) != 1:
            add("formula", "undetermined", "single_metric_reference_required")
            add("numeric", "undetermined", "independent_calculation_unavailable")
            return
        metric_id = claim.metric_ids[0]
        # Resolve by independent ID first, then compare claim scope; using the
        # candidate's incorrect guards would hide a provable identity mismatch.
        expected = self._calculator.calculate_financial_metric(
            CalculateFinancialMetricRequest(metric_id=metric_id)
        )
        result.caveats.extend(expected.caveats)
        if expected.status != "computed":
            add(
                "formula",
                "undetermined",
                "independent_calculation_unavailable",
                observed={"status": expected.status, "reasons": expected.reasons},
            )
            add("numeric", "undetermined", "independent_calculation_unavailable")
            return
        if expected.formula_id not in APPROVED_FORMULAS:
            add("formula", "undetermined", "formula_not_approved")
            return
        evidence, trace = expected.evidence, expected.trace
        add(
            "quality",
            "pass",
            "approved_calculation_gates_and_caveats_preserved",
            kind="source_quality_limitation",
        )
        period = evidence.record.request.operand_periods[PERIOD_ROLES[expected.formula_id]]
        operand = next(o for o in trace.operands if o.role == PERIOD_ROLES[expected.formula_id])
        self._context(
            batch,
            claim,
            result,
            company=operand.company_id,
            document=expected.document_id,
            snapshot=expected.snapshot_id,
            period=period,
            period_type=operand.context.period_type,
            scope=evidence.reporting_scope,
            refs=refs,
            assertion=assertion,
            prior=evidence.record.request.operand_periods.get("prior_revenue"),
        )
        self._citations(claim, result, evidence.citations, refs)
        self._numeric(
            result,
            assertion,
            target=expected.formula_id,
            value=Decimal(expected.result),
            unit=expected.output_unit,
            scale=Decimal(1),
            refs=refs,
        )
        bound = [o.observation for o in trace.operands]
        supplied = [r.observation for r in refs if r.kind == "fact"]
        add(
            "operand_references",
            "pass"
            if sorted(map(str, bound)) == sorted(map(str, supplied)) and len(refs) == len(bound)
            else "fail",
            "operand_references_match"
            if set(bound) == set(supplied) and len(refs) == len(bound)
            else "operand_references_mismatch",
        )
        calc = claim.calculation
        if calc is None:
            add("formula", "undetermined", "calculation_evidence_missing")
            return
        request_matches = (
            calc.request.metric_id == metric_id
            and calc.request.document_id in {None, expected.document_id}
            and calc.request.snapshot_id in {None, expected.snapshot_id}
        )
        add(
            "calculation_request",
            "pass" if request_matches else "fail",
            "calculation_request_matches" if request_matches else "calculation_request_mismatch",
            kind="context_scope_snapshot_mismatch",
        )
        for name, fields in (
            (
                "formula",
                (
                    "metric_id",
                    "document_id",
                    "snapshot_id",
                    "formula_id",
                    "formula_version",
                    "formula_digest",
                    "output_unit",
                    "status",
                ),
            ),
            ("calculation_result", ("result",)),
        ):
            actual = {k: getattr(calc, k) for k in fields}
            wanted = {k: getattr(expected, k) for k in fields}
            differences = [k for k in fields if actual[k] is not None and actual[k] != wanted[k]]
            missing = any(v is None for v in actual.values())
            add(
                name,
                "fail" if differences else "undetermined" if missing else "pass",
                name + "_matches_independent_calculation"
                if actual == wanted
                else name + "_missing"
                if missing and not differences
                else name + "_mismatch",
                kind="formula_calculation_mismatch",
                expected=wanted,
                observed=actual,
            )
        for name, actual, wanted in (
            ("calculation_trace", calc.trace, trace),
            ("calculation_lineage", calc.evidence, evidence),
        ):
            missing = actual is None or (
                name == "calculation_lineage" and actual.reviewed_lineage.lineage is None
            )
            wanted_trace = {"metric_id": metric_id, "formula_digest": expected.formula_digest}
            actual_trace = {"independent_payload_equal": actual == wanted}
            if name == "calculation_trace" and actual != wanted:
                wanted_trace["trace"] = wanted.model_dump(mode="json")
                actual_trace["trace"] = actual.model_dump(mode="json") if actual else None
            add(
                name,
                "undetermined" if missing else "pass" if actual == wanted else "fail",
                name + "_missing"
                if missing
                else name + "_matches"
                if actual == wanted
                else name + "_mismatch",
                kind="formula_calculation_mismatch",
                expected=wanted_trace,
                observed=actual_trace,
                citations=evidence.citations,
            )
        for supporting in claim.supporting_evidence:
            if supporting.kind != "metric":
                add("supporting_metric", "fail", "supporting_metric_kind_mismatch")
                continue
            mismatch = (
                supporting.reference.record_id != metric_id
                or supporting.value != expected.result
                or (
                    supporting.calculation is not None
                    and not _same_calculation(supporting.calculation, expected)
                )
                or supporting.unit != expected.output_unit
                or supporting.scale != "1"
                or supporting.period != period
                or supporting.company_id != operand.company_id
                or supporting.document_id != expected.document_id
                or supporting.snapshot_id != expected.snapshot_id
                or supporting.operand_periods != evidence.record.request.operand_periods
                or supporting.citations != evidence.citations
            )
            add(
                "supporting_metric",
                "fail"
                if mismatch
                else "undetermined"
                if supporting.calculation is None
                else "pass",
                "supporting_metric_mismatch"
                if mismatch
                else "supporting_calculation_missing"
                if supporting.calculation is None
                else "supporting_metric_matches",
                kind="formula_calculation_mismatch",
            )
