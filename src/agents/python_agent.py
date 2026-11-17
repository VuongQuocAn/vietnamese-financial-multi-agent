"""Shared Python capability for the existing Coordinator; candidate authority only."""

import json
from decimal import Context, Decimal, localcontext
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..tools.financial_calculator import DynamicOperation
from ..tools.python_execution import PythonExecutor, digest
from ..tools.question_understanding import normalize
from .evidence_coordination import observation
from .planner_contracts import PlannerLLMMetadata

# Missing primitives, not financial definitions. Ordinary operation DAGs stay in Calculator.
PythonRequirement = Literal["power", "sqrt", "root_finding", "dispersion", "iterative_solver"]
CALCULATOR_OPERATORS = list(DynamicOperation.model_fields["operator"].annotation.__args__)


def requires_python(question, objective, requirement):
    """Conservative capability gate grounded in the user's request, not just model routing."""
    signals = {
        "power": ("luy thua", "binh phuong", "can bac", "rms", "cagr", "kep", "power"),
        "sqrt": ("can bac", "sqrt", "rms", "do lech chuan"),
        "dispersion": ("do lech chuan", "phuong sai", "standard deviation", "variance"),
        "root_finding": ("irr", "nghiem", "root", "noi hoan"),
        "iterative_solver": ("lap", "solver", "toi uu", "hoi tu"),
    }
    terms = signals.get(requirement, ())
    return all(any(term in normalize(text) for term in terms) for text in (question, objective))


class AlgorithmConstant(FinancialModel):
    value: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=300)


class PythonProposal(FinancialModel):
    code: str = Field(min_length=1, max_length=12288)
    outputs: dict[str, str] = Field(min_length=1, max_length=8)
    computation: str = Field(min_length=1, max_length=1200)
    constants: list[AlgorithmConstant] = Field(max_length=12)


def input_manifest(matches):
    """Hydrate ONLY tool-returned observations. Preserve every supplied source and raw scale."""
    operands = {}
    for match in matches:
        row = observation(match)
        fact = match.record
        if (
            row["value"] is None
            or not row["citations"]
            or not row["selectors"]
            or not fact.context.period
            or not fact.value.unit
            or fact.context.scale is None
        ):
            raise ValueError("python_operand_context_missing")
        with localcontext(Context(prec=34)):
            value, scale = Decimal(row["value"]), Decimal(str(fact.context.scale))
            if not value.is_finite() or not scale.is_finite() or scale <= 0:
                raise ValueError("python_operand_non_finite")
            row.update(base_value=str(value * scale), raw_scale=str(scale))
        operands[row["evidence_id"]] = row
    contexts = {(r["company_id"], r["document_id"], r["snapshot_id"]) for r in operands.values()}
    if not operands or len(operands) > 40 or len(contexts) != 1:
        raise ValueError("python_operand_scope_invalid")
    if len(json.dumps(operands, ensure_ascii=False).encode()) > 240000:
        raise ValueError("python_manifest_limit")
    return operands


class PythonAgent:
    def __init__(self, gateway, executor=None):
        self.gateway = gateway
        self.executor = executor or PythonExecutor()

    def run(self, *, objective, requirement, matches, context, repair_available=True):
        record = dict(
            version="python_execution_proof_v1",
            candidate_id="python-" + uuid4().hex,
            objective=objective,
            requirement=requirement,
            status="candidate",
            financial_fact_verified=False,
            verification="requires_M6-PY-01",
            executions=[],
            generation_trace=[],
            lineage="entire_input_manifest",
            rounding="Decimal34_HALF_EVEN",
            calls=0,
        )
        metadata = PlannerLLMMetadata()
        if requirement not in PythonRequirement.__args__:
            return dict(record, execution_status="calculator_required"), metadata
        try:
            manifest = input_manifest(matches)
        except ValueError as error:
            return dict(record, execution_status=str(error)), metadata
        record.update(operands=manifest, input_digest=digest(manifest))
        ready = self.executor.preflight()
        record["preflight"] = ready
        if ready["status"] != "ready" or self.gateway is None:
            return dict(record, execution_status="python_unavailable"), metadata
        instruction = (
            "Return JSON {code,outputs,computation,constants}. code defines solve(data). "
            "NO imports: Decimal is already available. NO I/O/network. "
            "data[handle] IS a Decimal, not a dict: never access ['base_value']. "
            "Return {output_key: Decimal_result}, never str(result). Do not call getcontext(). "
            "Only Decimal, abs, all, any, enumerate, len, max, min, range, sorted, sum, zip; "
            "Decimal.sqrt()/ln()/exp() are available. No float. "
            "Use ONLY supplied data values for financial operands; never embed them as literals. "
            "0,1,2,100 are permitted algorithm constants; declare others with value and purpose. "
            "outputs maps requested output keys to proposed units. computation explains the formula. "
            "constants is an array of {value: numeric string,purpose: explanation}; [] if none needed. "
            "Scale already applied ONCE. Produce ONLY requested outputs. No verdict or invented sources."
        )
        first = next(iter(manifest))
        prompt = dict(
            schema=PythonProposal.model_json_schema(),
            objective=objective,
            missing_calculator_primitive=requirement,
            calculator_operators=CALCULATOR_OPERATORS,
            data={key: row["base_value"] for key, row in manifest.items()},
            shape_example=f'def solve(data):\n    x = data["{first}"]\n    return {{"result": x}}',
            example_note="Only illustrates the function interface; implement the requested formula.",
            operand_metadata={
                k: {p: row[p] for p in ("label", "unit", "context", "header", "verification")}
                for k, row in manifest.items()
            },
        )
        if len(json.dumps(prompt, ensure_ascii=False)) > 40000:
            return dict(record, execution_status="python_prompt_limit"), metadata
        messages = [
            Message(role="system", content=instruction),
            Message(role="user", content=json.dumps(prompt, ensure_ascii=False)),
        ]
        tokens = dict(input_tokens=0, output_tokens=0, total_tokens=0)
        known_usage = True
        for attempt in range(2 if repair_available else 1):
            response = self.gateway.generate(
                LLMRequest(
                    contract_version="llm_gateway_v1",
                    request_id="m5-python-" + uuid4().hex,
                    model=context.model,
                    messages=messages,
                    generation=GenerationParameters(temperature=0.0, max_output_tokens=2000),
                    output_spec=OutputSpec(format="json"),
                    constraints=RequestConstraints(
                        timeout_seconds=context.provider_timeout_seconds
                    ),
                )
            )
            record["calls"] += 1
            record["generation_trace"].append(response.model_dump(mode="json"))
            metadata = PlannerLLMMetadata(
                calls=record["calls"],
                model=context.model,
                status=response.status,
                usage=response.usage,
                cost=response.cost,
                error=response.error,
                provenance=response.provenance,
            )
            for key in tokens:
                value = getattr(response.usage, key, None)
                if value is None:
                    known_usage = False
                else:
                    tokens[key] += value
            if response.status != "success" or not isinstance(response.output, JSONOutput):
                record["execution_status"] = "generation_failed"
                break
            try:
                proposal = PythonProposal.model_validate(response.output.payload)
            except ValueError:
                record["execution_status"] = "proposal_schema_invalid"
                break  # Schema/transport failures do not get another hidden repair.
            constants = [c.model_dump() for c in proposal.constants]
            execution = self.executor.execute(proposal.code, manifest, proposal.outputs, constants)
            record["executions"].append(
                dict(
                    revision=attempt + 1,
                    code=proposal.code,
                    code_digest=digest(proposal.code),
                    input_digest=record["input_digest"],
                    outputs=proposal.outputs,
                    computation=proposal.computation,
                    constants=constants,
                    **execution,
                )
            )
            record["execution_status"] = execution["status"]
            if execution["status"] == "success":
                record["results"] = execution["results"]
                break
            if execution["status"] != "code_error" or attempt == 1:
                break
            messages += [
                Message(role="assistant", content=json.dumps(proposal.model_dump())),
                Message(
                    role="user",
                    content=json.dumps(
                        dict(
                            instruction=(
                                "Repair code ONCE. No imports/getcontext. Decimal is already "
                                "available. data[handle] is Decimal. Return Decimal, not str. "
                                "Keep the same operands, formula and output keys."
                            ),
                            traceback=execution["traceback"],
                            input_digest=record["input_digest"],
                        ),
                        ensure_ascii=False,
                    ),
                ),
            ]
        if known_usage and metadata.usage is not None:
            metadata.usage = metadata.usage.model_copy(update=tokens)
        return record, metadata
