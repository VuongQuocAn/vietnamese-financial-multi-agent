"""D-03: read-only real-artifact diagnostics; no Gateway, extraction or API startup.

Run from repository root. Writes only to a NEW ignored output directory. Baseline
981 facts and effective D-02 recovery are reported separately, never merged as
duplicate snapshots. Detailed financial rows stay in ignored artifacts.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from threading import RLock

import httpx
import pypdfium2 as pdfium
from evaluate_d01_coverage import ROLES, compare_observations
from vietnamese_financial_multi_agent.accounting.item_mapping import ITEM_CATALOG, _text
from vietnamese_financial_multi_agent.accounting.relationships import (
    evaluate_automated_relationships,
)
from vietnamese_financial_multi_agent.api.document_store import DocumentStore
from vietnamese_financial_multi_agent.api.main import create_app
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    EvidenceQuery,
    EvidenceRetrieval,
    FinancialOperand,
    evidence_from_persisted_result,
    facts_from_persisted_result,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
    assess_analytical_readiness,
    source_review_status,
)
from vietnamese_financial_multi_agent.evidence.contracts import assess_fact_consistency
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def pointer(payload, selector):
    value = payload
    for key in selector.strip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def manifest(root, output):
    # Reuse accepted evidence scope; do not hash unrelated local research datasets.
    paths = [root / p for p in load(root / "artifacts/evidence/D-02-final/hashes-before.json")]
    paths.extend([root / "web/next-env.d.ts", root / "configs/d02-analytical-policies.json"])
    for directory in ("artifacts/evidence/D-02-final", "artifacts/web-demo-v1"):
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file())
    return {
        p.relative_to(root).as_posix(): digest(p)
        for p in sorted(set(paths))
        if not p.is_relative_to(output)
    }


def classify(fact):
    """Diagnostic hypotheses only; source code alone never authorizes a mapping."""
    label, code = fact.context.raw_item_label or "", fact.source_item_code
    statement = fact.context.statement_type
    matching = [
        r for r in ITEM_CATALOG if r.statement_type == statement and r.observed_source_code == code
    ]
    known_label = [
        r
        for r in ITEM_CATALOG
        if r.statement_type == statement and _text(label) in map(_text, r.aliases)
    ]
    if not code:
        kind = "structural_section_or_signature"
    elif not re.fullmatch(r"\d{2,3}[a-z]?", code.strip()):
        kind = "uncoded_review_required"
    elif fact.context.period is None:
        kind = "descriptive_header_slot"
    else:
        kind = "financial_item"
    rule = (
        "not_a_mapping_target"
        if kind != "financial_item"
        else "ambiguous_label_code"
        if len(known_label) > 1
        else "rule_mismatch"
        if known_label
        else "alias_candidate"
        if matching
        else "missing_rule_new_id_candidate"
    )
    # An ordinal source code may identify both a detailed line and a subtotal.
    subtotal = (
        (
            statement == "B01"
            and code
            in {
                "100",
                "110",
                "120",
                "130",
                "140",
                "150",
                "200",
                "210",
                "220",
                "230",
                "240",
                "250",
                "260",
                "270",
                "300",
                "310",
                "330",
                "400",
                "410",
                "430",
                "440",
            }
        )
        or (statement == "B02" and code in {"10", "20", "30", "40", "50", "60"})
        or (statement == "B03" and code in {"20", "30", "40", "50", "60", "70"})
    )
    return dict(
        kind=kind,
        rule_diagnosis=rule,
        item_level="subtotal_candidate" if subtotal else "detail_or_section_review_required",
        candidate_ids=[r.canonical_item_id for r in matching],
    )


def fact_diagnostics(year, fact, records, reviews):
    page = fact.sources[0].reference.anchor.page.page if fact.sources else None
    record = records[page] if page in records else None
    problems = []
    if record:
        payload = record["response"]["output"]["payload"]
        for source in fact.sources:
            try:
                pointer(payload, source.reference.source_pointer)
            except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                problems.append("selector_unresolved")
        index = int(fact.local_observation_id.rsplit("/", 1)[1])
        link = record["extraction"]["links"][index]
        table = payload["tables"][link["table"]]
        cells = [
            c for c in table["cells"] if (c["row"], c["column"]) == (link["row"], link["column"])
        ]
        if len(cells) != 1:
            problems.append("value_position_missing_or_ambiguous")
        elif (cells[0]["text"] or "") != fact.value.raw_value:
            problems.append("raw_value_binding_mismatch")
    else:
        problems.append("record_missing")
    issues = sorted({i.code for q in fact.quality_context for i in q.issues})
    consistency = assess_fact_consistency(fact)
    return dict(
        filing=year,
        statement=fact.context.statement_type,
        page=page,
        observation=fact.observation_identity().model_dump(mode="json"),
        source_code=fact.source_item_code,
        raw_label=fact.context.raw_item_label,
        period=fact.context.period,
        header=fact.raw_header,
        numeric=fact.value.normalized_value is not None,
        raw_value=fact.value.raw_value,
        canonical_id=fact.canonical_item_id,
        quality=[q.decision for q in fact.quality_context],
        quality_reasons=issues,
        quality_details=[i.model_dump() for q in fact.quality_context for i in q.issues],
        context_reasons=[i.code for i in fact.resolution_issues],
        consistency=consistency.status,
        consistency_reasons=[i.code for i in consistency.issues],
        binding_problems=problems,
        source_review=source_review_status(fact, reviews),
        **classify(fact),
    )


async def web_diagnostics(root, web_root, inventory):
    """GET routes against a read-only store object, without lifespan/workers/locks."""
    store = object.__new__(DocumentStore)
    store.root, store.lock = web_root, RLock()
    app = create_app(storage_root=web_root, service=object())
    app.state.store = store
    documents = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        listing = await client.get("/api/documents")
        for path in sorted((web_root / "documents").glob("*/document.json")):
            doc = load(path)
            attempt = (doc.get("latest_result") or {}).get("attempt_id")
            row = dict(
                document_id=doc["id"], content_id=doc.get("content_id"), latest_attempt=attempt
            )
            if attempt:
                response = await client.get(
                    f"/api/documents/{doc['id']}/evidence",
                    params=dict(attempt_id=attempt, limit=500),
                )
                body = response.json()
                row.update(
                    http_status=response.status_code,
                    items=body.get("total"),
                    statements=dict(
                        Counter(i["context"]["statement_type"] for i in body.get("items", []))
                    ),
                    periods=dict(Counter(i["context"]["period"] for i in body.get("items", []))),
                )
                for i in body.get("items", []):
                    assert i["sources"] and all(
                        s["pdf_page"] > 0 and s["source_pointer"] for s in i["sources"]
                    )
                original = path.parent / "original.pdf"
                row["original_sha256"] = digest(original) if original.exists() else None
                row["filing_matches"] = [
                    r["year"] for r in inventory if r["sha256"] == row["original_sha256"]
                ]
                foreign = await client.get(
                    f"/api/documents/{doc['id']}/evidence",
                    params=dict(attempt_id="D-01/normalized-v2"),
                )
                row["d01_snapshot_request"] = dict(status=foreign.status_code, body=foreign.json())
            documents.append(row)
    return dict(
        storage=web_root.relative_to(root).as_posix(),
        environment_override=bool(os.environ.get("WEB_STORAGE_ROOT")),
        list_http_status=listing.status_code,
        documents=documents,
        api_routes=sorted({r.path for r in app.routes}),
        method="ASGI GET only; lifespan not entered; no browser run",
    )


def qa_diagnostics(api, scopes, metrics, readiness, validation, closure):
    # Structured inputs fixed in source, independent of available values.
    cases = [
        ("Doanh thu thuần 2023?", 2023, "b02.net_revenue", "2023"),
        ("Tổng tài sản cuối 2024?", 2024, "b01.total_assets", "2024-12-31"),
        ("Lợi nhuận sau thuế 2025?", 2025, "b02.profit_after_tax", "2025"),
        ("Dòng tiền kinh doanh 2022?", 2022, "b03.operating_cash_flow", "2022"),
        ("Vốn chủ sở hữu cuối 2021?", 2021, "b01.total_equity", "2021-12-31"),
        ("Giá vốn 2024?", 2024, "b02.cost_of_sales", "2024"),
        ("Tiền cuối kỳ 2025?", 2025, "b03.closing_cash", "2025"),
        ("Dòng tiền đầu tư 2023?", 2023, "b03.investing_cash_flow", "2023"),
        ("Nợ ngắn hạn cuối 2024?", 2024, "b01.short_term_liabilities", "2024-12-31"),
        ("Doanh thu 2024 không chọn filing?", None, "b02.net_revenue", "2024"),
        ("Tổng tài sản báo cáo 2023 không chọn kỳ?", 2023, "b01.total_assets", None),
    ]
    rows = []
    for question, year, item, period in cases:
        query = EvidenceQuery(
            **(scopes[year] if year else {}), canonical_item_id=item, period=period
        )
        result = api.find_facts(query)
        rows.append(
            dict(
                question=question,
                operation="direct_retrieval",
                query=query.model_dump(mode="json"),
                result=result.model_dump(mode="json"),
                operands_complete=len(result.matches) == 1,
                period_unit_ok=bool(result.matches)
                and all(
                    m.record.context.period is not None
                    and m.record.context.currency == "VND"
                    and m.record.value.unit == "VND"
                    and m.record.context.scale == 1
                    for m in result.matches
                ),
                citations_sufficient_for_page_display=bool(result.matches)
                and all(
                    m.citations
                    and all(
                        c.pdf_page and c.source.snapshot_id == m.record.snapshot_id
                        for c in m.citations
                    )
                    for m in result.matches
                ),
                calculation="not_requested",
                outcome="ANSWER_DATA_WITH_CAVEAT"
                if result.status == "found"
                and result.matches[0].display_status == "display_with_caveat"
                else "BLOCKED_SELECTION"
                if result.status == "ambiguous"
                else "BLOCKED_MAPPING",
            )
        )
    for year, name, question in [
        (2023, "revenue_yoy", "Doanh thu thay đổi 2022–2023 theo cùng filing 2023?"),
        (2024, "gross_margin", "Tỷ suất lợi nhuận gộp 2024?"),
        (2025, "debt_to_assets", "Nợ phải trả trên tài sản 2025?"),
    ]:
        metric = next(
            m
            for m in metrics
            if m.request.document_id == scopes[year]["document_id"] and m.definition.name == name
        )
        refs = [api.get_fact(o.observation) for o in metric.operands]
        rows.append(
            dict(
                question=question,
                operation="derived_metric",
                metric_id=metric.metric_id,
                retrieval=[r.model_dump(mode="json") for r in refs],
                readiness=readiness[metric.metric_id],
                outcome="BLOCKED_EXECUTION",
            )
        )
    for year in (2023,):
        refs = [
            api.find_facts(
                EvidenceQuery(**scopes[year], canonical_item_id=item, period=f"{year}-12-31")
            )
            for item in (
                "b01.total_assets",
                "b01.total_liabilities",
                "b01.total_equity",
                "b01.total_funding",
            )
        ]
        rows.append(
            dict(
                question=f"Báo cáo {year} cân đối tài sản/nguồn vốn?",
                operation="balance_validation",
                retrieval=[r.model_dump(mode="json") for r in refs],
                outcome="BLOCKED_VALIDATION_RULE_AND_MAPPING",
                validation=[
                    v
                    for v in validation
                    if v["filing"] == year and v["rule_id"] == "b01.balance_identity"
                ],
            )
        )
    rows.append(
        dict(
            question="Những chỉ tiêu 2021–2025 nào bất thường?",
            operation="anomaly_detection",
            facts_retrieved=len(api.find_facts(EvidenceQuery()).matches),
            outcome="BLOCKED_RULE_NOT_IMPLEMENTED",
            blocker="No source-backed anomaly rule/threshold/baseline selected; raw inventory is retrievable",
        )
    )
    rows.append(
        dict(
            question="Doanh thu 2023 trong hai filing 2023/2024 có so sánh được?",
            operation="cross_document",
            retrieval=[
                api.find_facts(
                    EvidenceQuery(**scopes[y], canonical_item_id="b02.net_revenue", period="2023")
                ).model_dump(mode="json")
                for y in (2023, 2024)
            ],
            outcome="BLOCKED_COMPARABILITY",
        )
    )
    selected_closure = next(c for c in closure if c["name"] == "gross_margin")
    rows.append(
        dict(
            question="Tỷ suất lợi nhuận gộp 2022 sau khi chọn snapshot recovery?",
            operation="recovered_snapshot_metric",
            original_metric_id=selected_closure["metric_id"],
            retrieval=selected_closure["original_operand_retrieval"],
            readiness=selected_closure["recovered_readiness"],
            outcome="BLOCKED_SNAPSHOT_CLOSURE",
        )
    )
    for year in (2024, 2025):
        result = api.find_facts(EvidenceQuery(**scopes[year], statement_type="B02"))
        eps = [m for m in result.matches if m.record.source_item_code == "70"]
        rows.append(
            dict(
                question=f"EPS {year} và số so sánh có đủ nguồn và diễn giải restatement?",
                operation="raw_eps_coverage",
                query=dict(**scopes[year], statement_type="B02"),
                raw_matches=[m.model_dump(mode="json") for m in eps],
                outcome="BLOCKED_EXTRACTION_COMPLETENESS"
                if not eps
                else "BLOCKED_RESTATEMENT_INTERPRETATION",
            )
        )
    for i, row in enumerate(rows, 1):
        row["id"] = f"QA{i:02}"
        serialized = [row["result"]] if "result" in row else row.get("retrieval", [])
        matches = [m for r in serialized for m in r["matches"]] + row.get("raw_matches", [])
        row.setdefault("facts_retrieved", len(matches))
        row.setdefault(
            "period_unit_ok",
            bool(matches)
            and all(
                m["record"]["context"]["period"]
                and m["record"]["value"]["unit"] == "VND"
                and m["record"]["context"]["scale"] == "1"
                for m in matches
            ),
        )
        row.setdefault(
            "operands_complete", bool(matches) and all(r["status"] == "found" for r in serialized)
        )
        row["citations_available"] = bool(matches) and all(
            m["citations"]
            and all(
                c["pdf_page"] and c["snapshot_id"] == m["record"]["snapshot_id"]
                for c in m["citations"]
            )
            for m in matches
        )
        row["calculation_allowed"] = row.get("readiness", {}).get("calculation_eligible", False)
        row["source_limitations"] = sorted(
            {s for m in matches for c in m["citations"] for s in c["limitations"]}
        )
        row["blocker_codes"] = row.get("readiness", {}).get("eligibility_blockers", []) or [
            reason for r in serialized for reason in r["reasons"]
        ]
        if row["operation"] == "raw_eps_coverage":
            row["period_unit_ok"] = "UNREVIEWED_ITEM_UNIT"
            row["operands_complete"] = len(matches) == 2
    return rows


def run(root, output, web_root):
    if output.exists() or not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Use a NEW directory under artifacts/evidence")
    if not web_root.is_relative_to(root) or not (web_root / "documents").is_dir():
        raise ValueError("Existing web storage inside repository required")
    output.mkdir(parents=True)
    before = manifest(root, output)
    save(output / "hashes-before.json", before)
    baseline = root / "artifacts/evidence/D-01/evaluation"
    previous = root / "artifacts/evidence/D-02"
    final = root / "artifacts/evidence/D-02-final"
    registry = load(root / "configs/d02-analytical-policies.json")
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(previous / "source-reviews.json")
    ]
    bases = [AccountingBasisReview(**r) for r in load(previous / "accounting-basis-reviews.json")]
    for r in bases:
        assert digest(root / "artifacts/evidence" / r.review_reference) == r.review_image_sha256
    inventory = load(root / "artifacts/evidence/D-01/inventory.json")
    for r in reviews:
        year = next(row["year"] for row in inventory if row["sha256"] == r.pdf_sha256)
        assert digest(previous / f"{year}-{r.pdf_page}.png") == r.review_image_sha256
    for row in inventory:
        assert digest(root / row["pdf"]) == row["sha256"]
    facts, evidence, scopes, results, rows = [], [], {}, {}, []
    for year in range(2021, 2026):
        result = load(baseline / str(year) / "normalized-result.json")
        results[year] = result
        scope = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        scopes[year] = scope
        selected = CanonicalFactRepository(baseline / str(year) / "canonical").list_by_document(
            **scope
        )
        facts.extend(selected)
        evidence.extend(evidence_from_persisted_result(result))
        records = {r["source"]["page"]["page"]: r for r in result["records"]}
        rows.extend(fact_diagnostics(year, f, records, reviews) for f in selected)
    assert len(facts) == 981 and sum(f.canonical_item_id is None for f in facts) == 816
    save(output / "observations.json", rows)
    unmapped = [r for r in rows if r["canonical_id"] is None]
    groups = defaultdict(list)
    for row in unmapped:
        groups[
            (
                row["statement"],
                row["source_code"],
                row["raw_label"],
                row["period"],
                row["filing"],
                row["numeric"],
                row["kind"],
                row["rule_diagnosis"],
                row["item_level"],
            )
        ].append(row["observation"])
    save(
        output / "unmapped-groups.json",
        [
            dict(
                statement=k[0],
                source_code=k[1],
                raw_label=k[2],
                period=k[3],
                filing=k[4],
                numeric=k[5],
                kind=k[6],
                rule_diagnosis=k[7],
                item_level=k[8],
                observations=v,
            )
            for k, v in sorted(groups.items(), key=str)
        ],
    )
    reason_rows = []
    for year in range(2021, 2026):
        for statement in ("B01", "B02", "B03"):
            group = [r for r in rows if (r["filing"], r["statement"]) == (year, statement)]
            reason_rows.append(
                dict(
                    year=year,
                    statement=statement,
                    total=len(group),
                    quality=dict(Counter(q for r in group for q in r["quality"])),
                    reasons=dict(Counter(i for r in group for i in r["quality_reasons"])),
                    context=dict(Counter(i for r in group for i in r["context_reasons"])),
                )
            )
    save(output / "quality-by-year-statement.json", reason_rows)
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m)) for m in load(baseline / "metrics.json")
    ]
    index = {f.observation_identity(): f for f in facts}
    policies = {p["formula_id"]: PreparedFormulaPolicy(**p) for p in registry["formula_policies"]}
    approvals = [FormulaExecutionApproval(**a) for a in registry["formula_execution_approvals"]]
    readiness = {}
    for metric in metrics:
        readiness[metric.metric_id] = assess_analytical_readiness(
            metric.definition.compatibility,
            [FinancialOperand(role=o.role, fact=index[o.observation]) for o in metric.operands],
            reviews,
            bases,
            approval=PreparationApproval(**registry["preparation_approval"]),
            formula_policy=policies[metric.definition.name],
            formula_approvals=approvals,
        )
        stored = next(
            r for r in load(final / "metrics-readiness.json") if r["metric_id"] == metric.metric_id
        )
        assert all(stored[k] == v for k, v in readiness[metric.metric_id].items())
    save(output / "metrics.json", readiness)
    recovery = load(previous / "recovery-2022/normalized-result.json")
    recovered = facts_from_persisted_result(
        recovery, company_id=recovery["metadata_binding"]["company_id"]
    )
    for f in recovered:
        f.semantic_role = ROLES.get(f.canonical_item_id)
    effective = [f for f in facts if f.document_id != recovery["document_id"]] + recovered
    evidence = [
        e for e in evidence if e.document_id != recovery["document_id"]
    ] + evidence_from_persisted_result(recovery)
    scopes[2022]["snapshot_id"] = recovery["attempt_id"]
    pairs = compare_observations(effective)
    assert pairs == load(final / "cross-year.json")
    save(output / "cross-year.json", pairs)
    recovery_reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(previous / "recovery-source-reviews.json")
    ]
    effective_reviews = [*reviews, *recovery_reviews]
    effective_index = {f.observation_identity().model_dump_json(): f for f in effective}
    pair_review_counts = Counter(
        source_review_status(
            effective_index[json.dumps(o, separators=(",", ":"))], effective_reviews
        )
        for p in pairs
        for o in p["observations"]
    )
    effective_rows = [r for r in rows if r["filing"] != 2022] + [
        fact_diagnostics(
            2022,
            f,
            {r["source"]["page"]["page"]: r for r in recovery["records"]},
            effective_reviews,
        )
        for f in recovered
    ]
    save(output / "effective-observations.json", effective_rows)
    validation = []
    for year, result in results.items():
        for check in evaluate_automated_relationships(
            (recovery if year == 2022 else result)["records"]
        ):
            validation.append(dict(filing=year, **check.model_dump(mode="json")))
    save(output / "validation.json", validation)
    api = EvidenceRetrieval(
        effective,
        evidence,
        coverage=[
            CanonicalCoverage(
                **s,
                canonical_extraction="available",
                missing_canonical_items=["b01.short_term_liabilities", "b01.total_funding"],
                inventory_reference="D-01/inventory",
            )
            for s in scopes.values()
        ],
    )
    assert all(api.get_fact(f.observation_identity()).matches[0].record == f for f in effective)
    closure = []
    for metric in metrics:
        if metric.request.document_id != recovery["document_id"]:
            continue
        operands = []
        for requirement in metric.definition.compatibility.operands:
            matches = api.find_facts(
                EvidenceQuery(
                    **scopes[2022],
                    canonical_item_id=requirement.canonical_item_id,
                    period=metric.request.operand_periods[requirement.role],
                )
            )
            assert matches.status == "found"
            operands.append(FinancialOperand(role=requirement.role, fact=matches.matches[0].record))
        actual = assess_analytical_readiness(
            metric.definition.compatibility,
            operands,
            effective_reviews,
            bases,
            approval=PreparationApproval(**registry["preparation_approval"]),
            formula_policy=policies[metric.definition.name],
            formula_approvals=approvals,
        )
        closure.append(
            dict(
                metric_id=metric.metric_id,
                name=metric.definition.name,
                original_snapshot=metric.request.snapshot_id,
                selected_snapshot=scopes[2022]["snapshot_id"],
                original_operand_retrieval=[
                    api.get_fact(o.observation).model_dump(mode="json") for o in metric.operands
                ],
                recovered_readiness=actual,
            )
        )
    save(output / "snapshot-closure.json", closure)
    qa = qa_diagnostics(api, scopes, metrics, readiness, validation, closure)
    save(output / "qa.json", qa)
    web = asyncio.run(web_diagnostics(root, web_root, inventory))
    save(output / "web.json", web)
    # One targeted original-PDF render for the EPS restatement note, no OCR.
    source = next(r for r in inventory if r["year"] == 2025)
    with pdfium.PdfDocument(root / source["pdf"]) as pdf:
        page = pdf[22]
        bitmap = page.render(scale=1.5)
        bitmap.to_pil().save(output / "2025-23.png")
        bitmap.close()
        page.close()
    save(
        output / "visual-sources.json",
        dict(
            pdf_sha256=source["sha256"],
            pdf_page=23,
            render_sha256=digest(output / "2025-23.png"),
            method="original_pdf_render_for_controlled_visual_read",
            independent_gold=False,
        ),
    )
    # Pure arithmetic diagnostics are signals, never approved financial execution.
    arithmetic = []
    for year in range(2021, 2026):
        for statement, period, ids, signs in [
            (
                "B01",
                f"{year}-12-31",
                ["b01.total_assets", "b01.total_liabilities", "b01.total_equity"],
                [1, -1, -1],
            ),
            (
                "B02",
                str(year),
                ["b02.net_revenue", "b02.cost_of_sales", "b02.gross_profit"],
                [1, -1, -1],
            ),
        ]:
            selected = [
                api.find_facts(EvidenceQuery(**scopes[year], canonical_item_id=i, period=period))
                for i in ids
            ]
            complete = all(
                r.status == "found" and r.matches[0].record.value.normalized_value is not None
                for r in selected
            )
            arithmetic.append(
                dict(
                    filing=year,
                    statement=statement,
                    period=period,
                    ids=ids,
                    complete=complete,
                    residual=sum(
                        r.matches[0].record.value.normalized_value * sign
                        for r, sign in zip(selected, signs, strict=True)
                    )
                    if complete
                    else None,
                    observations=[
                        r.matches[0].record.observation_identity().model_dump(mode="json")
                        for r in selected
                        if r.matches
                    ],
                    financial_fact_verified=False,
                )
            )
    save(output / "arithmetic-signals.json", arithmetic)
    summary = dict(
        baseline_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        baseline_facts=len(rows),
        unmapped=len(unmapped),
        numeric=sum(r["numeric"] for r in rows),
        unmapped_kind=dict(Counter(r["kind"] for r in unmapped)),
        unmapped_rule=dict(Counter(r["rule_diagnosis"] for r in unmapped)),
        unmapped_numeric=dict(Counter(str(r["numeric"]) for r in unmapped)),
        unmapped_statement=dict(Counter(r["statement"] for r in unmapped)),
        financial_unmapped_numeric=sum(
            r["kind"] == "financial_item" and r["numeric"] for r in unmapped
        ),
        financial_unmapped_codes=len(
            {(r["statement"], r["source_code"]) for r in unmapped if r["kind"] == "financial_item"}
        ),
        unmapped_levels=dict(
            Counter(r["item_level"] for r in unmapped if r["kind"] == "financial_item")
        ),
        quality=dict(Counter(q for r in rows for q in r["quality"])),
        quality_reasons=dict(Counter(i for r in rows for i in r["quality_reasons"])),
        context_reasons=dict(Counter(i for r in rows for i in r["context_reasons"])),
        binding_problems=dict(Counter(i for r in rows for i in r["binding_problems"])),
        source_review=dict(Counter(r["source_review"] for r in rows)),
        consistency=dict(Counter(r["consistency"] for r in rows)),
        effective_quality=dict(Counter(q.decision for f in effective for q in f.quality_context)),
        effective_source_review=dict(
            Counter(source_review_status(f, effective_reviews) for f in effective)
        ),
        effective_binding_problems=dict(
            Counter(i for r in effective_rows for i in r["binding_problems"])
        ),
        cross_year_operand_review_occurrences=dict(pair_review_counts),
        recovered_2022_preparation_ready=sum(
            c["recovered_readiness"]["preparation_ready"] for c in closure
        ),
        original_2022_refs_unavailable_in_selected_view=sum(
            r["status"] == "not_found" for c in closure for r in c["original_operand_retrieval"]
        ),
        preparation_ready=sum(r["preparation_ready"] for r in readiness.values()),
        calculation_eligible=sum(r["calculation_eligible"] for r in readiness.values()),
        eligibility_blockers=dict(
            Counter(b for r in readiness.values() for b in r["eligibility_blockers"])
        ),
        qa=dict(Counter(q["outcome"] for q in qa)),
        arithmetic_zero_residual=sum(a["complete"] and a["residual"] == 0 for a in arithmetic),
        exact_retrieval=len(effective),
        cross_year=len(pairs),
        web_documents=len(web["documents"]),
        gemini_calls=0,
        tokens=0,
    )
    after = manifest(root, output)
    save(output / "hashes-after.json", after)
    assert before == after, "source_files_changed"
    summary.update(input_hash_count=len(before), input_hashes_unchanged=True)
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-03"))
    parser.add_argument(
        "--web-storage",
        type=Path,
        default=Path(os.environ.get("WEB_STORAGE_ROOT", "artifacts/web-demo-v1")),
    )
    args = parser.parse_args()
    run(Path.cwd().resolve(), args.output.resolve(), args.web_storage.resolve())
