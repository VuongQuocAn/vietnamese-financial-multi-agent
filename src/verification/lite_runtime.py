"""One deterministic pass, at most one semantic batch, no critics or revision."""

import hashlib
import json
import re
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from ..agents.planner_contracts import PlannerLLMMetadata
from ..agents.specialist_common import ReasoningProof, _number, source_projection
from ..core.llm_contracts import (
    GenerationParameters,
    LLMRequest,
    Message,
    ModelIdentity,
    OutputSpec,
    RequestConstraints,
)
from ..core.prompt_payload import compact_prompt
from ..evidence.retrieval import EvidenceCitation
from ..tools.python_execution import PythonExecutor
from .contracts import VerificationInput
from .decision_contracts import (
    LiteDecisionTrace,
    VerificationDecisionRecord,
    VerificationLoopResult,
)
from .evidence_context import EvidenceContextBuilder
from .evidence_obligations import (
    candidate_output,
    feedback,
    goal_binding_issue,
    goal_completion_issue,
    goal_context,
    goal_output_type,
    independent_candidate_output,
    numeric_question_binding,
    replay_obligations,
    supported_goals,
)
from .lite_contracts import (
    INDEPENDENT_VERIFIER_INSTRUCTION,
    QUESTION_COVERAGE_INSTRUCTION,
    QUESTION_OPERAND_INSTRUCTION,
    VERIFIER_INSTRUCTION,
    GoalSemanticVerdict,
    LiteProof,
    LiteProofV2,
    LiteVerificationHistory,
    LiteVerificationHistoryV2,
    SemanticVerdict,
    bind_question_slots,
    independent_question_coverage,
    independent_verifier_schema,
    question_completion,
    question_parts,
    semantic_output,
    verified_completion_refs,
    verifier_citations,
    verifier_output_schema,
)
from .numeric import NUMBER, NumericAssertion, extract_assertion
from .validation_contracts import ClaimValidationResult, ValidationResult, verification_input_digest
from .validators import DeterministicFinancialValidator


def semantic_payload(batch, claim, goal_context=None):
    """Stable digest input for existing ledger proofs. The model sees _semantic_row."""
    proof = claim.reasoning
    payload = dict(
        claim_id=claim.candidate_id,
        statement=claim.content,
        question=batch.question if goal_context is not None else batch.question[:1500],
        scope={
            k: getattr(claim, k) for k in ("company_id", "document_id", "snapshot_id", "period")
        },
        facts=[
            {
                k: getattr(s, k)
                for k in ("label", "canonical_item_id", "value", "unit", "scale", "period")
            }
            for s in claim.supporting_evidence
        ],
        calculations=[
            dict(
                formula=s.calculation.formula_id,
                result=s.calculation.result,
                unit=s.calculation.output_unit,
            )
            for s in claim.supporting_evidence
            if s.calculation
        ]
        + (
            [
                dict(operation=s.operation.model_dump(mode="json"), result=s.result, unit=s.unit)
                for s in proof.calculation.steps
            ]
            if proof and proof.calculation
            else []
        ),
        sources=[
            dict(evidence_id=s.evidence_id, **source_projection(s))
            for s in claim.supporting_evidence
        ],
        assumptions=proof.assumptions if proof else [],
        limitations=list(
            dict.fromkeys(
                [*claim.caveats, *claim.missing_information, *(proof.limitations if proof else [])]
            )
        ),
    )
    if goal_context is not None:
        from .evidence_obligations import semantic_goal_context

        payload["evidence_bindings"] = [
            dict(
                evidence_id=e.evidence_id,
                item=e.canonical_item_id,
                label=e.label,
                value=e.value,
                period=e.period,
                unit=e.unit,
                scale=e.scale,
            )
            for e in claim.supporting_evidence
        ]
        payload.update(semantic_goal_context(goal_context))
        payload["trusted_context"] = batch.context.model_dump(mode="json")
        payload["operand_bindings"] = (
            {
                key: operand.model_dump(mode="json")
                for key, operand in proof.calculation.operands.items()
            }
            if proof and proof.calculation
            else {}
        )
    if claim.python_execution:
        # Generation responses/diagnostic executions are trace, not semantic authority.
        record = claim.python_execution.execution
        payload["python_execution"] = dict(
            version=record["version"],
            execution_sha256=claim.python_execution.execution_sha256,
            # Exact citations/selectors are already bound in sources/observations;
            # keep source hashes, identities, parser/context and raw/base values here.
            operands={
                key: {k: v for k, v in row.items() if k not in {"citations", "selectors"}}
                for key, row in record["operands"].items()
            },
            execution=record["executions"][-1],
            output_key=claim.python_execution.output_key,
            rounding=record["rounding"],
            lineage=record["lineage"],
        )
    return payload


def payload_digest(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _semantic_row(proof, handle):
    """Project replayed financial inputs without copying workspace or ledger metadata."""
    claim = proof.batch.claims[0]
    context = getattr(proof, "goal_context", {})
    reasoning = claim.reasoning
    checks = proof.validation.claims[0].checks
    evidence, aliases = {}, {}

    def alias(key):
        return aliases.setdefault(key, f"E{len(aliases) + 1}")

    def locations(citations):
        rows = {}
        for c in citations:
            ref = c.source.reference
            page = ref.anchor.page
            key = (c.document_id, c.snapshot_id, page.page, c.pdf_page)
            row = rows.setdefault(
                key,
                dict(
                    document=f"{page.symbol}_{page.year}",
                    page=c.pdf_page if c.pdf_page is not None else page.page,
                    page_kind="PDF" if c.pdf_page is not None else "source",
                ),
            )
            if ref.source_pointer:
                pointers = row.setdefault("source_pointers", [])
                if ref.source_pointer not in pointers:
                    pointers.append(ref.source_pointer)
        return list(rows.values())

    for source in claim.supporting_evidence:
        evidence[alias(source.evidence_id)] = dict(
            item=source.canonical_item_id,
            label=source.label,
            period=source.period,
            value=source.value,
            unit=source.unit,
            scale=source.scale,
            company_id=source.company_id,
            observation=(
                source.reference.observation.model_dump(mode="json")
                if source.reference.observation
                else None
            ),
            sources=locations(source.citations),
            source_quality=list(
                dict.fromkeys(
                    [*source.caveats, *(note for c in source.citations for note in c.limitations)]
                )
            ),
        )

    def observe(rows):
        handles = []
        for row in rows:
            key = alias(row["evidence_id"])
            handles.append(key)
            citations = [EvidenceCitation.model_validate(c) for c in row["citations"]]
            evidence.setdefault(key, {k: row[k] for k in ("item", "label", "value", "unit")})
            evidence[key].update(
                header=row["header"],
                company_id=row["company_id"],
                observation=row["reference"].get("observation"),
                sources=locations(citations),
                source_quality=list(
                    dict.fromkeys(
                        [
                            *evidence[key].get("source_quality", []),
                            *row.get("caveats", []),
                            *(note for c in citations for note in c.limitations),
                        ]
                    )
                ),
                **{
                    k: row["context"][k]
                    for k in (
                        "period",
                        "scale",
                        "currency",
                        "period_type",
                        "reporting_scope",
                        "statement_type",
                    )
                    if k in row["context"]
                },
            )
        return handles

    selections, joins = [], []
    for result in context.get("task_results", {}).values():
        if "request_work" in result:
            observe(result.get("selected_observations", []))
        observe(
            [
                row
                for row in result.get("selected_observations", [])
                if row["evidence_id"] in aliases
            ]
        )
        coordination = result.get("coordination", {})
        if selection := coordination.get("selection"):
            selections.append(
                dict(
                    criteria=selection["selection"],
                    domain=observe(selection["domain"]),
                    selected=[alias(key) for key in selection["selected_ids"]],
                    ties=selection["ties"],
                    caveats=selection["caveats"],
                )
            )
        for join in coordination.get("joins", []):
            joins.append(
                dict(
                    left=observe(join["left"]),
                    right=observe(join["right"]),
                    pairs=[[alias(k) for k in pair] for pair in join["pairs"]],
                    keys=join["keys"],
                    status=join["status"],
                    caveats=join["caveats"],
                )
            )

    calculations = []
    if reasoning and reasoning.calculation:
        operations = {
            step.operation.operation_id: f"R{i}"
            for i, step in enumerate(reasoning.calculation.steps, 1)
        }
        for step in reasoning.calculation.steps:
            op = step.operation
            calculations.append(
                dict(
                    result_id=operations[op.operation_id],
                    operator=op.operator,
                    inputs=[
                        operations[key] if key in operations else alias(key) for key in op.inputs
                    ],
                    result=step.result,
                    unit=step.unit,
                    period_relation=op.period_relation,
                )
            )
    for source in claim.supporting_evidence:
        calc = source.calculation
        if calc and calc.trace:
            formula = calc.trace.formula
            calculations.append(
                dict(
                    result_id=alias(source.evidence_id),
                    expression=formula.expression,
                    multiplier=formula.output_multiplier,
                    operands=[
                        dict(
                            role=o.role,
                            value=o.value,
                            unit=o.unit,
                            period=o.context.period,
                            scale=o.context.scale,
                            label=o.context.raw_item_label,
                        )
                        for o in calc.trace.operands
                    ],
                )
            )

    summary = dict(
        source_facts=evidence,
        calculation_proof=calculations,
        deterministic_checks={
            status: list(
                dict.fromkeys(
                    c.check_id
                    for c in checks
                    if c.status == status and c.check_id != "semantic_conclusion"
                )
            )
            for status in ("pass", "fail", "undetermined")
        },
    )
    row = dict(
        claim_id=handle,
        evidence_summary=summary,
        statement=claim.content,
        selections=selections,
        joins=joins,
        assumptions=reasoning.assumptions if reasoning else [],
        limitations=list(
            dict.fromkeys(
                [
                    *claim.caveats,
                    *claim.missing_information,
                    *(reasoning.limitations if reasoning else []),
                ]
            )
        ),
    )
    if "candidate_need_refs" in context:
        summary["candidate_need_refs"] = context["candidate_need_refs"]
        replayed_tasks = {
            c.expected.get("task_id")
            for c in checks
            if c.status == "pass" and c.reason_code == "coordination_sources_replayed"
        }
        for tid, result in context["task_results"].items():
            sources = {s["handle"]: s["reference"] for s in result.get("source_context", [])}
            for eo_id, binding in result.get("need_bindings", {}).items():
                if binding["missing_inputs"] and binding["missing_scope"] == "need":
                    summary.setdefault("eo_limitations", []).append(
                        dict(eo_id=eo_id, task_id=tid, missing_inputs=binding["missing_inputs"])
                    )
                for key in binding["evidence_refs"]:
                    receipt_ids = [
                        receipt["result_id"]
                        for receipt in result.get("tool_results", [])
                        if receipt["result_id"] in binding["tool_result_ids"]
                        and eo_id in receipt["need_refs"]
                        and key in receipt["evidence_refs"]
                    ]
                    if not receipt_ids:
                        continue
                    link = dict(
                        eo_id=eo_id,
                        task_id=tid,
                        receipt_ids=receipt_ids,
                        sources_replayed=tid in replayed_tasks,
                    )
                    if (fact := evidence.get(aliases.get(key))) is not None:
                        fact.setdefault("eo_receipts", []).append(link)
                    elif key in sources:
                        summary.setdefault("document_receipts", []).append(
                            dict(source_id=key, source=sources[key], **link)
                        )
    # Keep unresolved semantic concerns, without replay diagnostics or duplicates.
    source_notes = {note for e in evidence.values() for note in e.get("source_quality", [])}
    row["limitations"] = list(
        dict.fromkeys(
            note
            for note in [
                *row["limitations"],
                *(
                    c.reason_code
                    for c in checks
                    if c.status in {"fail", "undetermined"} and c.check_id != "semantic_conclusion"
                ),
            ]
            if note not in source_notes
        )
    )
    if claim.python_execution:
        record = claim.python_execution.execution
        execution = record["executions"][-1]
        row["python_execution"] = dict(
            code=execution["code"],
            constants=execution["constants"],
            output_key=claim.python_execution.output_key,
            results=record["results"],
            operands={
                key: dict(evidence=alias(key), base_value=operand["base_value"])
                for key, operand in record["operands"].items()
            },
        )
    row["candidate_output"] = candidate_output(claim)
    summary["source_facts"] = {
        key: {k: v for k, v in e.items() if v not in (None, [], {})} for key, e in evidence.items()
    }
    row["evidence_summary"] = {k: v for k, v in summary.items() if v not in ([], {})}
    return {k: v for k, v in row.items() if v not in (None, [], {})}


def deterministic_state(claim, validation):
    checks = [c for c in validation.checks if c.check_id != "semantic_conclusion"]
    required = {"context", "provenance", "numeric", "quality", "lite_sources"}
    absent = not required <= {c.check_id for c in checks if c.status == "pass"}
    failed = [c.reason_code for c in checks if c.status == "fail"]
    missing = [
        c.reason_code
        for c in checks
        if c.status == "undetermined"
        and c.reason_code not in {"reporting_scope_unresolved", "canonical_mapping_missing"}
    ]
    if failed:
        return "ABSTAIN", sorted(set(failed))
    if absent or missing or not claim.citations or not claim.supporting_evidence:
        return "INVESTIGATE", sorted(set(missing or ["valid_source_required"]))
    if claim.status != "candidate":
        return "INVESTIGATE", ["candidate_insufficient_evidence"]
    derived = claim.reasoning and claim.reasoning.claim_type == "derived_fact"
    if claim.kind == "supported_interpretation" and not derived:
        return "SEMANTIC", []
    if any(c.check_id == "typed_assertion" and c.status == "pass" for c in checks):
        return "ACCEPT", ["deterministic_source_and_calculation_verified"]
    # Parser proves one numerical clause only. Any extra prose needs semantics.
    if not derived:
        assertion = extract_assertion(claim.content)
        if assertion is None:
            return "INVESTIGATE", ["numeric_statement_unbound"]
        for end in range(1, len(claim.content) + 1):
            if extract_assertion(claim.content[:end]) == assertion:
                if claim.content[end:].strip(" ,.;\n"):
                    return "SEMANTIC", []
                break
    return "ACCEPT", ["deterministic_source_and_calculation_verified"]


def _semantic_required(proof, state):
    claim = proof.batch.claims[0]
    return state == "SEMANTIC" or (
        state == "ACCEPT"
        and (
            bool(
                claim.calculation
                or claim.python_execution
                or claim.reasoning
                and claim.reasoning.calculation
            )
            or any(
                s.kind == "fact" and s.canonical_item_id is None for s in claim.supporting_evidence
            )
            or isinstance(proof, LiteProofV2)
            and any(
                r.get("coordination", {}).get("selection") or r.get("coordination", {}).get("joins")
                for r in proof.goal_context.get("task_results", {}).values()
            )
        )
    )


def direct_fact_goals(proof):
    """Bind a literal source fact to trusted Coordinator obligations, without NLP."""
    claim = proof.batch.claims[0]
    checked = proof.validation.claims[0]
    context = getattr(proof, "goal_context", {})
    if (
        deterministic_state(claim, checked)[0] != "ACCEPT"
        or _semantic_required(proof, "ACCEPT")
        or claim.kind != "fact"
        or claim.reasoning
        or claim.caveats
        or claim.missing_information
        or len(claim.supporting_evidence) != 1
        or not any(c.check_id == "typed_assertion" and c.status == "pass" for c in checked.checks)
        or not any(
            c.check_id == "quality" and c.observed.get("decisions") == ["usable"]
            for c in checked.checks
        )
        or any(
            c.status == "undetermined" and c.reason_code != "reporting_scope_unresolved"
            for c in checked.checks
        )
    ):
        return []
    source = claim.supporting_evidence[0]
    if (
        source.scale != "1"
        or source.caveats
        or proof.batch.caveats
        or any(c.limitations for c in source.citations)
    ):
        return []
    requirements = {r["requirement_id"]: r for r in context.get("local_requirements", [])}
    goals = []
    for rid in context.get("proposed_requirement_ids", []):
        r = requirements.get(rid, {})
        if (
            r.get("kind") != "fact"
            or not source.canonical_item_id
            or r.get("target_id") != source.canonical_item_id
            or r.get("period") != source.period
            or r.get("requested_unit") != source.unit
            or r.get("interpretation", False)
            or r.get("interpretation_topic")
            or r.get("depends_on")
            or r.get("aspect", "value") != "value"
            or r.get("answer_goal", "value") != "value"
            or r.get("reasoning_operations")
            or r.get("reasoning_periods")
            or set(r.get("required_indicators", [])) - {source.canonical_item_id}
        ):
            return []
        goals.append(rid)
    return list(dict.fromkeys(goals))


def decide(proof):
    batch = proof.batch
    claim = batch.claims[0]
    validation = proof.validation.claims[0]
    state, reasons = deterministic_state(claim, validation)
    needs_semantic = _semantic_required(proof, state)
    if needs_semantic or (
        state == "ACCEPT" and isinstance(proof, LiteProofV2) and not direct_fact_goals(proof)
    ):
        semantic = proof.semantic
        if (
            semantic
            and semantic.claim_id == claim.candidate_id
            and proof.metadata.status == "success"
            and proof.metadata.calls == 1
            and proof.semantic_input_sha256
            == payload_digest(semantic_payload(batch, claim, getattr(proof, "goal_context", None)))
        ):
            state = {
                "SUPPORTED": "ACCEPT",
                "INSUFFICIENT": "INVESTIGATE",
                "UNSUPPORTED": "ABSTAIN",
            }[semantic.verdict]
            if needs_semantic or state != "ACCEPT":
                reasons = ["semantic_" + semantic.verdict.lower(), semantic.reason]
        else:
            state, reasons = (
                "INVESTIGATE",
                [proof.semantic_error or "semantic_verification_required"],
            )
    limitations = list(
        dict.fromkeys(
            [*claim.missing_information, *(claim.reasoning.limitations if claim.reasoning else [])]
        )
    )
    return VerificationDecisionRecord(
        candidate_id=claim.candidate_id,
        original_claim=claim,
        decision=state,
        reason_codes=reasons,
        supporting_references=list(
            {
                r.model_dump_json(): r
                for r in [*claim.fact_references, *claim.provenance.supporting_references]
            }.values()
        ),
        supporting_citations=claim.citations,
        validation=validation,
        caveats=sorted(
            set(
                [
                    *claim.caveats,
                    *validation.caveats,
                    *batch.caveats,
                    *limitations,
                    *(claim.reasoning.assumptions if claim.reasoning else []),
                ]
            )
        ),
        limitations=limitations,
        trace=LiteDecisionTrace(
            policy_version="verification_lite_v2"
            if any(c.check_id == "integration_v2" for c in validation.checks)
            else "verification_lite_v1",
            source_result_sha256=batch.source_result_sha256,
            verification_input_sha256=verification_input_digest(batch),
            validation_result_sha256=verification_input_digest(proof.validation),
            semantic_result_sha256=verification_input_digest(proof),
        ),
    )


class LiteFinancialValidator(DeterministicFinancialValidator):
    def __init__(self, catalog):
        super().__init__(catalog)

    def _assertion(self, claim, statement):
        return self._typed_assertion(claim, statement) or super()._assertion(claim, statement)

    def _typed_assertion(self, claim, statement):
        if claim.kind == "fact" and len(claim.supporting_evidence) == 1:
            source = claim.supporting_evidence[0]
            # The exact independently stored row label binds an observation even
            # when its accounting mapping is absent. Other prose needs semantics.
            labels = {
                fact.context.raw_item_label: fact.canonical_item_id
                for fact in self._catalog.facts
                if fact.observation_identity() == source.reference.observation
            }
            if source.label not in labels:
                return None
            ptype = "tại ngày" if len(source.period) > 4 else "kỳ"
            value = _number(source.value)
            scale = f" (hệ số đơn vị {source.scale})" if source.scale != "1" else ""
            forms = {
                f"{source.label} {ptype} {source.period} là {value} {source.unit}{scale}.",
                f"{source.label} kỳ {source.period} là {value} {source.unit}{scale}.",
            }
            if statement in forms:
                # _fact independently rehydrates identity/value/unit/period/citations.
                return NumericAssertion(
                    labels[source.label],
                    Decimal(source.value),
                    source.unit,
                    Decimal(source.scale),
                    source.period,
                    "as_of" if len(source.period) > 4 else "fiscal_year",
                )
        return None

    def _analysis(self, batch, claim, result):
        if claim.python_execution:
            # Reuse source/context/numeric/quality/citation validators on every premise.
            # Output arithmetic and statement are checked by the worker replay below.
            local = batch.model_copy(deep=True)
            local.context.reporting_year = None
            return super()._analysis(local, claim.model_copy(update={"content": ""}), result)
        if claim.reasoning and claim.reasoning.claim_type == "derived_fact":
            return super()._analysis(batch, claim, result)
        # Validate premises/operations with the existing tools. Prose/causality is
        # delegated to a single semantic verifier, not the legacy numeric grammar.
        if claim.analysis_premises:
            local = (
                claim
                if claim.reasoning
                else claim.model_copy(
                    update={
                        "reasoning": ReasoningProof(
                            claim_type="reasoned_conclusion", goal="Verify statement"
                        )
                    }
                )
            )
            # Premises may include comparative columns and balance-sheet dates
            # in this filing. Replay their own canonical periods, retaining the
            # request's company/document/snapshot binding.
            premise_batch = batch.model_copy(deep=True)
            # Keep an exact-date request binding. Only explicit comparison
            # endpoints may relax it in the shared deterministic validator.
            premise_batch.context.reporting_year = None
            super()._reasoning(premise_batch, local, result)
            result.checks = [
                c
                for c in result.checks
                if c.reason_code
                not in {
                    "reasoning_unbound_number",
                    "reasoning_unbound_unit",
                    "reasoning_calculation_required",
                }
            ]
        else:
            super()._analysis(batch, claim, result)


class LiteVerificationRuntime:
    def __init__(self, catalog, gateway=None, *, model=None, python_executor=None):
        self.validator = LiteFinancialValidator(
            catalog,
        )
        self.integration_context = {}
        self.builder = EvidenceContextBuilder(catalog)
        self.gateway = gateway
        self.model = model or ModelIdentity(provider="gemini", model="gemini-3.5-flash-lite")
        self.provider_metadata = []
        self.stage_latency_ms = {}
        self.summary = {}
        self.wire_claim_handles = []
        self.python_executor = python_executor or PythonExecutor()

    def verify(self, batch, *, integration_context=None, **_):
        self.integration_context = integration_context or {}
        self.protocol_errors = []
        self.semantic_proposals = []
        self.goal_completion = {
            r["requirement_id"]: dict(status="unverified", candidate_ids=[])
            for r in self.integration_context.get("requirements", [])
        }
        batch = VerificationInput.model_validate_json(batch.model_dump_json())
        start = perf_counter()
        proofs, pending = [], []
        duplicate_ids = {
            c.candidate_id
            for c in batch.claims
            if sum(x.candidate_id == c.candidate_id for x in batch.claims) > 1
        }
        for claim in batch.claims:
            local = batch.model_copy(update={"claims": []}).model_copy(
                deep=True, update={"claims": [claim]}
            )
            if len({c.period[:4] for c in batch.claims}) > 1:
                # Preserve the multi-period guard's meaning when validating one
                # candidate at a time; reporting year belongs to the filing.
                local.context.reporting_year = None
            try:
                validation = self.validator.validate(local)
                contexts = self.builder.build(claim)
            except (ValueError, ArithmeticError, KeyError, TypeError):
                validation = ValidationResult(
                    source_result_sha256=local.source_result_sha256,
                    verification_input_sha256=verification_input_digest(local),
                    claims=[
                        ClaimValidationResult(
                            candidate_id=claim.candidate_id, claim_kind=claim.kind
                        )
                    ],
                )
                self.validator._check(
                    validation.claims[0], "lite_validation", "fail", "claim_validation_error"
                )
                contexts = []
            checked = validation.claims[0]
            self.validator._check(checked, "integration_v2", "pass", "typed_source_profile")
            if self.validator._typed_assertion(claim, claim.content):
                self.validator._check(checked, "typed_assertion", "pass", "exact_typed_rendering")
            # Bind source-record availability independently, even when values match.
            valid = bool(contexts) and all(c.available for c in contexts)
            valid = valid and claim.candidate_id not in duplicate_ids
            # Canonical identities, scalar values and citations are replayed by
            # the validator/builder. A presentation label is not source identity.
            self.validator._check(
                checked,
                "lite_sources",
                "fail"
                if claim.candidate_id in duplicate_ids
                else "pass"
                if valid
                else "undetermined",
                "duplicate_candidate_id"
                if claim.candidate_id in duplicate_ids
                else "canonical_sources_bound"
                if valid
                else "independent_sources_unavailable",
            )
            if any(
                s.kind == "fact" and s.canonical_item_id is None for s in claim.supporting_evidence
            ):
                self.validator._check(
                    checked, "metadata", "undetermined", "canonical_mapping_missing"
                )
            if checked.caveats and batch.context.reporting_scope:
                if "reporting_scope_unresolved" in checked.caveats:
                    self.validator._check(
                        checked, "lite_scope", "undetermined", "requested_scope_unresolved"
                    )
            context = goal_context(self.integration_context, claim)
            if (
                context
                and any(r["kind"] == "question" for r in context["local_requirements"])
                and claim.kind == "supported_interpretation"
                and not claim.python_execution
                and (not claim.reasoning or claim.reasoning.claim_type != "derived_fact")
            ):
                # Replayed premises prove their own rows, not a reassigned amount
                # in prose. Dates explicitly marked as reporting years may remain.
                proposition = re.sub(
                    r"(?i)\b(?:năm|kỳ)\s+(?:19|20|21)\d{2}"
                    r"(?!\d|[.,]\d|\s*(?:VND|USD|đồng|%))",
                    "",
                    claim.content,
                )
                if re.search(r"(?<!\w)" + NUMBER, proposition):
                    self.validator._check(
                        checked,
                        "numeric_binding",
                        "fail",
                        "interpretation_quantity_requires_typed_proposition",
                        observed={
                            "statement": claim.content,
                            "source_labels": {
                                source.evidence_id: source.label
                                for source in claim.supporting_evidence
                            },
                        },
                    )
            if context is not None:
                for check, status, reason, tid in replay_obligations(
                    self.validator._catalog, local, context
                ):
                    self.validator._check(checked, check, status, reason, expected={"task_id": tid})
                replay = None
                if claim.python_execution:
                    from .python_proof import replay_python

                    try:
                        replay = replay_python(self.validator._catalog, claim, self.python_executor)
                        self.validator._check(
                            checked,
                            "python_execution",
                            "pass",
                            "python_independent_replay_matches",
                            expected=replay,
                        )
                    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError) as error:
                        reason = (
                            str(error) if isinstance(error, ValueError) else "python_proof_invalid"
                        )
                        self.validator._check(
                            checked,
                            "python_execution",
                            "undetermined"
                            if reason.startswith("python_replay_")
                            and reason != "python_replay_mismatch"
                            else "fail",
                            reason,
                        )
                proof = LiteProofV2(
                    batch=local, validation=validation, goal_context=context, python_replay=replay
                )
                if replay:
                    from .python_proof import validate_python_history
                    from .python_units import UnitNotProven, check_python_units

                    try:
                        units = check_python_units(claim.python_execution.execution)
                        self.validator._check(
                            checked,
                            "python_units",
                            "pass",
                            "python_output_dimensions_verified",
                            expected=units,
                        )
                        validate_python_history(proof)
                    except UnitNotProven as error:
                        self.validator._check(checked, "python_units", "undetermined", str(error))
                    except (ValueError, KeyError, TypeError, IndexError) as error:
                        self.validator._check(checked, "python_units", "fail", str(error))
            else:
                if claim.python_execution:
                    self.validator._check(
                        checked, "python_execution", "undetermined", "python_goal_context_required"
                    )
                proof = LiteProof(batch=local, validation=validation)
            proofs.append(proof)
            state = deterministic_state(claim, checked)[0]
            if _semantic_required(proof, state) or (
                state == "ACCEPT" and context and not direct_fact_goals(proof)
            ):
                pending.append(proof)
        self.stage_latency_ms["validators"] = (perf_counter() - start) * 1000
        if pending:
            # Only an expected semantic assessment can fail technically. A
            # controlled deterministic rejection leaves goals unverified.
            for completion in self.goal_completion.values():
                completion["status"] = "technical_error"
            if self.gateway:
                self._semantic(pending)
        histories = []
        for proof in proofs:
            decision = decide(proof)
            if binding := numeric_question_binding(proof, decision):
                proof.goal_context["verified_question"] = binding
                decision.trace.semantic_result_sha256 = verification_input_digest(proof)
            histories.append(
                (
                    LiteVerificationHistoryV2
                    if isinstance(proof, LiteProofV2)
                    else LiteVerificationHistory
                )(
                    proof=proof,
                    outcome=VerificationLoopResult(
                        parent_candidate_id=decision.candidate_id,
                        initial_input=proof.batch,
                        attempts=[decision],
                        stopped=True,
                        stop_reason="lite_single_pass",
                    ),
                )
            )
        self.summary = dict(
            mode="lite",
            candidate_count=len(proofs),
            deterministic_accept_count=sum(
                deterministic_state(p.batch.claims[0], p.validation.claims[0])[0] == "ACCEPT"
                for p in proofs
            ),
            semantic_candidate_count=len(pending),
            semantic_calls=len(self.provider_metadata),
            technical_errors=sorted(
                {
                    p.semantic_error
                    for p in proofs
                    if p.semantic_error
                    and p.semantic_error
                    not in {"semantic_output_truncated", "semantic_verdict_missing_or_invalid"}
                }
            ),
            protocol_errors=sorted(
                set(self.protocol_errors)
                | {
                    p.semantic_error
                    for p in proofs
                    if p.semantic_error
                    in {"semantic_output_truncated", "semantic_verdict_missing_or_invalid"}
                }
            ),
            wire_claim_handles=self.wire_claim_handles,
            semantic_proposals=self.semantic_proposals,
            decisions={
                state: sum(h.outcome.final.decision == state for h in histories)
                for state in ("ACCEPT", "INVESTIGATE", "ABSTAIN")
            },
            findings=[
                dict(
                    candidate_id=h.outcome.final.candidate_id,
                    decision=h.outcome.final.decision,
                    reasons=h.outcome.final.reason_codes,
                    citations=[
                        c.model_dump(mode="json") for c in h.outcome.final.supporting_citations
                    ],
                )
                for h in histories
            ],
        )
        self.summary["supported_requirements"] = {
            h.outcome.final.candidate_id: supported_goals(h.proof, h.outcome.final)
            for h in histories
            if h.outcome.final.decision == "ACCEPT"
        }
        for history in histories:
            if history.outcome.final.decision == "ACCEPT":
                for rid in direct_fact_goals(history.proof):
                    self.goal_completion[rid] = dict(
                        status="satisfied",
                        candidate_ids=[history.outcome.final.candidate_id],
                    )
        for rid, result in self.goal_completion.items():
            if rid == "Q1":
                bindings = [
                    h.proof.goal_context["verified_question"]
                    for h in histories
                    if getattr(h.proof, "goal_context", {}).get("verified_question")
                ]
                if bindings:
                    self.goal_completion[rid] = question_completion(*bindings)
                continue
            if result["status"] == "satisfied" and any(
                rid not in self.summary["supported_requirements"].get(cid, [])
                for cid in result["candidate_ids"]
            ):
                result.update(status="unverified", candidate_ids=[])
            if result["status"] == "satisfied":
                selected = [
                    h.proof
                    for h in histories
                    if h.outcome.final.candidate_id in result["candidate_ids"]
                ]
                requirement = next(
                    r
                    for r in self.integration_context["requirements"]
                    if r["requirement_id"] == rid
                )
                if issue := goal_completion_issue(selected, requirement, self.integration_context):
                    result.update(status="unverified", candidate_ids=[], alignment_issue=issue)
        self.summary["goal_alignment"] = {
            h.outcome.final.candidate_id: {
                r["requirement_id"]: dict(
                    expected=goal_output_type(r),
                    actual=candidate_output(h.proof.batch.claims[0]),
                    issue=goal_binding_issue(h.proof, r),
                )
                for r in getattr(h.proof, "goal_context", {}).get("local_requirements", [])
            }
            for h in histories
        }
        self.summary["goal_completion"] = self.goal_completion
        if any(r["status"] == "technical_error" for r in self.goal_completion.values()):
            self.summary["technical_errors"].append("semantic_goal_completion_missing_or_invalid")
        self.summary["feedback"] = [
            feedback(h.proof, h.outcome.final)
            for h in histories
            if isinstance(h.proof, LiteProofV2)
        ]
        return histories

    def _semantic(self, proofs):
        start = perf_counter()
        wire_ids = {f"C{i}": p.batch.claims[0].candidate_id for i, p in enumerate(proofs, 1)}
        requirements = {
            r["requirement_id"]: r
            for proof in proofs
            for r in getattr(proof, "goal_context", {}).get("local_requirements", [])
            if r["requirement_id"]
            in getattr(proof, "goal_context", {}).get(
                "proposed_requirement_ids",
                [r["requirement_id"]],
            )
        }
        question_level = any(r.get("kind") == "question" for r in requirements.values())
        expected = self.integration_context.get("expected_answers") if question_level else None
        question_operands = question_level and any(
            (claim := p.batch.claims[0]).kind == "fact"
            or (claim.reasoning and claim.reasoning.calculation)
            for p in proofs
        )
        parts = (
            question_parts(proofs[0].batch.question) if question_level and expected is None else {}
        )
        schema = (
            independent_verifier_schema(wire_ids, expected)
            if expected is not None
            else verifier_output_schema(
                wire_ids,
                requirements,
                question_level=question_level,
                question_operands=question_operands,
                part_ids=parts,
            )
        )
        rows = [_semantic_row(p, handle) for handle, p in zip(wire_ids, proofs, strict=True)]
        body = dict(
            question=proofs[0].batch.question,
            question_parts=parts,
            question_understanding=self.integration_context.get("question_understanding"),
            requirements=[
                dict(
                    {
                        k: r[k]
                        for k in (
                            "requirement_id",
                            "text",
                            "period",
                            "requested_unit",
                            "kind",
                            "target_id",
                            "required_indicators",
                            "reasoning_operations",
                            "calculation_intent",
                            "interpretation",
                            "aspect",
                            "answer_goal",
                            "reasoning_periods",
                            "verification_requirements",
                            "source_scope",
                        )
                        if r.get(k) not in (None, [], {})
                    },
                    evidence_obligations={
                        f"{r['requirement_id']}.need[{i}]": need
                        for i, need in enumerate(r.get("evidence_needs", []))
                    },
                )
                for r in requirements.values()
            ],
            goal_output_types={rid: goal_output_type(r) for rid, r in requirements.items()},
            claims=rows,
            direct_document_evidence=[
                dict(
                    content=e.content,
                    sources=verifier_citations(
                        e.citations, proofs[0].batch.context.model_dump(mode="json")
                    ),
                )
                for proof in proofs
                for e in self.builder.build(proof.batch.claims[0])
                if e.reference.kind in {"text", "table"}
            ],
        )
        if expected is not None:
            body["requirements"] = expected["requirements"]
            body["requirement_revision"] = expected["revision"]
            body.pop("goal_output_types")
            body.pop("question_understanding")
            if any("answer_type" in item for item in expected["requirements"]):
                for row, proof in zip(rows, proofs, strict=True):
                    row["candidate_output"] = independent_candidate_output(proof)
        # Omit empty document context; numeric facts already carry their sources.
        if scope := proofs[0].batch.context.reporting_scope:
            body["reporting_scope"] = scope
        body = {k: v for k, v in body.items() if v not in (None, [], {})}
        payload = json.dumps(
            compact_prompt(body, extra_fields=("claims",)) if len(rows) > 1 else body,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        if len(payload) > 40000 or len(rows) > 32:
            for p in proofs:
                p.semantic_error = "semantic_payload_limit"
            return
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m6-lite-" + uuid4().hex,
            model=self.model,
            messages=[
                Message(
                    role="system",
                    content=INDEPENDENT_VERIFIER_INSTRUCTION
                    if expected is not None
                    else (
                        (
                            "Đối chiếu từng mệnh đề của statement với đúng nhãn hàng, header, "
                            "đối tượng và kỳ trên evidence. Một số trùng ở chỉ tiêu khác không "
                            "xác minh mệnh đề. Với claim nhiều vế, chỉ SUPPORTED khi mọi vế được "
                            "chứng minh; nếu sai hoặc thiếu, nêu vế và nguồn không khớp trong reason. "
                            + VERIFIER_INSTRUCTION
                        )
                        + (QUESTION_OPERAND_INSTRUCTION if question_operands else "")
                        + (QUESTION_COVERAGE_INSTRUCTION if parts else "")
                        + (
                            " Với phép tính, reasoning_operations có thể là mã hoặc mô tả. "
                            "Xác định phép tính, thứ tự toán hạng và đơn vị từ câu hỏi gốc, "
                            "rồi đối chiếu với intent của Goal, EO và chuỗi phép tính đã replay. "
                            "question_understanding là phân tích sơ bộ từ trước candidate. "
                            "Đối chiếu từng mục với câu hỏi nguyên văn, phát hiện mục thiếu hoặc sai trong bản phân tích. "
                            "Coordinator và Reasoning đồng ý vẫn chưa đủ. Nếu intent mơ hồ, "
                            "mâu thuẫn hoặc phép tính không tương đương, không cấp relevance "
                            "cho claim kết quả đó và để completion rỗng cho Goal."
                        )
                    ),
                ),
                Message(role="user", content=payload),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
            output_spec=OutputSpec(format="json", json_schema=schema),
            constraints=RequestConstraints(timeout_seconds=60),
        )
        self.wire_claim_handles.append(dict(request_id=request.request_id, handles=wire_ids))
        metadata = PlannerLLMMetadata(calls=1, model=self.model, status="error")
        items, completion, coverage, error = [], {}, {}, "semantic_gateway_exception"
        try:
            response = self.gateway.generate(request)
            metadata = PlannerLLMMetadata(
                calls=1,
                model=self.model,
                status=response.status,
                usage=response.usage,
                cost=response.cost,
                error=response.error,
                provenance=response.provenance,
                latency_ms=(perf_counter() - start) * 1000,
            )
            items = semantic_output(response)
            self.semantic_proposals.append(
                dict(
                    request_id=request.request_id,
                    output=dict(payload=getattr(response.output, "payload", None)),
                )
            )
            if expected is not None:
                coverage = independent_question_coverage(
                    expected, response=response, schema=schema, wire_ids=wire_ids
                )
            elif response.status == "success" and response.finish_reason != "length":
                completion = verified_completion_refs(response, schema)
                coverage = bind_question_slots(
                    response, schema, parts, wire_ids, requirements.get("Q1")
                )
            model_output = response.status in {"success", "malformed", "partial"} or (
                response.error
                and response.error.category in {"structured_output_invalid", "schema_mismatch"}
            )
            error = (
                "semantic_output_truncated"
                if response.finish_reason == "length"
                else "semantic_verdict_missing_or_invalid"
                if model_output
                else "semantic_provider_failure"
            )
            if model_output:
                for result in self.goal_completion.values():
                    result["status"] = "unverified"
        except Exception:
            pass
        self.provider_metadata.append(("semantic", metadata))
        self.stage_latency_ms["semantic"] = (
            self.stage_latency_ms.get("semantic", 0) + (perf_counter() - start) * 1000
        )
        for handle, proof in zip(wire_ids, proofs, strict=True):
            proof.metadata = metadata
            proof.semantic_error = error
            matches = [v for v in items if isinstance(v, dict) and v.get("claim_id") == handle]
            if len(matches) != 1:
                continue
            cid = wire_ids[handle]
            try:
                row = dict(matches[0], claim_id=cid)
                if expected is not None:
                    row["supported_requirement_ids"] = []
                verdict = GoalSemanticVerdict.model_validate(row)
            except ValueError:
                continue
            context = getattr(proof, "goal_context", {})
            claim_requirements = {
                r["requirement_id"]: r for r in context.get("local_requirements", [])
            }
            if not set(verdict.supported_requirement_ids) <= claim_requirements.keys():
                continue
            if isinstance(proof, LiteProofV2):
                proof.semantic = verdict
                if parts or expected is not None:
                    proof.goal_context["question_coverage"] = coverage
            else:
                proof.semantic = SemanticVerdict.model_validate(
                    verdict.model_dump(include={"claim_id", "verdict", "reason"})
                )
            proof.semantic_error = None
            proof.semantic_input_sha256 = payload_digest(
                semantic_payload(
                    proof.batch, proof.batch.claims[0], getattr(proof, "goal_context", None)
                )
            )
        for rid in self.goal_completion:
            if rid == "Q1" and (parts or expected is not None):
                continue
            if rid not in requirements:
                self.goal_completion[rid]["status"] = "unverified"
                continue
            refs = completion.get(rid) if isinstance(completion, dict) else None
            if not isinstance(refs, list) or any(
                not isinstance(ref, str) or ref not in wire_ids for ref in refs
            ):
                if self.goal_completion[rid]["status"] != "technical_error":
                    self.protocol_errors.append("semantic_goal_completion_missing_or_invalid")
                continue
            self.goal_completion[rid] = dict(
                status="satisfied" if refs else "unverified",
                candidate_ids=list(dict.fromkeys(wire_ids[ref] for ref in refs)),
            )
