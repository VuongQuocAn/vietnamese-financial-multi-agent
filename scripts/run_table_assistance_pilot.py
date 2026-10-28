"""M1-12a: default dry-run; explicit live, hoặc offline checkpoint revalidation."""

import argparse
import json
import re
from pathlib import Path

from google import genai
from google.genai import types
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.core.llm_quota_budget import ProjectPolicy
from vietnamese_financial_multi_agent.document_processing.checkpoints import CheckpointStore
from vietnamese_financial_multi_agent.document_processing.classification_pilot import PilotStop
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.crop_expansion import write_once
from vietnamese_financial_multi_agent.document_processing.extraction_artifacts import (
    read_local_evidence,
)
from vietnamese_financial_multi_agent.document_processing.table_assistance import TableReconstructor
from vietnamese_financial_multi_agent.document_processing.table_pilot import (
    compose_tables,
    prepare_tables,
    run_tables,
    table_arguments,
)


class OfflineOnly:
    """Fail closed nếu checkpoint miss; không có provider binding hoặc credential."""

    calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        raise PilotStop("offline_checkpoint_miss")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("artifacts/classification-pilot/M1-11b/live-policy.json"),
    )
    parser.add_argument("--key-file", type=Path, default=Path("src/api/api_key/api_gemini.txt"))
    parser.add_argument("--key-index", type=int)
    args = parser.parse_args()
    client = None
    try:
        config = load_data_config()
        prepared = prepare_tables(config)
        if args.resume:
            # Only previously accepted units; missing/invalid checkpoints must never call API.
            report = read_local_evidence(prepared.root / "live-result.json", config)
            service = OfflineOnly()
            engine = TableReconstructor(
                service,
                checkpoints=CheckpointStore(
                    prepared.root / "checkpoints",
                    data_config=config,
                ),
            )
            hits = 0
            for record in report["records"]:
                if record["result"]["status"] != "resolved":
                    continue
                loaded, table_id = prepared.units[record["index"]]
                result = engine.reconstruct(
                    loaded, table_id, **table_arguments(loaded, "offline-no-provider")
                )
                if result.deterministic.status != "resolved":
                    if (
                        result.checkpoint_status != "HIT"
                        or result.table.export_result() != record["result"]
                    ):
                        raise PilotStop("offline_revalidation_failed")
                    hits += 1
            prepared.verify()
            stats = dict(
                mode="offline_resume",
                checkpoint_hits=hits,
                service_calls=service.calls,
                requests=0,
            )
            write_once(prepared.root / "offline-resume.json", stats)
        elif not args.live:
            stats = dict(mode="dry_run", pages=4, tables=len(prepared.units), cells=310, requests=0)
            write_once(prepared.root / "dry-run.json", stats)
        else:
            if args.key_index is None or args.key_index < 0:
                raise PilotStop("explicit_key_index_required")
            settings = read_local_evidence(args.policy.absolute(), config)
            for flag in (
                "free_tier_confirmed",
                "pricing_confirmed",
                "data_export_approved",
                "exclusive_pilot_scope_confirmed",
            ):
                if settings.get(flag) is not True:
                    raise PilotStop("live_scope_not_confirmed")
            if settings.get("monetary_cap_usd") != "0":
                raise PilotStop("free_only_pilot")
            policy_payload = settings["project_policy"]
            policy_payload["quota_limits"]["rpd"] = min(15, policy_payload["quota_limits"]["rpd"])
            policy = ProjectPolicy.model_validate_json(json.dumps(policy_payload))
            keys = re.findall(
                r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$",
                args.key_file.read_text(encoding="utf-8-sig"),
            )
            if args.key_index >= len(keys):
                raise PilotStop("selected_credential_missing")
            key = keys[args.key_index]
            del keys
            client = genai.Client(
                api_key=key,
                vertexai=False,
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1),
                    timeout=60_000,
                ),
            )
            del key
            service, guard, meter = compose_tables(client, policy)
            prepared.verify()
            # Exclusive marker prevents resetting the 15-attempt budget by process restart.
            with (prepared.root / "live.started.json").open("x", encoding="utf-8") as stream:
                json.dump(
                    dict(
                        protocol="M1-12a",
                        request_limit=15,
                        key_index=args.key_index,
                        project_ref=policy.project_ref,
                        credential_ref=policy.credential_refs[0],
                    ),
                    stream,
                )
            write_once(prepared.root / "live-policy.json", settings)
            stats, records = run_tables(prepared, service, meter, policy.credential_refs[0])
            quota = guard.snapshot(policy.project_ref, policy.provider, policy.model)
            stats["guard_requests_admitted"] = quota["rpd_used"]
            stats["guard_money_status"] = quota["project_budget"]["status"]
            write_once(prepared.root / "live-result.json", dict(summary=stats, records=records))
        print(json.dumps(stats, sort_keys=True))
    except (CropError, OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Table pilot stopped: input, policy, provenance, quota or artifact conflict."
        ) from None
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
