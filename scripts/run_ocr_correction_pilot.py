"""M1-13: hai trang frozen manifest, full OCR context; không retry hoặc quota probes."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from google import genai
from google.genai import types
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
)
from vietnamese_financial_multi_agent.document_processing.checkpoints import (
    CheckpointStore,
    fingerprint_json,
)
from vietnamese_financial_multi_agent.document_processing.classification_pilot import (
    MeteredModels,
    PilotStop,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.crop_expansion import write_once
from vietnamese_financial_multi_agent.document_processing.extraction_artifacts import (
    read_local_evidence,
)
from vietnamese_financial_multi_agent.document_processing.extraction_pilot import (
    parse_manifest,
    snapshot,
)
from vietnamese_financial_multi_agent.document_processing.ocr_correction import (
    OUTPUT_CAP,
    OCRCorrector,
    correction_schema_registry,
)
from vietnamese_financial_multi_agent.document_processing.ocr_loader import load_ocr_page
from vietnamese_financial_multi_agent.document_processing.path_resolver import resolve_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--key-index", type=int)
    parser.add_argument("--key-file", type=Path, default=Path("src/api/api_key/api_gemini.txt"))
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("artifacts/classification-pilot/M1-11b/live-policy.json"),
    )
    args = parser.parse_args()
    client = None
    try:
        config = load_data_config()
        root = config.project_root / "artifacts/ocr-correction/M1-13"
        CheckpointStore(root, data_config=config)  # Existing output/source-root guard only.
        manifest_path = config.project_root / "artifacts/extraction-validation/M1-04b/manifest.json"
        manifest_payload = read_local_evidence(manifest_path, config)
        manifest = parse_manifest(manifest_payload, config)
        manifest_digest = fingerprint_json(manifest_payload)
        captured = []
        expected = {s.path: s.model_dump(mode="json") for s in manifest.snapshots}
        pages = []
        # Existing small sample: BCC has visually apparent recognition errors; BED
        # includes financial cells. Selection fixed before any live request.
        for index in (2, 4):
            selected = manifest.pages[index]
            request = selected.request.model_copy(deep=True)
            target = resolve_path(request, config).confirmed_target
            if target is None:
                raise PilotStop("source_unresolved")
            source = config.get_root(target.root_key) / target.relative_suffix
            before = snapshot(source, config)
            if before != expected.get(str(source)):
                raise PilotStop("source_changed")
            captured.append(before)
            request.reference.source_ref = request.reference.original_path
            request.reference.anchor = SourceAnchor(
                page=RawPageIdentity(
                    symbol=selected.identity[0],
                    year=selected.identity[1],
                    page=selected.identity[2],
                    image=selected.image_reference,
                    source_ref=request.reference.source_ref,
                ),
                status="unresolved",
            )
            pages.append(load_ocr_page(request, config))
        if not args.live:
            print(json.dumps(dict(mode="dry_run", pages=len(pages), requests=0)))
            return
        if args.key_index is None or args.key_index < 0:
            raise PilotStop("explicit_key_index_required")
        settings = read_local_evidence(args.policy.absolute(), config)
        if (
            any(
                settings.get(flag) is not True
                for flag in (
                    "free_tier_confirmed",
                    "pricing_confirmed",
                    "data_export_approved",
                    "exclusive_pilot_scope_confirmed",
                )
            )
            or settings.get("monetary_cap_usd") != "0"
        ):
            raise PilotStop("live_scope_not_confirmed")
        payload = settings["project_policy"]
        # M1-13 owner authorization supersedes artificial M1-11/12a pilot caps.
        # Owner-attested limits; not an independent query of provider quota remaining.
        payload["quota_limits"] = dict(rpm=15, tpm=250_000, rpd=500)
        payload["verification_source"] = "user-authorized-M1-13-2026-10-28"
        policy = ProjectPolicy.model_validate_json(json.dumps(payload))
        if (
            policy.model != "gemini-3.5-flash-lite"
            or policy.provider != "gemini"
            or policy.tier != "free"
            or not policy.mapping_confirmed
            or len(policy.credential_refs) != 1
        ):
            raise PilotStop("invalid_correction_policy")
        keys = re.findall(
            r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$",
            args.key_file.read_text(encoding="utf-8-sig"),
        )
        if args.key_index >= len(keys):
            raise PilotStop("selected_credential_missing")
        client = genai.Client(
            api_key=keys[args.key_index],
            vertexai=False,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1), timeout=60_000
            ),
        )
        del keys
        meter = MeteredModels(
            client.models,
            request_limit=len(pages),
            output_cap=OUTPUT_CAP,
            request_input_bound=policy.quota_limits.tpm,
            rpm=policy.quota_limits.rpm,
        )
        schemas = correction_schema_registry()
        adapter = GeminiAdapter(SimpleNamespace(models=meter), schema_registry=schemas)
        gateway = SharedLLMGateway({"gemini": adapter}, schema_registry=schemas)
        credential = policy.credential_refs[0]
        guard = QuotaBudgetGuard(
            ProjectRegistry([policy]),
            [
                GatewayBinding(
                    policy.account_ref,
                    policy.project_ref,
                    credential,
                    "gemini",
                    policy.model,
                    gateway,
                )
            ],
        )
        guard.initialize(confirmed_fresh_scope=True)
        service = CachedLLMService(
            guard,
            tenant_ref="ocr-correction-pilot",
            project_ref=policy.project_ref,
            credential_refs=frozenset({credential}),
            configuration_revision="M1-13-v1",
            scope_confirmed=True,
            schema_registry=schemas,
            ttl_seconds=3600,
        )
        root.mkdir(parents=True, exist_ok=True)
        # Exclusive marker prevents resetting the small live scope after restart.
        with (root / "live.started.json").open("x", encoding="utf-8") as stream:
            json.dump(dict(pages=2, request_limit=2, key_index=args.key_index), stream)
        write_once(
            root / "manifest.json",
            dict(indices=[2, 4], snapshots=captured, source_manifest_digest=manifest_digest),
        )
        write_once(root / "live-policy.json", policy.model_dump(mode="json"))
        records, counts = [], Counter()
        stop_reason = None
        for index, loaded in zip((2, 4), pages, strict=True):
            before = loaded.page.export_source()
            meter.pace()
            result = OCRCorrector(service).correct(
                loaded,
                source_ref=loaded.mapping_result.reference.source_ref,
                credential_ref=credential,
                cache_allowed=True,
            )
            if loaded.page.export_source() != before:
                raise PilotStop("raw_mutated")
            record = dict(manifest_index=index, view=result.view.model_dump(mode="json"))
            write_once(root / f"page-{index}.json", record)
            records.append(record)
            counts.update(c.status for c in result.view.corrections)
            if meter.stopped or result.view.issues:
                stop_reason = meter.stopped or "validation_error"
                break
        for item in captured:
            if snapshot(Path(item["path"]), config) != item:
                raise PilotStop("source_changed")
        if fingerprint_json(read_local_evidence(manifest_path, config)) != manifest_digest:
            raise PilotStop("manifest_changed")
        stats = dict(
            pages=len(records),
            corrections=sum(counts.values()),
            proposed=counts["proposed"],
            confirmed=counts["confirmed"],
            unresolved=counts["unresolved"],
            unresolved_pages=sum(r["view"]["status"] == "unresolved" for r in records),
            requests=meter.requests,
            input_tokens=meter.input_tokens,
            output_tokens=meter.output_tokens,
            total_tokens=meter.total_tokens,
            failures=meter.failures,
            unknown_usage=meter.unknown_usage,
            source_unchanged=True,
            stop_reason=stop_reason,
            guard_money_status=guard.snapshot(policy.project_ref, "gemini", policy.model)[
                "project_budget"
            ]["status"],
        )
        write_once(root / "live-result.json", dict(summary=stats, records=records))
        print(json.dumps(stats, sort_keys=True))
    except (CropError, OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Correction pilot stopped: input, policy, provenance or artifact conflict."
        ) from None
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
