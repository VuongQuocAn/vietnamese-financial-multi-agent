"""Xuất duy nhất JSON Schema raw_ocr_v1 từ Python models đã cài đặt."""

import json
from pathlib import Path

from vietnamese_financial_multi_agent.document_processing.contracts import raw_ocr_json_schema


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "schemas/raw_ocr_v1.schema.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(raw_ocr_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
