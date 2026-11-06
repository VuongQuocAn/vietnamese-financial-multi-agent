"""Read saved fresh traces against independent QA-Q01 PDF references; no live calls."""

import json
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

from run_qa_fix_02 import QUESTIONS

ITEM_REFERENCE = {
    "b02.net_revenue": "revenue_2025",
    "b02.gross_profit": "gross_profit_2025",
    "b01.total_liabilities": "liabilities_2025",
    "b01.total_assets": "assets_2025",
    "b03.operating_cash_flow": "cfo_2025",
}
ROLES = {
    "profitability": "Profitability",
    "liquidity_and_leverage": "Liquidity & Leverage",
    "cash_flow_and_earnings_quality": "Cash Flow & Earnings Quality",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "/").replace("\n", " ")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        + ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    )


def audit(root):
    output = root / "artifacts/evidence/QA-Fix-02"
    references = read(root / "artifacts/evidence/QA-Q01/independent-reference-input.json")
    refs = {r["id"]: r for r in references["observations"]}
    with localcontext() as ctx:
        ctx.prec = 40
        ratios = {
            "gross_margin": (
                Decimal(refs["gross_profit_2025"]["value"])
                / Decimal(refs["revenue_2025"]["value"])
                * 100
            ).quantize(Decimal("0.01")),
            "debt_to_assets": (
                Decimal(refs["liabilities_2025"]["value"])
                / Decimal(refs["assets_2025"]["value"])
                * 100
            ).quantize(Decimal("0.01")),
        }
    ledgers = sorted(output.glob("provider-ledger-*.json"))
    calls = read(ledgers[-1]) if ledgers else []
    provider_errors = Counter(
        (c.get("response", {}).get("error") or {}).get("provider_error_code", "none") for c in calls
    )
    known_tokens = sum(
        c["response"]["usage"]["total_tokens"]
        for c in calls
        if c.get("response", {}).get("usage", {}).get("total_tokens") is not None
    )
    unknown_calls = sum(
        c.get("response", {}).get("usage", {}).get("total_tokens") is None for c in calls
    )
    actual = {
        case: read(output / f"{case}-actual-result.json")["result"]
        for case in QUESTIONS
        if (output / f"{case}-actual-result.json").exists()
    }
    for case in QUESTIONS:
        corrected = output / f"{case}-correction-actual-result.json"
        if corrected.exists():
            actual[case + "-correction"] = read(corrected)["result"]
    full = [
        case
        for case, result in actual.items()
        if result["specialist_executions"]
        and result["candidates"]
        and any(
            t["stage"] == "candidate_aggregation" and t["outcome"] == "completed"
            for t in result["trace"]
        )
    ]
    specialist_calls = Counter(
        e["role"] for result in actual.values() for e in result["specialist_executions"]
    )
    tool_calls = Counter(
        t["operation"]
        for result in actual.values()
        for t in (result["supervisor_result"] or {}).get("tool_trace", [])
        if t["bound_request"] is not None
    )
    before = read(root / "artifacts/evidence/QA-Q01/m5-Q07-result.json")
    saved = read(output / "Q07-saved-result.json")["result"]
    checks, sections, outcomes = [], [], []
    for case, result in actual.items():
        planner = result["planner_result"]
        proposal = planner["effective_proposal"] or planner["proposal"]
        routing, supervisor = result["routing_decision"], result["supervisor_result"]
        executed = {e["role"]: e for e in result["specialist_executions"]}
        stage_rows = []
        for label, stage in (
            ("Planner", "planning"),
            ("Supervisor", "supervisor"),
            ("Router", "routing"),
        ):
            event = next(t for t in result["trace"] if t["stage"] == stage)
            ran = event["outcome"] != "skipped"
            stage_rows.append(
                [
                    label,
                    "yes" if ran else "no",
                    "yes" if ran else "no",
                    event["outcome"] if ran else "NOT_EXECUTED",
                    f"{event['latency_ms']:.1f} ms",
                ]
            )
        for role, label in ROLES.items():
            execution = executed.get(role)
            stage_rows.append(
                [
                    label,
                    "yes" if routing and role in routing["selected_roles"] else "no",
                    "yes" if execution else "no",
                    execution["status"] if execution else "NOT_EXECUTED",
                    f"{execution['latency_ms']:.1f} ms" if execution else "—",
                ]
            )
        event = next(t for t in result["trace"] if t["stage"] == "candidate_aggregation")
        stage_rows.append(
            [
                "Aggregation",
                "yes" if event["outcome"] != "skipped" else "no",
                "yes" if event["outcome"] != "skipped" else "no",
                event["outcome"] if event["outcome"] != "skipped" else "NOT_EXECUTED",
                f"{event['latency_ms']:.1f} ms",
            ]
        )
        parts = [
            f"### {case} — {result['status']}",
            f"> {result['question']}",
            "Execution mode: **ACTUAL_EXECUTION**.",
            f"Planner: raw intent `{planner['proposal']['intent'] if planner['proposal'] else 'none'}` → effective `{proposal['intent'] if proposal else 'none'}`, status `{planner['status']}`. Requirements: `{', '.join(result['planner_result']['query']['required_indicators']) or 'none'}`; formulas `{', '.join(result['planner_result']['query']['requested_formula_ids']) or 'none'}`.",
            f"Operations: {', '.join(o['operation'] for o in proposal['operations']) if proposal else 'none'}. Missing/blocked: `{', '.join(result['missing_evidence'] + planner['missing_information']) or 'none'}`; stop `{', '.join(result['stop_conditions'])}`.",
            f"Raw targets: `{(planner['proposal'] or {}).get('required_indicators', [])}`; raw missing: `{(planner['proposal'] or {}).get('missing_information', [])}`; raw unsupported: `{(planner['proposal'] or {}).get('unsupported_capabilities', [])}`. Policy: `{[t for t in planner['trace'] if t['stage'] == 'semantic_policy']}`.",
            table(["Stage", "Selected", "Executed", "Status", "Duration"], stage_rows),
        ]
        if supervisor:
            rows = []
            for step in supervisor["tool_trace"]:
                request, response = step["bound_request"], step["response"]
                if request is None:
                    continue
                target = (
                    request.get("canonical_item_id")
                    or request.get("metric_id")
                    or request.get("reference", {}).get("kind")
                    or "source/lineage binding"
                )
                if request.get("metric_id"):
                    target = (response or {}).get("formula_id", "metric lineage")
                evidence = [
                    r
                    for r in supervisor["resolved_requirements"]
                    if r["requirement_id"] in step["output_evidence_ids"]
                ]
                pages = sorted({c["pdf_page"] for r in evidence for c in r["citations"]})
                rows.append(
                    [
                        step["operation"],
                        "Supervisor",
                        str(target)
                        + (" / " + str(request["period"]) if request.get("period") else ""),
                        f"{step['final_state']}/{(response or {}).get('status', 'typed result')}",
                        f"{step['latency_ms']:.1f} ms",
                        ", ".join(step["output_evidence_ids"]) + f"; PDF pages {pages}",
                    ]
                )
            parts.extend(
                [
                    "Supervisor gọi M4; Specialists nhận typed evidence projection, không gọi thêm M4:",
                    table(["Tool", "Caller", "Input chính", "Result", "Time", "Evidence"], rows),
                ]
            )
        if routing:
            parts.append(
                "Router: "
                + "; ".join(
                    f"{ROLES[r['role']]}={r['selection_reason']} (items={r['assigned_items']}, formulas={r['assigned_formulas']}, requirements={r['covered_requirement_ids']})"
                    for r in routing["routes"]
                )
                + "."
            )
        evidence_rows, claim_rows = [], []
        for role, execution in executed.items():
            projection = execution["projection"]
            source_result = execution["result"]
            parts.append(
                f"{ROLES[role]} projection: assigned {projection['assigned_requirement_ids']}; dependency closure {len(projection['dependency_requirement_ids'])}; {len(projection['citations'])} citations. Status {execution['status']}; thiếu {execution['missing_requirement_ids']}; model annotations {(source_result or {}).get('missing_evidence', [])}."
            )
            for evidence in (source_result or {}).get("supporting_evidence", []):
                item, calculation = evidence["canonical_item_id"], evidence["calculation"]
                formula = calculation["formula_id"] if calculation else None
                if item:
                    reference = refs[ITEM_REFERENCE[item]]
                    expected = Decimal(reference["value"])
                    expected_period = "2025-12-31" if item.startswith("b01.") else "2025"
                    value_ok = (
                        Decimal(evidence["value"]) == expected
                        and evidence["unit"] == "VND"
                        and Decimal(evidence["scale"]) == 1
                        and evidence["period"] == expected_period
                    )
                    pages_ok = {c["pdf_page"] for c in evidence["citations"]} == {reference["page"]}
                    operands = "direct fact"
                else:
                    expected = ratios[formula]
                    expected_period = "2025-12-31" if formula == "debt_to_assets" else "2025"
                    value_ok = (
                        Decimal(evidence["value"]) == expected
                        and evidence["unit"] == "percent"
                        and evidence["period"] == expected_period
                    )
                    operand_checks = []
                    names = []
                    for operand in calculation["evidence"]["operands"]:
                        fact = operand["facts"]["matches"][0]["record"]
                        reference = refs[ITEM_REFERENCE[fact["canonical_item_id"]]]
                        operand_checks.append(
                            Decimal(fact["value"]["normalized_value"])
                            == Decimal(reference["value"])
                            and fact["value"]["unit"] == "VND"
                            and fact["context"]["scale"] == "1"
                            and fact["context"]["period"] == expected_period
                        )
                        names.append(f"{fact['canonical_item_id']}={reference['value']}")
                    value_ok &= all(operand_checks) and calculation["trace"]["approval"] is not None
                    operands = (
                        "; ".join(names)
                        + "; "
                        + calculation["trace"]["formula"]["expression"]
                        + " ×100"
                    )
                    pages_ok = {c["pdf_page"] for c in evidence["citations"]} == (
                        {7} if formula == "gross_margin" else {5, 6}
                    )
                binding_ok = (
                    evidence["document_id"] == result["context"]["document_id"]
                    and evidence["snapshot_id"] == result["context"]["snapshot_id"]
                    and all(
                        c["document_id"] == evidence["document_id"]
                        and c["snapshot_id"] == evidence["snapshot_id"]
                        for c in evidence["citations"]
                    )
                )
                checks.append(
                    dict(
                        case=case,
                        role=role,
                        target=item or formula,
                        value=evidence["value"],
                        value_period_unit_operands_ok=bool(value_ok),
                        page_ok=pages_ok,
                        document_snapshot_ok=binding_ok,
                    )
                )
                assert value_ok and pages_ok and binding_ok, checks[-1]
                evidence_rows.append(
                    [
                        ROLES[role] + "/" + evidence["evidence_id"],
                        item or formula,
                        evidence["value"] + " " + evidence["unit"],
                        evidence["period"],
                        operands,
                        sorted({c["pdf_page"] for c in evidence["citations"]}),
                    ]
                )
        for number, candidate in enumerate(result["candidates"], 1):
            supporting = [
                e for origin in candidate["origins"] for e in origin["supporting_evidence"]
            ]
            source_citations = {stable(c) for e in supporting for c in e["citations"]}
            provenance_ok = bool(supporting) and all(
                stable(c) in source_citations for c in candidate["citations"]
            )
            caveats_ok = set(c for e in supporting for c in e["caveats"]) <= set(
                candidate["caveats"]
            )
            assert provenance_ok and caveats_ok and not candidate["financial_fact_verified"]
            checks.append(
                dict(
                    case=case,
                    candidate=number,
                    provenance_ok=provenance_ok,
                    caveats_preserved=caveats_ok,
                    verified=False,
                )
            )
            claim_rows.append(
                [
                    f"C{number:02}",
                    candidate["kind"],
                    candidate["content"],
                    ", ".join(ROLES[o["role"]] for o in candidate["origins"]),
                    sorted({c["pdf_page"] for c in candidate["citations"]}),
                    "candidate; caveats preserved",
                ]
            )
        if evidence_rows:
            parts.extend(
                [
                    "Independent checks: BBS_2025, scale1, source page đúng; formula/operands/period/unit kiểm riêng:",
                    table(
                        [
                            "Agent/evidence",
                            "Target",
                            "Value",
                            "Period",
                            "Operands/formula",
                            "PDF page",
                        ],
                        evidence_rows,
                    ),
                ]
            )
        if claim_rows:
            parts.extend(
                [
                    "Aggregation giữ origins, citations và caveats:",
                    table(
                        ["Claim", "Kind", "Actual content", "Origin", "PDF pages", "Disposition"],
                        claim_rows,
                    ),
                ]
            )
        parts.append(
            f"Caveats: {', '.join(result['caveats'])}. Conflicts: {len(result['conflicts'])}; errors: {result['errors']}. Total {result['latency_ms'] / 1000:.3f}s; provider calls {result['usage']['calls']}; known tokens {result['usage']['total_tokens']}; unknown-token calls {result['usage']['calls_with_unknown_tokens']}."
        )
        sections.append("\n\n".join(parts))
        outcomes.append(
            [
                case,
                planner["status"],
                result["status"],
                ", ".join(ROLES[r] for r in executed) or "NOT_EXECUTED",
                len(result["candidates"]),
                result["usage"]["calls"],
                result["usage"]["total_tokens"],
                f"{result['latency_ms'] / 1000:.3f}s",
            ]
        )
    summary = dict(
        mode="EVIDENCE_LINEAGE",
        actual_cases=len(actual),
        unique_questions=len(QUESTIONS),
        fresh_downstream=full,
        provider_attempts=len(calls),
        successful_calls=sum(c["status"] == "success" for c in calls),
        provider_errors=dict(provider_errors),
        known_tokens=known_tokens,
        unknown_token_calls=unknown_calls,
        specialist_calls=dict(specialist_calls),
        actual_tools=dict(tool_calls),
        checks=checks,
    )
    (output / "independent-audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = f"""# QA-Fix-02 — M5 Planner & Downstream Recovery

Ngày06/11/2026 (Asia/Bangkok). **REVIEW — chờ Tech Lead nghiệm thu**.
[Spec](../planning/tasks/QA/QA-Fix-02.md). Baseline main/origin `0451b37`;
implementation là commit chứa báo cáo này; CI đối chiếu đúng SHA qua commit checks.

## A. Executive Summary

F02: **confirmed/fixed trong phạm vi capability/intent**. Broad domains cần
clarification, không tự chọn ratios. F03: client recovery đã bổ sung và kiểm bằng
OFFLINE_TEST; nguyên nhân sâu503 của QA-Q01 **unresolved**. Fresh task này:
**{len(full)}/{len(actual)}** chạy đủ downstream ({", ".join(full)}),
{sum(specialist_calls.values())} Specialist invocations, {len(calls)}/20 provider attempts,
{sum(c["status"] == "success" for c in calls)} success, HTTP503={provider_errors["http_503"]},
HTTP429={provider_errors["http_429"]}; {known_tokens} known tokens/{unknown_calls} unknown-usage calls.
Không đổi model `gemini-3.5-flash-lite`, không key rotation/OCR/extraction/M6/M7 release.
Sáu câu hỏi khác nhau,7fresh runs do một Q08 correction có căn cứ alias gap;
không thử lại để ép successful status. Bốn runs completed, Q07/Q08 và Q08correction
clarification_required;0failed. Tổng21candidate claims,8Specialist invocations.
Runtime sửa: `query_planner.py`, `planner_contracts.py`, `llm_gateway.py`,
`adaptive_router.py`, `orchestrator.py`; Supervisor/M4/M6/M7 implementation giữ nguyên.
CI chỉ thêm new regression file vào focused suite.

{table(["Case", "Planner", "Orchestration", "Specialists executed", "Candidates", "Calls", "Tokens", "Latency"], outcomes)}

## B. Root-Cause Analysis

| Finding | Root cause | Confidence | Fix |
| --- | --- | --- | --- |
| F02 | Saved Gemini proposal ghi cả ba registered role là unsupported, operations rỗng. `_resolve()` short-circuit unsupported trước Supervisor/Router. Prompt chưa phân biệt broad domain với exact targets; chưa có semantic guard. | Confirmed về proposal/stop/guard thiếu; prompt contribution probable | Prompt + bounded alias semantic policy; giữ raw và effective proposals |
| F03 | Saved3responses là provider HTTP503/category provider_unavailable, usage unknown. Adapter/Gateway không retry; SDK cũng attempts1. | Confirmed client behavior; provider outage/quota root cause unresolved | Opt-in Gateway retry một lần503,0,25s backoff,total deadline; preserve attempts |

Không có bằng chứng Router gây F02 hoặc503 do hết quota. Credential resolver giữ
key index0; không thử các key khác. HTTP429/rate-limit/quota, auth, timeout,
invalid JSON, schema-contract và semantic rejection là các nhóm riêng.

Planner kiểm schema rồi semantic policy, resolve metadata/catalog, materialize và
validate như trước. Recovery chỉ dựng operations khi aliases xác định explicit
targets, giữ metadata gốc và tất cả accounting gates. Không recovery thành số liệu.
Nếu proposal có DAG nhưng bỏ explicit target: clarify; unapproved metric không
được thay bằng approved metric khác. Supported+unsupported giữ unsupported portion
cho Router partial. Registered roles/capabilities không đồng nghĩa mọi metric thuộc
domain đã được approve.

## C. Planner Before/After

Q07 nguyên văn: “{QUESTIONS["Q07"]}”

- SAVED_TRACE trước: `{before["planner_result"]["status"]}`, intent unsupported,
  requirements/operations rỗng; unsupported cả3roles,0downstream.
- SAVED_TRACE sau: `{saved["planner_result"]["status"]}`; missing
  `{", ".join(saved["planner_result"]["missing_information"])}`. Giữ proposal gốc;
  không chọn ROA/ROE/gross margin/debt ratio đại diện.
- ACTUAL_EXECUTION sau: xem Q07 dưới; không coi replay là fresh collaboration.
- Hai paraphrases mới N02/N03 được chạy fresh; exact questions, intent,
  requirements/operations/stages bên dưới. OFFLINE_TEST còn đảo thứ tự domains,
  dùng TEST2030,2/3targets và scope/year/missing evidence controls.
- Q08 initial bộc lộ alias gap: “dòng tiền kinh doanh” chưa match CFO. Hai failing
  controls dẫn đến thêm query aliases này/CFO và đưa shared aliases vào prompt.
  Q08 correction nhận rõ revenue+CFO, model yêu cầu criteria cho quality verdict;
  downstream NOT_EXECUTED đúng policy. Fresh correction còn ghi generic omission
  reason: một failing control bổ sung đã sửa để giữ nguyên clarification detail;
  final-policy behavior kiểm OFFLINE_TEST, không gọi Gemini lần nữa.

## D–E. Actual Multi-Agent Results & Collaboration

Tools thực thi thật: {dict(tool_calls)}. Specialists: {dict(specialist_calls)}.
Supervisor gọi M4; các Specialists chia sẻ typed context/evidence do Orchestrator
project. Không có bằng chứng messaging trực tiếp agent-to-agent. Aggregation chỉ
tổng hợp candidates và giữ origins; không ghi ledger hoặc phát hành M7.

{chr(10).join(sections)}

## F. Regression & Financial Checks

OFFLINE_TEST trước sửa: **19failed/3passed** (tests-before.txt), gồm capability,
partial/false substitution và API recovery chưa có. Các provider tests lúc này
fail cả do thiếu context/attempt metadata; không gọi đây là live503 recovery.
Sau sửa24new controls PASS (tests-policy-final.txt);305focused/consumer PASS
(tests-final.txt). Alias correction:2failing rồi66focused PASS; clarification
reason correction:1failing rồi final27new controls/focused group ở tests-final-m5.txt.
Final M5/Gateway/adapter: **133PASS**. Các Specialist/M6/M7 controls trong nhóm305
không bị alias/reason correction thay đổi; không chạy lại nhóm đã PASS.
Không sửa expected assertions của existing tests.
M5-02/03/07/08,3Specialists,Gateway/adapter và M6candidate/M7composer/firewall boundaries.
HTTP503→success/503, attempts1,429,401,403,invalidJSON,timeout,total deadline,
provenance,known11tokens+1unknown attempt và no fake downstream được kiểm.

EVIDENCE_LINEAGE audit độc lập dùng QA-Q01 visual PDF references, không lấy
Planner output làm gold. Gross margin32.482.519.668/450.474.531.227×100=
**{ratios["gross_margin"]}%**; liabilities157.146.559.558/assets266.086.680.765×100=
**{ratios["debt_to_assets"]}%**. Revenue **450.474.531.227 VND**, CFO
**14.319.681.754 VND**. BBS2025 PDF pages5/6/7/8; B01 instant31/12/2025,
B02/B03 fiscal2025, scale1. Audit kiểm values/operands/period/unit/formula approval,
document/snapshot/page và candidate provenance/caveats; không tự nâng candidates
thành verified. Interpretations phải đọc như mô tả tỷ lệ/dấu CFO, không kết luận
solvency hoặc chất lượng lợi nhuận tốt chỉ từ revenue+CFO.

## G. Remaining Limitations

Không còn provider failure trong fresh runs nếu503/429 bằng0; điều đó không xác
định nguyên nhân provider503 trước đây và không bảo đảm availability tương lai.
Specialists giữ one-attempt; retry opt-in hiện chỉ Planner. Broad-domain clarify
là policy outcome đúng. Unsupported metrics/missing evidence/accounting restrictions
vẫn giữ. Page-level/source_reference_uncertain, reporting_scope unresolved,
usable_with_caveat và các caveats inherited (kể cả formula_policy_not_approved
từ lineage cũ) không bị xóa; approval hiện hành kiểm riêng qua M4 gate.
Không benchmark accuracy toàn PDF/M8; không chứng minh M5→M6→M7 release tự động.
Chi phí tiền unknown; không quy đổi tokens thành tiền/quota còn lại.
Không phát hiện P0/P1 implementation còn lại trong F02/client recovery;
nguyên nhân sâu provider503 vẫn unresolved. Clarification text Gemini Q08 có
gợi ý ratios chưa approved; giữ raw để review, không coi đó là execution authority.

Ruff lint toàn repository PASS; format changed files/planning/diff checks được
ghi ở delivery checkpoint. Một full local format check gặp baseline CRLF trong
docs/m7-05-information-firewall.md: nội dung normalized đúng Git HEAD, Git blob LF;
không sửa file ngoài scope. CI chạy checkout LF và phải được xác nhận đúng SHA.

Selected-input integrity: chỉ hash Web local và14QA-Q01M5JSON (15files); kiểm logical
equality hydrated facts/metrics/source reviews trước/sau. Không hash toàn bộ
16.000+files và không tuyên bố đã kiểm hash tất cả protected dataset.
Artifacts ignored `artifacts/evidence/QA-Fix-02/`: actual-result, per-call
request/response, durable provider-ledgers, saved Q07 replay, integrity,
tests-before/final và independent-audit.json. Raw dataset không commit.
Delivery checkpoint local ghi implementation SHA, CI và current validation;
SHA/CI cuối được bàn giao trực tiếp cho Tech Lead, không tạo checkpoint commit.
[Fresh runner](../scripts/run_qa_fix_02.py), [independent audit](../scripts/audit_qa_fix_02.py).

## H. Next Action

Tech Lead review QA-Fix-02 và quyết định nghiệm thu trước khi giao QA-Fix-03.
**Dừng REVIEW; không tự triển khai task tiếp theo.**
"""
    (root / "docs/qa-fix-02-m5-planner-downstream-recovery.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    audit(Path(__file__).resolve().parents[1])
