"""Offline M7-05 oracle freezing and saved BBS replay, with exclusive outputs.

Freeze reads accepted oracles/artifacts only, without importing the firewall.
Runtime loads the pinned M6 repository once; warm cases use its AND-filter view.
"""

import argparse
import json
import re
import statistics
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from evaluate_m7_04_citations import checksum, expectations, file_hash, oracle_hash, read, write_new

ORACLE_SHA256 = "b382e4232a94f9f695cdf83f142f6c3cc82815eab1d28e12e26656d73ae2063e"
LEDGER_PATH = "artifacts/evidence/M6-06-ledger-final-v2/ledger"

# Known mutations are labels, not firewall-derived predictions. Each attacks an
# accepted production output; synthetic ledger controls are reported separately.
ATTACKS = [
    ("qa", "fake_verified_id", "F03"),
    ("qa", "pending_candidate_id", "F03"),
    ("qa", "accepted_changed_content", "F08"),
    ("qa", "wrong_document", "F02"),
    ("qa", "wrong_snapshot", "F02"),
    ("qa", "wrong_period", "F02"),
    ("qa", "false_scope", "F02"),
    ("qa", "removed_caveat", "F08"),
    ("qa", "removed_citation", "F08"),
    ("qa", "unsupported_cause", "F08"),
    ("qa", "unsupported_recommendation", "F08"),
    ("qa", "invented_ratio", "F08"),
    ("qa", "numeric_mutation", "F08"),
    ("qa", "unit_mutation", "F08"),
    ("qa", "modified_answer", "F08"),
    ("qa", "forged_validation", "F08"),
    ("qa", "changed_original_question", "F02"),
    ("qa", "joint_requirement_forgery", "F02"),
    ("qa", "empty_answered", "F08"),
    ("qa", "wrong_requirements", "F02"),
    ("report", "closing_date", "F02"),
    ("report", "mixed_recovery", "F02"),
    ("report", "removed_paragraph", "F08"),
    ("report", "reordered_paragraph", "F08"),
    ("report", "changed_paragraph", "F08"),
    ("report", "forged_status", "F08"),
    ("report", "mismatched_report_request", "F02"),
    ("report", "invalid_equivalent_merge", "F02"),
    ("report", "missing_section", "F08"),
    ("report", "fabricated_page", "F09"),
    ("report", "fabricated_cell", "F09"),
    ("report", "wrong_anchor", "F09"),
    ("report", "source_pointer", "F09"),
    ("report", "forged_render_status", "F09"),
    ("report", "wrong_paragraph_binding", "F09"),
    ("report", "rendered_text", "F09"),
    ("report", "wrong_marker", "F09"),
    ("report", "provenance_upgrade", "F09"),
    ("report", "lost_rendered_caveats", "F09"),
    ("report", "missing_reference", "F09"),
]


def freeze(root, oracle_path):
    cases, pins = [], {}
    for mode, predecessor, folder, group in (
        ("qa", "m7-01", "M7-01-offline-v2", "saved_BBS_QA"),
        ("report", "m7-03", "M7-03-report-final/offline", "saved_source"),
    ):
        prior_path = root / f"evaluation/{predecessor}-scenarios.json"
        prior = read(prior_path)
        pins[prior_path.relative_to(root).as_posix()] = oracle_hash(prior_path)
        selected = [c for c in prior["scenarios"] if c["group"] == group]
        # Include legitimate refusals/clarifications, separately from real cases.
        names = (
            [
                "control-no-claim",
                "control-missing-snapshot",
                "control-cross-document",
                "control-empty-ledger",
            ]
            if mode == "qa"
            else ["missing-snapshot", "wrong-document", "multi-year", "empty-ledger"]
        )
        selected += [c for c in prior["scenarios"] if c["id"] in names]
        for item in selected:
            relative = f"artifacts/evidence/{folder}/response-{item['id']}.json"
            source = read(root / relative)
            assert source["validation_result"]["valid"], item["id"]
            expected_status = item.get("expected_report_status", item["expected_status"])
            assert source["status"] == expected_status
            authority_ids = (
                sorted({k for r in item["requirements"] for k in r["required_verified_claim_ids"]})
                if mode == "qa"
                else sorted(item["required_verified_claim_ids"])
            )
            assert sorted(source["used_verified_claim_ids"]) == authority_ids
            citation = expectations(source, mode)
            warnings = []
            if source["caveats"]:
                warnings.append("required_caveats_disclosed")
            if source["status"] == "partial":
                warnings.append("partial_coverage_disclosed")
            contexts = (
                [s["context"] for s in source["grounded_segments"]]
                if mode == "qa"
                else [
                    c["claim_context"]
                    for s in source["sections"]
                    for p in s["paragraphs"]
                    for c in p["context"]
                ]
            )
            if any(c["reporting_scope"] is None for c in contexts):
                warnings.append("reporting_scope_unknown")
            if any(r["provenance"] == "page" for r in citation["references"]):
                warnings.append("page_level_location")
            # Location uncertainty is frozen directly from accepted citations.
            if any(
                c["source"]["reference"] is None
                or c["source"]["reference"]["anchor"]["status"] != "resolved"
                or not c["anchor_id"]
                or not c["source"]["reference"]["anchor"]["page"]["image"].strip()
                for c in source["citations"]
            ):
                warnings.append("source_location_unresolved")
            decision = (
                "CLARIFICATION_REQUIRED"
                if expected_status == "clarification_required"
                else "ALLOW_WITH_CAVEAT"
                if warnings
                else "ALLOW"
            )
            cases.append(
                dict(
                    id=mode + "-" + item["id"],
                    mode=mode,
                    source_id=item["id"],
                    category="saved_BBS" if source["citations"] else "saved_refusal",
                    path=relative,
                    sha256=file_hash(root / relative),
                    request=item["request"],
                    empty_ledger=bool(item.get("empty_ledger")),
                    expected=dict(
                        decision=decision,
                        status=expected_status,
                        claims=authority_ids,
                        citations=[r["id"] for r in citation["references"]],
                        context=contexts,
                        warnings=warnings,
                        blockers=[],
                        release=expected_status != "clarification_required",
                        citation_inventory=citation,
                    ),
                )
            )
    attacks = [
        dict(
            id=f"attack-{mode}-{name}",
            mode=mode,
            mutation=name,
            base="qa-revenue-2025" if mode == "qa" else "report-annual-general-2025",
            expected=dict(
                decision="BLOCK", release=False, claims=[], citations=[], blocker_check=check
            ),
        )
        for mode, name, check in ATTACKS
    ]
    ledger = root / LEDGER_PATH / "verified-claims.json"
    assert file_hash(ledger) == prior["ledger_sha256"]
    write_new(
        oracle_path,
        dict(
            version="m7_05_firewall_oracle_v1",
            pins=pins,
            ledger_sha256=file_hash(ledger),
            scenarios=cases,
            controls=attacks,
            label_authority="accepted M6/M7 oracles and known mutations; never firewall decisions",
        ),
    )
    print(
        "Frozen:",
        dict(Counter(c["category"] + "_" + c["mode"] for c in cases)),
        len(attacks),
        "attacks",
    )


def mutate(request, source, rendered, name):
    """Mutate detached inputs; never touch accepted artifacts or ledger records."""
    from vietnamese_financial_multi_agent.outputs import CitationRenderer
    from vietnamese_financial_multi_agent.outputs.citation_renderer import _report_text
    from vietnamese_financial_multi_agent.outputs.qa_composer import _answer_text

    request, source, rendered = (x.model_copy(deep=True) for x in (request, source, rendered))
    is_qa = hasattr(source, "grounded_segments")
    if is_qa:
        segment = source.grounded_segments[0]
        if name in ("fake_verified_id", "pending_candidate_id"):
            fake = "verified:unknown" if name == "fake_verified_id" else "candidate:pending-M5"
            old = segment.verified_claim_ids[0]
            source = type(source).model_validate_json(source.model_dump_json().replace(old, fake))
        elif name in ("wrong_document", "wrong_snapshot", "wrong_period", "false_scope"):
            field, value = {
                "wrong_document": ("document_id", "other"),
                "wrong_snapshot": ("snapshot_id", "recovery-other"),
                "wrong_period": ("period", "1900"),
                "false_scope": ("reporting_scope", "consolidated"),
            }[name]
            setattr(request, field, value)
        elif name in ("changed_original_question", "joint_requirement_forgery"):
            request.question = "Tổng tài sản năm 2025?"
            if name == "joint_requirement_forgery":
                source.question = request.question
        elif name == "removed_caveat":
            segment.caveats = []
            source.caveats = []
        elif name == "removed_citation":
            segment.citations = []
            source.citations = []
        elif name == "empty_answered":
            source.grounded_segments = []
            source.used_verified_claim_ids = []
            source.citations = []
        elif name == "wrong_requirements":
            source.plan.requirements[0].target_id = "b01.total_assets"
            source.answered_requirements[0].target_id = "b01.total_assets"
        elif name == "modified_answer":
            source.answer_vi += " Doanh nghiệp có sức khỏe tài chính rất tốt."
        elif name == "numeric_mutation":
            tokens = list(re.finditer(r"\d[\d.,]*", segment.content))
            assert tokens, "numeric_control_requires_existing_financial_value"
            token = tokens[-1]
            segment.content = (
                segment.content[: token.start()] + "999999" + segment.content[token.end() :]
            )
        elif name == "unit_mutation":
            assert "VND" in segment.content, "unit_control_requires_existing_unit"
            segment.content = segment.content.replace("VND", "USD")
        else:
            segment.content += {
                "accepted_changed_content": " Tài chính rất tốt.",
                "unsupported_cause": " Doanh thu tăng do quản trị hiệu quả.",
                "unsupported_recommendation": " Nên đầu tư vào doanh nghiệp.",
                "invented_ratio": " ROE đạt 99%.",
                "forged_validation": " Doanh nghiệp có tài chính an toàn.",
            }[name]
        if name != "modified_answer":
            source.answer_vi = _answer_text(source)
    else:
        section = next(s for s in source.sections if any(p.source_slot_ids for p in s.paragraphs))
        paragraph = next(p for p in section.paragraphs if p.source_slot_ids)
        if name == "closing_date":
            request.outline_request.period_context.period_end = "2025-12-30"
        elif name == "mixed_recovery":
            request.outline_request.snapshot_id = "recovery2022"
        elif name == "mismatched_report_request":
            request.outline_request.report_type = "profitability"
        elif name == "invalid_equivalent_merge":
            slots = [s for section in request.outline.sections for s in section.claim_slots]
            slots[0].verified_claim_ids += slots[-1].verified_claim_ids
        elif name == "removed_paragraph":
            section.paragraphs.remove(paragraph)
        elif name == "reordered_paragraph":
            section.paragraphs.reverse()
        elif name == "changed_paragraph":
            paragraph.text_vi += " Doanh nghiệp đang có sức khỏe tài chính rất tốt."
        elif name == "forged_status":
            source.status = "abstained"
        elif name == "missing_section":
            source.sections.remove(section)
        elif name == "fabricated_page":
            rendered.references[0].pdf_page = 999
        elif name == "fabricated_cell":
            rendered.references[0].source_locator.cell_id = "invented-cell"
        elif name == "wrong_anchor":
            rendered.references[0].anchor_id = "invented-anchor"
        elif name == "source_pointer":
            rendered.references[0].source_locator.source_pointer = "/fake"
        elif name == "forged_render_status":
            rendered.status = (
                "rendered" if rendered.status == "location_limited" else "location_limited"
            )
        elif name == "wrong_paragraph_binding":
            rendered.citation_bindings[0].output_segment_id = "scope-0"
        elif name in ("rendered_text", "wrong_marker"):
            rendered.rendered_text += " [999]" if name == "wrong_marker" else " Tài chính rất tốt."
        elif name == "provenance_upgrade":
            rendered.references[0].provenance_level = "cell"
        elif name == "lost_rendered_caveats":
            rendered.caveats = []
        elif name == "missing_reference":
            rendered.references.pop(0)
        else:
            raise ValueError("unknown_mutation")
        if source.sections:
            source.body_vi = _report_text(source, {})
    source.validation_result.valid = True
    source.validation_result.errors = []
    rendered.validation_result.valid = True
    # Co-tamper source+display when M7-04 permits it. This tests the independent
    # ledger/request gates, not merely a stale rendering fingerprint.
    if (is_qa and name != "modified_answer") or name in (
        "changed_paragraph",
        "reordered_paragraph",
        "removed_paragraph",
        "missing_section",
    ):
        try:
            rendered = getattr(CitationRenderer(), "render_qa" if is_qa else "render_report")(
                source
            )
        except ValueError:
            pass
    return request, source, rendered


def evaluate(root, output, oracle_path):
    from evaluate_m7_01_qa import SavedVerifiedView
    from vietnamese_financial_multi_agent.outputs import (
        CitationRenderer,
        GroundedFinancialReport,
        GroundedReportRequest,
        InformationFirewall,
        ReportOutlinePlanner,
        ReportOutlineRequest,
        VietnameseQARequest,
        VietnameseQAResponse,
    )
    from vietnamese_financial_multi_agent.verification import (
        VerifiedClaimLedger,
        VerifiedClaimQuery,
        VerifiedClaimRepository,
    )

    assert oracle_hash(oracle_path) == ORACLE_SHA256, "firewall_oracle_pin_mismatch"
    oracle = read(oracle_path)
    for path, pin in oracle["pins"].items():
        assert oracle_hash(root / path) == pin, "accepted_oracle_changed"
    assert file_hash(root / LEDGER_PATH / "verified-claims.json") == oracle["ledger_sha256"]
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "expected-oracle.json", oracle)
    print("Cold M6 proof-validated load (read only)", flush=True)
    start = perf_counter()
    entries = (
        VerifiedClaimLedger(VerifiedClaimRepository(root / LEDGER_PATH))
        .find_claims(VerifiedClaimQuery())
        .claims
    )
    cold_ms = (perf_counter() - start) * 1000
    ledger = VerifiedClaimLedger(SavedVerifiedView(entries))
    empty = VerifiedClaimLedger(SavedVerifiedView([]))
    rows, saved, calls = [], {}, Counter()

    def forbid(*args, **kwargs):
        calls["unauthorized_calls"] += 1
        raise AssertionError("forbidden_runtime_call")

    def run(case, request, source, rendered, active_ledger):
        before = [x.model_dump_json() for x in (request, source, rendered)]
        firewall = InformationFirewall(active_ledger)
        start = perf_counter()
        decision = (
            firewall.evaluate_qa(request=request, response=source, rendered=rendered)
            if case["mode"] == "qa"
            else firewall.evaluate_report(request=request, report=source, rendered=rendered)
        )
        elapsed = (perf_counter() - start) * 1000
        expected = case["expected"]
        checks = dict(
            decision=decision.decision == expected["decision"],
            release=(decision.release_status == "released") == expected["release"],
            claims=sorted(decision.validated_verified_claim_ids)
            == sorted(expected["claims"] if expected["release"] else []),
            citations=decision.validated_citation_ids
            == (expected["citations"] if expected["release"] else []),
            input_immutability=before == [x.model_dump_json() for x in (request, source, rendered)],
            query_bound=decision.ledger_queries <= (2 if case["mode"] == "report" else 1),
        )
        if "blocker_check" in expected:
            checks["root_cause"] = any(
                c.check_id == expected["blocker_check"] and c.status == "fail"
                for c in decision.checks
            )
            checks["safe_refusal"] = (
                decision.validated_output.rendered_text is None
                and not decision.validated_output.references
                and not decision.validated_output.verified_claim_ids
            )
        else:
            checks["status"] = decision.original_status == expected["status"]
            checks["warnings"] = decision.warnings == expected["warnings"]
            checks["no_blockers"] = not decision.blockers
            checks["contexts"] = (
                [s.context.model_dump(mode="json") for s in source.grounded_segments]
                if case["mode"] == "qa"
                else [
                    c.claim_context.model_dump(mode="json")
                    for s in source.sections
                    for p in s.paragraphs
                    for c in p.context
                ]
            ) == expected["context"]
            if expected["release"]:
                view = decision.validated_output
                citation = expected["citation_inventory"]
                checks["caveat_retention"] = (
                    checksum(view.caveats) == citation["caveats_sha256"]
                    and checksum(view.limitations) == citation["limitations_sha256"]
                )
                checks["locator_integrity"] = [
                    checksum(r.source_locator.model_dump(mode="json")) for r in view.references
                ] == [r["locator_sha256"] for r in citation["references"]]
                checks["exact_rendered_view"] = view.rendered_text == rendered.rendered_text
        row = dict(
            id=case["id"],
            category=case.get("category", "adversarial_saved_BBS"),
            mode=case["mode"],
            expected=expected["decision"],
            actual=decision.decision,
            passed=all(checks.values()),
            checks=checks,
            latency_ms=elapsed,
            ledger_queries=decision.ledger_queries,
            checks_count=len(decision.checks),
            reasons_count=sum(len(c.reasons) for c in decision.checks),
            result_bytes=len(decision.model_dump_json().encode()),
            blockers=decision.blockers,
        )
        rows.append(row)
        write_new(output / "decisions" / f"{case['id']}.json", decision.model_dump(mode="json"))
        print(case["id"], decision.decision, "PASS" if row["passed"] else "FAIL", flush=True)
        return decision

    with ExitStack() as guards:
        for target in (
            "core.llm_gateway.SharedLLMGateway.generate",
            "tools.financial_calculator.FinancialCalculator.calculate_financial_metric",
            "tools.financial_retrieval.FinancialRetrievalTools.find_financial_facts",
            "agents.orchestrator.FinancialMultiAgentOrchestrator.run",
        ):
            guards.enter_context(patch("vietnamese_financial_multi_agent." + target, forbid))
        for case in oracle["scenarios"]:
            assert file_hash(root / case["path"]) == case["sha256"], "saved_source_changed"
            active = empty if case["empty_ledger"] else ledger
            if case["mode"] == "qa":
                request = VietnameseQARequest.model_validate(case["request"])
                source = VietnameseQAResponse.model_validate_json(
                    (root / case["path"]).read_bytes()
                )
                rendered = CitationRenderer().render_qa(source)
            else:
                original = ReportOutlineRequest.model_validate(case["request"])
                request = GroundedReportRequest(
                    outline=ReportOutlinePlanner(active).plan(original), outline_request=original
                )
                source = GroundedFinancialReport.model_validate_json(
                    (root / case["path"]).read_bytes()
                )
                rendered = CitationRenderer().render_report(source)
            # Freeze all upstream generation before entering the firewall.
            with (
                patch(
                    "vietnamese_financial_multi_agent.outputs.qa_composer.VietnameseQAComposer.compose",
                    forbid,
                ),
                patch(
                    "vietnamese_financial_multi_agent.outputs.grounded_report_writer.GroundedReportWriter.write",
                    forbid,
                ),
                patch(
                    "vietnamese_financial_multi_agent.outputs.report_outline_planner.ReportOutlinePlanner.plan",
                    forbid,
                ),
            ):
                decision = run(case, request, source, rendered, active)
            saved[case["id"]] = (request, source, rendered)
            if case["id"] in ("qa-revenue-2025", "report-annual-general-2025"):
                write_new(
                    output / "samples" / (case["id"] + ".json"),
                    dict(
                        original_identity=case["id"],
                        source_sha256=case["sha256"],
                        evidence_mapping=case["expected"]["citation_inventory"],
                        decision=decision.model_dump(mode="json"),
                    ),
                )
        for case in oracle["controls"]:
            request, source, rendered = mutate(*saved[case["base"]], case["mutation"])
            decision = run(case, request, source, rendered, ledger)
            if case["mutation"] == "numeric_mutation":
                write_new(
                    output / "samples/blocked-financial-mutation.json",
                    dict(
                        original_identity=case["base"],
                        mutation=case["mutation"],
                        evidence_mapping=next(
                            c["expected"]["citation_inventory"]
                            for c in oracle["scenarios"]
                            if c["id"] == case["base"]
                        ),
                        decision=decision.model_dump(mode="json"),
                    ),
                )
    baseline = read(root / "artifacts/evidence/M7-05-preflight/hashes-before.json")
    changed = [
        p for p, pin in baseline.items() if not (root / p).is_file() or file_hash(root / p) != pin
    ]
    matrix = Counter((r["expected"], r["actual"]) for r in rows)
    summary = dict(
        passed=all(r["passed"] for r in rows) and not changed and not calls,
        cases=len(rows),
        passed_cases=sum(r["passed"] for r in rows),
        real_cases=dict(Counter(r["mode"] for r in rows if r["category"] == "saved_BBS")),
        refusal_cases=sum(r["category"] == "saved_refusal" for r in rows),
        adversarial_controls=len(oracle["controls"]),
        unique_documents=len({e.identity.document_id for e in entries}),
        unique_document_snapshots=len(
            {(e.identity.document_id, e.identity.snapshot_id) for e in entries}
        ),
        verified_ledger_entries=len(entries),
        confusion_matrix=[
            dict(expected=a, actual=b, count=n) for (a, b), n in sorted(matrix.items())
        ],
        false_acceptance=sum(
            r["expected"] == "BLOCK" and r["actual"] in ("ALLOW", "ALLOW_WITH_CAVEAT") for r in rows
        ),
        false_rejection=sum(
            r["expected"] in ("ALLOW", "ALLOW_WITH_CAVEAT")
            and r["actual"] not in ("ALLOW", "ALLOW_WITH_CAVEAT")
            for r in rows
        ),
        safety_checks={
            k: sum(not r["checks"].get(k, True) for r in rows)
            for k in (
                "claims",
                "citations",
                "contexts",
                "locator_integrity",
                "caveat_retention",
                "safe_refusal",
            )
        },
        cold_ledger_load_ms=cold_ms,
        warm_latency_ms={
            mode: dict(
                median=statistics.median(r["latency_ms"] for r in rows if r["mode"] == mode),
                maximum=max(r["latency_ms"] for r in rows if r["mode"] == mode),
            )
            for mode in ("qa", "report")
        },
        ledger_queries=sum(r["ledger_queries"] for r in rows),
        calls=dict(calls),
        llm_ocr_extraction_calculator_calls=0,
        protected_hashes=len(baseline),
        protected_changed=changed,
        oracle_sha256=oracle_hash(oracle_path),
        rows=rows,
        limitations=[
            "source-bound oracle agreement, not independent PDF financial accuracy",
            "resource mapping not supplied; no PDF opening proof",
            "free financial paraphrase not approved",
        ],
    )
    write_new(output / "summary.json", summary)
    print(
        json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False, indent=2)
    )
    return summary["passed"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    oracle = root / "evaluation/m7-05-scenarios.json"
    if args.freeze:
        freeze(root, oracle)
        return 0
    if args.output is None:
        parser.error("--output required")
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence"):
        parser.error("output must be a new directory under artifacts/evidence")
    return 0 if evaluate(root, output, oracle) else 1


if __name__ == "__main__":
    raise SystemExit(main())
