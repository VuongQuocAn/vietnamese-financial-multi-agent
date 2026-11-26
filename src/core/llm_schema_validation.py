"""Schemas đăng ký local; JSON Schema Draft 2020-12, không resolve qua network."""

from copy import deepcopy
from itertools import islice
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .llm_contracts import SchemaIssue, SchemaReference


def schema_issues(schema, payload):
    """Bounded codes/known field names only; never include completion values/messages."""
    fields, pending = set(), [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            fields.update(node.get("properties", {}))
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    candidates = []
    validator = Draft202012Validator(schema)
    for top in islice(Draft202012Validator(schema).iter_errors(payload), 3):
        if top.validator == "oneOf":
            candidates.append(
                (
                    top,
                    "jsonschema_oneOf_no_match"
                    if top.context
                    else "jsonschema_oneOf_multiple_match",
                    [],
                )
            )
            if top.context:
                branches = {}
                for child in top.context:
                    branches.setdefault(child.schema_path[0], []).append(child)
                for children in islice(branches.values(), 3):
                    error = best_match(children)
                    candidates.append((error, "jsonschema_" + error.validator, []))
            else:
                for index, branch in enumerate(top.validator_value):
                    if validator.evolve(schema=branch).is_valid(top.instance):
                        candidates.append((top, "jsonschema_oneOf_match", [index]))
                    if len(candidates) >= 4:
                        break
        else:
            error = best_match([top])
            candidates.append((error, "jsonschema_" + error.validator, []))
    issues = []
    # Legacy protocol names may identify rejected fields without exposing arbitrary keys.
    diagnostic_fields = fields | {"analyses", "goal", "operation_id", "citations", "provenance"}
    schema_fields = fields | set(Draft202012Validator.VALIDATORS) | {"$defs"}
    for error, code, branch_path in candidates[:4]:
        path = list(error.absolute_path)
        if error.validator == "required" and isinstance(error.instance, dict):
            path.append(next(k for k in error.validator_value if k not in error.instance))
        elif (
            error.validator == "additionalProperties"
            and isinstance(error.instance, dict)
            and not error.schema.get("patternProperties")
        ):
            path.append(
                next(k for k in error.instance if k not in error.schema.get("properties", {}))
            )
        issues.append(
            SchemaIssue(
                code=code,
                path=[
                    p if type(p) is int or p in diagnostic_fields and len(p) <= 64 else "<field>"
                    for p in path[:8]
                ],
                schema_path=[
                    p if type(p) is int or p in schema_fields and len(p) <= 64 else "<field>"
                    for p in [*error.absolute_schema_path, *branch_path][:16]
                ],
            )
        )
    return issues


class LocalSchemaRegistry:
    def __init__(self, schemas: list[tuple[SchemaReference, dict[str, Any]]]) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}
        for reference, schema in schemas:
            key = reference.to_json()
            if key in self._schemas:
                raise ValueError("Duplicate schema identity")
            snapshot = deepcopy(schema)
            try:
                self._check_local(snapshot)
                Draft202012Validator.check_schema(snapshot)
            except Exception:
                raise ValueError("Invalid or nonlocal schema") from None
            self._schemas[key] = snapshot

    @classmethod
    def _check_local(cls, node: Any) -> None:
        if isinstance(node, dict):
            if (
                "$schema" in node
                and node["$schema"] != "https://json-schema.org/draft/2020-12/schema"
            ):
                raise ValueError("Unsupported dialect")
            # $id thay đổi base URI; M1-07 chỉ hỗ trợ document-local refs.
            if "$id" in node:
                raise ValueError("Schema base URI unsupported")
            for key, value in node.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(value, str) or not value.startswith("#")
                ):
                    raise ValueError("External schema reference unsupported")
                cls._check_local(value)
        elif isinstance(node, list):
            for value in node:
                cls._check_local(value)

    def schema_for(self, reference: SchemaReference) -> dict[str, Any]:
        try:
            return deepcopy(self._schemas[reference.to_json()])
        except KeyError:
            raise ValueError("Schema not registered") from None

    def is_valid(self, reference: SchemaReference, payload: Any) -> bool:
        return Draft202012Validator(self.schema_for(reference)).is_valid(payload)
