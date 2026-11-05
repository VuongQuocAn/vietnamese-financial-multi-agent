"""Frozen saved-source citation evaluation; never loads ledger histories or models.

Oracle freezing uses raw JSON and stdlib only, independently of CitationRenderer.
Inputs are pinned accepted M7-01/M7-03 artifacts. All artifacts use exclusive writes.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ORACLE_SHA256 = "a4bf893d4b129c32b33774294449b8d97364283c1a07d87f9a0ba4b25681981d"
PAGE_LIMIT = "Vị trí chứng cứ hiện chỉ được xác định ở cấp trang."
LOCATION_LIMIT = "Vị trí nguồn chưa được phân giải đầy đủ."


def checksum(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def oracle_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def source_parts(source, mode):
    if mode == "qa":
        return [
            dict(
                id=s["segment_id"],
                text=f"Kỳ {s['context']['period']} — {s['content']}",
                claims=s["verified_claim_ids"],
                citations=s["citations"],
                contexts=[s["context"]],
                slots=[],
            )
            for s in source["grounded_segments"]
        ]
    return [
        dict(
            id=p["paragraph_id"],
            text=p["text_vi"],
            claims=p["verified_claim_ids"],
            citations=p["citations"],
            contexts=[c["claim_context"] for c in p["context"]],
            slots=p["source_slot_ids"],
        )
        for section in source["sections"]
        for p in section["paragraphs"]
        if p["citations"]
    ]


def source_key(c):
    # Independent spelling of the documented EvidenceAnchor.source_key contract.
    r = c["source"]["reference"]
    a, p = r["anchor"], r["anchor"]["page"]
    return [
        c["document_id"],
        c["snapshot_id"],
        p["page"],
        p["image"],
        p["source_ref"],
        a["element_id"],
        a["table_id"],
        a["cell_id"],
        a["line_id"],
        a["observed_bbox"],
        r["source_pointer"],
    ]


def expected_locator(c):
    r, a = c["source"]["reference"], c["source"]["reference"]["anchor"]
    return dict(
        document_id=c["document_id"],
        snapshot_id=c["snapshot_id"],
        pdf_page=c["pdf_page"],
        source_ref=a["page"]["source_ref"],
        source_pointer=r["source_pointer"],
        image_reference=a["page"]["image"],
        **{k: a[k] for k in ("element_id", "table_id", "cell_id", "line_id", "observed_bbox")},
        provenance_level=c["provenance_level"],
        resolution_status="resolved"
        if a["status"] == "resolved" and c["anchor_id"] and a["page"]["image"].strip()
        else "unresolved",
        resource_mapping_status="not_provided",
    )


def cited_body(source, mode, numbers):
    """Position-based oracle, independent of renderer templates or text replacement."""

    def marker(sid):
        return " " + "".join(f"[{n}]" for n in numbers[sid]) if sid in numbers else ""

    if mode == "report":
        if not source["sections"]:
            return source["body_vi"]
        return (
            "# "
            + source["report_title"]
            + "\n\n"
            + "\n\n".join(
                f"## {s['order']}. {s['title_vi']}\n\n"
                + "\n\n".join(p["text_vi"] + marker(p["paragraph_id"]) for p in s["paragraphs"])
                for s in source["sections"]
            )
        )
    # The accepted QA starts with exactly one introduction line. Consume each
    # known segment by offset; identical text never causes a global replacement.
    original, cursor, chunks = source["answer_vi"], 0, []
    if source["grounded_segments"]:
        cursor = original.index("\n") + 1
        chunks.append(original[:cursor])
    for s in source["grounded_segments"]:
        text = f"Kỳ {s['context']['period']} — {s['content']}"
        assert original[cursor : cursor + len(text)] == text
        chunks.extend([text, marker(s["segment_id"])])
        cursor += len(text)
        if cursor < len(original):
            assert original[cursor] == "\n"
            chunks.append("\n")
            cursor += 1
    chunks.append(original[cursor:])
    return "".join(chunks)


def expectations(source, mode):
    refs, bindings, numbers = [], [], {}
    registry = {}
    for part in source_parts(source, mode):
        selected = []
        for c in part["citations"]:
            identity = "citation:" + checksum(source_key(c))
            if identity not in registry:
                locator = expected_locator(c)
                limits = list(c["limitations"])
                if c["provenance_level"] == "page":
                    limits = unique(limits + [PAGE_LIMIT])
                if locator["resolution_status"] != "resolved":
                    limits = unique(limits + [LOCATION_LIMIT])
                ref = dict(
                    id=identity,
                    number=len(refs) + 1,
                    page=c["pdf_page"],
                    provenance=c["provenance_level"],
                    anchor=c["anchor_id"],
                    identity_sha256=checksum([c["document_id"], c["snapshot_id"]]),
                    locator_sha256=checksum(locator),
                    limits=limits,
                    source_citations=[checksum(c)],
                    claims=[],
                    segments=[],
                )
                refs.append(ref)
                registry[identity] = ref
            ref = registry[identity]
            ref["claims"] = unique(ref["claims"] + part["claims"])
            ref["segments"] = unique(ref["segments"] + [part["id"]])
            ref["limits"] = unique(ref["limits"] + c["limitations"])
            ref["source_citations"] = unique(ref["source_citations"] + [checksum(c)])
            selected = unique(selected + [ref["number"]])
        numbers[part["id"]] = selected
        bindings.append(
            dict(
                segment=part["id"],
                numbers=selected,
                claim_sha256=checksum(part["claims"]),
                contexts_sha256=checksum(part["contexts"]),
                slots_sha256=checksum(part["slots"]),
            )
        )
    annotations = [source]
    if mode == "qa":
        annotations += source["grounded_segments"]
    else:
        annotations += source["sections"]
        annotations += [p for s in source["sections"] for p in s["paragraphs"]]
    caveats = unique(v for item in annotations for v in item["caveats"])
    limits = unique(
        [v for item in annotations for v in item["limitations"]]
        + [v for r in refs for v in r["limits"]]
    )
    for r in refs:
        for key in ("limits", "claims", "segments"):
            r[key + "_sha256"] = checksum(r.pop(key))
    return dict(
        references=refs,
        bindings=bindings,
        cited_body_sha256=checksum(cited_body(source, mode, numbers)),
        caveats_sha256=checksum(caveats),
        limitations_sha256=checksum(limits),
        status=source["status"],
        source_fingerprint=checksum(source),
    )


def freeze(root, path):
    cases = []
    qa_root = "artifacts/evidence/M7-01-offline-v2"
    report_root = "artifacts/evidence/M7-03-report-final/offline"
    qa_names = [
        f"{kind}-{year}" for kind in ("revenue", "margin", "multi") for year in range(2021, 2026)
    ] + [
        "recovery-cfo",
        "recovery-revenue",
        "partial-missing",
        "partial-unsupported",
        "control-empty-ledger",
        "control-missing-snapshot",
        "control-cross-document",
    ]
    report_names = [
        f"{kind}-{year}"
        for kind in ("general", "profit")
        for year in ("2021", "2022", "2022-recovery", "2023", "2024", "2025")
    ]
    report_names += [
        "multi-2024",
        "multi-2025",
        "missing-2025",
        "wrong-document",
        "missing-snapshot",
        "multi-year",
    ]
    files = [("qa", name, f"{qa_root}/response-{name}.json") for name in qa_names]
    files += [("report", name, f"{report_root}/response-{name}.json") for name in report_names]
    files += [
        (
            "report",
            "sample-" + name,
            f"artifacts/evidence/M7-03-report-final/replay/reports/{name}.json",
        )
        for name in ("annual-general-2025", "profit-2025", "missing-2025")
    ]
    for mode, name, relative in files:
        source = read(root / relative)
        assert source["validation_result"] == dict(valid=True, errors=[])
        cases.append(
            dict(
                id=mode + "-" + name,
                mode=mode,
                path=relative,
                sha256=file_hash(root / relative),
                category="saved_BBS" if source["citations"] else "saved_empty_control",
                expected=expectations(source, mode),
            )
        )
    attacks = [
        ("page", "references.0.pdf_page", 999),
        ("document", "references.0.document_id", "other"),
        ("snapshot", "references.0.snapshot_id", "other"),
        ("anchor", "references.0.anchor_id", "other"),
        ("cell", "references.0.source_locator.cell_id", "B12"),
        ("bbox", "references.0.source_locator.observed_bbox", [1, 2, 3, 4]),
        ("locator_page", "references.0.source_locator.pdf_page", 999),
        ("pointer", "references.0.source_locator.source_pointer", "/fake"),
        ("image", "references.0.source_locator.image_reference", "fake.png"),
        ("provenance", "references.0.provenance_level", "cell"),
        ("number", "references.0.display_number", 99),
        ("label", "references.0.display_label", "[99]"),
        ("id", "references.0.citation_id", "fake"),
        ("claims", "references.0.bound_verified_claim_ids", ["fake"]),
        ("binding", "citation_bindings.0.output_segment_id", "other-paragraph"),
        ("context", "citation_bindings.0.contexts.0.period", "1900"),
        ("limitations", "limitations", []),
        ("caveats", "caveats", []),
        ("fingerprint", "source_fingerprint", "fake"),
        ("source_citation", "references.0.source_citations.0.pdf_page", 999),
        ("missing_reference", "special", "missing"),
        ("extra_reference", "special", "extra"),
        ("wrong_marker", "special", "marker"),
        ("content", "special", "content"),
        ("claim_binding", "citation_bindings.0.verified_claim_ids", ["fake"]),
    ]
    controls = [
        dict(id=f"{mode}-{name}", mode=mode, field=field, value=value, expected="rejected")
        for mode in ("qa", "report")
        for name, field, value in attacks
    ]
    write_new(
        path,
        dict(
            version="m7_04_citation_oracle_v1",
            scenarios=cases,
            controls=controls,
            independent_pdf_accuracy="not_evaluated",
        ),
    )
    print("Frozen independent oracle:", len(cases), "sources;", len(controls), "controls")


def mutate(output, control):
    path, value = control["field"], control["value"]
    if path == "special":
        if value == "missing":
            output.references.pop()
        elif value == "extra":
            output.references.append(output.references[0].model_copy(deep=True))
        elif value == "marker":
            output.rendered_text = output.rendered_text.replace("[1]", "[999]", 1)
        else:
            output.rendered_text = "Financial mutation\n" + output.rendered_text
        return
    pieces, target = path.split("."), output
    for key in pieces[:-1]:
        target = target[int(key)] if key.isdigit() else getattr(target, key)
    setattr(target, pieces[-1], value)


def evaluate(root, output, oracle_path):
    from vietnamese_financial_multi_agent.outputs import (
        CitationRenderer,
        GroundedFinancialReport,
        RenderedCitationOutput,
        VietnameseQAResponse,
        validate_rendered_citations,
    )

    assert oracle_hash(oracle_path) == ORACLE_SHA256, "citation_oracle_pin_mismatch"
    oracle = read(oracle_path)
    write_new(output / "expected-oracle.json", oracle)
    rows, sources, results = [], {}, {}
    metrics = Counter()
    for case in oracle["scenarios"]:
        path = root / case["path"]
        assert file_hash(path) == case["sha256"], case["id"] + ":source_pin_mismatch"
        raw = read(path)
        kind = VietnameseQAResponse if case["mode"] == "qa" else GroundedFinancialReport
        source = kind.model_validate_json(path.read_bytes())
        before = source.model_dump_json()
        method = getattr(CitationRenderer(), "render_" + case["mode"])
        result = method(source)
        expected = case["expected"]
        checks = {}
        checks["citation_precision"] = len(result.references) == len(
            expected["references"]
        ) and all(
            r.citation_id == e["id"]
            for r, e in zip(result.references, expected["references"], strict=False)
        )
        checks["citation_recall"] = [r.citation_id for r in result.references] == [
            r["id"] for r in expected["references"]
        ]
        actual_bindings = [
            dict(
                segment=b.output_segment_id,
                numbers=b.display_numbers,
                claim_sha256=checksum(b.verified_claim_ids),
                contexts_sha256=checksum([c.model_dump(mode="json") for c in b.contexts]),
                slots_sha256=checksum(b.source_slot_ids),
            )
            for b in result.citation_bindings
        ]
        checks["marker_binding_correctness"] = actual_bindings == expected["bindings"]
        checks["source_locator_correctness"] = all(
            checksum(r.source_locator.model_dump(mode="json")) == e["locator_sha256"]
            for r, e in zip(result.references, expected["references"], strict=True)
        )
        checks["page_correctness"] = all(
            r.pdf_page == e["page"]
            for r, e in zip(result.references, expected["references"], strict=True)
        )
        checks["provenance_correctness"] = all(
            r.provenance_level == e["provenance"]
            for r, e in zip(result.references, expected["references"], strict=True)
        )
        checks["citation_reuse_consistency"] = all(
            r.display_number == e["number"]
            and r.display_label == f"[{e['number']}]"
            and checksum(r.bound_verified_claim_ids) == e["claims_sha256"]
            and checksum(r.bound_output_segment_ids) == e["segments_sha256"]
            and [checksum(c.model_dump(mode="json")) for c in r.source_citations]
            == e["source_citations"]
            and checksum(r.limitations) == e["limits_sha256"]
            for r, e in zip(result.references, expected["references"], strict=True)
        )
        checks["caveat_retention"] = checksum(result.caveats) == expected["caveats_sha256"] and (
            checksum(result.limitations) == expected["limitations_sha256"]
        )
        checks["source_identity_preservation"] = all(
            checksum([r.document_id, r.snapshot_id]) == e["identity_sha256"]
            and r.anchor_id == e["anchor"]
            for r, e in zip(result.references, expected["references"], strict=True)
        )
        body = cited_body(
            raw, case["mode"], {b["segment"]: b["numbers"] for b in expected["bindings"]}
        )
        checks["financial_content_preservation"] = (
            checksum(body) == expected["cited_body_sha256"]
            and result.rendered_text.startswith(body)
            and source.model_dump_json() == before
            and result.original_status == expected["status"]
            and result.source_fingerprint == expected["source_fingerprint"]
        )
        # Verify every reference line and exact body independently; the local
        # validator additionally verifies the complete presentation incl. labels.
        checks["reference_list"] = all(
            f"{r.display_label} Tài liệu {r.document_id} — Snapshot {r.snapshot_id} — Trang PDF {r.pdf_page}."
            in result.rendered_text
            for r in result.references
        )
        checks["json_round_trip"] = result == RenderedCitationOutput.model_validate_json(
            result.model_dump_json()
        )
        checks["determinism"] = result == method(source)
        checks["local_validation"] = validate_rendered_citations(result, source).valid
        for name, passed in checks.items():
            metrics[name + "_passed"] += passed
            metrics[name + "_total"] += 1
        rows.append(
            dict(
                id=case["id"],
                category=case["category"],
                checks=checks,
                references=len(result.references),
                bindings=len(result.citation_bindings),
            )
        )
        sources[case["id"]], results[case["id"]] = source, result
        write_new(output / "rendered" / (case["id"] + ".json"), result.model_dump(mode="json"))
    control_rows = []
    for control in oracle["controls"]:
        key = "qa-multi-2025" if control["mode"] == "qa" else "report-sample-annual-general-2025"
        candidate = results[key].model_copy(deep=True)
        mutate(candidate, control)
        validation = validate_rendered_citations(candidate, sources[key])
        control_rows.append(
            dict(id=control["id"], rejected=not validation.valid, errors=validation.errors)
        )
    for name, key in [
        ("qa-multi-2025", "qa-multi-2025"),
        ("annual-general-2025", "report-sample-annual-general-2025"),
        ("partial-2025", "report-sample-missing-2025"),
    ]:
        result, source = results[key], sources[key]
        write_new(output / "samples" / (name + ".json"), result.model_dump(mode="json"))
        write_new(
            output / "samples" / (name + "-locators.json"),
            [r.source_locator.model_dump(mode="json") for r in result.references],
        )
        write_new(
            output / "samples" / (name + "-validation.json"),
            validate_rendered_citations(result, source).model_dump(mode="json"),
        )
        with (output / "samples" / (name + ".md")).open("x", encoding="utf-8") as stream:
            stream.write(result.rendered_text + "\n")
    baseline_path = root / "artifacts/evidence/M7-04-preflight/hashes-before.json"
    baseline = read(baseline_path)
    changed = [
        p
        for p, digest in baseline.items()
        if not (root / p).is_file() or file_hash(root / p) != digest
    ]
    passed = (
        all(all(row["checks"].values()) for row in rows)
        and all(row["rejected"] for row in control_rows)
        and not changed
    )
    summary = dict(
        passed=passed,
        cases=len(rows),
        real_qa=sum(
            c["mode"] == "qa" and c["category"] == "saved_BBS" for c in oracle["scenarios"]
        ),
        real_reports=sum(
            c["mode"] == "report" and c["category"] == "saved_BBS" for c in oracle["scenarios"]
        ),
        adversarial_rejected=sum(r["rejected"] for r in control_rows),
        adversarial_total=len(control_rows),
        metrics=dict(metrics),
        rows=rows,
        controls=control_rows,
        oracle_sha256=file_hash(oracle_path),
        protected_hashes=len(baseline),
        protected_changed=changed,
        independent_pdf_accuracy="not_evaluated",
        calls=0,
    )
    write_new(output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rows", "controls")}, indent=2))
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-oracle", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M7-04-final"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    oracle = root / "evaluation/m7-04-scenarios.json"
    if args.freeze_oracle:
        freeze(root, oracle)
    else:
        raise SystemExit(0 if evaluate(root, args.output.resolve(), oracle) else 1)
