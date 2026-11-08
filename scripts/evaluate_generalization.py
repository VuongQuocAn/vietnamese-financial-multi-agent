"""GEN-02: freeze independent source oracles, then run the actual QA pipeline.

Questions and financial/document source payloads remain in ignored local artifacts.
This runner never changes an oracle after freezing and never substitutes model outputs.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from evaluate_composition_graph import bbs_catalog
from evaluate_document_qa import build_pipeline
from evaluate_evidence_fusion import accepted_bcc, read, save
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.composition_graph import select_financial_catalog
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pipeline(root, label, output, bbs=None):
    p = build_pipeline(root / "artifacts/evidence/EXT-01", output / label / "ledger")
    company, year = label.split("_")
    doc = next(d for d in p.documents if d.company_id == company and d.reporting_year == int(year))
    manifest = next(m for m in p.compositions if m.logical_document_id == doc.document_id)
    if label.startswith("BCC"):
        p.catalog = accepted_bcc(root, label, manifest.financial_snapshot)
    elif label == "BBS_2025":
        p.catalog = select_financial_catalog(bbs or bbs_catalog(root), manifest)
    else:
        p.catalog = SnapshotCatalog([manifest.financial_snapshot])
    p.documents = [
        QADocument(
            document_id=doc.document_id,
            company_id=p.catalog.facts[0].company_id if p.catalog.facts else company,
            company_aliases=[company],
            reporting_year=int(year),
        )
    ]
    return p, manifest


def freeze(root, base):
    if (base / "freeze.json").exists():
        raise ValueError("dataset_already_frozen")
    questions = read(base / "questions.json")
    assert len(questions) == 40 and len({q["id"] for q in questions}) == 40
    records = read(root / "artifacts/evidence/EXT-01/repository/document-evidence.json")["records"]
    bbs = bbs_catalog(root)
    sources = {}
    for label in sorted({q["label"] for q in questions}):
        p, manifest = pipeline(root, label, base / "oracle-inputs", bbs)
        pins = {
            (pin.identity.document_id, pin.identity.snapshot_id, pin.identity.local_id)
            for s in manifest.sources
            if s.status == "verified"
            for pin in s.evidence
        }
        sources[label] = dict(
            manifest=manifest.model_dump(mode="json"),
            facts=[f.model_dump(mode="json") for f in p.catalog.facts],
            records=[
                r
                for r in records
                if (r["document_id"], r["snapshot_id"], r["local_evidence_id"]) in pins
            ],
        )
    for q in questions:
        source = sources[q["label"]]
        year = q["label"].split("_")[1]

        def fact(item, previous=False, *, year=year, source=source, q=q):
            period = str(int(year) - int(previous))
            matches = [
                f
                for f in source["facts"]
                if f["canonical_item_id"] == item
                and f["context"]["period"].startswith(period)
                and (
                    f["context"]["period_type"] != "as_of"
                    or f["context"]["period"] == period + "-12-31"
                )
            ]
            assert len(matches) == 1, (q["id"], item, period, len(matches))
            return matches[0]

        for requirement in q["requirements"]:
            if "fact" in requirement:
                f = fact(requirement["fact"])
                requirement["expected_value"] = f["value"]["normalized_value"]
                requirement["expected_facts"] = [f]
            elif "metric" in requirement:
                formula = requirement["metric"]
                ids = {
                    "gross_margin": ("b02.gross_profit", "b02.net_revenue"),
                    "debt_to_assets": ("b01.total_liabilities", "b01.total_assets"),
                    "revenue_yoy": ("b02.net_revenue", "b02.net_revenue"),
                }[formula]
                a, b = fact(ids[0]), fact(ids[1], formula == "revenue_yoy")
                numerator = Decimal(a["value"]["normalized_value"])
                denominator = Decimal(b["value"]["normalized_value"])
                requirement["expected_value"] = str(
                    (numerator / denominator - int(formula == "revenue_yoy")) * 100
                )
                requirement["expected_facts"] = [a, b]
                requirement["formula"] = (
                    "(current / previous - 1) * 100"
                    if formula == "revenue_yoy"
                    else "numerator / denominator * 100"
                )
            elif "page" in requirement:
                pointers = requirement.get("pointers") or [
                    f"/text_elements/{i}" for i in requirement["selectors"]
                ]
                chosen = [
                    r
                    for r in source["records"]
                    if r["kind"] == "text"
                    and any(
                        s.get("reference")
                        and s["reference"]["anchor"]["page"]["page"] == requirement["page"]
                        and s["reference"]["source_pointer"] in pointers
                        for s in r["sources"]
                    )
                ]
                assert len(chosen) == len(pointers), (q["id"], pointers, len(chosen))
                requirement["expected_records"] = chosen
        q.setdefault(
            "source_answerable", q["answerability"] in {"FULLY_ANSWERABLE", "PARTIALLY_ANSWERABLE"}
        )
    save(base / "sources.json", sources)
    save(base / "development-oracles.json", [q for q in questions if q["id"].startswith("D")])
    save(base / "holdout-oracles.json", [q for q in questions if q["id"].startswith("H")])
    save(
        base / "freeze.json",
        dict(
            created_utc=datetime.now(UTC).isoformat(),
            head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            method="Codex source-first oracle; Decimal formulas independent of runtime; accepted financial inputs; pinned document selectors; representative original PDF visual review, not full independent human gold",
            files={
                name: digest(base / name)
                for name in (
                    "questions.json",
                    "sources.json",
                    "development-oracles.json",
                    "holdout-oracles.json",
                )
            },
        ),
    )


def run(root, base, subset, phase, *, live=False, case_ids=None):
    frozen = read(base / "freeze.json")
    assert all(digest(base / name) == value for name, value in frozen["files"].items())
    if subset == "holdout":
        assert (base / "development-complete.json").exists(), "finish_development_before_holdout"
        checkpoint = read(base / "development-complete.json")
        assert all(
            digest(root / p) == value for p, value in checkpoint["runtime_hashes"].items()
        ), "runtime_changed_after_development_seal"
    questions = read(base / f"{subset}-oracles.json")
    if case_ids:
        assert subset == "development", "never_select_holdout_cases_for_tuning"
        questions = [q for q in questions if q["id"] in case_ids]
        assert len(questions) == len(set(case_ids))
    gateway = None
    if live:
        assert subset == "development", "live_supplement_is_development_only"
        adapter, _ = create_qa_adapter(root)

        def transport(request):
            budget = base / "provider-attempts.jsonl"
            existing = len(budget.read_text().splitlines()) if budget.exists() else 0
            if existing >= 6:
                raise ValueError("GEN_02_live_budget_exhausted")
            with budget.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        dict(
                            request_id=request.request_id, started_utc=datetime.now(UTC).isoformat()
                        )
                    )
                    + "\n"
                )
            return adapter(request)

        gateway = SharedLLMGateway({"gemini": transport})
    output = base / phase
    if output.exists():
        raise ValueError("use_fresh_phase_directory")
    output.mkdir(parents=True)
    save(
        output / "run-manifest.json",
        dict(
            subset=subset,
            phase=phase,
            freeze_sha256=digest(base / "freeze.json"),
            started_utc=datetime.now(UTC).isoformat(),
            execution_mode="gemini" if live else "deterministic_saved_evidence",
            gateway_enabled=live,
            runtime_hashes={p.as_posix(): digest(p) for p in sorted((root / "src").rglob("*.py"))},
        ),
    )
    pipelines = {}
    bbs = bbs_catalog(root)
    for q in questions:
        if q["label"] not in pipelines:
            pipelines[q["label"]], _ = pipeline(root, q["label"], output, bbs)
        p = pipelines[q["label"]]
        p.gateway = gateway
        result = p.run(
            FinancialQARequest(
                question=q["question"],
                force_refresh=True,
                allow_gateway=live,
                execution_mode="gemini" if live else "deterministic",
            )
        )
        save(
            output / f"{q['id']}.json",
            dict(
                case_id=q["id"],
                original_question=q["question"],
                expected_answerability=q["answerability"],
                actual=result.model_dump(mode="json"),
            ),
        )
        print(
            q["id"],
            result.status,
            round(result.trace.total_latency_ms),
            result.trace.errors,
            flush=True,
        )
    save(
        output / "completed.json",
        dict(completed_utc=datetime.now(UTC).isoformat(), count=len(questions)),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "run", "seal"])
    parser.add_argument("--base", type=Path, default=Path("artifacts/evidence/GEN-02"))
    parser.add_argument("--subset", choices=["development", "holdout"], default="development")
    parser.add_argument("--phase", default="development-before")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    if args.action == "freeze":
        freeze(Path.cwd(), args.base)
    elif args.action == "seal":
        audit = read(args.base / "development-after/independent-audit.json")
        assert audit["completed_cases"] == audit["expected_cases"] == 25
        manifest = read(args.base / "development-after/run-manifest.json")
        assert all(digest(Path(p)) == value for p, value in manifest["runtime_hashes"].items()), (
            "runtime_changed_during_development_evaluation"
        )
        assert not (args.base / "development-complete.json").exists()
        save(
            args.base / "development-complete.json",
            dict(
                sealed_utc=datetime.now(UTC).isoformat(),
                development_audit_sha256=digest(
                    args.base / "development-after/independent-audit.json"
                ),
                freeze_sha256=digest(args.base / "freeze.json"),
                runtime_hashes={p.as_posix(): digest(p) for p in sorted(Path("src").rglob("*.py"))},
            ),
        )
    else:
        run(Path.cwd(), args.base, args.subset, args.phase, live=args.live, case_ids=args.cases)


if __name__ == "__main__":
    main()
