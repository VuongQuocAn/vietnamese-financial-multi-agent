"""Same-eight-table pilot; reuse shared Gateway/quota/cache/checkpoints and SDK meter."""

import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from ..core.gemini_adapter import GeminiAdapter
from ..core.llm_cache import CachedLLMService
from ..core.llm_gateway import SharedLLMGateway
from ..core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
    Reservation,
)
from .checkpoints import CheckpointStore, fingerprint_json
from .classification_pilot import MeteredModels, PilotStop
from .contracts.document_understanding import (
    DocumentClassification,
    DocumentUnderstandingResult,
    RawPageIdentity,
    SourceAnchor,
)
from .contracts.document_understanding_validation import validate_understanding_quality
from .crop_expansion import write_once
from .extraction_artifacts import read_local_evidence
from .extraction_pilot import parse_manifest, snapshot, verify_bindings
from .ocr_loader import load_ocr_page
from .path_resolver import resolve_path
from .table_assistance import AssistanceConfig, TableReconstructor, table_schema_registry
from .table_reconstruction import reconstruct_table

REQUEST_LIMIT = 15
INPUT_BOUND = 100_000  # Per-request SDK UTF-8 upper bound; no aggregate input-token cap.
OUTPUT_CAP = 16384


@dataclass(frozen=True)
class PreparedTables:
    units: tuple = field(repr=False)
    root: Path = field(repr=False)
    config: object = field(repr=False)
    source_manifest: Path = field(repr=False)
    manifest_payload: dict = field(repr=False)
    snapshots: tuple = field(repr=False)

    def verify(self):
        if read_local_evidence(self.source_manifest, self.config) != self.manifest_payload:
            raise PilotStop("frozen_manifest_changed")
        for before in self.snapshots:
            if snapshot(Path(before["path"]), self.config) != before:
                raise PilotStop("selected_source_changed")


def prepare_tables(config):
    manifest_path = config.project_root / "artifacts/extraction-validation/M1-04b/manifest.json"
    payload = read_local_evidence(manifest_path, config)
    manifest = parse_manifest(payload, config)
    verify_bindings(manifest, config)
    baseline_path = config.project_root / "artifacts/table-reconstruction/M1-12/validation.json"
    before_baseline = snapshot(baseline_path, config)
    baseline = read_local_evidence(baseline_path, config)
    if baseline["source_manifest"] != manifest.manifest_id or [
        r["manifest_index"] for r in baseline["records"]
    ] != [0, 2, 4, 5]:
        raise PilotStop("baseline_membership_mismatch")
    captured = [before_baseline, *baseline["snapshots"]]
    expected = {s.path: s.model_dump(mode="json") for s in manifest.snapshots}
    for item in baseline["snapshots"]:
        if item != expected.get(item["path"]):
            raise PilotStop("baseline_snapshot_mismatch")
    root = config.project_root / "artifacts/table-reconstruction/M1-12a"
    CheckpointStore(root, data_config=config)  # Source-root protection, no write yet.
    units = []
    for record in baseline["records"]:
        selected = manifest.pages[record["manifest_index"]]
        request = selected.request.model_copy(deep=True)
        target = resolve_path(request, config).confirmed_target
        if target is None:
            raise PilotStop("source_unresolved")
        source = config.get_root(target.root_key) / target.relative_suffix
        if snapshot(source, config) != expected.get(str(source)):
            raise PilotStop("source_changed")
        request.reference.source_ref = request.reference.original_path
        identity = RawPageIdentity(
            symbol=selected.identity[0],
            year=selected.identity[1],
            page=selected.identity[2],
            image=selected.image_reference,
            source_ref=request.reference.source_ref,
        )
        request.reference.anchor = SourceAnchor(page=identity, status="unresolved")
        loaded = load_ocr_page(request, config)
        if fingerprint_json(loaded.page.export_source()) != record["source_digest"]:
            raise PilotStop("baseline_source_mismatch")
        actual_ids = [e.id for e in loaded.page.elements if e.type == "table"]
        if actual_ids != [t["id"] for t in record["result"]["tables"]]:
            raise PilotStop("baseline_tables_mismatch")
        for old in record["result"]["tables"]:
            current = reconstruct_table(loaded.page, old["id"], source_ref=identity.source_ref)
            if current.export_result() != old:
                raise PilotStop("baseline_deterministic_changed")
            units.append((loaded, old["id"]))
    prepared = PreparedTables(tuple(units), root, config, manifest_path, payload, tuple(captured))
    prepared.verify()
    if (
        len(units) != 8
        or sum(len(e.cells) for loaded, key in units for e in loaded.page.elements if e.id == key)
        != 310
    ):
        raise PilotStop("baseline_count_mismatch")
    write_once(
        root / "manifest.json",
        dict(
            protocol="same-eight-tables-v1",
            source_manifest=manifest.manifest_id,
            snapshots=captured,
            units=[
                dict(source_ref=p.mapping_result.reference.source_ref, table_id=t) for p, t in units
            ],
        ),
    )
    return prepared


def compose_tables(client, policy: ProjectPolicy, *, clock=time.monotonic, sleep=time.sleep):
    if (
        policy.model != AssistanceConfig().model
        or policy.provider != "gemini"
        or policy.tier != "free"
        or not policy.mapping_confirmed
        or len(policy.credential_refs) != 1
        or policy.quota_limits.rpm > 5
        or policy.quota_limits.rpd > REQUEST_LIMIT
    ):
        raise PilotStop("invalid_table_pilot_policy")
    schemas = table_schema_registry()
    meter = MeteredModels(
        client.models,
        clock=clock,
        sleep=sleep,
        request_limit=REQUEST_LIMIT,
        output_cap=OUTPUT_CAP,
        request_input_bound=INPUT_BOUND,
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
        tenant_ref="table-pilot",
        project_ref=policy.project_ref,
        credential_refs=frozenset({credential}),
        configuration_revision="M1-12a-v1",
        scope_confirmed=True,
        schema_registry=schemas,
        ttl_seconds=3600,
    )
    return service, guard, meter


def table_arguments(loaded, credential):
    return dict(
        source_ref=loaded.mapping_result.reference.source_ref,
        credential_ref=credential,
        reservation=Reservation(
            token_upper_bound=INPUT_BOUND + OUTPUT_CAP, token_basis="caller_attested_upper_bound"
        ),
        cache_allowed=True,
        checkpoint_allowed=True,
    )


def run_tables(prepared, service, meter, credential):
    prepared.verify()
    engine = TableReconstructor(
        service,
        checkpoints=CheckpointStore(
            prepared.root / "checkpoints",
            data_config=prepared.config,
        ),
    )
    baseline_counts, assisted_counts, reasons = Counter(), Counter(), Counter()
    cache_hits = checkpoint_hits = anchors = cells = 0
    outcomes, private_records = [], []
    stop_reason = None
    for number, (loaded, table_id) in enumerate(prepared.units):
        prepared.verify()
        before = fingerprint_json(loaded.page.export_source())
        args = table_arguments(loaded, credential)
        meter.pace()
        result = engine.reconstruct(loaded, table_id, **args)
        base, table = result.deterministic, result.table
        du = DocumentUnderstandingResult(
            contract_version="document_understanding_v1",
            raw_page=table.anchors[0].page,
            classification=DocumentClassification(label=None, status="unresolved", anchors=[]),
            text_regions=[],
            tables=[table],
            issues=[],
        )
        quality = validate_understanding_quality(du, raw_page=loaded.page)
        if fingerprint_json(loaded.page.export_source()) != before or any(
            i.code != "empty_text" for i in quality
        ):
            raise PilotStop("source_validation_failed")
        baseline_counts[base.status] += 1
        assisted_counts[table.status] += 1
        anchors += len(table.anchors) + sum(len(c.anchors) for c in table.cells)
        cells += len(table.cells)
        reasons.update(i.code for i in table.issues or [] if not i.code.startswith("reviewed_"))
        llm = result.llm_result
        outcome = dict(
            index=number,
            baseline=base.status,
            assisted=table.status,
            cells=len(table.cells),
            anchors=len(table.anchors) + sum(len(c.anchors) for c in table.cells),
            issues=dict(Counter(i.code for i in table.issues or [])),
        )
        outcomes.append(outcome)
        record = dict(
            index=number,
            input_digest=before,
            table_id=table_id,
            result=table.export_result(),
            prediction=result.prediction.model_dump(mode="json") if result.prediction else None,
            config=AssistanceConfig().model_dump(mode="json"),
        )
        write_once(prepared.root / f"table-{number}.json", record)
        private_records.append(record)
        # Reuse probes: prohibit even an accidental SDK call on a miss.
        meter.allow_new_requests = False
        if llm is not None and llm.response is not None and llm.response.status == "success":
            probe = TableReconstructor(service).reconstruct(loaded, table_id, **args)
            if probe.llm_result is None or not probe.llm_result.cache_hit or probe.table != table:
                raise PilotStop("cache_reuse_failed")
            cache_hits += 1
        if table.status == "resolved" and base.status == "unresolved":
            probe = engine.reconstruct(loaded, table_id, **args)
            if probe.checkpoint_status != "HIT" or probe.table != table:
                raise PilotStop("checkpoint_reuse_failed")
            checkpoint_hits += 1
        meter.allow_new_requests = True
        if meter.stopped or (
            llm is not None and (llm.response is None or llm.response.status != "success")
        ):
            stop_reason = meter.stopped or "guard_or_schema_error"
            break
    prepared.verify()
    summary = dict(
        pages=len(
            {fingerprint_json(p.page.page.model_dump(mode="json")) for p, _ in prepared.units}
        ),
        selected_tables=len(prepared.units),
        processed_tables=len(outcomes),
        baseline=dict(baseline_counts),
        assisted=dict(assisted_counts),
        cells=cells,
        validated_anchors=anchors,
        remaining_issues=dict(reasons),
        requests=meter.requests,
        input_tokens=meter.input_tokens,
        output_tokens=meter.output_tokens,
        total_tokens=meter.total_tokens,
        failures=meter.failures,
        unknown_usage=meter.unknown_usage,
        cache_hits=cache_hits,
        checkpoint_hits=checkpoint_hits,
        source_unchanged=True,
        stop_reason=stop_reason,
        outcomes=outcomes,
    )
    return summary, private_records
