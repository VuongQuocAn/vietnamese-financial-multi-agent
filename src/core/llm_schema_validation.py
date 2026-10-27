"""Schemas đăng ký local; JSON Schema Draft 2020-12, không resolve qua network."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from .llm_contracts import SchemaReference


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
