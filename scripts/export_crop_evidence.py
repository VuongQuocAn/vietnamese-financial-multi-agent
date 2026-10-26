"""Export strictly allowlisted numeric evidence from a private local summary."""

import argparse
import json
from pathlib import Path

from vietnamese_financial_multi_agent.document_processing.crop_evidence import public_statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    print(json.dumps(public_statistics(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
