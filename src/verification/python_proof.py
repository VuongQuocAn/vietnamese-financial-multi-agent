"""M6 projection and independent replay of the existing Python worker proof."""

from decimal import Decimal

from ..agents.orchestration_contracts import CandidateOrigin
from ..agents.specialist_common import ReasoningProof, SpecialistEvidence, _number
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
from ..tools.python_execution import digest


def render_python(record, output_key):
    execution = record["executions"][-1]
    return (
        f"{record['objective'].rstrip(' .')} — {output_key}: "
        f"{_number(record['results'][output_key])} {execution['outputs'][output_key]}. "
        f"Công thức: {execution['computation']}"
    )


def project_python(context):
    """Project saved Workspace candidates only; source authority is checked in M6."""
    from .contracts import CandidateClaim, ClaimProvenance, PythonClaimProof

    claims = []
    for tid, task in context.get("tasks", {}).items():
        record = context.get("task_results", {}).get(tid, {}).get("python_candidate")
        if not record or record.get("execution_status") != "success":
            continue
        try:
            evidence = [
                SpecialistEvidence.model_validate(
                    dict(
                        evidence_id=key,
                        kind="fact",
                        reference=row["reference"],
                        company_id=row["company_id"],
                        document_id=row["document_id"],
                        snapshot_id=row["snapshot_id"],
                        period=row["context"]["period"],
                        label=row["label"],
                        value=row["value"],
                        unit=row["unit"],
                        scale=row["raw_scale"],
                        canonical_item_id=row["item"],
                        citations=row["citations"],
                        caveats=sorted(
                            {c for cite in row["citations"] for c in cite["limitations"]}
                        ),
                    )
                )
                for key, row in record["operands"].items()
            ]
            owner = evidence[0]
            citations = list(
                {c.model_dump_json(): c for e in evidence for c in e.citations}.values()
            )
            refs = [e.reference for e in evidence]
            for key in record["results"]:
                cid = record["candidate_id"] + ":" + key
                content = render_python(record, key)
                origin = CandidateOrigin(
                    role=task["role"],
                    execution_id=tid,
                    candidate_id=cid,
                    original_content=content,
                    supporting_evidence=evidence,
                )
                claims.append(
                    CandidateClaim(
                        candidate_id=cid,
                        kind="supported_interpretation",
                        content=content,
                        company_id=owner.company_id,
                        document_id=owner.document_id,
                        snapshot_id=owner.snapshot_id,
                        period=owner.period,
                        fact_references=refs,
                        supporting_evidence_ids=[e.evidence_id for e in evidence],
                        supporting_evidence=evidence,
                        citations=citations,
                        caveats=sorted({c for e in evidence for c in e.caveats}),
                        analysis_premises=[
                            f"{e.label} kỳ {e.period} là {_number(e.value)} {e.unit}"
                            + (f" (hệ số đơn vị {e.scale})" if e.scale != "1" else "")
                            + "."
                            for e in evidence
                        ],
                        reasoning=ReasoningProof(
                            claim_type="reasoned_conclusion", goal=record["objective"]
                        ),
                        provenance=ClaimProvenance(
                            m5_candidate_id=cid,
                            origins=[origin],
                            origin_roles=[task["role"]],
                            supporting_references=refs,
                        ),
                        python_execution=PythonClaimProof(
                            execution=record,
                            execution_sha256=digest(record),
                            output_key=key,
                        ),
                    )
                )
        except (ValueError, KeyError, TypeError, IndexError):
            # Incomplete records remain unverified in Workspace; never fabricate output.
            continue
    return claims


def replay_python(catalog, claim, executor):
    """Rehydrate every manifest row, then replay exact code/image/Decimal inputs."""
    from ..agents.python_agent import input_manifest

    proof = claim.python_execution
    record = proof.execution
    execution = record["executions"][-1]
    if (
        record["version"] != "python_execution_proof_v1"
        or proof.execution_sha256 != digest(record)
        or record["input_digest"] != digest(record["operands"])
        or execution["input_digest"] != record["input_digest"]
        or execution["code_digest"] != digest(execution["code"])
        or record["rounding"] != "Decimal34_HALF_EVEN"
        or record["lineage"] != "entire_input_manifest"
        or record["execution_status"] != "success"
        or execution["status"] != "success"
        or record["results"] != execution["results"]
        or set(record["results"]) != set(execution["outputs"])
        or claim.content != render_python(record, proof.output_key)
    ):
        raise ValueError("python_execution_digest_or_projection_mismatch")
    tools, matches = FinancialRetrievalTools(catalog), []
    for row in record["operands"].values():
        identity = row["reference"]["observation"]
        response = tools.get_financial_fact(
            GetFinancialFactRequest(
                document_id=claim.document_id,
                snapshot_id=claim.snapshot_id,
                local_observation_id=identity["local_id"],
            )
        )
        if response.status != "found" or len(response.matches) != 1:
            raise ValueError("python_source_unavailable")
        matches.append(response.matches[0])
    manifest = input_manifest(matches)
    if manifest != record["operands"]:
        raise ValueError("python_source_manifest_mismatch")
    if set(manifest) != {e.evidence_id for e in claim.supporting_evidence}:
        raise ValueError("python_operand_closure_mismatch")
    if any(
        e.reference.model_dump(mode="json") != manifest[e.evidence_id]["reference"]
        for e in claim.supporting_evidence
    ):
        raise ValueError("python_operand_reference_mismatch")
    for value in record["results"].values():
        if not Decimal(value).is_finite():
            raise ValueError("python_result_non_finite")
    image = execution["worker"]["image"]
    if record["preflight"]["image"] != image or executor.image != image:
        raise ValueError("python_worker_identity_mismatch")
    replay = executor.execute(
        execution["code"], manifest, execution["outputs"], execution["constants"]
    )
    if replay.get("status") != "success":
        raise ValueError("python_replay_" + replay.get("status", "unavailable"))
    if replay.get("worker") != execution["worker"] or replay["results"] != record["results"]:
        raise ValueError("python_replay_mismatch")
    return dict(
        execution_sha256=proof.execution_sha256,
        input_digest=digest(manifest),
        code_digest=digest(execution["code"]),
        worker=replay["worker"],
        results=replay["results"],
    )


def validate_python_history(proof):
    """Bind saved replay evidence to the exact admitted execution and projection."""
    claim = proof.batch.claims[0]
    python = claim.python_execution
    record, replay = python.execution, proof.python_replay
    execution = record["executions"][-1]
    from .python_units import check_python_units

    units = check_python_units(record)
    if not any(
        c.check_id == "python_units" and c.status == "pass" and c.expected == units
        for c in proof.validation.claims[0].checks
    ):
        raise ValueError("python_unit_check_missing")
    owners = proof.goal_context["owner_task_ids"]
    if (
        not replay
        or python.execution_sha256 != digest(record)
        or not owners
        or any(
            proof.goal_context["task_results"][tid].get("python_candidate") != record
            for tid in owners
        )
        or replay
        != dict(
            execution_sha256=digest(record),
            input_digest=digest(record["operands"]),
            code_digest=digest(execution["code"]),
            worker=execution["worker"],
            results=record["results"],
        )
        or record["input_digest"] != replay["input_digest"]
        or execution["input_digest"] != replay["input_digest"]
        or execution["code_digest"] != replay["code_digest"]
        or execution["results"] != replay["results"]
        or claim.content != render_python(record, python.output_key)
    ):
        raise ValueError("python_saved_replay_mismatch")
