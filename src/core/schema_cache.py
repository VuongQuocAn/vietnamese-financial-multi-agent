"""Immutable schema text keyed by the Python contract class; detached callers."""

import json
from functools import lru_cache


@lru_cache(maxsize=64)
def _schema_text(model):
    return json.dumps(model.model_json_schema(), ensure_ascii=False)


def model_schema(model):
    return json.loads(_schema_text(model))
