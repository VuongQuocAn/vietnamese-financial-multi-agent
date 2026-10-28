"""Xuất JSON Schema Financial Normalization v1 từ models."""

import json
from pathlib import Path

from vietnamese_financial_multi_agent.accounting import financial_normalization_json_schema


def main() -> None:
    destination = (
        Path(__file__).resolve().parents[1] / "schemas/financial_normalization_v1.schema.json"
    )
    destination.write_text(
        json.dumps(financial_normalization_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
