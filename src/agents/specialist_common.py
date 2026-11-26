"""Shared M5 evidence contracts and bounded grounding/Gateway functions.

Only provenance mechanics live here; each specialist owns its domain and prose.
"""

import json
from copy import deepcopy
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, get_args
from uuid import uuid4

from pydantic import Field, ValidationError, model_serializer

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
    parse_json_output,
)
from ..core.prompt_payload import compact_prompt
from ..evidence.contracts import is_json_reference
from ..evidence.graph import graph_id
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from ..evidence.search import SearchDocumentEvidenceRequest
from ..tools.financial_calculator import (
    DynamicCalculation,
    DynamicOperand,
    DynamicOperation,
    FinancialCalculationResponse,
    execute_dynamic,
    render_dynamic,
)
from ..tools.financial_retrieval import FindFinancialFactsRequest
from ..tools.graph_retrieval import GetGraphContextRequest
from ..tools.hybrid_rag import SearchHybridEvidenceRequest
from .contracts import RiskSignal, SpecialistRole
from .planner_contracts import PlannerLLMMetadata

ClaimKind = Literal["fact", "approved_metric", "supported_interpretation"]


class ScalarProposal(FinancialModel):
    """Shared fact/metric selection; financial reasoning stays in AnalysisProposal."""

    evidence_id: str
    kind: Literal["fact", "approved_metric"]
    meaning: Literal["fact_value", "metric_value"]
    period: str
    statement: str | None = Field(default=None, max_length=700)


class ReasoningProof(FinancialModel):
    claim_type: Literal["derived_fact", "reasoned_conclusion", "conditional_inference"]
    goal: str = Field(min_length=1, max_length=1000)
    calculation: DynamicCalculation | None = None
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class SpecialistEvidence(FinancialModel):
    evidence_id: str
    kind: Literal["fact", "metric"]
    reference: RetrievalReference
    company_id: str
    document_id: str
    snapshot_id: str
    period: str
    operand_periods: dict[str, str] = Field(default_factory=dict)
    label: str
    value: str
    unit: str
    scale: str = "1"
    canonical_item_id: str | None = None
    citations: list[EvidenceCitation]
    caveats: list[str]
    # Full accepted execution includes formula/version, operands, lineage and reviews.
    calculation: FinancialCalculationResponse | None = None


class SpecialistCandidate(FinancialModel):
    """Temporary M5 contract; M6-01 owns the eventual CandidateClaim."""

    candidate_id: str
    kind: ClaimKind
    content: str
    company_id: str
    document_id: str
    snapshot_id: str
    period: str
    fact_references: list[RetrievalReference] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str]
    citations: list[EvidenceCitation]
    calculation: FinancialCalculationResponse | None = None
    caveats: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    analysis_premises: list[str] = Field(default_factory=list, max_length=16)
    reasoning: ReasoningProof | None = None
    status: Literal["candidate", "insufficient_evidence"] = "candidate"
    financial_fact_verified: Literal[False] = False

    @model_serializer(mode="wrap")
    def serialize_candidate(self, handler):
        wire = handler(self)
        if not wire.get("analysis_premises"):
            wire.pop("analysis_premises", None)
        if wire.get("reasoning") is None:
            wire.pop("reasoning", None)
        return wire


class AnalysisProposal(FinancialModel):
    statement: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=16)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    goal: str = Field(default="", max_length=1000)
    operations: list[DynamicOperation] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    claim_type: Literal["derived_fact", "reasoned_conclusion", "conditional_inference"] = (
        "reasoned_conclusion"
    )


SPECIALIST_TOOLS_BY_ROLE = {
    "retrieval": frozenset(
        {
            "find_financial_facts",
            "get_financial_fact",
            "search_document_evidence",
            "search_hybrid_evidence",
            "find_document_evidence",
            "get_evidence_item",
            "get_evidence_sources",
            "get_graph_context",
        }
    ),
    "reasoning": frozenset(
        {
            "get_financial_fact",
            "get_evidence_item",
            "get_evidence_sources",
            "get_graph_context",
            "calculate_dynamic",
            "calculate_financial_metric",
        }
    ),
}


def _reasoning_action(action, required, **properties):
    return dict(
        type="object",
        additionalProperties=False,
        required=["action", *required],
        properties=dict(action=dict(type="string", enum=[action]), **properties),
    )


CALCULATION_OPERATORS = get_args(DynamicOperation.model_fields["operator"].annotation)


def _formula_fields(formula, binding_key):
    return {
        "formula_id": dict(type="string", enum=[formula["formula_id"]]),
        binding_key: dict(
            type="object",
            additionalProperties=False,
            required=list(formula["operands"]),
            properties={
                role: dict(type="string", enum=[eid]) for role, eid in formula["operands"].items()
            },
        ),
    }


def formula_decision_schema(formulas):
    choices = [
        dict(
            type="object",
            additionalProperties=False,
            required=["formula_id", "bindings"],
            properties=_formula_fields(formula, "bindings"),
        )
        for formula in formulas
    ]
    return choices[0] if len(choices) == 1 else dict(type="object", oneOf=choices)


def _calculation_decision_schema(operand_schema, operators):
    inputs = DynamicOperation.model_json_schema()["properties"]["inputs"]
    return {
        "type": "object",
        "required": ["operator", "inputs"],
        "additionalProperties": False,
        "properties": {
            "operator": dict(type="string", enum=list(operators)),
            "inputs": dict(
                type="array",
                minItems=inputs["minItems"],
                maxItems=inputs["maxItems"],
                items=operand_schema,
            ),
            "period_relation": dict(
                type="string",
                enum=list(get_args(DynamicOperation.model_fields["period_relation"].annotation)),
            ),
        },
        "if": dict(properties=dict(operator=dict(enum=["sum", "mean"]))),
        "else": dict(properties=dict(inputs=dict(maxItems=2))),
    }


def indexed_calculation_schema(operand_count, operators=CALCULATION_OPERATORS):
    return _calculation_decision_schema(
        dict(type="integer", enum=list(range(operand_count))), operators
    )


def _step_input_limits(definitions, operand_definition, step_refs):
    """Bind local results by position, starting with only assigned operands."""
    source = {"$ref": f"#/$defs/{operand_definition}"}
    limits = [source]
    for i in range(1, len(step_refs) + 1):
        name = f"{operand_definition}{i}"
        definitions[name] = dict(anyOf=[source, dict(enum=step_refs[:i])])
        limits.append({"$ref": f"#/$defs/{name}"})
    return [dict(properties=dict(inputs=dict(items=limit))) for limit in limits]


def bind_specialist_schema(
    schema,
    proposal,
    evidence,
    documents,
    tools,
    *,
    need_refs=(),
    role=None,
    input_results=(),
    requirements=(),
    operand_ids=None,
    parent_operands=(),
    operand_count=0,
    formulas=(),
    parent_decision=False,
):
    """One advertised/API schema, bound only to Python-issued references."""
    schema = deepcopy(schema)
    if role is not None:
        tools = {k: v for k, v in tools.items() if k in SPECIALIST_TOOLS_BY_ROLE.get(role, ())}
    reasoning = role == "reasoning"
    question_level = reasoning and any(r.kind == "question" for r in requirements)
    final = schema["oneOf"][1] if "oneOf" in schema else schema
    final["required"] = ["claims", "missing_information"]
    if need_refs:
        final["properties"]["missing_need_inputs"] = dict(
            type="object",
            additionalProperties=False,
            properties={ref: dict(type="array", items=dict(type="string")) for ref in need_refs},
        )
    ids = [e["id"] for e in evidence]
    choices = []
    parent_schema = None
    operation = schema["$defs"]["DynamicOperation"]["properties"]
    required = schema["$defs"]["DynamicOperation"]["required"]
    operation.pop("operation_id")
    required.remove("operation_id")
    if "period_relation" not in required:
        required.append("period_relation")
    operation["period_relation"]["description"] = (
        "Khai rõ theo kỳ nguồn: same nếu cùng kỳ; across_periods nếu khác kỳ, kể cả divide."
    )
    operation["inputs"]["items"]["description"] = (
        "E handle hoặc R1/R2/... của bước TRƯỚC trong chính steps, đánh số từ 1 bởi Python. "
        "Không dùng D/S handles, số literal, nhãn hay statement; Python kiểm/thực thi dependencies."
    )
    step_refs = [f"R{i}" for i in range(1, 12)]
    if not reasoning:
        operation["inputs"]["items"]["enum"] = ids + step_refs
    fact_ids = ids if operand_ids is None else list(operand_ids)
    if ids and role != "retrieval":
        analysis = deepcopy(final["properties"]["analyses"]["items"])
        analysis["required"] = ["statement"]
        analysis["properties"].pop("goal", None)
        analysis["properties"].pop("operations", None)
        analysis["properties"]["claim_type"].pop("default", None)
        analysis["properties"]["evidence_ids"]["items"]["enum"] = ids
        analysis["description"] = (
            "steps mặc định derived_fact. Chỉ có evidence_ids mặc định reasoned_conclusion."
        )
        operators = operation["operator"]["enum"]
        terminal = "FinalOperation"
        if fact_ids:
            # Final mirrors Calculator arity and accepts only fact handles as operands.
            # Keep Tool preview on the existing DynamicOperation schema.
            schema["$defs"]["FinalOperand"] = dict(
                type="string",
                enum=fact_ids + list(parent_operands) + ([] if reasoning else step_refs),
            )
            inputs = dict(
                type="array",
                minItems=operation["inputs"]["minItems"],
                maxItems=operation["inputs"]["maxItems"],
                items=dict(type="string", enum=fact_ids + list(parent_operands) + step_refs)
                if reasoning
                else {"$ref": "#/$defs/FinalOperand"},
            )
            aggregates = ["sum", "mean", "add"] if question_level else ["sum", "mean"]
            binary = dict(
                type="object",
                additionalProperties=False,
                required=required,
                properties=dict(
                    operator=dict(
                        type="string", enum=[op for op in operators if op not in aggregates]
                    ),
                    inputs=dict(inputs, maxItems=2),
                    period_relation={"$ref": "#/$defs/DynamicOperation/properties/period_relation"},
                ),
            )
            schema["$defs"]["FinalAggregateOperation"] = dict(
                binary,
                properties=dict(
                    binary["properties"],
                    operator=dict(type="string", enum=aggregates),
                    inputs=inputs,
                ),
            )
            aggregate = {"$ref": "#/$defs/FinalAggregateOperation"}
            schema["$defs"]["FinalOperation"] = dict(anyOf=[binary, aggregate])
            analysis["required"].append("steps")
            analysis["properties"]["steps"] = dict(
                type="array", minItems=1, maxItems=12, items={"$ref": "#/$defs/FinalOperation"}
            )
            if reasoning:
                limits = _step_input_limits(schema["$defs"], "FinalOperand", step_refs)
                analysis["properties"]["steps"].update(
                    prefixItems=[{"$ref": "#/$defs/FinalOperation", **limit} for limit in limits],
                    items=False,
                )
        # Calculator comparison operators always produce boolean and cannot feed another step.
        comparators = {"greater", "less", "equal"}
        requirements = tuple(requirements)
        if (
            reasoning
            and fact_ids
            and requirements
            and all(
                r.answer_goal == r.aspect == "value"
                and not r.interpretation
                and r.requested_unit != "boolean"
                and (
                    (r.kind == "fact" and not r.reasoning_operations)
                    or (
                        r.kind == "metric"
                        and r.reasoning_operations
                        and set(r.reasoning_operations) <= set(operators)
                        and r.reasoning_operations[-1] not in comparators
                    )
                )
                for r in requirements
            )
        ):
            terminal = "NumericFinalOperation"
            numeric_step = deepcopy(binary)
            numeric_step["properties"]["operator"]["enum"] = [
                operator
                for operator in binary["properties"]["operator"]["enum"]
                if operator not in comparators
            ]
            schema["$defs"][terminal] = dict(anyOf=[numeric_step, aggregate])
        if reasoning:
            schema["$defs"]["EvidenceHandle"] = dict(type="string", enum=ids)
            handle = {"$ref": "#/$defs/EvidenceHandle"}
            fields = {
                key: {k: v for k, v in spec.items() if k != "title"}
                for key, spec in analysis["properties"].items()
            }
            evidence_ids = dict(fields["evidence_ids"], items=handle)
            annotations = {key: fields[key] for key in ("assumptions", "limitations")}
            choices.append(_reasoning_action("direct", ["evidence_id"], evidence_id=handle))
            choices.extend(
                _reasoning_action(
                    "calculate",
                    ["formula_id", "operands"],
                    **_formula_fields(formula, "operands"),
                )
                for formula in formulas
            )
            if operand_count and not question_level:
                allowed = [
                    op
                    for op in operators
                    if terminal != "NumericFinalOperation" or op not in comparators
                ]
                modes = [indexed_calculation_schema(operand_count, allowed)]
                if parent_decision and parent_operands:
                    parent_schema = _calculation_decision_schema(
                        dict(type="string", enum=list(parent_operands)), allowed
                    )
                    modes.append(parent_schema)
                for mode in modes:
                    choices.append(
                        mode
                        | _reasoning_action("calculate", mode["required"], **mode["properties"])
                    )
            if fact_ids and question_level:
                choices.append(_reasoning_action("calculate", ["steps"], steps=fields["steps"]))
            elif fact_ids:
                final_step = {"$ref": f"#/$defs/{terminal}"}
                calculation = _reasoning_action(
                    "calculate",
                    ["final_step"],
                    prior_steps=dict(
                        fields["steps"],
                        minItems=0,
                        maxItems=11,
                        prefixItems=fields["steps"]["prefixItems"][:-1],
                        description="Chỉ khai nếu cần kết quả trung gian để tính final_step.",
                    ),
                    final_step=final_step | limits[-1],
                    evidence_ids=evidence_ids,
                    **annotations,
                )
                calculation["allOf"] = [
                    {
                        "if": dict(properties=dict(prior_steps=dict(maxItems=i))),
                        "then": dict(properties=dict(final_step=limit)),
                    }
                    for i, limit in enumerate(limits[:-1])
                ]
                choices.append(calculation)
            interpretation = dict(statement=fields["statement"], evidence_ids=evidence_ids)
            kind = dict(type="string", enum=["reasoned_conclusion", "conditional_inference"])
            choices.append(
                _reasoning_action(
                    "interpret",
                    ["statement", "evidence_ids"],
                    **interpretation,
                    **(dict(kind=kind, **annotations) if not question_level else {}),
                )
            )
            if fact_ids and not question_level:
                choices.append(
                    _reasoning_action(
                        "interpret",
                        ["statement", "steps"],
                        **interpretation,
                        steps=fields["steps"],
                        kind=kind,
                        **annotations,
                    )
                )
        else:
            choices.append(
                dict(type="string", enum=ids, description="Numeric claim: E handle only")
            )
            evidence_only = dict(deepcopy(analysis), required=["statement", "evidence_ids"])
            evidence_only["properties"].pop("steps", None)
            evidence_only["properties"]["claim_type"]["enum"].remove("derived_fact")
            choices.append(dict(anyOf=[evidence_only, analysis] if fact_ids else [evidence_only]))
    if documents:
        document = deepcopy(final["properties"]["claims"]["items"]["oneOf"][1])
        document["description"] = (
            "Document Selection để trích nội dung nguồn, không hydrate numeric fact. "
            "S selector phải qua get_financial_fact/calculate_financial_metric để nhận E."
        )
        document["properties"]["source"]["enum"] = list(documents)
        document["properties"]["source"]["description"] = (
            "D handle tài liệu đã nhận từ Tool; không dùng S/E."
        )
        document["properties"]["query"]["description"] = (
            "Nhãn dòng hoặc đoạn nguyên văn thực có trong D source. Không nhận S/E/D handles "
            "hoặc diễn đạt lại câu hỏi; muốn đọc giá trị của S hãy gọi Financial Tool để nhận E."
        )
        choices.append(
            _reasoning_action("document", document["required"], **document["properties"])
            if reasoning
            else document
        )
    claims = final["properties"]["claims"]
    claims["items"] = dict(oneOf=choices) if choices else dict(type="string")
    if not choices:
        claims["maxItems"] = 0
    if role == "retrieval":
        final["required"] = ["missing_information"]
        claims.update(items=dict(type="string"), maxItems=0)
    final["properties"].pop("analyses")
    if "oneOf" in schema:
        call = schema["oneOf"][0]["properties"]["tool_calls"]["items"]
        call["properties"]["tool"]["enum"] = list(tools)
        # S namespace is compact; the executor still resolves exact identity/kind.
        # Never serialize the entire source catalog merely to constrain Tool args.
        signatures = {
            "get_financial_fact": (
                "source",
                dict(
                    type="string",
                    pattern=r"^S[0-9]+$",
                    description="S selector kind=fact từ inventory/numeric_sources; Tool hydrate E có provenance. Chọn E để trả giá trị, không đặt S vào Document Selection.query.",
                ),
            ),
            "calculate_financial_metric": (
                "source",
                dict(
                    type="string",
                    pattern=r"^S[0-9]+$",
                    description="S selector kind=metric đã đăng ký; Tool tính và cấp metric evidence E. Không dùng D hoặc literal value làm selector.",
                ),
            ),
            "get_evidence_item": (
                "source",
                dict(type="string", enum=list(documents)),
            ),
            "get_evidence_sources": (
                "evidence_id",
                dict(type="string", enum=ids),
            ),
        }
        variants = []
        for name in tools:
            if (name == "get_evidence_item" and not documents) or (
                name in {"get_evidence_sources", "calculate_dynamic"} and not ids
            ):
                continue
            variant = deepcopy(call)
            if need_refs and role != "retrieval":
                variant["properties"]["need_refs"] = dict(
                    type="array", maxItems=128, items=dict(type="string", enum=list(need_refs))
                )
            variant["properties"]["tool"]["enum"] = [name]
            args = dict(type="object", additionalProperties=False)
            if name == "get_evidence_item":
                args.update(
                    required=["source"],
                    properties=dict(
                        source=signatures[name][1],
                        offset=dict(type="integer", minimum=0),
                        limit=dict(type="integer", minimum=1),
                    ),
                )
            elif name == "find_document_evidence":
                args.update(
                    required=["source_page"],
                    properties=dict(
                        source_page=dict(type="integer", minimum=1),
                        evidence_type=dict(type="string", enum=["text", "table"]),
                    ),
                )
            elif name in signatures:
                parameter, value_schema = signatures[name]
                args.update(required=[parameter], properties={parameter: value_schema})
            elif name == "find_financial_facts":
                fields = FindFinancialFactsRequest.model_json_schema()["properties"]
                filters = []
                # Disjoint complete objects avoid backend anyOf/property intersections.
                for selector, keys in (
                    (
                        "canonical_item_id",
                        {"canonical_item_id", "statement_type", "period", "source_page"},
                    ),
                    ("statement_type", {"statement_type", "period", "source_page"}),
                    ("source_page", {"period", "source_page"}),
                    *(
                        [("source_label", {"source_label", "statement_type", "period"})]
                        if question_level
                        else []
                    ),
                ):
                    properties = {
                        key: deepcopy(value) for key, value in fields.items() if key in keys
                    }
                    # Identity's unanchored \S is not a one-character wire grammar.
                    # M4 still validates the original Identity after Tool binding.
                    properties["period"] = dict(
                        anyOf=[dict(type="string", minLength=1), dict(type="null")]
                    )
                    properties[selector] = (
                        dict(type="integer", minimum=1)
                        if selector == "source_page"
                        else dict(type="string", enum=["B01", "B02", "B03", "B09"])
                        if selector == "statement_type"
                        else dict(type="string", minLength=1)
                    )
                    filters.append(
                        dict(
                            type="object",
                            additionalProperties=False,
                            required=[selector],
                            properties=properties,
                        )
                    )
                args = dict(oneOf=filters)
            elif name == "calculate_dynamic":
                steps = dict(
                    type="array",
                    minItems=1,
                    maxItems=12,
                    items={"$ref": "#/$defs/DynamicOperation"},
                )
                if reasoning:
                    tool_limits = (
                        limits
                        if ids == fact_ids and not parent_operands
                        else _step_input_limits(schema["$defs"], "EvidenceHandle", step_refs)
                    )
                    steps.update(
                        prefixItems=[
                            {"$ref": "#/$defs/DynamicOperation", **limit} for limit in tool_limits
                        ],
                        items=False,
                    )
                args.update(
                    required=["steps"],
                    properties=dict(steps=steps),
                )
            else:
                model, fields, required = (
                    (
                        SearchDocumentEvidenceRequest,
                        {"query", "evidence_type", "top_k", "context_radius", "source_page"},
                        ["query"],
                    )
                    if name == "search_document_evidence"
                    else (
                        SearchHybridEvidenceRequest,
                        {"query", "top_k"},
                        ["query"],
                    )
                    if name == "search_hybrid_evidence"
                    else (
                        GetGraphContextRequest,
                        {"node_id", "depth", "limit", "relations"},
                        ["node_id"],
                    )
                )
                args.update(
                    required=required,
                    properties={
                        key: value
                        for key, value in model.model_json_schema()["properties"].items()
                        if key in fields
                    },
                )
            variant["properties"]["args"] = args
            variants.append(variant)
        if reasoning and not variants:
            schema["oneOf"].pop(0)
        else:
            schema["oneOf"][0]["properties"]["tool_calls"]["items"] = dict(oneOf=variants)
    if reasoning:
        missing = dict(type="array", items=dict(type="string"))
        notes = {
            k: final["properties"][k] for k in ("missing_need_inputs",) if k in final["properties"]
        }
        branches = []
        if choices:
            branches.append(
                dict(
                    type="object",
                    additionalProperties=False,
                    required=["actions"],
                    properties=dict(
                        actions=dict(
                            type="array",
                            minItems=1,
                            maxItems=claims["maxItems"],
                            items=dict(oneOf=choices),
                        ),
                        missing_information=missing,
                        **notes,
                    ),
                )
            )
        branches.append(
            _reasoning_action(
                "need_more",
                ["missing_information"],
                missing_information=dict(
                    type="array", minItems=1, items=dict(type="string", minLength=1)
                ),
                **notes,
            )
        )
        if "oneOf" in schema:
            index = schema["oneOf"].index(final)
            schema["oneOf"][index : index + 1] = branches
        else:
            schema = dict(type="object", oneOf=branches, **{"$defs": schema["$defs"]})
        if parent_schema:
            parent_schema["properties"]["action"] = dict(type="string", enum=["calculate"])
            schema["oneOf"].append(parent_schema)
    if reasoning and (need_refs or any(r.kind == "question" for r in requirements)):
        from .coordinator_plan import TaskProposal

        fields = TaskProposal.model_json_schema()["properties"]
        work = dict(
            type="object",
            additionalProperties=False,
            required=["request_work"],
            properties=dict(
                request_work=dict(
                    type="object",
                    additionalProperties=False,
                    required=["objective"],
                    properties=dict(
                        role=dict(type="string", enum=["retrieval"]),
                        objective=fields["objective"],
                        need_refs=dict(
                            type="array",
                            minItems=int(bool(need_refs)),
                            maxItems=len(need_refs),
                            items=dict(type="string", enum=list(need_refs))
                            if need_refs
                            else dict(type="string"),
                        ),
                        input_results=dict(
                            type="array",
                            maxItems=min(6, len(input_results)),
                            items=dict(type="string", enum=list(input_results))
                            if input_results
                            else dict(type="string"),
                        ),
                    ),
                ),
                missing_information=dict(type="array", items=dict(type="string")),
            ),
        )
        if "oneOf" in schema:
            schema["oneOf"].append(work)
        else:
            schema = dict(
                type="object",
                **{"$defs": schema["$defs"]},
                oneOf=[{k: v for k, v in schema.items() if k != "$defs"}, work],
            )
    if question_level:
        refs = [*ids, *documents]
        schema["$defs"]["RequirementBinding"] = dict(
            type="object",
            additionalProperties=False,
            properties=dict(
                requirement=dict(type="string", minLength=1),
                kind=dict(type="string", enum=["answer", "operand", "condition"]),
                evidence_refs=dict(
                    type="array",
                    maxItems=min(8, len(refs)),
                    items=dict(type="string", enum=refs) if refs else dict(type="string"),
                ),
            ),
            required=["requirement", "kind", "evidence_refs"],
        )
        for branch in schema["oneOf"]:
            if "tool_calls" in branch["properties"]:
                continue
            branch["properties"] = dict(
                requirement_mapping=dict(
                    type="array",
                    minItems=1,
                    maxItems=20,
                    items={"$ref": "#/$defs/RequirementBinding"},
                ),
                **branch["properties"],
            )
            branch["required"].insert(0, "requirement_mapping")
    return schema


def check_requirement_mapping(rows, claims):
    """Require exactly the sources mapped as operands in the terminal Calculator proof."""
    used = set()
    for claim in claims:
        if isinstance(claim, dict) and (steps := claim.get("steps")):
            leaves = {f"R{len(steps)}"}
            for i, step in reversed(list(enumerate(steps, 1))):
                output = f"R{i}"
                if output in leaves:
                    leaves.remove(output)
                    leaves.update(step["inputs"])
            used.update(leaves)
    operands = [row["evidence_refs"] for row in rows if row["kind"] == "operand"]
    if used and (not all(operands) or used != {ref for refs in operands for ref in refs}):
        raise ValueError("calculator_operands_do_not_match_requirements")


def expand_steps(steps):
    """Expand positional step references; never select operands or repair an operation."""
    if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
        raise ValueError("dynamic_graph_bounds")
    operations, evidence_ids = [], []
    step_ids = {f"R{i}" for i in range(1, 13)}
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != {"operator", "inputs", "period_relation"}:
            raise ValueError("dynamic_step_invalid")
        try:
            operation = DynamicOperation.model_validate(
                dict(step, operation_id=f"R{index}"), strict=True
            )
        except ValidationError:
            raise ValueError("dynamic_step_invalid") from None
        previous = {op["operation_id"] for op in operations}
        if any(key in step_ids - previous for key in operation.inputs):
            raise ValueError("dynamic_dependency_invalid")
        evidence_ids.extend(key for key in operation.inputs if key not in previous)
        operations.append(operation.model_dump(mode="json"))
    return dict(evidence_ids=list(dict.fromkeys(evidence_ids)), operations=operations)


def _project_calculation_steps(steps, aliases, parents):
    """Inline referenced parent proofs into the existing, replayable Calculator DAG."""
    projected, local, inherited = [], {}, {}
    for index, step in enumerate(steps, 1):
        inputs = []
        for ref in step["inputs"]:
            if ref in parents:
                if ref not in inherited:
                    operations = [row["operation"] for row in parents[ref]["steps"]]
                    rebase = {
                        op["operation_id"]: f"R{i}"
                        for i, op in enumerate(operations, len(projected) + 1)
                    }
                    projected.extend(
                        dict(
                            operator=op["operator"],
                            period_relation=op["period_relation"],
                            inputs=[rebase.get(key, key) for key in op["inputs"]],
                        )
                        for op in operations
                    )
                    inherited[ref] = rebase[operations[-1]["operation_id"]]
                inputs.append(inherited[ref])
            elif ref in aliases:
                inputs.append(aliases[ref])
            elif ref in local:
                inputs.append(local[ref])
            else:
                raise ValueError("dynamic_dependency_invalid")
        # Preserve the left-to-right Decimal evaluation and declared period relation.
        if step["operator"] == "add" and len(inputs) > 2:
            left, *rest = inputs
            for right in rest:
                projected.append(dict(step, inputs=[left, right]))
                left = f"R{len(projected)}"
        else:
            projected.append(dict(step, inputs=inputs))
        local[f"R{index}"] = f"R{len(projected)}"
    return projected


def _indexed_step(operator, indices, operands, period_relation=None):
    """Resolve a single decision against the operand table advertised for this call."""
    if any(type(index) is not int or not 0 <= index < len(operands) for index in indices):
        raise ValueError("calculation_operand_index_invalid")
    return _selected_step(operator, [operands[index] for index in indices], period_relation)


def _selected_step(operator, selected, period_relation):
    periods = {period for _, periods in selected for period in periods}
    actual_relation = "across_periods" if len(periods) > 1 else "same"
    if period_relation is not None:
        if any(not periods or not all(periods) for _, periods in selected):
            raise ValueError("calculation_period_metadata_missing")
        if period_relation != actual_relation:
            raise ValueError("calculation_period_relation_mismatch")
    return dict(
        operator=operator,
        inputs=[handle for handle, _ in selected],
        period_relation=actual_relation,
    )


def project_reasoning_actions(
    payload,
    *,
    aliases,
    objective,
    parent_calculations=None,
    indexed_operands=(),
    formulas=(),
    parent_decision=False,
):
    """Project a schema-validated Final into the existing proposal shapes."""
    claims, analyses, scalars = [], [], []
    for index, item in enumerate(payload.get("actions", ())):
        action = item["action"]
        fields = {key: value for key, value in item.items() if key != "action"}
        if action == "direct":
            claims.append(aliases[fields["evidence_id"]])
            scalars.append(index)
        elif action == "document":
            claims.append(fields)
        else:
            if action == "calculate":
                if "formula_id" in fields:
                    operands = {role: aliases.get(eid) for role, eid in fields["operands"].items()}
                    matches = [
                        f
                        for f in formulas
                        if (f["formula_id"], f["operands"]) == (fields["formula_id"], operands)
                    ]
                    if len(matches) != 1:
                        raise ValueError("formula_operand_binding_invalid")
                    (formula,) = matches
                    fields = dict(
                        steps=[
                            dict(
                                operator=formula["operator"],
                                inputs=[fields["operands"][role] for role in formula["operands"]],
                                period_relation="same",
                            )
                        ]
                    )
                elif "operator" in fields:
                    operator, inputs = fields.pop("operator"), fields.pop("inputs")
                    relation = fields.pop("period_relation", None)
                    if parent_decision and any(isinstance(ref, str) for ref in inputs):
                        parents = parent_calculations or {}
                        if any(not isinstance(ref, str) or ref not in parents for ref in inputs):
                            raise ValueError("calculation_parent_handle_invalid")
                        step = _selected_step(
                            operator,
                            [(ref, parents[ref]["steps"][-1]["periods"]) for ref in inputs],
                            relation,
                        )
                    else:
                        step = _indexed_step(operator, inputs, indexed_operands, relation)
                    fields["steps"] = [step]
                elif "steps" not in fields:
                    fields["steps"] = [*fields.pop("prior_steps", ()), fields.pop("final_step")]
                fields.update(statement=objective, claim_type="derived_fact")
            else:
                fields["claim_type"] = fields.pop("kind", "reasoned_conclusion")
            if "evidence_ids" in fields:
                fields["evidence_ids"] = [aliases[e] for e in fields["evidence_ids"]]
            if "steps" in fields:
                fields["steps"] = _project_calculation_steps(
                    fields["steps"], aliases, parent_calculations or {}
                )
            claims.append(fields)
            analyses.append(index)
    proposal = dict(claims=claims, missing_information=payload.get("missing_information", []))
    if "missing_need_inputs" in payload:
        proposal["missing_need_inputs"] = payload["missing_need_inputs"]
    return proposal, (analyses, scalars)


def _prepare_analysis(raw, evidence_by_id):
    """Keep source annotations in the backend; resolve declared operand handles."""
    if isinstance(raw, dict) and isinstance(raw.get("evidence_ids"), list):
        sources = [e for key, e in evidence_by_id.items() if key in raw["evidence_ids"]]
        source_caveats = {note for source in sources for note in source.caveats}
        if isinstance(raw.get("limitations"), list):
            raw = dict(
                raw,
                limitations=[
                    note
                    for note in raw["limitations"]
                    if not isinstance(note, str) or note not in source_caveats
                ],
            )
    analysis = AnalysisProposal.model_validate(raw)
    ids = list(
        dict.fromkeys(
            analysis.evidence_ids
            + [
                key
                for operation in analysis.operations
                for key in operation.inputs
                if key in evidence_by_id and evidence_by_id[key].kind == "fact"
            ]
        )
    )
    analysis = AnalysisProposal.model_validate(dict(analysis.model_dump(), evidence_ids=ids))
    return analysis


class SpecialistTrace(FinancialModel):
    stage: Literal["selection", "generation", "grounding"]
    outcome: str
    evidence_id: str | None = None
    proposal_index: int | None = None
    reasons: list[str] = Field(default_factory=list)


class SpecialistResult(FinancialModel):
    version: Literal[
        "profitability_specialist_v1",
        "liquidity_leverage_specialist_v1",
        "cash_flow_earnings_quality_specialist_v1",
    ] = "profitability_specialist_v1"
    role: SpecialistRole = "profitability"
    question: str
    upstream_status: Literal["completed", "partial", "blocked", "failed"]
    candidates: list[SpecialistCandidate] = Field(default_factory=list)
    supporting_evidence: list[SpecialistEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    status: Literal["generated", "partial", "abstained", "failed"] = "abstained"
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    raw_output: Any = None
    trace: list[SpecialistTrace] = Field(default_factory=list)
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False


def _unique(values):
    return list({v.model_dump_json(): v for v in values}.values())


def source_projection(evidence):
    """Project selected citation bindings without upgrading source precision."""
    groups = {}
    for citation in evidence.citations:
        json_page = (
            citation.source.reference.anchor.page.page
            if (citation.source.reference and is_json_reference(citation.source.reference))
            else None
        )
        key = (
            citation.document_id,
            citation.snapshot_id,
            citation.pdf_page,
            citation.provenance_level,
            json_page,
        )
        row = groups.setdefault(
            key,
            dict(
                document_id=key[0],
                snapshot_id=key[1],
                pdf_page=key[2],
                provenance_level=key[3],
                availability="linked",
                selector_available=False,
                limitations=[],
            ),
        )
        reference = citation.source.reference
        if json_page is not None:
            row.update(source_kind="json", json_page=json_page)
        row["selector_available"] |= bool(reference and reference.source_pointer)
        row["limitations"] = sorted(set(row["limitations"] + citation.limitations))
    return dict(
        availability="linked" if groups else "missing",
        bindings=list(groups.values()),
        caveats=evidence.caveats,
    )


def _number(value):
    # Display only; never calculate a new financial metric or silently change scale.
    return format(Decimal(value), ",f").translate(str.maketrans({",": ".", ".": ","}))


def _citations_valid(citations, document, snapshot, sources, bundle):
    return bool(citations) and all(
        c in bundle.citations
        and c.document_id == c.source.document_id == document
        and c.snapshot_id == c.source.snapshot_id == snapshot
        and c.source in sources
        and c.source.source_key() is not None
        and c.anchor_id == graph_id("anchor", c.source.source_key())
        and c.source.reference is not None
        and (
            c.pdf_page == c.source.reference.anchor.page.page
            or (c.pdf_page is None and "json_source_not_pdf_verified" in c.limitations)
        )
        and c.provenance_level == c.source.reference.provenance_level
        for c in citations
    )


def _fact_error(match, bundle):
    fact = match.record
    if fact.source_metadata.get("source_kind") == "refined_json" and not match.json_source_bound:
        return match.json_source_issue or "json_fact_unbound_or_ineligible"
    decisions = [q.decision for q in fact.quality_context if q.task_type == "direct_qa"]
    if (
        not fact.company_id
        or not fact.context.period
        or not fact.context.scale
        or not fact.value.unit
        or fact.value.status != "resolved"
        or fact.value.normalized_value is None
        or match.reference.observation != fact.observation_identity()
    ):
        return "fact_context_or_identity_missing"
    if (
        match.display_status == "blocked"
        or not decisions
        or any(d in {"insufficient", "conflicted"} for d in decisions)
        or (
            not match.json_source_bound
            and (
                match.source_review.status != "found"
                or not match.source_review.matches
                or any(
                    v.observation != fact.observation_identity()
                    or v.original_sources != fact.sources
                    or v.status in {"source_inconsistent", "source_missing"}
                    for v in match.source_review.matches
                )
            )
        )
    ):
        return "fact_conflicted_or_unusable"
    if not _citations_valid(
        match.citations, fact.document_id, fact.snapshot_id, fact.sources, bundle
    ):
        return "fact_citations_missing_or_mismatched"
    return None


def _metric_error(calc, bundle):
    evidence, trace = calc.evidence, calc.trace
    if (
        calc.status != "computed"
        or calc.result is None
        or evidence is None
        or trace is None
        or not evidence.closure.calculation_eligible
        or evidence.closure.status != "closed"
        or evidence.reviewed_lineage.status != "found"
        or evidence.reviewed_lineage.lineage is None
        or evidence.reviewed_lineage.lineage.completeness != "complete"
    ):
        return "metric_trace_or_lineage_incomplete"
    if (
        calc.metric_id != evidence.record.metric_id
        or calc.document_id != evidence.record.request.document_id
        or calc.snapshot_id != evidence.record.request.snapshot_id
        or calc.formula_id != evidence.record.definition.name
        or calc.formula_id != trace.formula.formula_id
        or calc.formula_id != trace.approval.formula_id
        or calc.formula_version != trace.formula.version
        or calc.formula_version != trace.approval.version
        or calc.formula_digest != trace.formula.definition_digest()
        or calc.formula_digest != trace.approval.definition_sha256
    ):
        return "metric_formula_binding_mismatch"
    if (
        evidence.closure.metric_id != calc.metric_id
        or evidence.reviewed_lineage.lineage.metric_id != calc.metric_id
        or evidence.reviewed_lineage.lineage.request != evidence.record.request
        or Decimal(calc.result) != Decimal(trace.scaled_value).quantize(Decimal("0.01"))
    ):
        return "metric_result_or_lineage_binding_mismatch"
    operands = trace.operands
    if len(operands) != 2 or len({o.role for o in operands}) != 2:
        return "metric_operand_missing"
    for operand in operands:
        facts = [f for f in bundle.facts if f.reference.observation == operand.observation]
        bindings = [b for b in evidence.record.operands if b.role == operand.role]
        if (
            len(facts) != 1
            or len(bindings) != 1
            or bindings[0].observation != operand.observation
            or bindings[0].source_fact_node_id != operand.source_fact_node_id
            or evidence.record.request.operand_periods.get(operand.role) != operand.context.period
            or _fact_error(facts[0], bundle)
            or operand.observation.document_id != calc.document_id
            or operand.observation.snapshot_id != calc.snapshot_id
            or operand.value != str(facts[0].record.value.normalized_value)
            or operand.unit != facts[0].record.value.unit
            or operand.context != facts[0].record.context
            or operand.company_id != facts[0].record.company_id
        ):
            return "metric_operand_binding_mismatch"
    if len({o.company_id for o in operands}) != 1:
        return "metric_company_mismatch"
    if not _citations_valid(
        evidence.citations,
        calc.document_id,
        calc.snapshot_id,
        [
            s
            for f in bundle.facts
            if f.reference.observation in {o.observation for o in operands}
            for s in f.record.sources
        ],
        bundle,
    ):
        return "metric_citations_missing_or_mismatched"
    return None


def select_evidence(
    upstream, result, *, item_labels, metric_labels, period_roles, balance_sheet=False
):
    bundle = upstream.evidence_bundle

    # Conflicts within the same observation or same financial context block all
    # variants, rather than picking the first record.
    def key(f):
        r = f.record
        return (
            r.document_id,
            r.snapshot_id,
            r.company_id,
            r.canonical_item_id or r.local_observation_id,
            (
                r.context.period,
                r.context.period_type,
                r.context.reporting_scope,
                r.context.currency,
                str(r.context.scale),
            ),
            r.value.unit,
        )

    groups = {}
    for fact in bundle.facts:
        groups.setdefault(key(fact), set()).add(fact.record.model_dump_json())
    rejected_observations = set()
    for fact in bundle.facts:
        record = fact.record
        if (
            bundle.claim_fact_references is not None
            and fact.reference not in bundle.claim_fact_references
        ):
            continue
        error = _fact_error(fact, bundle)
        if len(groups[key(fact)]) > 1:
            error = "conflicting_fact_variants"
        if error:
            rejected_observations.add(fact.reference.observation)
            result.missing_evidence.append(error)
            result.trace.append(
                SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
            )
            continue
        caveats = [
            *fact.issues,
            *fact.reporting_scope.reasons,
            *[c for view in fact.source_review.matches for c in view.quality_caveats],
            *[i.code for i in record.resolution_issues],
            *[c for q in record.quality_context for c in [q.decision, *q.caveats]],
            *[c for cite in fact.citations for c in cite.limitations],
        ]
        result.supporting_evidence.append(
            SpecialistEvidence(
                evidence_id="",
                kind="fact",
                reference=fact.reference,
                company_id=record.company_id,
                document_id=record.document_id,
                snapshot_id=record.snapshot_id,
                period=record.context.period,
                label=record.context.raw_item_label
                or item_labels.get(record.canonical_item_id, ""),
                canonical_item_id=record.canonical_item_id,
                value=str(record.value.normalized_value),
                unit=record.value.unit,
                scale=str(record.context.scale),
                citations=fact.citations,
                caveats=sorted(set(caveats)),
            )
        )
    for calc in bundle.calculations:
        if calc.formula_id not in metric_labels:
            continue
        error = _metric_error(calc, bundle)
        if calc.trace and any(o.observation in rejected_observations for o in calc.trace.operands):
            error = "metric_operand_conflicted"
        if error:
            result.missing_evidence.append(error)
            result.trace.append(
                SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
            )
            continue
        periods = {o.role: o.context.period for o in calc.trace.operands}
        period = periods[period_roles[calc.formula_id]]
        result.supporting_evidence.append(
            SpecialistEvidence(
                evidence_id="",
                kind="metric",
                reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
                company_id=calc.trace.operands[0].company_id,
                document_id=calc.document_id,
                snapshot_id=calc.snapshot_id,
                period=period,
                operand_periods=periods,
                label=metric_labels[calc.formula_id],
                value=calc.result,
                unit="percent",
                citations=calc.evidence.citations,
                caveats=sorted(
                    set(
                        calc.caveats
                        + [c for cite in calc.evidence.citations for c in cite.limitations]
                    )
                ),
                calculation=calc,
            )
        )
    result.supporting_evidence = _unique(result.supporting_evidence)
    # Planner permits 32 indicators and 8 approved metrics. A larger digest must
    # not discard every independently usable source.
    if len(result.supporting_evidence) > 40:
        result.missing_evidence.append("evidence_digest_limit_exceeded")
        result.supporting_evidence = result.supporting_evidence[:40]
    for index, evidence in enumerate(result.supporting_evidence, 1):
        evidence.evidence_id = f"E{index:03d}"


def with_assignment(prompt, upstream):
    """Scope a projected call without rewriting the original user question."""
    if upstream.evidence_bundle.claim_fact_references is None:
        return prompt
    query = upstream.final_plan_state.query
    reasoning = any(c.startswith("PLANNER_TASK:") for c in upstream.evidence_bundle.limitations)
    if reasoning:
        prompt = dict(
            prompt,
            analysis_schema=AnalysisProposal.model_json_schema(),
            instruction=prompt["instruction"]
            + (
                " NHIỆM VỤ PHÂN TÍCH: đọc PLANNER_TASK và PRIOR_AGENT_RESULTS trong limitations. "
                "Grammar mẫu, giới hạn không tính mới và không thêm mệnh đề ở schema claims cũ "
                "chỉ áp dụng claims; analyses dùng contract suy luận và operations bên dưới. "
                "Ngoài claims số liệu theo schema cũ, thêm analyses:[{statement,evidence_ids,limitations}] "
                "để diễn giải quan hệ giữa evidence được giao, trả lời mục tiêu thực tế. "
                "Statement do bạn suy luận, không bị giới hạn vào grammar mẫu số học cũ; "
                "mọi tiền đề phải có evidence_ids. Dùng analyses.operations theo analysis_schema "
                "cho so sánh/phép tính mới; inputs là evidence_id hoặc operation_id trước đó. "
                "greater/less/equal đối chiếu độ lớn, subtract tính chênh lệch, ratio tính tỷ số ad hoc, "
                "percentage_change dùng current trước/prior sau với period_relation=across_periods. "
                "Mọi operation so sánh hoặc tính toán inputs khác kỳ đều phải khai báo "
                "period_relation=across_periods, kể cả subtract/greater/less/equal. "
                "Backend dùng Decimal và M6 replay độc lập; không gọi tỷ số ad hoc là metric chuẩn. "
                "analyses có goal, operations, assumptions, claim_type. "
                "assumptions=[] khi chỉ dùng facts/đơn vị/kỳ đã có trong evidence; không ghi metadata "
                "đã biết thành giả định. Chỉ ghi assumptions cho điều kiện chưa được chứng minh. "
                "Statement diễn giải ý nghĩa của quan hệ đã tính, được chứa số có nguồn hoặc kết quả "
                "kiểm chứng; không đoán nguyên nhân. "
                "Ưu tiên một analysis ngắn trực tiếp đáp ứng task; không lặp các giới hạn thành nhiều claims. "
                "Nếu người dùng hỏi ý nghĩa, đánh giá hay giải thích tính chất phép đối chiếu, phải có "
                "analysis claim_type=reasoned_conclusion với statement tự diễn giải từ evidence/operations; "
                "derived_fact chỉ trình bày phép tính và không thay thế phần diễn giải được hỏi. "
                "Đánh giá có giới hạn cần nói quan hệ đó có ý nghĩa gì trong phạm vi kỳ/chỉ tiêu, "
                "không chỉ lặp số hoặc nói chỉ tiêu này lớn hơn chỉ tiêu kia. "
                "Không chép evidence IDs hay diagnostic flags vào statement/limitations; chúng ở metadata. "
                "Không tự gán tình trạng đã/chưa kiểm toán hoặc tính xác thực của báo cáo nếu evidence "
                "không khai báo điều đó; chỉ nêu đúng giới hạn nguồn được cung cấp. "
                "limitations tối đa 8 ý; backend đã giữ source caveats nên không chép toàn bộ flags vào đây. "
                "statement giải thích ý nghĩa có giới hạn của quan hệ giữa những facts được giao; "
                "tách ý nghĩa của kết quả khỏi việc chỉ nhắc lại kết quả số học. Điều chưa thể kết luận "
                "hoặc nguyên nhân chưa biết ghi riêng trong limitations, không ghép thành claim thiếu nguồn. "
                "Không biến việc agent này chưa được giao một chỉ tiêu thành claim rằng toàn hệ thống thiếu "
                "chỉ tiêu đó. Nếu task vượt phạm vi evidence được giao, ghi giới hạn trong missing_information; "
                "giữ facts hợp lệ, không tạo analysis kết luận về toàn câu hỏi từ chỉ một chỉ tiêu. "
                "Nhận định là candidate_pending_M6, không tự phê duyệt. Thiếu evidence nêu missing_information. "
                "Không dùng prior agent claim làm nguồn thay cho evidence gốc."
            ),
        )
    return dict(
        prompt,
        orchestration_assignment=dict(
            roles=upstream.final_plan_state.specialist_roles,
            assigned_fact_targets=query.required_indicators,
            assigned_formula_targets=query.requested_formula_ids,
        ),
        instruction=prompt["instruction"]
        + (
            " CÂU HỎI GỐC được giữ đầy đủ cho context; bạn CHỈ thực hiện targets trong "
            "orchestration_assignment bằng evidence digest được giao. Các targets thuộc "
            "Specialist khác KHÔNG phải missing_information của bạn. Supporting operands "
            "của metric không phải factual claims độc lập. Không báo thiếu dữ liệu cho "
            "phân tích sâu, so sánh kỳ khác hoặc ratio không được giao. Giữ caveats nguồn "
            "nhưng không tự mở rộng workload."
        ),
    )


def _numeric_proposals(evidence):
    return [
        dict(
            evidence_id=e.evidence_id,
            kind="approved_metric" if e.calculation else "fact",
            meaning="metric_value" if e.calculation else "fact_value",
            period=e.period,
        )
        for e in evidence
    ]


def parse_specialist_output(payload, *, role=None, need_refs=()):
    """Strict role envelopes; legacy shape normalization only for callers without a role."""
    if role is not None and not isinstance(payload, dict):
        raise ValueError("invalid_proposal_envelope")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, list):
        payload = dict(tool_calls=payload)
    elif role is None and isinstance(payload, dict) and set(payload) == {"tool", "args"}:
        payload = dict(tool_calls=[payload])
    if not isinstance(payload, dict):
        raise ValueError("invalid_proposal_envelope")
    if "request_work" in payload:
        from .coordinator_plan import TaskProposal

        work = payload["request_work"]
        if (
            role != "reasoning"
            or set(payload) - {"request_work", "missing_information"}
            or not isinstance(work, dict)
            or "objective" not in work
            or set(work) - {"role", "objective", "need_refs", "input_results"}
        ):
            raise ValueError("work_request_invalid")
        work = dict(role="retrieval", need_refs=list(need_refs), input_results=[]) | work
        payload = dict(payload, request_work=work)
        try:
            TaskProposal.model_validate(
                {k: work[k] for k in ("role", "objective", "need_refs")}, strict=True
            )
        except ValidationError:
            raise ValueError("work_request_invalid") from None
        if (
            work["role"] != "retrieval"
            or not isinstance(work["input_results"], list)
            or any(not isinstance(ref, str) for ref in work["input_results"])
        ):
            raise ValueError("work_request_invalid")
        if not isinstance(payload.get("missing_information", []), list) or any(
            not isinstance(note, str) for note in payload.get("missing_information", [])
        ):
            raise ValueError("invalid_missing_information")
        return dict(payload, missing_information=payload.get("missing_information", []))
    if "tool_calls" in payload:
        calls = payload["tool_calls"]
        if (
            set(payload)
            - ({"tool_calls"} if role is not None else {"tool_calls", "missing_information"})
            or not isinstance(calls, list)
            or not 1 <= len(calls) <= 16
        ):
            raise ValueError("tool_calls_schema_invalid")
        missing = payload.get("missing_information", [])
        if not isinstance(missing, list) or any(not isinstance(note, str) for note in missing):
            raise ValueError("invalid_missing_information")
        if any(
            not isinstance(c, dict)
            or not {"tool", "args"} <= c.keys()
            or not isinstance(c["tool"], str)
            or set(c) - {"tool", "args", "need_refs"}
            or not isinstance(c["args"], dict)
            or not isinstance(c.get("need_refs", []), list)
            or len(c.get("need_refs", [])) > 128
            or any(not isinstance(ref, str) for ref in c.get("need_refs", []))
            for c in calls
        ):
            raise ValueError("tool_request_invalid")
        if role is not None:
            payload = deepcopy(payload)
            for call in payload["tool_calls"]:
                if call["tool"] not in SPECIALIST_TOOLS_BY_ROLE.get(role, ()):
                    raise ValueError("tool_not_allowed_for_role")
                if call["tool"] == "calculate_dynamic":
                    if set(call["args"]) != {"steps"}:
                        raise ValueError("tool_args_invalid")
                    call["args"] = expand_steps(call["args"]["steps"])
        return payload
    if role is not None and "analyses" in payload:
        raise ValueError(
            "retrieval_candidates_forbidden"
            if role == "retrieval" and payload["analyses"]
            else "invalid_proposal_envelope"
        )
    if role == "retrieval":
        payload = dict(
            payload, claims=payload.get("claims", []), analyses=payload.get("analyses", [])
        )
        if payload["claims"] or payload["analyses"]:
            raise ValueError("retrieval_candidates_forbidden")
    if (
        set(payload) - {"missing_need_inputs"}
        not in ({"claims", "missing_information"}, {"claims", "missing_information", "analyses"})
        or not isinstance(payload["claims"], list)
        or len(payload["claims"]) > 32
    ):
        raise ValueError("invalid_proposal_envelope")
    missing, analyses = payload["missing_information"], payload.get("analyses", [])
    missing_needs = payload.get("missing_need_inputs", {})
    if not isinstance(missing_needs, dict) or any(
        not isinstance(ref, str)
        or not isinstance(notes, list)
        or any(not isinstance(note, str) for note in notes)
        for ref, notes in missing_needs.items()
    ):
        raise ValueError("invalid_missing_need_inputs")
    if not isinstance(missing, list) or any(not isinstance(m, str) for m in missing):
        raise ValueError("invalid_missing_information")
    if not isinstance(analyses, list) or len(analyses) > 8:
        raise ValueError("invalid_analysis_envelope")
    claims = list(payload["claims"])
    if role == "reasoning":
        analyses, scalar_claims = [], []
        for choice in claims:
            if isinstance(choice, dict) and "statement" in choice:
                raw = dict(choice)
                steps = raw.pop("steps", None)
                if steps is not None:
                    expanded = expand_steps(steps)
                    raw["operations"] = expanded["operations"]
                    raw["evidence_ids"] = list(
                        dict.fromkeys(raw.get("evidence_ids", []) + expanded["evidence_ids"])
                    )
                raw.setdefault("claim_type", "derived_fact" if steps else "reasoned_conclusion")
                try:
                    analyses.append(AnalysisProposal.model_validate(raw, strict=True).model_dump())
                except ValidationError:
                    raise ValueError("invalid_analysis_schema") from None
            else:
                scalar_claims.append(choice)
        claims = scalar_claims
        if len(analyses) > 8:
            raise ValueError("invalid_analysis_envelope")
    for index, choice in enumerate(claims):
        if role is None and isinstance(choice, str) and choice.lstrip().startswith("{"):
            choice = parse_json_output(choice).payload
            if not isinstance(choice, dict) or set(choice) != {"source", "query"}:
                raise ValueError("invalid_claim_schema")
            claims[index] = choice
    return dict(
        payload,
        claims=claims,
        **(dict(analyses=analyses) if role == "reasoning" else {}),
        missing_information=list(
            dict.fromkeys(missing + [n for notes in missing_needs.values() for n in notes])
        ),
    )


def generate_candidates(
    *,
    gateway,
    model,
    result,
    prompt,
    proposal_type,
    render,
    prefix,
    deterministic=False,
    emit_derived=True,
    operation_inputs_only=False,
    numeric_fallback=True,
    candidate_payload=None,
    proposal_order=None,
):
    if candidate_payload is not None:
        payload = candidate_payload
        result.raw_output = payload
    elif deterministic:
        # Existing typed numeric renderers; no model, interpretation or new calculation.
        result.llm.status = "deterministic"
        payload = {
            "claims": _numeric_proposals(result.supporting_evidence),
            "missing_information": [],
        }
    else:
        executions = [
            dict(
                evidence_id=e.evidence_id,
                status=e.calculation.status,
                formula_id=e.calculation.formula_id,
                calculation_eligible=e.calculation.evidence.closure.calculation_eligible,
                verification_status="candidate_pending_M6",
            )
            for e in result.supporting_evidence
            if e.calculation
        ]
        if executions:
            prompt = dict(
                prompt,
                current_metric_executions=executions,
                instruction=prompt["instruction"]
                + (
                    " current_metric_executions là phép tính Tools đã thực hiện, "
                    "có thể dùng làm evidence cho candidate, M6 vẫn phải kiểm chứng ngữ nghĩa."
                ),
            )
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id=prefix + "-" + uuid4().hex,
            model=model,
            messages=[
                Message(
                    role="system",
                    content=json.dumps(
                        compact_prompt(prompt), ensure_ascii=False, separators=(",", ":")
                    ),
                ),
                Message(role="user", content=result.question),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=60.0),
        )
        result.llm.calls, result.llm.model = 1, model
        actual_events = getattr(gateway, "events", None)
        events_before = len(actual_events) if isinstance(actual_events, list) else None
        call_start = perf_counter()
        response = gateway.generate(request)
        if events_before is not None:
            result.llm.calls = len(actual_events) - events_before
        result.llm.latency_ms = (perf_counter() - call_start) * 1000
        result.llm.status, result.llm.usage, result.llm.cost = (
            response.status,
            response.usage,
            response.cost,
        )
        result.llm.provenance, result.llm.error = response.provenance, response.error
        if isinstance(response.output, JSONOutput):
            result.raw_output = response.output.payload
        if response.status != "success" or not isinstance(result.raw_output, dict):
            result.trace.append(
                SpecialistTrace(
                    stage="generation", outcome="excluded", reasons=["gateway_response_failed"]
                )
            )
            payload = {
                "claims": _numeric_proposals(result.supporting_evidence)
                if numeric_fallback
                else [],
                "missing_information": [],
            }
        else:
            payload = result.raw_output
    try:
        payload = parse_specialist_output(payload)
        if "tool_calls" in payload:
            raise ValueError("invalid_proposal_envelope")
    except (ValueError, TypeError, RecursionError) as error:
        result.trace.append(
            SpecialistTrace(stage="generation", outcome="excluded", reasons=[str(error)])
        )
        # Only local, selected source facts are rendered; malformed model text
        # supplies no claim. These candidates still require ordinary native M6.
        payload = {
            "claims": _numeric_proposals(result.supporting_evidence) if numeric_fallback else [],
            "missing_information": [],
        }
    missing = payload["missing_information"]
    if (
        numeric_fallback
        and not deterministic
        and not payload["claims"]
        and not missing
        and result.supporting_evidence
    ):
        # An unexplained empty model response supplies no rejection reason. Reuse
        # the existing numeric pathway only after source/metric selection gates;
        # keep the original model payload and send all candidates through M6.
        payload = dict(payload, claims=_numeric_proposals(result.supporting_evidence))
        result.trace.append(
            SpecialistTrace(
                stage="generation",
                outcome="deterministic_numeric_fallback",
                reasons=["empty_model_claims_without_missing_information"],
            )
        )
    # Model limitations are untrusted annotations, never financial claims.
    result.missing_evidence.extend(missing)
    evidence_by_id = {e.evidence_id: e for e in result.supporting_evidence}
    analyses = payload.get("analyses", [])
    analysis_positions, scalar_positions = proposal_order or ((), ())
    positions = {}
    for index, raw in enumerate(analyses):
        try:
            analysis = _prepare_analysis(raw, evidence_by_id)
            if analysis.claim_type == "derived_fact" and not analysis.operations:
                raise ValueError("derived_fact_requires_computation")
            if set(analysis.evidence_ids) - evidence_by_id.keys():
                raise ValueError("analysis_unknown_evidence")
            sources = [evidence_by_id[key] for key in dict.fromkeys(analysis.evidence_ids)]
            owner = sources[0]
            if any(
                (s.company_id, s.document_id, s.snapshot_id)
                != (owner.company_id, owner.document_id, owner.snapshot_id)
                for s in sources
            ):
                raise ValueError("analysis_context_mismatch")
            computation = None
            if analysis.operations:
                input_ids = {key for op in analysis.operations for key in op.inputs}
                operands = {
                    s.evidence_id: DynamicOperand(
                        **{k: getattr(s, k) for k in DynamicOperand.model_fields}
                    )
                    for s in sources
                    if s.kind == "fact"
                    and (not operation_inputs_only or s.evidence_id in input_ids)
                }
                # Execute exactly the Agent's DAG. A failed operation rejects
                # this analysis, never turns a subtotal into a new conclusion.
                computation = execute_dynamic(operands, analysis.operations)
            reasoning = ReasoningProof(
                claim_type=analysis.claim_type,
                goal=analysis.goal or result.question,
                calculation=computation,
                assumptions=analysis.assumptions,
                limitations=analysis.limitations,
            )
            result.candidates.append(
                SpecialistCandidate(
                    candidate_id=prefix + "-analysis-" + uuid4().hex,
                    kind="supported_interpretation",
                    content=render_dynamic(computation, {s.evidence_id: s.label for s in sources})
                    if analysis.claim_type == "derived_fact"
                    else " ".join(
                        [
                            analysis.statement,
                            *("Giả định: " + a for a in analysis.assumptions),
                            *("Giới hạn: " + note for note in analysis.limitations),
                        ]
                    ),
                    company_id=owner.company_id,
                    document_id=owner.document_id,
                    snapshot_id=owner.snapshot_id,
                    period=owner.period,
                    fact_references=_unique(
                        [
                            r
                            for s in sources
                            for r in (
                                [s.reference]
                                if not s.calculation
                                else [
                                    RetrievalReference(kind="fact", observation=o.observation)
                                    for o in s.calculation.trace.operands
                                ]
                            )
                        ]
                    ),
                    metric_ids=[s.calculation.metric_id for s in sources if s.calculation],
                    supporting_evidence_ids=analysis.evidence_ids,
                    reasoning=reasoning,
                    analysis_premises=[
                        f"{s.label} {'tại ngày' if len(s.period) > 4 else 'kỳ'} {s.period} là {_number(s.value)} "
                        + ("%" if s.unit == "percent" else s.unit)
                        + (f" (hệ số đơn vị {s.scale})" if s.scale != "1" else "")
                        + "."
                        for s in sources
                    ],
                    citations=_unique([c for s in sources for c in s.citations]),
                    # Model-authored caveats are part of the proposition assessed
                    # above, never an unchecked path around numeric/semantic gates.
                    caveats=sorted(set(c for s in sources for c in s.caveats)),
                )
            )
            if analysis_positions:
                positions[result.candidates[-1].candidate_id] = analysis_positions[index]
            if emit_derived and computation and reasoning.claim_type != "derived_fact":
                derived = result.candidates[-1].model_copy(deep=True)
                derived.candidate_id = prefix + "-derived-" + uuid4().hex
                derived.content = render_dynamic(
                    computation, {s.evidence_id: s.label for s in sources}
                )
                derived.reasoning.claim_type = "derived_fact"
                derived.reasoning.assumptions = []
                derived.reasoning.limitations = []
                result.candidates.append(derived)
        except (ValidationError, ValueError, ArithmeticError) as error:
            result.trace.append(
                SpecialistTrace(
                    stage="grounding",
                    outcome="excluded",
                    proposal_index=analysis_positions[index] if analysis_positions else None,
                    reasons=[
                        "invalid_analysis_schema"
                        if isinstance(error, ValidationError)
                        else str(error)
                    ],
                )
            )
    seen = set()
    for index, raw in enumerate(payload["claims"]):
        try:
            proposal = proposal_type.model_validate(raw)
            if proposal.evidence_id not in evidence_by_id:
                raise ValueError("unknown_evidence_id")
            evidence = evidence_by_id[proposal.evidence_id]
            content = render(proposal, evidence)
            key = (proposal.evidence_id, proposal.meaning)
            if key in seen:
                raise ValueError("duplicate_proposition")
            seen.add(key)
            calc = evidence.calculation
            facts = (
                [
                    RetrievalReference(kind="fact", observation=o.observation)
                    for o in calc.trace.operands
                ]
                if calc
                else [evidence.reference]
            )
            result.candidates.append(
                SpecialistCandidate(
                    candidate_id=prefix + "-" + uuid4().hex,
                    kind=proposal.kind,
                    content=content,
                    company_id=evidence.company_id,
                    document_id=evidence.document_id,
                    snapshot_id=evidence.snapshot_id,
                    period=evidence.period,
                    fact_references=facts,
                    metric_ids=[calc.metric_id] if calc else [],
                    supporting_evidence_ids=[evidence.evidence_id],
                    citations=evidence.citations,
                    calculation=calc,
                    caveats=evidence.caveats,
                )
            )
            if scalar_positions:
                positions[result.candidates[-1].candidate_id] = scalar_positions[index]
            result.trace.append(
                SpecialistTrace(
                    stage="grounding",
                    outcome="candidate",
                    evidence_id=proposal.evidence_id,
                    proposal_index=scalar_positions[index] if scalar_positions else index,
                )
            )
        except (ValidationError, ValueError) as error:
            reason = "invalid_claim_schema" if isinstance(error, ValidationError) else str(error)
            result.trace.append(
                SpecialistTrace(
                    stage="grounding",
                    outcome="excluded",
                    proposal_index=scalar_positions[index] if scalar_positions else index,
                    reasons=[reason],
                )
            )
    if positions:
        result.candidates.sort(key=lambda candidate: positions.get(candidate.candidate_id, -1))
    rejected = any(t.outcome == "excluded" for t in result.trace)
    if any(
        reason
        in {
            "gateway_response_failed",
            "invalid_proposal_envelope",
            "invalid_missing_information",
            "invalid_analysis_envelope",
        }
        for trace in result.trace
        for reason in trace.reasons
    ):
        result.limitations.append("specialist_processing_failure")
    result.status = (
        "partial"
        if result.candidates
        and (result.upstream_status == "partial" or result.missing_evidence or rejected)
        else "generated"
        if result.candidates
        else "abstained"
    )
