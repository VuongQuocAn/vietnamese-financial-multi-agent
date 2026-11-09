"""Typed dynamic document/fusion planning through the shared Gateway."""

import json
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
from .document_qa_contracts import DocumentRequirement
from .fusion_contracts import FusionPlan


class DocumentPlan(FinancialModel):
    requirements: list[DocumentRequirement] = Field(min_length=1, max_length=12)
    reasoning_required: bool = False
    selection_reason: str


def structured_call(gateway, model, schema, payload, prefix):
    response = gateway.generate(
        LLMRequest(
            contract_version="llm_gateway_v1",
            request_id=prefix + "-" + uuid4().hex,
            model=model,
            messages=[
                Message(
                    role="user",
                    content=json.dumps(
                        dict(
                            payload,
                            schema=schema.model_json_schema(),
                            response_contract="Return exactly one JSON object at root, never an array or markdown.",
                        ),
                        ensure_ascii=False,
                    ),
                )
            ],
            generation=GenerationParameters(temperature=0, max_output_tokens=3000),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=45),
        )
    )
    if response.status != "success" or not isinstance(response.output, JSONOutput):
        raise ValueError(prefix + "_provider_failed")
    payload = response.output.payload
    # Some provider JSON outputs use a singleton envelope. Unwrap only this
    # unambiguous transport shape, then apply the unchanged strict typed schema.
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        payload = payload[0]
    return schema.model_validate(payload)


def plan_document(gateway, request, requirements, *, feedback=None, reusable=()):
    return structured_call(
        gateway,
        request.model,
        DocumentPlan,
        dict(
            instruction=(
                "Bạn là Planner cho Document QA. Hiểu câu hỏi/context, lập requirements truy xuất BM25 "
                "động bằng tiếng Việt; kind exact_text/entity_role/table_labels/source_excerpt. "
                "Giữ target/label/kind của các yêu cầu gốc, có thể thay query và bổ sung yêu cầu còn thiếu. "
                "Không trả lời, không tạo bằng chứng hoặc suy đoán source IDs. "
                "entity_role: truy xuất từng vai trò. source_excerpt: đọc đầy đủ điều kiện/ngoại lệ. "
                "reasoning_required=true khi cần phân tích, false cho quotation/entity lookup đơn giản. "
                "Nếu có feedback, chỉ điều chỉnh truy xuất bị ảnh hưởng, giữ phần đã được kiểm chứng."
            ),
            question=request.question,
            conversation=request.conversation_context,
            original_requirements=[r.model_dump(mode="json") for r in requirements],
            feedback=feedback,
            reusable_results=list(reusable),
        ),
        "document-planner",
    )


def plan_fusion(gateway, request):
    plan = structured_call(
        gateway,
        request.model,
        FusionPlan,
        dict(
            instruction=(
                "Bạn là Planner cho Mixed QA. Chia mục tiêu thành các requirements có DAG, chọn lane "
                "financial/document/relation/unsupported theo ý nghĩa câu hỏi. Không dùng nhiều financial "
                "subrequests cho cùng mục tiêu phân tích: một câu phân tích giao toàn bộ cho financial Planner. "
                "original_span giữ đúng phần câu hỏi; execution_question là nhu cầu rõ nghĩa, không thêm facts. "
                "Document requirement phải có target,label,kind,query. kind của FusionRequirement dùng "
                "fact/metric/interpretation/document_summary/source_context; không phê duyệt hoặc tạo số. "
                "Không thay công ty, filing hoặc scope, không thêm tên công ty/năm chưa nêu. "
                "Các phần độc lập không phụ thuộc nhau. relation phụ thuộc requirements nguồn."
            ),
            question=request.question,
            conversation=request.conversation_context,
        ),
        "fusion-planner",
    )
    keys = {r.requirement_id for r in plan.requirements}
    if (
        plan.question != request.question
        or len(keys) != len(plan.requirements)
        or not 1 <= len(keys) <= 12
    ):
        raise ValueError("fusion_plan_binding_invalid")
    if any(r.lane == "document" and r.document_requirement is None for r in plan.requirements):
        raise ValueError("document_lane_requires_typed_requirement")
    visited, active = set(), set()
    ordered = []
    parts = {r.requirement_id: r for r in plan.requirements}

    def visit(key):
        if key not in keys or key in active:
            raise ValueError("fusion_dependency_invalid")
        if key in visited:
            return
        active.add(key)
        for dep in parts[key].dependencies:
            visit(dep)
        active.remove(key)
        visited.add(key)
        ordered.append(key)

    for key in parts:
        visit(key)
    plan.requirements = [parts[key] for key in ordered]
    return plan
