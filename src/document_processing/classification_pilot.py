"""Bounded sequential pilot, private inputs và aggregate-only diagnostics."""

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL, GeminiAdapter
from ..core.llm_cache import CachedLLMService
from ..core.llm_contracts import parse_llm_request
from ..core.llm_gateway import SharedLLMGateway
from ..core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
    Reservation,
)
from .checkpoints import CheckpointStore, fingerprint_json
from .classification import (
    SCHEMA_REF,
    ClassificationConfig,
    PageClassifier,
    classification_schema_registry,
)
from .contracts.document_understanding import RawPageIdentity, SourceAnchor
from .contracts.document_understanding_validation import validate_understanding_quality
from .crop_expansion import write_once
from .extraction_artifacts import read_local_evidence
from .extraction_pilot import parse_manifest, snapshot, verify_bindings
from .ocr_loader import LoadedOCRPage, load_ocr_page
from .path_resolver import resolve_path

MAX_REQUESTS = 20
REQUEST_INPUT_BOUND = 100_000
OUTPUT_CAP = 512
LOCAL_LIMITS = {
    "input_token_limit",
    "request_input_limit",
    "request_limit",
    "invalid_model_or_output_cap",
}
USAGE_FAILURES = {"unknown_usage", "input_bound_exceeded"}


class PilotStop(ValueError):
    """Chỉ fixed safe code, không payload/provider exception/path."""


@dataclass(frozen=True)
class PreparedPilot:
    pages: tuple[LoadedOCRPage, ...] = field(repr=False)
    manifest: dict = field(repr=False)
    config: object = field(repr=False)
    root: Path = field(repr=False)

    def verify(self):
        parent = parse_manifest(
            read_local_evidence(Path(self.manifest["source_manifest_path"]), self.config),
            self.config,
        )
        if parent.manifest_id != self.manifest["source_manifest"]:
            raise PilotStop("source_manifest_changed")
        for item in self.manifest["snapshots"]:
            if snapshot(Path(item["path"]), self.config) != item:
                raise PilotStop("source_changed")

    def statistics(self):
        return {
            "selected_pages": len(self.pages),
            "symbols": len({p.page.page.symbol for p in self.pages}),
            "strata": len({(p.page.page.symbol, p.page.page.year) for p in self.pages}),
            "pages_with_ocr_quality_issues": sum(bool(p.quality_issues) for p in self.pages),
        }


def prepare_pilot(config, manifest_path: Path, *, limit=19) -> PreparedPilot:
    if type(limit) is not int or not 10 <= limit <= 19:
        raise PilotStop("invalid_page_limit")
    parent = parse_manifest(read_local_evidence(manifest_path, config), config)
    # Reuse approved plan/index/ledger bindings; metadata only, không scan raw dataset.
    verify_bindings(parent, config)
    selection = sorted(parent.pages, key=lambda p: (p.group != "coverage", p.identity))[:limit]
    if len(selection) < 10:
        raise PilotStop("insufficient_verified_pages")
    snapshots = {s.path: s.model_dump(mode="json") for s in parent.snapshots}
    captured = []
    for path in parent.evidence_paths.values():
        current = snapshot(Path(path), config)
        if current != snapshots[path]:
            raise PilotStop("evidence_changed")
        captured.append(current)
    pages, requests = [], []
    for selected in selection:
        request = selected.request.model_copy(deep=True)
        mapped = resolve_path(request, config)
        if mapped.status != "resolved" or mapped.confirmed_target is None:
            raise PilotStop("unresolved_mapping")
        target = mapped.confirmed_target
        path = config.get_root(target.root_key) / target.relative_suffix
        current = snapshot(path, config)
        if current != snapshots.get(str(path)):
            raise PilotStop("source_changed")
        captured.append(current)
        # Exact artifact locator từ manifest đã duyệt, không bịa document/OCR run identity.
        request.reference.source_ref = request.reference.original_path
        symbol, year, number = selected.identity
        request.reference.anchor = SourceAnchor(
            page=RawPageIdentity(
                symbol=symbol,
                year=year,
                page=number,
                image=selected.image_reference,
                source_ref=request.reference.source_ref,
            ),
            status="unresolved",
        )
        loaded = load_ocr_page(request, config)
        if snapshot(path, config) != current:
            raise PilotStop("source_changed")
        pages.append(loaded)
        requests.append(request.export_result())
    root = config.project_root / "artifacts/classification-pilot/M1-11b"
    # Reuse root containment/source protection, không ghi vào source data roots.
    CheckpointStore(root, data_config=config)
    body = dict(
        protocol="bounded_classification_pilot_v1",
        source_manifest=parent.manifest_id,
        source_manifest_path=str(manifest_path),
        requests=requests,
        snapshots=captured,
    )
    manifest = {**body, "manifest_id": fingerprint_json(body)}
    write_once(root / "manifest.json", manifest)
    prepared = PreparedPilot(tuple(pages), manifest, config, root)
    prepared.verify()
    return prepared


class MeteredModels:
    """SDK boundary: counts actual generate_content attempts incl failures, zero retries.

    Text-only upper bound = UTF-8 JSON bytes of actual SDK contents/config + 2048
    envelope tokens; conservative caller-attested ceiling, không provider tokenizer.
    Unknown usage giữ bound và dừng. Input counter includes smoke and failures.
    """

    def __init__(self, models, *, clock=time.monotonic, sleep=time.sleep, input_token_budget=None):
        if input_token_budget is not None and (
            type(input_token_budget) is not int or input_token_budget <= 0
        ):
            raise PilotStop("invalid_input_token_budget")
        self._models, self._clock, self._sleep = models, clock, sleep
        self.input_token_budget = input_token_budget
        self.requests = self.successes = self.failures = 0
        self.input_tokens = self.output_tokens = self.total_tokens = 0
        self.input_charged = 0
        self.unknown_usage = 0
        self.stopped = None
        self.last_http_status = None
        self.allow_new_requests = True
        self._last_start = None

    def pace(self):
        # Pace before Guard admission too; the sixth call must not hit RPM before
        # the SDK-boundary sleep gets a chance to run.
        if self._last_start is not None:
            delay = self._last_start + 12.1 - self._clock()
            if delay > 0:
                self._sleep(delay)

    def generate_content(self, *, model, contents, config):
        if not self.allow_new_requests:
            raise PilotStop("reuse_probe_miss")
        if self.stopped:
            raise PilotStop("pilot_stopped")
        content = [c.model_dump(mode="json", exclude_none=True) for c in contents]
        cfg = config.model_dump(mode="json", exclude_none=True)
        bound = len(json.dumps([content, cfg], ensure_ascii=False).encode("utf-8")) + 2048
        if model != DEFAULT_GEMINI_MODEL or config.max_output_tokens > OUTPUT_CAP:
            self.stopped = "invalid_model_or_output_cap"
        elif self.requests >= MAX_REQUESTS:
            self.stopped = "request_limit"
        elif bound > REQUEST_INPUT_BOUND:
            self.stopped = "request_input_limit"
        elif (
            self.input_token_budget is not None
            and self.input_charged + bound > self.input_token_budget
        ):
            self.stopped = "input_token_limit"
        if self.stopped:
            raise PilotStop(self.stopped)
        self.pace()
        self._last_start = self._clock()
        self.requests += 1
        self.input_charged += bound
        try:
            raw = self._models.generate_content(model=model, contents=contents, config=config)
        except Exception as error:
            self.failures += 1
            self.unknown_usage += 1
            self.stopped = "provider_error"
            code = getattr(error, "code", None)
            if type(code) is int and 100 <= code < 600:
                self.last_http_status = code
            raise  # Adapter maps structured error category; không log exception body.
        self.successes += 1
        usage = raw.usage_metadata
        if usage is None or any(
            v is None
            for v in (
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.total_token_count,
            )
        ):
            self.unknown_usage += 1
            self.stopped = "unknown_usage"
        else:
            self.input_tokens += usage.prompt_token_count
            self.output_tokens += usage.candidates_token_count
            self.total_tokens += usage.total_token_count
            if usage.prompt_token_count > bound:
                self.stopped = "input_bound_exceeded"
            self.input_charged += usage.prompt_token_count - bound
            if self.input_token_budget is not None and self.input_charged > self.input_token_budget:
                self.stopped = "input_token_limit"
        return raw


def compose_pilot(
    client,
    policy: ProjectPolicy,
    *,
    clock=time.monotonic,
    sleep=time.sleep,
    input_token_budget=None,
):
    """User-confirmed one-project free-tier scope, fixed model, fresh pilot process.

    Giá free = 0 chỉ sau user/tariff attestation tại CLI. Guard money NOT_CONFIGURED;
    CLI không cho paid calls; không giả actual provider billing = 0.
    """
    if (
        policy.model != DEFAULT_GEMINI_MODEL
        or policy.provider != "gemini"
        or policy.tier != "free"
        or not policy.mapping_confirmed
        or len(policy.credential_refs) != 1
        or policy.quota_limits.rpm > 5
        or policy.quota_limits.rpd > MAX_REQUESTS
    ):
        raise PilotStop("invalid_pilot_policy")
    schemas = classification_schema_registry()
    meter = MeteredModels(
        client.models, clock=clock, sleep=sleep, input_token_budget=input_token_budget
    )
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
        tenant_ref="classification-pilot",
        project_ref=policy.project_ref,
        credential_refs=frozenset({credential}),
        configuration_revision="M1-11a-free-v1",
        scope_confirmed=True,
        schema_registry=schemas,
    )
    return service, guard, meter


def pilot_config():
    return ClassificationConfig(
        taxonomy_version="experimental-candidates-v1",
        enabled_labels=("B01", "B02", "B03", "B09"),
        configuration_revision="M1-11a-free-v1",
        max_output_tokens=OUTPUT_CAP,
    )


def run_pilot(prepared, service, meter, *, credential_ref, smoke=True):
    """Sequential single invocation; schema/provider error đầu tiên dừng bảo thủ."""
    prepared.verify()
    stats = {
        **prepared.statistics(),
        "processed_pages": 0,
        "attempted_pages": 0,
        "resolved": 0,
        "unresolved": 0,
        "schema_errors": 0,
        "provider_errors": 0,
        "budget_denials": 0,
        "guard_denials": 0,
        "usage_errors": 0,
        "checkpoint_hits": 0,
        "cache_hits": 0,
        "anchors_checked": 0,
        "source_validation_failures": 0,
        "page_outcomes": [],
        "source_unchanged": False,
        "smoke_passed": False,
        "stop_reason": None,
    }
    reasons = Counter()
    reserve = Reservation(
        token_upper_bound=REQUEST_INPUT_BOUND + OUTPUT_CAP,
        token_basis="caller_attested_upper_bound",
    )
    if smoke:
        meter.pace()
        response = service.generate(
            parse_llm_request(
                dict(
                    contract_version="llm_gateway_v1",
                    request_id="pilot-smoke",
                    model=dict(provider="gemini", model=DEFAULT_GEMINI_MODEL),
                    messages=[
                        dict(
                            role="user",
                            content="Synthetic connectivity test. Return label null, "
                            "disposition insufficient, evidence []. No financial data.",
                        )
                    ],
                    generation=dict(max_output_tokens=OUTPUT_CAP, temperature=0.0),
                    constraints=dict(timeout_seconds=30.0),
                    output_spec=dict(format="json", schema_ref=SCHEMA_REF.export(), strict=True),
                )
            ),
            credential_ref=credential_ref,
            reservation=reserve,
            cache_allowed=False,
        )
        stats["smoke_passed"] = (
            response.response is not None
            and response.response.status == "success"
            and response.response.output.validation_status == "schema_valid"
        )
        if not stats["smoke_passed"] or meter.stopped:
            stats["stop_reason"] = meter.stopped or "smoke_failed"
            error = response.response.error if response.response is not None else None
            schema_error = error is not None and error.category in {
                "schema_mismatch",
                "structured_output_invalid",
            }
            if meter.stopped in LOCAL_LIMITS:
                stats["budget_denials"] += 1
            elif meter.stopped in USAGE_FAILURES:
                stats["usage_errors"] += 1
            elif response.response is None:
                stats["guard_denials"] += 1
            else:
                stats["schema_errors" if schema_error else "provider_errors"] += 1
                stats["safe_error_category"] = error.category if error else "guard_denied"
    smoke_requests = meter.requests
    classifier = PageClassifier(
        service,
        pilot_config(),
        checkpoints=CheckpointStore(
            prepared.root / "checkpoints",
            data_config=prepared.config,
        ),
    )
    for loaded in prepared.pages:
        if stats["stop_reason"]:
            break
        prepared.verify()
        before = loaded.page.export_source()
        stats["attempted_pages"] += 1
        args = dict(
            source_ref=loaded.mapping_result.reference.source_ref,
            credential_ref=credential_ref,
            reservation=reserve,
            cache_allowed=True,
            checkpoint_allowed=True,
        )
        meter.pace()
        result = classifier.classify(loaded, **args)
        if (
            loaded.page.export_source() != before
            or validate_understanding_quality(result.understanding, raw_page=loaded.page)
            or any(i.code == "source_validation_failed" for i in result.understanding.issues)
        ):
            stats["source_validation_failures"] += 1
            stats["stop_reason"] = "source_validation_failed"
            break
        if meter.stopped in LOCAL_LIMITS:
            stats["budget_denials"] += 1
            stats["stop_reason"] = meter.stopped
            break
        llm = result.llm_result
        if llm is not None:
            stats["cache_hits"] += llm.cache_hit
            if llm.response is None:
                stats["guard_denials"] += 1
                stats["stop_reason"] = "guard_denied"
            elif llm.response.status != "success":
                schema_error = llm.response.error is not None and llm.response.error.category in {
                    "schema_mismatch",
                    "structured_output_invalid",
                }
                stats["schema_errors" if schema_error else "provider_errors"] += 1
                stats["stop_reason"] = "schema_error" if schema_error else "provider_error"
                if llm.response.error is not None:
                    stats["safe_error_category"] = llm.response.error.category
        if stats["stop_reason"]:
            break
        stats["processed_pages"] += 1
        stats[result.understanding.classification.status] += 1
        stats["anchors_checked"] += len(result.understanding.classification.anchors)
        reasons.update(i.code for i in result.understanding.issues)
        stats["page_outcomes"].append(
            dict(
                status=result.understanding.classification.status,
                issues=[i.code for i in result.understanding.issues],
                anchors_checked=len(result.understanding.classification.anchors),
            )
        )
        stats["checkpoint_hits"] += result.checkpoint_status == "HIT"
        if meter.stopped:
            stats["usage_errors"] += meter.stopped in USAGE_FAILURES
            stats["stop_reason"] = meter.stopped
        if not stats["stop_reason"]:
            # Resume/cache verification sau mỗi completed page; không cho probe miss gọi API.
            calls = meter.requests
            meter.allow_new_requests = False
            try:
                repeated = classifier.classify(loaded, **args)
            finally:
                meter.allow_new_requests = True
            stats["checkpoint_hits"] += repeated.checkpoint_status == "HIT"
            stats["cache_hits"] += bool(repeated.llm_result and repeated.llm_result.cache_hit)
            if meter.requests != calls or repeated.understanding != result.understanding:
                stats["stop_reason"] = "reuse_verification_failed"
    prepared.verify()
    stats.update(
        source_unchanged=True,
        issue_counts=dict(reasons),
        api_requests=meter.requests,
        real_api_requests=meter.requests - smoke_requests,
        successful_responses=meter.successes,
        failed_requests=meter.failures,
        last_http_status=meter.last_http_status,
        input_tokens=meter.input_tokens,
        output_tokens=meter.output_tokens,
        total_tokens=meter.total_tokens,
        unknown_usage=meter.unknown_usage,
        input_tokens_charged=meter.input_charged,
        input_token_budget=meter.input_token_budget,
        estimated_cost_usd="0",
        actual_billing="unknown",
    )
    return stats
