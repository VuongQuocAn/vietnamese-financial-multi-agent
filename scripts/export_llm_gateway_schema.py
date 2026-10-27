"""Xuất schema LLM Gateway v1; không resolve schema refs hoặc gọi provider."""

import json
from pathlib import Path

from vietnamese_financial_multi_agent.core.llm_contracts import llm_gateway_json_schema


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "schemas/llm_gateway_v1.schema.json"
    destination.write_text(
        json.dumps(llm_gateway_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
