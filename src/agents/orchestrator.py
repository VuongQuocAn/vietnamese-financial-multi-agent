"""Sequential bounded orchestration; Router owns selection, M6 owns verification."""

import hashlib
import json

from .orchestration_contracts import (
    AggregatedCandidate,
    CandidateConflict,
    CandidateOrigin,
)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _id(prefix, value):
    return prefix + ":" + hashlib.sha256(_json(value).encode()).hexdigest()[:24]


def _unique(models):
    return list({m.model_dump_json(): m for m in models}.values())


def _check_assignment(result, *, supporting_references, citations):
    evidence = {e.evidence_id: e for e in result.supporting_evidence}
    if len(evidence) != len(result.supporting_evidence) or any(
        e.reference not in supporting_references for e in evidence.values()
    ):
        raise ValueError("specialist_evidence_outside_assignment")
    for candidate in result.candidates:
        if not candidate.supporting_evidence_ids or any(
            key not in evidence for key in candidate.supporting_evidence_ids
        ):
            raise ValueError("candidate_evidence_identity_missing")
        supports = [evidence[key] for key in candidate.supporting_evidence_ids]
        calculation = candidate.reasoning.calculation if candidate.reasoning else None

        def bound_period(support, candidate=candidate, calculation=calculation):
            if candidate.period == support.period:
                return True
            return bool(
                calculation
                and candidate.period in {o.period for o in calculation.operands.values()}
                and any(
                    o.reference == support.reference and o.period == support.period
                    for o in calculation.operands.values()
                )
                and any(
                    step.operation.period_relation == "across_periods"
                    and support.evidence_id in step.operands
                    for step in calculation.steps
                )
            )

        if any(
            (candidate.company_id, candidate.document_id, candidate.snapshot_id)
            != (e.company_id, e.document_id, e.snapshot_id)
            or not bound_period(e)
            for e in supports
        ) or any(c not in citations for c in candidate.citations):
            raise ValueError("candidate_provenance_outside_assignment")


def aggregate_candidates(executions):
    """Exact semantic/provenance dedup; preserve competing versions without a winner."""
    aggregated, keys, groups = [], {}, {}
    for execution in executions:
        result = execution.result
        if result is None or execution.status not in {"generated", "partial"}:
            continue
        for candidate in result.candidates:
            if candidate.status != "candidate":
                continue
            evidence = [
                e
                for e in result.supporting_evidence
                if e.evidence_id in candidate.supporting_evidence_ids
            ]
            if candidate.reasoning:
                # Premises and the owner are emitted in the declared ID order.
                # Inventory order can differ, especially for annual/as-of sources.
                by_id = {e.evidence_id: e for e in evidence}
                evidence = [by_id[k] for k in dict.fromkeys(candidate.supporting_evidence_ids)]
            if not evidence or len({e.evidence_id for e in evidence}) != len(
                set(candidate.supporting_evidence_ids)
            ):
                raise ValueError("candidate_evidence_identity_missing")
            semantics = sorted(
                {
                    e.canonical_item_id or (e.calculation.formula_id if e.calculation else e.label)
                    for e in evidence
                }
            )
            # Local evidence IDs and random candidate IDs never define identity.
            provenance = sorted(
                [e.model_dump(mode="json", exclude={"evidence_id"}) for e in evidence], key=_json
            )
            identity = dict(
                kind=candidate.kind,
                company=candidate.company_id,
                document=candidate.document_id,
                snapshot=candidate.snapshot_id,
                period=candidate.period,
                semantics=semantics,
                content=candidate.content,
                provenance=provenance,
                references=sorted(
                    [r.model_dump(mode="json") for r in candidate.fact_references], key=_json
                ),
                citations=sorted(
                    [c.model_dump(mode="json") for c in candidate.citations], key=_json
                ),
            )
            key = _json(identity)
            if candidate.reasoning:
                identity["reasoning"] = candidate.reasoning.model_dump(mode="json")
                key = _json(identity)
            origin = CandidateOrigin(
                role=execution.role,
                execution_id=execution.execution_id,
                candidate_id=candidate.candidate_id,
                original_content=candidate.content,
                supporting_evidence=evidence,
            )
            if key in keys:
                item = keys[key]
                item.origins.append(origin)
                item.origin_roles = list(dict.fromkeys([*item.origin_roles, execution.role]))
                item.caveats = sorted(set(item.caveats + candidate.caveats))
                item.missing_information = sorted(
                    set(item.missing_information + candidate.missing_information)
                )
                continue
            item = AggregatedCandidate(
                **dict(candidate.model_dump(), candidate_id=_id("candidate", identity)),
                origins=[origin],
                origin_roles=[execution.role],
                supporting_evidence=evidence,
                supporting_references=_unique(
                    [e.reference for e in evidence] + candidate.fact_references
                ),
            )
            keys[key] = item
            aggregated.append(item)
            # Interpretations with different wording/meaning are separate propositions.
            if candidate.kind in {"fact", "approved_metric"}:
                group = _json([candidate.kind, candidate.company_id, candidate.period, semantics])
                signature = _json(
                    [
                        candidate.document_id,
                        candidate.snapshot_id,
                        [(e.value, e.unit, e.scale, e.operand_periods) for e in evidence],
                    ]
                )
                groups.setdefault(group, []).append((signature, item))
    conflicts = []
    for group, values in groups.items():
        if len({signature for signature, _ in values}) < 2:
            continue
        ids = [item.candidate_id for _, item in values]
        conflict = CandidateConflict(conflict_id=_id("conflict", [group, ids]), candidate_ids=ids)
        conflicts.append(conflict)
        for _, item in values:
            item.conflict_ids.append(conflict.conflict_id)
    return aggregated, conflicts
