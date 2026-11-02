"""CLI demo Planner trên persisted BBS; chỉ xuất kế hoạch JSON, không execute."""

import argparse
from pathlib import Path

from evaluate_m4_05_qa import setup
from vietnamese_financial_multi_agent.agents import EvidenceAwareQueryPlanner, PlannerContext
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument(
        "--allow-live", action="store_true", help="Một Gemini call, dùng local key resolver"
    )
    parser.add_argument("--snapshot-id")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    data, _, _, documents = setup(root)
    adapter = create_qa_adapter(root)[0] if args.allow_live else None
    try:
        planner = EvidenceAwareQueryPlanner(
            SnapshotCatalog(**data),
            documents,
            SharedLLMGateway({"gemini": adapter}) if adapter else None,
        )
        result = planner.plan(
            args.question,
            PlannerContext(
                mode="gemini" if adapter else "deterministic", snapshot_id=args.snapshot_id
            ),
        )
        print(result.model_dump_json(indent=2))
    finally:
        if adapter:
            adapter.close()
