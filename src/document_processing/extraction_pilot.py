"""M1-04b bounded pilot; private frozen inputs, unchanged extraction validators."""

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts.path_mapping import PathMappingRequest, PathRootMapping
from .crop_audit import MAX_IMAGE_BYTES, CropError, digest, reference_request
from .crop_expansion import write_once
from .crop_recovery import _check_components, _read_output
from .extraction_artifacts import (
    check_bbox_ledger,
    parse_recovery_entries,
    read_local_evidence,
)
from .extraction_validation import ExtractionIssue, ExtractionReport, validate_extraction
from .local_crop_mapping import page_request
from .path_resolver import resolve_path

PROTOCOL = "bounded_extraction_pilot_v1"
GROUPS = ("coverage", "risk-focused")
STRATA = [(s, str(y)) for s in ("BBS", "BCC", "BED") for y in range(2021, 2026)]
SIGNALS = ("duplicate_positions", "invalid_bbox", "empty_cell_text", "sparse_table", "missing_crop")
QUALITY_CODES = (
    "sparse_table",
    "duplicate_cell_position",
    "empty_cell_text",
    "invalid_bbox_geometry",
    "bbox_outside_image",
    "line_count_mismatch",
    "source_bbox_incomplete_table",
)
STATUS_VALUES = {
    "structural_status": ("valid", "invalid", "not_verified"),
    "image_status": ("checked", "invalid", "not_verified"),
    "source_binding_status": ("caller_bound", "caller_bound_run_unverified", "not_verified"),
    "ledger_status": ("consistent", "not_verified"),
}
AVAILABILITY = ("existing_original", "reconstructed_available", "missing_unrecovered")
MAPPING = ("resolved", "missing", "unmapped", "ambiguous", "unsafe", "not_checked")


class PilotModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class PilotPage(PilotModel):
    group: Literal["coverage", "risk-focused"]
    request: PathMappingRequest
    identity: list[str | int] = Field(min_length=3, max_length=3)
    image_reference: str
    references: int = Field(ge=0, le=500)
    reasons: list[str]


class InputSnapshot(PilotModel):
    path: str
    exists: bool
    sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: list[int] | None = Field(min_length=4, max_length=4)


class PilotManifest(PilotModel):
    protocol: Literal["bounded_extraction_pilot_v1"]
    manifest_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: list[PilotPage] = Field(min_length=1, max_length=30)
    mappings: list[PathRootMapping]
    image_bindings: dict[str, list[str | int]]
    ledger_plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_paths: dict[str, str]
    snapshots: list[InputSnapshot]
    selection: dict
    roots: dict[str, str]


def output_root(config):
    root = config.project_root / "artifacts/extraction-validation/M1-04b"
    _check_components(root)
    for source in (config.financial_report_dir, config.financial_ocr_dir):
        if root.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(
            root.resolve()
        ):
            raise CropError("overlapping_pilot_output")
    return root


def _allowed_input(path, config):
    if not path.is_absolute() or ".." in path.parts:
        raise CropError("unsafe_pilot_input")
    _check_components(path)
    roots = (
        config.financial_report_dir,
        config.financial_ocr_dir,
        config.project_root / "data/recovered_crops",
        config.project_root / "artifacts",
    )
    if not any(path.is_relative_to(root) and path != root for root in roots):
        raise CropError("unsafe_pilot_input")
    if path.is_relative_to(output_root(config)):
        raise CropError("pilot_input_output_overlap")


def snapshot(path, config):
    """Hash only explicitly selected inputs, including absence of original crops."""
    _allowed_input(path, config)
    try:
        before = path.stat()
    except FileNotFoundError:
        return dict(path=str(path), exists=False, sha256=None, metadata=None)
    content = _read_output(path, MAX_IMAGE_BYTES)
    after = path.stat()

    def metadata(s):
        return [s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino]

    if metadata(before) != metadata(after):
        raise CropError("pilot_source_changed")
    return dict(
        path=str(path),
        exists=True,
        sha256=hashlib.sha256(content).hexdigest(),
        metadata=metadata(after),
    )


def _reference_path(request, config):
    result = resolve_path(request, config)
    if result.status not in {"resolved", "missing"}:
        return None
    target = result.confirmed_target or result.candidate_targets[0]
    return config.get_root(target.root_key) / target.relative_suffix


def _reference_count(row):
    count = sum(v for k, v in row["references"].items() if k.startswith("crop:"))
    if type(count) is not int or count < 0:
        raise CropError("invalid_inventory_count")
    return count


def _signals(row):
    warnings = row.get("warnings", {})
    return {
        "duplicate_positions": any(t.get("duplicate_positions", 0) for t in row["tables"]),
        "invalid_bbox": any(
            warnings.get(k, 0)
            for k in ("cell_bbox_missing_or_invalid", "element_bbox_missing_or_invalid")
        ),
        "empty_cell_text": bool(warnings.get("cell_text_empty", 0)),
        "sparse_table": any(
            "sparse_grid_or_merged_cells_unverified" in t.get("suspicions", [])
            for t in row["tables"]
        ),
        "missing_crop": bool(warnings.get("crop_reference_colab_suffix_missing", 0)),
    }


def select_sample(rows, risk_sources, *, max_pages=30, max_references=500):
    """Pure deterministic selection over approved inventory metadata; no dataset I/O."""
    if (
        type(max_pages) is not int
        or not 1 <= max_pages <= 30
        or type(max_references) is not int
        or not 0 <= max_references <= 500
    ):
        raise CropError("pilot_bounds_exceeded")
    pool = {}
    for row in rows:
        source = row["source"]
        if source in pool and pool[source] != row:
            raise CropError("ambiguous_inventory_source")
        pool[source] = row
    if not set(risk_sources) <= pool.keys():
        raise CropError("missing_approved_binding")
    chosen, seen, omitted = [], set(), []
    references = 0

    def add(row, group, reason):
        nonlocal references
        if row["source"] in seen:
            return
        count = _reference_count(row)
        if len(chosen) >= max_pages or references + count > max_references:
            omitted.append(dict(source=row["source"], reason="omitted_budget"))
            return
        chosen.append(dict(row=row, group=group, reasons=[reason]))
        seen.add(row["source"])
        references += count

    for source in sorted(set(risk_sources)):
        add(pool[source], "risk-focused", "human_review")
    # Do not silently omit known human cases under a smaller resource budget.
    if not set(risk_sources) <= seen:
        raise CropError("human_sample_budget_exceeded")
    for symbol, year in STRATA:
        candidates = [
            r
            for r in pool.values()
            if r["source"] not in seen and (r["symbol"], r["year"]) == (symbol, year)
        ]
        if candidates:
            candidates.sort(
                key=lambda r: (
                    -len(r.get("element_types", {})),
                    -sum(t.get("cells", 0) for t in r["tables"]),
                    r["source"],
                )
            )
            add(candidates[0], "coverage", "stratum")
    for signal in SIGNALS:
        candidates = sorted(
            (r for r in pool.values() if r["source"] not in seen and _signals(r)[signal]),
            key=lambda r: r["source"],
        )
        if candidates:
            add(candidates[0], "risk-focused", signal)
    coverage = {(v["row"]["symbol"], v["row"]["year"]) for v in chosen if v["group"] == "coverage"}
    return chosen, dict(
        policy=PROTOCOL,
        max_pages=max_pages,
        max_references=max_references,
        selected_references=references,
        candidate_pages=len(pool),
        omitted=omitted,
        missing_coverage_strata=[list(s) for s in STRATA if s not in coverage],
        metadata_signals={s: sum(bool(_signals(r)[s]) for r in pool.values()) for s in SIGNALS},
    )


def _root_bindings(config):
    return {k: str(config.get_root(k)) for k in ("FINANCIAL_REPORT_DIR", "FINANCIAL_OCR_DIR")}


def build_manifest(config, plan_path, inventory_path, index_path, ledger_path):
    """Preflight selected approved sources only. Does not write or call validators."""
    paths = dict(plan=plan_path, inventory=inventory_path, index=index_path, ledger=ledger_path)
    initial = {str(p): snapshot(p, config) for p in paths.values()}
    plan = read_local_evidence(plan_path, config)
    if digest({k: v for k, v in plan.items() if k != "plan_id"}) != plan["plan_id"]:
        raise CropError("recovery_plan_mismatch")
    inventory = read_local_evidence(inventory_path, config, jsonl=True)
    entries = parse_recovery_entries(read_local_evidence(index_path, config, jsonl=True))
    ledger = read_local_evidence(ledger_path, config)
    issues = check_bbox_ledger(ledger, entries, plan_id=plan["plan_id"])
    context = plan["context"]
    approved = {r["source"]: r for r in context["rows"]}
    rows = []
    for row in inventory:
        if row["source"] in approved:
            if row != approved[row["source"]]:
                raise CropError("inventory_binding_mismatch")
            rows.append(row)
    lookup = {e.recovery_id: e for e in entries}
    risk = {lookup[i["recovery_id"]].ocr_source for i in issues}
    chosen, selection = select_sample(rows, risk)
    bindings = context["bindings"]
    mappings = [PathRootMapping.model_validate(m) for m in bindings["mappings"]]
    pages, snapshots = [], dict(initial)

    def capture(path):
        value = snapshot(path, config)
        if str(path) in snapshots and snapshots[str(path)] != value:
            raise CropError("pilot_source_changed")
        snapshots[str(path)] = value
        return value

    for selected in chosen:
        row = selected["row"]
        source = row["source"]
        identity = [row["symbol"], row["year"], row["page"]]
        audits = [a for a in context["audit"] if a["ocr_source"] == source]
        images = {a["source_image"] for a in audits}
        if len(images) != 1:
            raise CropError("missing_approved_binding")
        image = next(iter(images))
        if (
            bindings["image_bindings"].get(image) != identity
            or any(a["page_identity"] != identity for a in audits)
            or len(audits) != _reference_count(row)
        ):
            raise CropError("missing_approved_binding")
        request = page_request(row)
        json_path = _reference_path(request, config)
        if json_path is None:
            raise CropError("missing_approved_binding")
        js = capture(json_path)
        old = context["json_snapshots"][source]
        if (
            not js["exists"]
            or [js["metadata"][0], js["metadata"][1], js["metadata"][3], js["sha256"]] != old
        ):
            raise CropError("approved_source_changed")
        refs = [(image, "raw_page_image")] + [(a["original_path"], "ocr_crop") for a in audits]
        for original, category in refs:
            path = _reference_path(
                reference_request(original, category, source, ["reference"], mappings), config
            )
            if path is not None:
                state = capture(path)
                if (
                    category == "raw_page_image"
                    and state["sha256"] != bindings["source_snapshots"][image]["sha256"]
                ):
                    raise CropError("approved_source_changed")
        for entry in entries:
            if entry.ocr_source == source:
                if entry.output_relative_path != entry.recovery_id + ".png":
                    raise CropError("unsafe_recovery_target")
                for suffix in (".png", ".json"):
                    capture(
                        config.project_root / "data/recovered_crops" / (entry.recovery_id + suffix)
                    )
        pages.append(
            dict(
                group=selected["group"],
                request=request.model_dump(mode="json"),
                identity=identity,
                image_reference=image,
                references=_reference_count(row),
                reasons=selected["reasons"],
            )
        )
    if not pages:
        raise CropError("empty_pilot_sample")
    for path in paths.values():
        capture(path)
    payload = dict(
        protocol=PROTOCOL,
        pages=pages,
        mappings=bindings["mappings"],
        image_bindings={p["image_reference"]: p["identity"] for p in pages},
        ledger_plan_id=plan["plan_id"],
        evidence_paths={k: str(v) for k, v in paths.items()},
        snapshots=[snapshots[k] for k in sorted(snapshots)],
        selection=selection,
        roots=_root_bindings(config),
    )
    return parse_manifest(dict(manifest_id=digest(payload), **payload), config)


def parse_manifest(value, config):
    try:
        manifest = PilotManifest.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise CropError("invalid_pilot_manifest") from None
    payload = manifest.model_dump(mode="json", exclude={"manifest_id"})
    if digest(payload) != manifest.manifest_id or manifest.roots != _root_bindings(config):
        raise CropError("pilot_manifest_mismatch")
    sources = [p.request.reference.original_path for p in manifest.pages]
    if len(sources) != len(set(sources)) or sum(p.references for p in manifest.pages) > 500:
        raise CropError("pilot_bounds_or_duplicate")
    for page in manifest.pages:
        if (
            [type(v) for v in page.identity] != [str, str, int]
            or page.request.reference.category != "ocr_page_json"
            or manifest.image_bindings.get(page.image_reference) != page.identity
        ):
            raise CropError("missing_approved_binding")
    if set(manifest.evidence_paths) != {"plan", "inventory", "index", "ledger"}:
        raise CropError("invalid_pilot_evidence")
    snap_paths = [s.path for s in manifest.snapshots]
    if len(snap_paths) != len(set(snap_paths)):
        raise CropError("duplicate_pilot_snapshot")
    for item in manifest.snapshots:
        _allowed_input(Path(item.path), config)
        if (item.exists and (item.sha256 is None or item.metadata is None)) or (
            not item.exists and (item.sha256 is not None or item.metadata is not None)
        ):
            raise CropError("invalid_pilot_snapshot")
    if not set(manifest.evidence_paths.values()) <= set(snap_paths):
        raise CropError("missing_pilot_snapshot")
    for path in manifest.evidence_paths.values():
        p = Path(path)
        if not p.is_relative_to(config.project_root / "artifacts"):
            raise CropError("invalid_pilot_evidence")
    return manifest


def freeze_manifest(manifest, config):
    checked = parse_manifest(manifest.model_dump(mode="json"), config)
    verify_inputs(checked, config)
    verify_bindings(checked, config)
    path = output_root(config) / "manifest.json"
    write_once(path, checked.model_dump(mode="json"))
    return path


def verify_inputs(manifest, config):
    for item in manifest.snapshots:
        if snapshot(Path(item.path), config) != item.model_dump(mode="json"):
            raise CropError("pilot_source_changed")


def verify_bindings(manifest, config):
    """Rebind frozen membership to approved evidence; never reselect on execution."""
    plan = read_local_evidence(Path(manifest.evidence_paths["plan"]), config)
    if (
        digest({k: v for k, v in plan.items() if k != "plan_id"}) != plan["plan_id"]
        or plan["plan_id"] != manifest.ledger_plan_id
    ):
        raise CropError("recovery_plan_mismatch")
    context = plan["context"]
    if [m.model_dump(mode="json") for m in manifest.mappings] != context["bindings"]["mappings"]:
        raise CropError("pilot_binding_mismatch")
    rows = {r["source"]: r for r in context["rows"]}
    snapshots = {s.path: s for s in manifest.snapshots}
    targets, images = set(), set()
    for page in manifest.pages:
        source = page.request.reference.original_path
        row = rows.get(source)
        audits = [a for a in context["audit"] if a["ocr_source"] == source]
        if (
            row is None
            or page.request != page_request(row)
            or page.identity != [row["symbol"], row["year"], row["page"]]
            or page.references != _reference_count(row)
            or len(audits) != page.references
            or not audits
            or {a["source_image"] for a in audits} != {page.image_reference}
            or context["bindings"]["image_bindings"].get(page.image_reference) != page.identity
        ):
            raise CropError("pilot_binding_mismatch")
        target = _reference_path(page.request, config)
        if target is None or str(target) not in snapshots:
            raise CropError("missing_pilot_snapshot")
        if str(target) in targets or page.image_reference in images:
            raise CropError("duplicate_pilot_binding")
        targets.add(str(target))
        images.add(page.image_reference)
        snap = snapshots[str(target)]
        old = context["json_snapshots"][source]
        if (
            not snap.exists
            or [snap.metadata[0], snap.metadata[1], snap.metadata[3], snap.sha256] != old
        ):
            raise CropError("approved_source_changed")
        refs = [(page.image_reference, "raw_page_image")] + [
            (a["original_path"], "ocr_crop") for a in audits
        ]
        for original, category in refs:
            target = _reference_path(
                reference_request(original, category, source, ["reference"], manifest.mappings),
                config,
            )
            if target is not None and str(target) not in snapshots:
                raise CropError("missing_pilot_snapshot")
            if (
                category == "raw_page_image"
                and target is not None
                and snapshots[str(target)].sha256
                != (context["bindings"]["source_snapshots"][original]["sha256"])
            ):
                raise CropError("approved_source_changed")
    entries = parse_recovery_entries(
        read_local_evidence(Path(manifest.evidence_paths["index"]), config, jsonl=True)
    )
    selected = {p.request.reference.original_path for p in manifest.pages}
    for entry in entries:
        if entry.ocr_source in selected:
            if entry.output_relative_path != entry.recovery_id + ".png":
                raise CropError("unsafe_recovery_target")
            for suffix in (".png", ".json"):
                path = config.project_root / "data/recovered_crops" / (entry.recovery_id + suffix)
                if str(path) not in snapshots:
                    raise CropError("missing_pilot_snapshot")
    ledger = read_local_evidence(Path(manifest.evidence_paths["ledger"]), config)
    issues = check_bbox_ledger(ledger, entries, plan_id=manifest.ledger_plan_id)
    lookup = {e.recovery_id: e for e in entries}
    if any(lookup[i["recovery_id"]].ocr_source not in selected for i in issues):
        raise CropError("missing_human_sample")


def aggregate(records):
    """Private exact counts; page and occurrence units have separate denominators."""
    groups = {}
    for group in GROUPS:
        subset = [r for r in records if r["group"] == group]
        reports = [r["report"] for r in subset]
        issues = [i for r in reports for i in r["issues"]]
        crops = [c for r in reports for c in r["crops"]]
        groups[group] = dict(
            selected_pages=len(subset),
            processed_pages=sum(r["failure"] is None for r in subset),
            failed_pages=sum(r["failure"] is not None for r in subset),
            expected_references=sum(r["expected_references"] for r in subset),
            observed_references=len(crops),
            unverified_references=sum(
                r["expected_references"] - len(r["report"]["crops"]) for r in subset
            ),
            statuses={k: dict(Counter(r[k] for r in reports)) for k in STATUS_VALUES},
            availability=dict(Counter(c["availability"] for c in crops)),
            mapping_status=dict(Counter(c["mapping_status"] for c in crops)),
            issue_occurrences=len(issues),
            issue_codes=dict(Counter(i["code"] for i in issues)),
            pages_with_issue_code=dict(
                Counter(code for r in reports for code in {i["code"] for i in r["issues"]})
            ),
            issue_categories=dict(Counter(i["category"] for i in issues)),
            human_issue_occurrences=sum(
                i["origin"] == "human_review" and i["code"] == "source_bbox_incomplete_table"
                for i in issues
            ),
            human_requires_review=sum(
                i["origin"] == "human_review"
                and i["code"] == "source_bbox_incomplete_table"
                and i["status"] == "requires_review"
                for i in issues
            ),
            human_not_verified=sum(
                i["origin"] == "human_review"
                and i["code"] == "source_bbox_incomplete_table"
                and i["status"] == "not_verified"
                for i in issues
            ),
            not_verified_issue_occurrences=sum(i["status"] == "not_verified" for i in issues),
        )
    return groups


def public_statistics(report):
    """Fixed numeric/enum allowlist: never copy arbitrary strings or private tokens."""
    public = {}
    for group in GROUPS:
        g = report["groups"][group]
        fields = (
            "selected_pages",
            "processed_pages",
            "failed_pages",
            "expected_references",
            "observed_references",
            "unverified_references",
            "issue_occurrences",
            "human_issue_occurrences",
            "human_requires_review",
            "human_not_verified",
            "not_verified_issue_occurrences",
        )
        out = {k: g[k] for k in fields}
        out["statuses"] = {
            k: {v: g["statuses"][k].get(v, 0) for v in values}
            for k, values in STATUS_VALUES.items()
        }
        for key, values in (
            ("availability", AVAILABILITY),
            ("mapping_status", MAPPING),
            ("issue_categories", ("structural", "quality", "artifact")),
        ):
            out[key] = {v: g[key].get(v, 0) for v in values}
        for key in ("issue_codes", "pages_with_issue_code"):
            out[key] = {v: g[key].get(v, 0) for v in QUALITY_CODES}
            out[key]["other"] = (
                sum(v for k, v in g[key].items() if k not in QUALITY_CODES)
                if key == "issue_codes"
                else sum(
                    any(i["code"] not in QUALITY_CODES for i in r["report"]["issues"])
                    for r in report["records"]
                    if r["group"] == group
                )
            )
        public[group] = out

    def numeric(value):
        if isinstance(value, dict):
            return all(numeric(v) for v in value.values())
        return type(value) is int and value >= 0

    if not numeric(public):
        raise CropError("invalid_public_statistics")
    return public


def execute_manifest(config, *, run):
    """Explicit read-only pilot; reruns never reselect, and conflicting output stops."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", run):
        raise CropError("invalid_pilot_run")
    root = output_root(config)
    manifest = parse_manifest(read_local_evidence(root / "manifest.json", config), config)
    verify_inputs(manifest, config)
    verify_bindings(manifest, config)
    entries = read_local_evidence(Path(manifest.evidence_paths["index"]), config, jsonl=True)
    ledger = read_local_evidence(Path(manifest.evidence_paths["ledger"]), config)
    checked_entries = parse_recovery_entries(entries)
    human_items = check_bbox_ledger(ledger, checked_entries, plan_id=manifest.ledger_plan_id)
    human_sources = {e.recovery_id: e for e in checked_entries}
    records = []
    for page in manifest.pages:
        try:
            result = validate_extraction(
                page.request,
                config,
                manifest.mappings,
                expected_identity=tuple(page.identity),
                image_bindings={k: tuple(v) for k, v in manifest.image_bindings.items()},
                recovery_entries=entries,
                bbox_ledger=ledger,
                ledger_plan_id=manifest.ledger_plan_id,
            ).export()
        except OSError:
            token = digest(page.request.reference.original_path)
            human = tuple(
                ExtractionIssue(
                    "source_bbox_incomplete_table",
                    "quality",
                    "human_review",
                    token,
                    artifact_token=digest(item),
                )
                for item in human_items
                if human_sources[item["recovery_id"]].ocr_source
                == page.request.reference.original_path
            )
            result = ExtractionReport(
                token,
                "not_verified",
                "not_verified",
                "not_verified",
                "consistent",
                (
                    ExtractionIssue(
                        "pilot_page_io_failure", "artifact", "pilot", token, status="not_verified"
                    ),
                )
                + human,
            ).export()
        if any(i["code"] in {"source_changed", "source_image_changed"} for i in result["issues"]):
            raise CropError("pilot_source_changed")
        if len(result["crops"]) > page.references:
            raise CropError("pilot_reference_mismatch")
        failure = None if result["structural_status"] == "valid" else "page_input_failure"
        records.append(
            dict(
                group=page.group,
                source_token=digest(page.request.reference.original_path),
                expected_references=page.references,
                failure=failure,
                report=result,
            )
        )
    verify_inputs(manifest, config)
    report = dict(
        protocol=PROTOCOL,
        manifest_id=manifest.manifest_id,
        records=records,
        groups=aggregate(records),
        understanding_status="not_supplied",
    )
    # Canonical report deliberately excludes run labels/timestamps.
    exported = dict(report_id=digest(report), **report)
    write_once(root / "canonical-report.json", exported)
    write_once(root / (run + ".json"), exported)
    verify_inputs(manifest, config)
    return exported
