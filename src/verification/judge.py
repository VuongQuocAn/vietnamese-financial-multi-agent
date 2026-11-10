"""Deterministic, evidence-first decision policy. Never calls tools or providers."""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .decision_contracts import (
    DecisionError,
    InvestigationRequirement,
    RevisionProposal,
    VerificationDecisionRecord,
    VerificationDecisionResult,
    VerificationDecisionTrace,
)
from .evidence_critic import _numeric_scope
from .financial_logic_critic import FinancialLogicCritic
from .logic_rules import assertion_spans, classify, context_gate
from .numeric import NUMBER, extract_assertion, parse_number
from .validation_contracts import validation_result_digest, verification_input_digest

COMMON_CHECKS = {
    "handoff_structure",
    "numeric",
    "item",
    "unit_scale",
    "context",
    "provenance",
    "quality",
}
FACT_CHECKS = {"fact_reference", "source_structure", "canonical_currency", "supporting_fact"}
METRIC_CHECKS = {
    "formula",
    "calculation_request",
    "calculation_result",
    "calculation_trace",
    "calculation_lineage",
    "operand_references",
    "supporting_metric",
}


def required_checks(claim):
    if claim.reasoning:
        required = COMMON_CHECKS.copy()
        if any(s.kind == "fact" for s in claim.supporting_evidence):
            required |= FACT_CHECKS
        if any(s.kind == "metric" for s in claim.supporting_evidence):
            required |= METRIC_CHECKS
        if claim.reasoning.calculation:
            required.add("dynamic_calculation")
        if claim.reasoning.claim_type == "derived_fact":
            required.add("derived_statement")
        return required
    return COMMON_CHECKS | (METRIC_CHECKS if claim.metric_ids or claim.calculation else FACT_CHECKS)


def _unique(items):
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _logic_binding(claim, validation, evidence, logic):
    if logic.content != claim.content or logic.conflict_ids != claim.provenance.conflict_ids:
        return "logic_claim_identity_mismatch"
    expected = [
        (a.assertion_id if len(spans) == 1 else f"{a.assertion_id}.{i + 1}", span, a)
        for a in evidence.assertions
        for spans in [assertion_spans(a.content)]
        for i, span in enumerate(spans)
    ]
    # Failed upstream assessment may contain a whole-claim placeholder. It is
    # still non-accepting, with the original structured errors retained below.
    if logic.errors:
        return None
    if len(logic.assertions) != len(expected):
        return "logic_assertion_coverage_mismatch"
    refs = [e.reference for e in evidence.evidence]
    eids = {e.evidence_id for e in evidence.evidence if e.available}
    citations = [c for e in evidence.evidence for c in e.citations]
    if any(c not in citations or c not in claim.citations for c in evidence.supporting_citations):
        return "evidence_citation_binding_mismatch"
    for finding, (aid, content, support) in zip(logic.assertions, expected, strict=True):
        if (
            finding.candidate_id != claim.candidate_id
            or finding.assertion_id != aid
            or finding.content != content
            or finding.validation_checks != validation.checks
            or finding.support_findings != [support]
            or any(r not in refs for r in finding.references)
            or set(finding.evidence_ids) - eids
        ):
            return "logic_assertion_binding_mismatch"
        rule = classify(content, claim, validation.checks)
        if finding.status == "not_applicable" and (rule is None or rule[0] != "not_applicable"):
            return "reasoning_cannot_be_not_applicable"
    return None


class VerificationJudge:
    """Consumes exact M6 results; legacy pairing is explicit and never backfilled."""

    def decide(
        self,
        batch,
        validation,
        evidence,
        logic,
        *,
        validated_batch=None,
        evidence_batch=None,
        evidence_validation=None,
    ) -> VerificationDecisionResult:
        batch, validation, evidence, logic = deepcopy((batch, validation, evidence, logic))
        trace = VerificationDecisionTrace(
            source_result_sha256=batch.source_result_sha256,
            verification_input_sha256=verification_input_digest(batch),
            validation_result_sha256=validation_result_digest(validation),
            evidence_result_sha256=verification_input_digest(evidence),
            logic_result_sha256=verification_input_digest(logic),
            legacy_pairing=validation.verification_input_sha256 is None
            or evidence.verification_input_sha256 is None
            or evidence.validation_result_sha256 is None,
        )
        result = VerificationDecisionResult(
            trace=trace,
            conflicts=batch.conflicts,
            caveats=sorted(
                set([*batch.caveats, *validation.caveats, *evidence.caveats, *logic.caveats])
            ),
        )
        binding = FinancialLogicCritic._binding_error(
            batch,
            validation,
            evidence,
            validated_batch,
            evidence_batch,
            evidence_validation,
        )
        if not re.fullmatch(r"[0-9a-f]{64}", batch.source_result_sha256):
            binding = "malformed_source_identity"
        if (
            logic.source_result_sha256 != batch.source_result_sha256
            or logic.verification_input_sha256 != trace.verification_input_sha256
            or logic.validation_result_sha256 != trace.validation_result_sha256
            or logic.evidence_result_sha256 != trace.evidence_result_sha256
            or logic.conflicts != batch.conflicts
        ):
            binding = binding or "logic_upstream_identity_mismatch"
        ids = [c.candidate_id for c in logic.claims]
        if len(ids) != len(set(ids)) or set(ids) != {c.candidate_id for c in batch.claims}:
            binding = binding or "logic_candidate_identity_mismatch"
        if binding:
            result.errors.append(DecisionError(code=binding))
        vals = {c.candidate_id: c for c in validation.claims}
        supports = {c.candidate_id: c for c in evidence.claims}
        logics = {c.candidate_id: c for c in logic.claims}
        for claim in batch.claims:
            val, support, reasoning = (m.get(claim.candidate_id) for m in (vals, supports, logics))
            record = VerificationDecisionRecord(
                candidate_id=claim.candidate_id,
                original_claim=claim,
                decision="ABSTAIN",
                reason_codes=[],
                validation=val,
                evidence=support,
                logic=reasoning,
                supporting_references=_unique(
                    [
                        *claim.fact_references,
                        *claim.provenance.supporting_references,
                        *[e.reference for e in claim.supporting_evidence],
                    ]
                ),
                supporting_citations=_unique(
                    [
                        *claim.citations,
                        *(support.supporting_citations if support else []),
                    ]
                ),
                caveats=sorted(
                    set(
                        [
                            *result.caveats,
                            *claim.caveats,
                            *claim.missing_information,
                            *(val.caveats if val else []),
                            *(support.caveats if support else []),
                            *(reasoning.caveats if reasoning else []),
                            *[c for e in (support.evidence if support else []) for c in e.caveats],
                            *[
                                c
                                for a in (reasoning.assertions if reasoning else [])
                                for c in a.caveats
                            ],
                        ]
                    )
                ),
                limitations=["source_bound_verification_is_not_an_independent_financial_audit"],
                trace=trace.model_copy(deep=True),
            )
            result.claims.append(record)
            error = binding
            if not error:
                error = FinancialLogicCritic._claim_binding_error(claim, val, support)
                error = error or _logic_binding(claim, val, support, reasoning)
            if error:
                record.errors.append(DecisionError(code=error, candidate_id=claim.candidate_id))
                self._investigate(
                    record, error, "Supply original paired inputs and fresh M6-02/03/04 results."
                )
                continue
            upstream_errors = [
                e
                for upstream in (evidence, logic)
                for e in upstream.errors
                if e.candidate_id in {None, claim.candidate_id}
            ] + [*support.errors, *reasoning.errors]
            record.errors.extend(
                DecisionError(code=e.code, candidate_id=e.candidate_id) for e in upstream_errors
            )
            if any(e.stage == "consistency" for e in upstream_errors):
                self._investigate(
                    record,
                    "upstream_consistency_error",
                    "Refresh consistent M6-02/03/04 assessments.",
                )
                continue
            record.trace.passed_gates.append("input_identity")
            self._decide_claim(batch, record)
        return result

    @staticmethod
    def _investigate(record, reason, action):
        record.decision = "INVESTIGATE"
        record.reason_codes.append(reason)
        record.unresolved_blockers.append(reason)
        record.investigations.append(
            InvestigationRequirement(
                reason_code=reason,
                action=action,
                recheck_condition="Resolve the named dependency, then rerun M6-02, M6-03 and M6-04 on the exact input.",
                references=record.supporting_references,
            )
        )

    def _decide_claim(self, batch, record):
        claim, val, support, logic = (
            record.original_claim,
            record.validation,
            record.evidence,
            record.logic,
        )
        required = required_checks(claim)
        record.trace.required_checks = sorted(required)
        checks = val.checks
        failures = [c for c in checks if c.status == "fail"]
        record.unresolved_blockers.extend(c.reason_code for c in failures)
        conflicts = [
            c.conflict_id for c in batch.conflicts if claim.candidate_id in c.candidate_ids
        ]
        if conflicts or claim.provenance.conflict_ids:
            self._investigate(
                record,
                "unresolved_candidate_conflict",
                "Resolve the retained candidate conflict without selecting a winner by confidence or order.",
            )
            return
        gate = context_gate(claim, val, support)
        if gate:
            self._investigate(
                record,
                gate,
                "Resolve document/snapshot/reporting scope and approved comparability; D03-B10 remains blocked.",
            )
            return
        if any(
            c.reason_code
            in {
                "canonical_fact_conflicted",
                "canonical_source_inconsistent",
                "canonical_currency_conflict",
            }
            for c in checks
        ):
            self._investigate(
                record,
                "canonical_source_conflict",
                "Resolve the exact canonical source inconsistency before proposing any correction.",
            )
            return
        record.trace.passed_gates.append("conflict_comparability")
        # A numeric correction is allowed only when every other required check
        # is PASS, with an exact source, no scope assertions and no other FAIL.
        if failures:
            proposal = self._numeric_revision(record)
            if proposal:
                record.decision, record.revision = "REVISE", proposal
                record.reason_codes = proposal.reason_codes
                return
            self._investigate(
                record,
                "financial_checks_failed",
                "Inspect the retained failing numeric/formula/context/provenance checks against their exact references.",
            )
            return
        missing = sorted(key for key in required if not any(c.check_id == key for c in checks))
        missing.extend(
            key
            for key in ("reporting_scope", "cross_document", "candidate_conflict")
            if not any(c.check_id == key for c in checks)
        )
        unproven = [c.reason_code for c in checks if c.check_id in required and c.status != "pass"]
        # All occurrences must pass: a later PASS never overrides an earlier FAIL/unknown.
        extras = [
            c.reason_code
            for c in checks
            if c.status == "undetermined"
            and c.check_id not in required | {"semantic_conclusion", "reporting_scope"}
        ]
        scope_unknown = [
            c for c in checks if c.check_id == "reporting_scope" and c.status == "undetermined"
        ]
        if scope_unknown:
            record.caveats = sorted(set([*record.caveats, "reporting_scope_unresolved"]))
        blockers = [*("required_check_missing:" + k for k in missing), *unproven, *extras]
        if blockers:
            record.unresolved_blockers.extend(blockers)
            if record.supporting_references:
                self._investigate(
                    record,
                    "required_financial_checks_unproven",
                    "Retrieve/review the named references and complete the missing required financial checks.",
                )
            else:
                record.reason_codes = ["financial_evidence_unavailable"]
            return
        record.trace.passed_gates.append("financial_checks")
        full_evidence = (
            support.status == "supported"
            and bool(support.assertions)
            and all(
                a.status == "supported" and a.evidence_ids and not a.missing
                for a in support.assertions
            )
            and bool(support.evidence)
            and all(e.available and e.citations for e in support.evidence)
            and not support.unsupported_portions
            and not support.errors
        )
        full_logic = (
            bool(logic.assertions)
            and all(
                a.status in {"consistent", "not_applicable"} and not a.missing_evidence
                for a in logic.assertions
            )
            and not logic.errors
        )
        if full_evidence and full_logic and not record.errors:
            record.decision = "ACCEPT"
            record.reason_codes = ["whole_claim_supported_with_required_checks"]
            record.trace.passed_gates.extend(
                ["whole_claim_evidence", "applicable_financial_reasoning"]
            )
            return
        record.unresolved_blockers.extend(
            _unique(
                [
                    *[r for a in support.assertions if a.status != "supported" for r in a.reasons],
                    *[
                        r
                        for a in logic.assertions
                        if a.status not in {"consistent", "not_applicable"}
                        for r in a.reason_codes
                    ],
                    *[e.code for e in record.errors],
                ]
            )
        )
        proposal = self._prefix_revision(record)
        if proposal:
            record.decision, record.revision = "REVISE", proposal
            record.reason_codes = proposal.reason_codes
        elif not support.evidence or not record.supporting_references or record.errors:
            record.reason_codes = [
                "required_semantic_assessment_unavailable"
                if record.errors
                else "no_supported_evidence_or_safe_recovery"
            ]
        elif any(a.missing for a in support.assertions) or any(
            a.missing_evidence for a in logic.assertions
        ):
            self._investigate(
                record,
                "additional_evidence_required",
                "Retrieve the explicitly missing assertion evidence/premises identified by the Critics.",
            )
        else:
            record.reason_codes = ["unsupported_claim_without_safe_revision"]

    @staticmethod
    def _prefix_revision(record):
        claim, evidence, logic = record.original_claim, record.evidence, record.logic
        numeric, tail = _numeric_scope(claim.content)
        if (
            not numeric
            or not tail
            or not any(
                a.content == numeric and a.status == "supported" and a.check_references
                for a in evidence.assertions
            )
        ):
            return None
        prefix_logic = [a for a in logic.assertions if a.content == numeric]
        if not prefix_logic or any(a.status != "not_applicable" for a in prefix_logic):
            return None
        return RevisionProposal(
            parent_candidate_id=claim.candidate_id,
            reason_codes=["remove_unverified_conclusion_keep_supported_numeric_prefix"],
            supported_portions=[numeric],
            unsupported_portions=[claim.content[len(numeric) :].lstrip(" ,.;\n")],
            content=numeric.rstrip(".;") + ".",
            kind="approved_metric" if claim.metric_ids else "fact",
        )

    @staticmethod
    def _numeric_revision(record):
        claim, checks = record.original_claim, record.validation.checks
        failures = [c for c in checks if c.status == "fail"]
        if len(failures) != 1 or failures[0].check_id != "numeric":
            return None
        required = required_checks(claim) - {"numeric"}
        if any(not any(c.check_id == k and c.status == "pass" for c in checks) for k in required):
            return None
        if any(c.check_id in required and c.status != "pass" for c in checks):
            return None
        if any(
            c.status == "undetermined"
            and c.check_id not in {"reporting_scope", "semantic_conclusion"}
            for c in checks
        ):
            return None
        numeric, tail = _numeric_scope(claim.content)
        if not numeric or tail:
            return None
        # Replace exactly one parser-bound value token in the original wording.
        assertion = extract_assertion(numeric)
        try:
            expected = Decimal(failures[0].expected["value"])
            if not expected.is_finite():
                return None
        except (KeyError, TypeError, InvalidOperation):
            return None
        positions = [
            m for m in re.finditer(NUMBER, numeric) if parse_number(m[0]) == assertion.value
        ]
        proposals = []
        for match in positions:
            proposed = (
                numeric[: match.start()]
                + format(expected, "f").replace(".", ",")
                + numeric[match.end() :]
            )
            parsed = extract_assertion(proposed)
            if (
                parsed
                and parsed.value == expected
                and parsed.__dict__ | {"value": assertion.value} == assertion.__dict__
            ):
                proposals.append(proposed.rstrip(".;") + ".")
        if len(proposals) != 1:
            return None
        return RevisionProposal(
            parent_candidate_id=claim.candidate_id,
            reason_codes=["exact_canonical_numeric_correction"],
            supported_portions=["canonical_value:" + str(expected)],
            unsupported_portions=[numeric],
            content=proposals[0],
            kind=claim.kind,
        )
