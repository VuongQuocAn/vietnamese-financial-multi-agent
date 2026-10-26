"""Export strictly allowlisted numeric evidence from a private local summary."""

import argparse
import json
from pathlib import Path

from vietnamese_financial_multi_agent.document_processing.crop_evidence import (
    public_expansion_statistics,
    public_statistics,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--expansion", action="store_true")
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    projection = public_expansion_statistics if args.expansion else public_statistics
    print(json.dumps(projection(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
