"""M1-15: PDF/PNG local entrypoint; dry-run default, explicit live credentials/project."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from google import genai
from google.genai import types
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    extract_financial_page,
    extraction_schema_registry,
)
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
)
from vietnamese_financial_multi_agent.document_processing.classification_pilot import MeteredModels
from vietnamese_financial_multi_agent.document_processing.crop_expansion import write_once
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import (
    MODEL,
    ingest_page,
    load_pages,
)
from vietnamese_financial_multi_agent.document_processing.ocr_correction import OUTPUT_CAP
from vietnamese_financial_multi_agent.document_processing.vision_ocr import vision_schema_registry


class ImageRecordingModels:
    """Record actual SDK-bound bytes by hash, never bytes or credentials in logs."""

    def __init__(self, models):
        self.models, self.records = models, []

    def generate_content(self, *, model, contents, config):
        images = [p.inline_data for c in contents for p in c.parts if p.inline_data is not None]
        if len(images) != 1 or images[0].mime_type != "image/png" or not images[0].data:
            raise ValueError("one_inline_png_required")
        self.records.append(
            dict(
                sha256=hashlib.sha256(images[0].data).hexdigest(),
                bytes=len(images[0].data),
            )
        )
        return self.models.generate_content(model=model, contents=contents, config=config)


def parse_pages(value):
    pages = []
    for part in value.split(","):
        bounds = part.split("-")
        if len(bounds) == 1:
            pages.append(int(part))
        elif len(bounds) == 2 and int(bounds[0]) <= int(bounds[1]):
            pages.extend(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            raise ValueError("invalid_page_range")
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--pages", required=True, help="One-based PDF pages: 5,7-8,14-15")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument(
        "--output", type=Path, required=True, help="New ignored artifacts directory"
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--financial", action="store_true", help="M2-04b automated numeric links")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--key-index", type=int)
    args = parser.parse_args()
    root = args.output.resolve()
    artifacts = (Path(__file__).resolve().parents[1] / "artifacts").resolve()
    if not root.is_relative_to(artifacts) or root == artifacts:
        parser.error("output must be a dedicated directory under artifacts/")
    pages = load_pages(
        args.source, symbol=args.symbol, year=args.year, pages=parse_pages(args.pages), dpi=args.dpi
    )
    write_once(root / "manifest.json", dict(model=MODEL, pages=[p.source for p in pages]))
    for page in pages:
        target = root / f"page-{page.source['page_number']}.png"
        if target.exists():
            if target.read_bytes() != page.image.content:
                raise ValueError("render_conflict")
        else:
            with target.open("xb") as stream:
                stream.write(page.image.content)
    if not args.live:
        print(json.dumps(dict(mode="dry_run", pages=[p.source for p in pages], requests=0)))
        return
    if args.policy is None or args.key_file is None or args.key_index is None or args.key_index < 0:
        parser.error("live requires --policy, --key-file and explicit --key-index")
    settings = json.loads(args.policy.read_text(encoding="utf-8"))
    if (
        not all(
            settings.get(k) is True
            for k in (
                "free_tier_confirmed",
                "pricing_confirmed",
                "data_export_approved",
                "exclusive_pilot_scope_confirmed",
            )
        )
        or settings.get("monetary_cap_usd") != "0"
    ):
        raise ValueError("live_policy_not_confirmed")
    payload = settings["project_policy"]
    payload["quota_limits"] = dict(rpm=15, tpm=250_000, rpd=500)
    payload["verification_source"] = (
        "user-authorized-M2-04b-2026-10-28"
        if args.financial
        else "user-authorized-M1-15-2026-10-28"
    )
    policy = ProjectPolicy.model_validate_json(json.dumps(payload))
    if (
        policy.model != MODEL
        or policy.provider != "gemini"
        or policy.tier != "free"
        or not policy.mapping_confirmed
        or len(policy.credential_refs) != 1
    ):
        raise ValueError("invalid_selected_project")
    # No restart sends: existing records can be inspected offline. A live marker
    # prevents resetting quota state/replaying failed or already processed pages.
    with (root / "live.started.json").open("x", encoding="utf-8") as stream:
        json.dump(dict(key_index=args.key_index, project_ref=policy.project_ref), stream)
    keys = re.findall(
        r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$", args.key_file.read_text(encoding="utf-8-sig")
    )
    if args.key_index >= len(keys):
        raise ValueError("credential_missing")
    with genai.Client(
        api_key=keys[args.key_index],
        vertexai=False,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
            timeout=120_000,
        ),
    ) as client:
        del keys
        transport = ImageRecordingModels(client.models)
        meter = MeteredModels(
            transport,
            request_limit=len(pages),
            output_cap=OUTPUT_CAP,
            request_input_bound=250_000,
            rpm=15,
        )
        schemas = extraction_schema_registry() if args.financial else vision_schema_registry()
        gateway = SharedLLMGateway(
            {
                "gemini": GeminiAdapter(
                    SimpleNamespace(models=meter),
                    schema_registry=schemas,
                )
            },
            schema_registry=schemas,
        )
        credential = policy.credential_refs[0]
        guard = QuotaBudgetGuard(
            ProjectRegistry([policy]),
            [
                GatewayBinding(
                    policy.account_ref,
                    policy.project_ref,
                    credential,
                    "gemini",
                    MODEL,
                    gateway,
                )
            ],
        )
        guard.initialize(confirmed_fresh_scope=True)
        service = CachedLLMService(
            guard,
            tenant_ref="financial-extraction" if args.financial else "gemini-ingestion",
            project_ref=policy.project_ref,
            credential_refs=frozenset({credential}),
            configuration_revision="M2-04b-v1" if args.financial else "M1-15-v1",
            scope_confirmed=True,
            schema_registry=schemas,
            ttl_seconds=3600,
        )
        records = []
        for page in pages:
            meter.pace()
            record = (
                extract_financial_page(service, page, credential_ref=credential)
                if args.financial
                else ingest_page(service, page, credential_ref=credential)
            )
            write_once(root / f"page-{page.source['page_number']}.json", record)
            records.append(record)
            print(
                json.dumps(
                    dict(
                        page=page.source["page_number"],
                        assessment=record.get("assessment")
                        or {
                            "issues": record["extraction"]["issues"],
                            "links": len(record["extraction"]["links"]),
                        },
                    )
                ),
                flush=True,
            )
            if meter.stopped:
                break
        unchanged = (
            hashlib.sha256(args.source.read_bytes()).hexdigest() == pages[0].source["source_sha256"]
        )
        stats = dict(
            pages_attempted=len(records),
            pages_with_components=sum(r.get("output") is not None for r in records),
            M1_partial_pages=sum(r.get("m1", {}).get("M1_compatible", False) for r in records),
            requests=meter.requests,
            input_tokens=meter.input_tokens,
            output_tokens=meter.output_tokens,
            total_tokens=meter.total_tokens,
            provider_failures=meter.failures,
            unknown_usage=meter.unknown_usage,
            stop_reason=meter.stopped,
            source_unchanged=unchanged,
            image_requests=transport.records,
        )
        if args.financial:
            stats["financial_links"] = {
                str(r["source"]["page"]["page"]): {
                    status: sum(link["status"] == status for link in r["extraction"]["links"])
                    for status in ("accepted_extraction", "uncertain", "unresolved")
                }
                for r in records
            }
        write_once(root / "summary.json", stats)
        print(json.dumps(stats))
        if not unchanged:
            raise ValueError("source_changed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Ingestion stopped: input, policy or artifact conflict; inspect private outputs."
        ) from None
