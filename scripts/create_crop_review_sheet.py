"""Create local review sheets and a pending template; never assert human approval."""

from pathlib import Path

from expand_table_crop_recovery import collect, prepare
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.crop_review import create_review_sheets


def main():
    config = load_data_config()
    inventory = Path("artifacts/dataset-inventory")
    records, requests, mappings, images, plan, states, reviewed = prepare(config, inventory)
    manifest = create_review_sheets(
        config,
        records,
        states,
        requests,
        mappings,
        images,
        plan,
        reviewed,
    )
    if collect(config, inventory)[-1] != plan:
        raise CropError("source_changed")
    print(f"Created/verified {len(manifest)} local sheets; human approval remains pending.")


if __name__ == "__main__":
    main()
