"""Opt-in đúng một live request synthetic qua Gateway; không retry hoặc raw output."""

import argparse
import json
import os

from vietnamese_financial_multi_agent.core.gemini_adapter import DEFAULT_GEMINI_MODEL, GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_contracts import SchemaReference, parse_llm_request
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if not args.allow_live or not os.environ.get("GEMINI_API_KEY", "").strip():
        print(json.dumps({"live_test": "NOT_RUN", "credentials_used": 0}))
        return 0
    reference = SchemaReference(
        schema_id="urn:synthetic:smoke",
        name="smoke",
        version="v1",
        dialect="https://json-schema.org/draft/2020-12/schema",
    )
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["other"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["category", "confidence"],
        "additionalProperties": False,
    }
    registry = LocalSchemaRegistry([(reference, schema)])
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    request = parse_llm_request(
        {
            "contract_version": "llm_gateway_v1",
            "request_id": "synthetic-live-smoke",
            "model": {"provider": "gemini", "model": model},
            "messages": [{"role": "user", "content": 'Return category "other" and confidence 1.'}],
            "generation": {"max_output_tokens": 256},
            "constraints": {"timeout_seconds": 30.0},
            "output_spec": {"format": "json", "schema_ref": reference.export(), "strict": True},
        }
    )
    adapter = None
    try:
        adapter = GeminiAdapter.from_environment(schema_registry=registry)
        result = SharedLLMGateway({"gemini": adapter}, schema_registry=registry).generate(request)
        validation = getattr(result.output, "validation_status", None)
        passed = result.status == "success" and validation == "schema_valid"
        summary = {
            "live_test": "PASS" if passed else "FAIL",
            "model": model,
            "status": result.status,
            "error_category": result.error.category if result.error else None,
            "validation_status": validation,
            "usage": result.usage.export(),
            "cost_status": result.cost.status,
            "credentials_used": 1,
            "project_identity": "unknown",
        }
    except Exception:
        # Không in exception client initialization/provider/cleanup chứa credentials.
        summary = {"live_test": "FAIL", "error_category": "internal", "credentials_used": 1}
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                pass
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["live_test"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
