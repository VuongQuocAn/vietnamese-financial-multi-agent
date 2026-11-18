"""Lossless sharing of repeated source objects in LLM wire projections only."""

import json
from collections import Counter


def compact_prompt(payload):
    fields = {
        "graph_context",
        "dependency_results",
        "document_source_context",
        "source_context",
        "shared_tasks",
        "evidence",
        "sources",
        "observations",
        "evidence_obligations",
        "facts",
        "evidence_bindings",
        "operand_bindings",
    }
    counts, identities, objects = Counter(), {}, {}

    def signature(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def count(value):
        if isinstance(value, dict):
            key = signature(value)
            if len(key) >= 256:
                counts[key] += 1
            for item in value.values():
                count(item)
        elif isinstance(value, list):
            for item in value:
                count(item)

    def pack(value):
        if isinstance(value, dict):
            key = signature(value)
            if counts[key] > 1:
                if key not in identities:
                    identity = "P" + str(len(identities) + 1)
                    identities[key] = identity
                    objects[identity] = {k: pack(v) for k, v in value.items()}
                return dict(shared_ref=identities[key])
            return {k: pack(v) for k, v in value.items()}
        if isinstance(value, list):
            return [pack(item) for item in value]
        return value

    for key in fields & payload.keys():
        count(payload[key])
    result = {k: pack(v) if k in fields else v for k, v in payload.items()}
    if objects:
        result["shared_payload_objects"] = objects
        result["payload_reference_rule"] = (
            "Khi đọc, thay object {shared_ref:P...} bằng shared_payload_objects[P...], "
            "kể cả references lồng nhau. Đây là chia sẻ nguyên đối tượng nguồn, không cắt dữ liệu. "
            "P chỉ là wire reference, không là evidence_id/operand hoặc quyền phê duyệt."
        )
        if len(signature(result)) >= len(signature(payload)):
            return payload
    return result
