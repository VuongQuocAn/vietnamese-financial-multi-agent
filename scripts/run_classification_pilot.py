"""M1-11a: dry-run mặc định; live cần explicit user-confirmed free-tier policy."""

import argparse
import json
import re
from pathlib import Path

from google import genai
from google.genai import types
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.core.llm_quota_budget import ProjectPolicy
from vietnamese_financial_multi_agent.document_processing.classification_pilot import (
    PilotStop,
    compose_pilot,
    prepare_pilot,
    run_pilot,
)
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.crop_expansion import write_once
from vietnamese_financial_multi_agent.document_processing.extraction_artifacts import (
    read_local_evidence,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/extraction-validation/M1-04b/manifest.json"),
    )
    parser.add_argument("--limit", type=int, default=19)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--live-policy", type=Path)
    parser.add_argument("--key-file", type=Path, default=Path("src/api/api_key/api_gemini.txt"))
    parser.add_argument("--key-index", type=int)
    args = parser.parse_args()
    client = None
    try:
        config = load_data_config()

        def absolute(p):
            return p if p.is_absolute() else config.project_root / p

        prepared = prepare_pilot(config, absolute(args.manifest), limit=args.limit)
        if not args.live:
            stats = {"mode": "dry_run", **prepared.statistics(), "api_requests": 0}
            write_once(prepared.root / "dry-run.json", stats)
        else:
            if args.live_policy is None or args.key_index is None or args.key_index < 0:
                raise PilotStop("explicit_live_configuration_required")
            settings = read_local_evidence(absolute(args.live_policy), config)
            for flag in (
                "free_tier_confirmed",
                "pricing_confirmed",
                "data_export_approved",
                "exclusive_pilot_scope_confirmed",
            ):
                if settings.get(flag) is not True:
                    raise PilotStop("live_approval_missing")
            if settings.get("monetary_cap_usd") != "0":
                raise PilotStop("free_only_pilot")
            policy = ProjectPolicy.model_validate_json(json.dumps(settings["project_policy"]))
            # Chọn một key một lần, không thử/fallback key khác. Không serialize/log key.
            keys = re.findall(
                r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$",
                absolute(args.key_file).read_text(encoding="utf-8-sig"),
            )
            if args.key_index >= len(keys):
                raise PilotStop("selected_credential_missing")
            key = keys[args.key_index]
            del keys
            # Exclusive marker giữ fail-closed qua restart; không reset live budget bằng rerun.
            with (prepared.root / "live.started.json").open("x", encoding="utf-8") as stream:
                json.dump({"protocol": "M1-11a", "request_limit": 20}, stream)
            client = genai.Client(
                api_key=key,
                vertexai=False,
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1),
                    timeout=30_000,
                ),
            )
            del key
            service, guard, meter = compose_pilot(client, policy)
            stats = {
                "mode": "live",
                **run_pilot(
                    prepared,
                    service,
                    meter,
                    credential_ref=policy.credential_refs[0],
                ),
            }
            quota = guard.snapshot(policy.project_ref, policy.provider, policy.model)
            stats["guard_requests_admitted"] = quota["rpd_used"]
            stats["guard_money_status"] = quota["project_budget"]["status"]
            write_once(prepared.root / "live-result.json", stats)
        print(json.dumps(stats, sort_keys=True))
    except (CropError, OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Classification pilot stopped: input, policy, provenance or output conflict."
        ) from None
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
