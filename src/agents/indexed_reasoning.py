"""Compact Q1 wire for the indexed Reasoning experiment."""

import json
from time import perf_counter
from uuid import uuid4

from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_schema_validation import schema_issues
from ..evidence.document_claim_support import document_projection
from ..evidence.search import normalize_search, rank_search_candidates
from ..tools.question_understanding import EXTRA_ALIASES, ITEM_RULES
from .planner_contracts import PlannerLLMMetadata
from .specialist_common import CALCULATION_OPERATORS, project_reasoning_actions


def _object(**fields):
    return dict(type="object", additionalProperties=False, required=list(fields), properties=fields)


ANSWER_TYPES = ("numeric", "comparison", "entity", "date", "explanation")
DERIVATIONS = ("direct", "calculated", "evidence_based", "unspecified")


def answer_requirement_schema():
    text = dict(type="string", maxLength=180)
    period = dict(type="string", maxLength=25)
    return _object(
        text=dict(text, minLength=2),
        answer_type=dict(type="string", enum=list(ANSWER_TYPES)),
        derivation=dict(type="string", enum=list(DERIVATIONS)),
        unit=dict(type="string", maxLength=25),
        indicator=text,
        periods=dict(type="array", maxItems=6, items=period),
        conditions=text,
        operator=dict(type="string", enum=["", *CALCULATION_OPERATORS]),
        operands=dict(
            type="array",
            maxItems=8,
            items=_object(
                label=text,
                period=period,
                role=dict(type="string", enum=["first", "second", "unspecified"]),
            ),
        ),
    )


ANSWER_REQUIREMENT_INSTRUCTION = (
    " Với requirements chỉ liệt kê đầu ra được hỏi. Kỳ, phạm vi, tiền đề và toán hạng là "
    "điều kiện. scope rỗng nếu câu hỏi không chỉ định. answer_type=numeric cho giá trị, "
    "chênh lệch, tỷ lệ hoặc phần trăm. comparison cho kết luận đúng/sai. "
    "derivation là cách chứng minh dự kiến, có thể để unspecified. "
    "Chỉ khai unit nếu câu hỏi yêu cầu rõ, dùng vnd, percent, ratio hoặc đơn vị tương ứng. "
    "indicator ghi tên chỉ tiêu ngắn. Nếu câu hỏi yêu cầu một quan hệ số, ghi operator "
    "và mọi operands, kể cả khi chưa chắc derivation. Với a-b, a/b, (a-b)/b hoặc so sánh "
    "có hướng, ghi role first cho a và second cho b theo câu hỏi gốc. "
    "role độc lập với thứ tự liệt kê. Phép toán giao hoán dùng unspecified. "
    "label dùng nhãn tiếng Việt theo báo cáo, ghi kỳ riêng ở period (YYYY hoặc YYYY-MM-DD). "
    "conditions ghi các ràng buộc còn lại. Giữ đủ mọi vế độc lập."
)


def confirm_missing_answer(gateway, context, question, current, suggestion):
    """One existing Recovery turn dedicated to the original question."""
    schema = _object(requirement=dict(anyOf=[answer_requirement_schema(), dict(type="null")]))
    request = LLMRequest(
        contract_version="llm_gateway_v1",
        request_id="m5-coordinator-answer-recovery-" + uuid4().hex,
        model=context.model,
        messages=[
            Message(
                role="system",
                content=(
                    "Đối chiếu gợi ý với câu hỏi gốc và danh sách đầu ra hiện tại. "
                    "Chỉ trả requirement nếu có một vế thực sự bị bỏ sót. Nếu đã có, "
                    "mơ hồ hoặc là tiền đề, trả null." + ANSWER_REQUIREMENT_INSTRUCTION
                ),
            ),
            Message(
                role="user",
                content=json.dumps(
                    dict(question=question, current=current, suggestion=suggestion),
                    ensure_ascii=False,
                ),
            ),
        ],
        generation=GenerationParameters(temperature=0, max_output_tokens=400),
        output_spec=OutputSpec(format="json", json_schema=schema),
        constraints=RequestConstraints(timeout_seconds=30),
    )
    response = gateway.generate(request)
    payload = response.output.payload if isinstance(response.output, JSONOutput) else None
    return request.request_id, (
        payload["requirement"]
        if response.status == "success" and not schema_issues(schema, payload)
        else None
    )


def understand_question(gateway, question, context, *, independent_requirements=False):
    """Coordinator draft before any retrieved source or candidate exists."""
    text = dict(type="string", maxLength=180)
    schema = _object(
        company=text,
        scope=dict(type="string", enum=["", "separate", "consolidated"]),
        requirements=dict(
            type="array",
            maxItems=6,
            items=answer_requirement_schema() if independent_requirements else text,
        ),
        needs=dict(
            type="array",
            maxItems=10,
            items=_object(
                role=dict(type="string", enum=["fact", "operand", "relation"]),
                label=text,
                statement=dict(type="string", enum=["", "B01", "B02", "B03", "B09"]),
                period=dict(type="string", maxLength=25),
            ),
        ),
        relationship=text,
    )
    started = perf_counter()
    response = gateway.generate(
        LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m5-coordinator-indexed-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(
                    role="system",
                    content=(
                        "Tách từng vế người dùng cần trả lời. Ghi needs theo thứ tự nghiệp vụ. "
                        "Mỗi need chỉ có một chỉ tiêu nguồn hoặc một quan hệ. Với NR, liệt kê từng "
                        "toán hạng, gồm mọi khoản được nêu, theo đúng thứ tự của phép tính; "
                        "relationship mô tả phép toán và dấu. Với MH, nêu quan hệ cần chứng minh. "
                        "Ghi kỳ YYYY cho dữ liệu trong năm, YYYY-MM-DD cho số dư tại ngày, "
                        "rỗng nếu chưa rõ. Dùng nhãn tài chính tiếng Việt để tìm nguồn, "
                        "tách chỉ tiêu số dư khỏi chỉ tiêu biến động. Không đoán số hay nguồn."
                        + (ANSWER_REQUIREMENT_INSTRUCTION if independent_requirements else "")
                    ),
                ),
                Message(role="user", content=question),
            ],
            generation=GenerationParameters(temperature=0, max_output_tokens=650),
            output_spec=OutputSpec(format="json", json_schema=schema),
            constraints=RequestConstraints(timeout_seconds=context.provider_timeout_seconds),
        )
    )
    metadata = PlannerLLMMetadata(
        calls=1,
        model=context.model,
        status=response.status,
        usage=response.usage,
        cost=response.cost,
        error=response.error,
        provenance=response.provenance,
        latency_ms=(perf_counter() - started) * 1000,
    )
    payload = response.output.payload if isinstance(response.output, JSONOutput) else None
    if response.status != "success" or schema_issues(schema, payload):
        return {}, metadata
    return payload, metadata


def fact_lookup(need):
    """Use existing exact aliases as retrieval keys, independent of source eligibility."""
    label = normalize_search(need["label"])
    items = {
        item
        for item, rule in ITEM_RULES.items()
        if need["statement"] in {"", rule.statement_type}
        and label in {normalize_search(a) for a in (*rule.aliases, *EXTRA_ALIASES.get(item, ()))}
    }
    filters = {
        output: need[field]
        for field, output in (("statement", "statement_type"), ("period", "period"))
        if need[field]
    }
    if len(items) == 1:
        yield dict(filters, canonical_item_id=next(iter(items)))
    yield dict(filters, source_label=need["label"])


def evidence_options(prompt, hits, question, draft, document_views=None):
    """Expose short source content and retain the bindings in request-local memory."""
    queries = [
        *(f"{need['label']} {need['period']}" for need in draft.get("needs", [])),
        *draft.get("requirements", []),
        question,
    ]
    facts = {row["id"]: row for row in prompt["evidence"] if row.get("observation_id")}
    fact_rank = rank_search_candidates(
        {
            handle: f"{row['label']} {row['period']} {row.get('statement_type') or ''}"
            for handle, row in facts.items()
        },
        queries,
        top_k=32,
    )
    fact_rank = list(dict.fromkeys([*fact_rank, *facts]))[:32]
    bindings = [(handle, None) for handle in fact_rank]
    groups = {}
    for i, handle in enumerate(fact_rank):
        fact = facts[handle]
        context = fact.get("source_context") or {}
        primary = next(iter(context.get("bindings", [])), {})
        pointer = primary.get("pointer") or ""
        row_key = (primary["source"], pointer.rsplit("/", 1)[0]) if "/rows/" in pointer else handle
        group = groups.setdefault(
            row_key,
            {
                key: fact[key]
                for key in (
                    "label",
                    "statement_type",
                    "source_item_code",
                    "source_kind",
                    "reporting_scope",
                )
                if fact.get(key) is not None
            }
            | {"kind": "financial_row", "cells": []}
            | ({"title": context["title"]} if context.get("title") else {}),
        )
        group["cells"].append(
            dict(
                index=i,
                period=fact["period"],
                value=fact["value"],
                unit=fact["unit"],
                scale=fact["scale"],
            )
            | ({"header": context["header"]} if context.get("header") else {})
        )
    documents = {}
    document_views = document_views or {}
    for view in prompt["document_source_context"]:
        handle = view["handle"]
        record = hits[handle][1].evidence.record
        source = document_projection(record, literal=True)
        if table := source.get("literal_table"):
            ref = record.sources[0].reference
            label_column = next(
                (
                    i
                    for i, column in enumerate(table["columns"])
                    if normalize_search(column) in {"chi tieu", "tai san", "nguon von"}
                ),
                0,
            )
            issues = document_views.get(handle, {}).get("numeric_issues", {})
            for r, cells in enumerate(table["rows"]):
                if (
                    label_column < len(cells)
                    and all(isinstance(c, str) for c in cells)
                    and normalize_search(cells[label_column])
                ):
                    shown = dict(
                        kind="row",
                        label=cells[label_column],
                        page=view["source_page"],
                        context=" | ".join([table.get("title") or "", *table["columns"]])[:350],
                        row=" | ".join(cells)[:440],
                    )
                    if issue := issues.get(cells[label_column]):
                        shown["operand_issue"] = issue
                    row_key = (ref.anchor.page.source_ref, f"{ref.source_pointer}/rows/{r}")
                    if row_key in groups:
                        shown["numeric_indices"] = [
                            cell["index"] for cell in groups[row_key]["cells"]
                        ]
                    documents.setdefault((handle, cells[label_column]), shown)
        elif text := source.get("text"):
            query = next((line.strip() for line in text.splitlines() if line.strip()), "")
            if query:
                documents[handle, query[:150]] = dict(
                    kind="text", page=view["source_page"], context=text[:460]
                )
    doc_rank = rank_search_candidates(
        {key: " ".join(str(v) for v in row.values()) for key, row in documents.items()},
        queries,
        top_k=14,
    )[:28]
    rows = [
        *groups.values(),
        *(dict(documents[key], index=i) for i, key in enumerate(doc_rank, len(bindings))),
    ]
    return rows, [*bindings, *doc_rank]


def available_operand_row(decision, options):
    """Identify a visible row for another selection, without assigning operand roles."""
    uses = set(decision["use"])
    for option in options:
        if option["kind"] == "financial_row":
            indices = [cell["index"] for cell in option["cells"]]
            selected = len(uses.intersection(indices)) == 1 and len(uses) == 1
        else:
            indices = option.get("numeric_indices", [])
            selected = option["index"] in uses
        if selected and len(indices) >= 2:
            return indices
    return []


def selection_schema(size):
    return _object(
        use=dict(
            type="array",
            maxItems=min(16, size),
            items=dict(type="integer", minimum=0, maximum=max(0, size - 1)),
        ),
        operator=dict(type="string", enum=["none", *CALCULATION_OPERATORS]),
        missing=dict(type="array", maxItems=6, items=dict(type="string", maxLength=180)),
    )


def bind_selection(decision, bindings, evidence, draft, objective, document_views=None):
    """Project the model's indexes into the existing Q1 proposal and Decimal proof."""
    indices = decision["use"]
    if any(type(i) is not int or not 0 <= i < len(bindings) for i in indices):
        raise ValueError("indexed_evidence_out_of_range")
    selected = [bindings[i] for i in dict.fromkeys(indices)]
    missing = list(decision["missing"])
    required = [n["label"] for n in draft.get("needs", []) if n["role"] == "operand"]
    operator = decision["operator"]
    if operator != "none":
        if any(query is not None for _, query in selected):
            blocked = [
                f"{query}: "
                + (document_views or {})
                .get(handle, {})
                .get("numeric_issues", {})
                .get(
                    query,
                    "missing_numeric_cell"
                    if (document_views or {}).get(handle, {}).get("cells")
                    else "unsupported_document_operand",
                )
                for handle, query in selected
                if query is not None
            ]
            return dict(claims=[], missing_information=blocked + missing), ([], [])
        if missing or len(selected) < max(2, len(required)):
            return dict(
                claims=[],
                missing_information=missing or ["Thiếu toán hạng: " + ", ".join(required)],
            ), ([], [])
        operands = [(handle, (evidence[handle]["period"],)) for handle, _ in selected]
        actions = [dict(action="calculate", operator=operator, inputs=list(range(len(operands))))]
        return project_reasoning_actions(
            dict(actions=actions, missing_information=[]),
            aliases={handle: handle for handle, _ in operands},
            objective=objective,
            indexed_operands=operands,
        )
    if required:
        missing = missing or ["Chưa có phép tính hoặc đủ toán hạng: " + ", ".join(required)]
        return dict(claims=[], missing_information=missing), ([], [])
    return dict(
        claims=[
            handle if query is None else dict(source=handle, query=query)
            for handle, query in selected
        ],
        missing_information=missing,
    ), ([], [i for i, (_, query) in enumerate(selected) if query is None])
