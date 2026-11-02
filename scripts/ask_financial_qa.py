"""Local BBS demo: nhập câu hỏi bất kỳ, hydrate accepted data, không đọc lại PDF."""

import argparse
import json
from pathlib import Path

from evaluate_m4_05_qa import setup
from vietnamese_financial_multi_agent.api.qa_gateway import QACredentialError, create_qa_adapter
from vietnamese_financial_multi_agent.core.gemini_adapter import DEFAULT_GEMINI_MODEL
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import FinancialQABaseline, QAContext


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--document-id")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--year", type=int)
    parser.add_argument("--formula-id", help="Target explicit cho câu hỏi tiếp nối")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Tối đa một Gemini request; env hoặc local key file",
    )
    parser.add_argument("--key-file", type=Path, help="Override local key file; không in nội dung")
    parser.add_argument(
        "--key-index", type=int, default=0, help="Một key cụ thể, không tự rotation"
    )
    parser.add_argument("--model", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data, _, _, documents = setup(Path.cwd().resolve())
    adapter = None
    gateway = None
    if args.allow_live:
        try:
            adapter, _ = create_qa_adapter(
                Path.cwd().resolve(), key_file=args.key_file, key_index=args.key_index
            )
            gateway = SharedLLMGateway({"gemini": adapter})
        except QACredentialError as error:
            print(f"Gateway configuration: {error}. Tiếp tục với deterministic baseline.")
    try:
        response = FinancialQABaseline(SnapshotCatalog(**data), documents, gateway=gateway).answer(
            args.question,
            QAContext(
                document_id=args.document_id,
                snapshot_id=args.snapshot_id,
                reporting_year=args.year,
                formula_id=args.formula_id,
                allow_gateway=args.allow_live,
                model=ModelIdentity(provider="gemini", model=args.model),
            ),
        )
        if args.json:
            print(response.model_dump_json(indent=2))
        else:
            print(response.answer_vi)
            print(
                json.dumps(
                    dict(
                        status=response.status,
                        document_id=response.document_id,
                        snapshot_id=response.snapshot_id,
                        snapshot_candidates=[d.snapshot_id for d in response.snapshot_candidates],
                        reasons=response.reasons,
                        llm=response.llm.model_dump(mode="json"),
                    ),
                    ensure_ascii=False,
                )
            )
    finally:
        if adapter is not None:
            adapter.close()


if __name__ == "__main__":
    main()
