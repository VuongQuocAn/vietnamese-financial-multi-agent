"""E2E-02 discovery runner. Freeze references first; never retry an executed turn.

Private manifests, PDF renders, ledgers and outputs remain in ignored artifacts.
Use --limit 2 for the initial runner check, then resume without --limit.
The first two observations remain part of the final forty, not cherry-picked reruns.
"""

import argparse
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected(root):
    paths = list((root / "artifacts/evidence/EXT-01").rglob("*.json"))
    paths += list((root / "artifacts/evidence/GEN-01").glob("*-release/*/*.json"))
    paths += list((root / "artifacts/source-quality").rglob("*.json"))
    paths += list((root / "data/raw").rglob("*.pdf"))
    paths += list((root / "src").rglob("*.py"))
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(set(paths))}


def runtime(base, head):
    """Import the committed runtime, leaving the owner's local work untouched."""
    # Frozen source lives outside its checkout. Preserve the operator's real
    # source-policy/release storage instead of silently loading an empty policy.
    root = Path.cwd().resolve()
    if (root / "pyproject.toml").is_file():
        os.environ.setdefault("FINANCIAL_PROJECT_ROOT", str(root))
        # Also supported by older frozen implementations which predate the
        # explicit project root setting.
        os.environ.setdefault("DOCUMENT_RELEASE_ROOT", str(root / "artifacts/source-quality"))
        os.environ.setdefault("DOCUMENT_SOURCE_POLICY_ROOT", str(root / "artifacts/source-quality"))
    target = base / "runtime"
    if not target.exists():
        archive = subprocess.check_output(["git", "archive", "--format=zip", head, "src"])
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            source.extractall(target)
    name = "vietnamese_financial_multi_agent"
    spec = importlib.util.spec_from_file_location(name, target / "src/__init__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)


def build(root, output):
    from evaluate_conversations import unique
    from evaluate_generalization import pipeline as load
    from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
    from vietnamese_financial_multi_agent.evidence import EvidenceGraph, SnapshotCatalog
    from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

    pipelines = [
        load(root, label, output)[0] for label in ("BBS_2025", "BCC_2024", "BCC_2025", "BBS_2024")
    ]
    catalogs = [p.catalog for p in pipelines]
    base = catalogs[0]
    # Document-only loaders fall back to ticker IDs. Bind their aliases to the
    # accepted company identity already present in another period's catalog.
    # This is runner composition only; no evidence/fact/policy is rewritten.
    companies = {}
    for p in pipelines:
        if p.catalog.facts:
            for d in p.documents:
                for alias in d.company_aliases:
                    companies[alias] = d.company_id
    documents = [
        d.model_copy(update={"company_id": companies.get(d.company_aliases[0], d.company_id)})
        for p in pipelines
        for d in p.documents
    ]
    catalog = SnapshotCatalog(
        unique([r for c in catalogs for r in c.descriptors]),
        unique([r for c in catalogs for r in c.facts]),
        unique([r for c in catalogs for r in c.evidence]),
        unique([r for c in catalogs for r in c.metrics]),
        graph=EvidenceGraph(
            nodes=unique([r for c in catalogs if c.graph for r in c.graph.nodes]),
            edges=unique([r for c in catalogs if c.graph for r in c.graph.edges]),
        ),
        source_reviews=unique([r for c in catalogs for r in c.reviews]),
        accounting_bases=unique([r for c in catalogs for r in c.bases]),
        reporting_scope_reviews=unique([r for c in catalogs for r in c.scope_reviews]),
        approval=base.approval,
        formula_policies=base.policies,
        formula_approvals=base.formula_approvals,
        execution_approval=base.execution_approval,
    )
    return FinancialQAPipeline(
        catalog=catalog,
        documents=documents,
        repository=VerifiedClaimRepository(output / "ledger"),
        compositions=pipelines[0].compositions,
        document_repository=pipelines[0].document_repository,
    )


def freeze(root, base):
    assert not (base / "freeze.json").exists(), "already_frozen"
    questions, references = read(base / "questions.json"), read(base / "reference.json")
    assert len(questions) == len(references) == 40
    assert {q["id"] for q in questions} == {r["id"] for r in references}
    assert [sum(q["level"] == level for q in questions) for level in range(1, 5)] == [10, 10, 8, 12]
    save(
        base / "freeze.json",
        dict(
            created_utc=datetime.now(UTC).isoformat(),
            runtime_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            files={name: digest(base / name) for name in ("questions.json", "reference.json")},
            protected=protected(root),
            local_status=subprocess.check_output(["git", "status", "--short"], text=True),
            execution_mode="deterministic",
            ingestion_calls=0,
            seed_ledger=None,
        ),
    )


def run(root, base, limit):
    frozen = read(base / "freeze.json")
    assert all(digest(base / name) == value for name, value in frozen["files"].items())
    assert frozen["protected"] == protected(root), "protected_inputs_changed"
    runtime(base, frozen["runtime_head"])
    from vietnamese_financial_multi_agent.api.conversations import ConversationService
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest

    started = perf_counter()
    pipeline = build(root, base)
    startup_ms = (perf_counter() - started) * 1000
    if not (base / "catalog-inputs.json").exists():
        save(
            base / "catalog-inputs.json",
            dict(
                facts=[f.model_dump(mode="json") for f in pipeline.catalog.facts],
                documents=[d.model_dump(mode="json") for d in pipeline.documents],
                compositions=[m.model_dump(mode="json") for m in pipeline.compositions],
            ),
        )
    service, sessions = ConversationService(pipeline), {}
    questions = read(base / "questions.json")
    rows = read(base / "results.json") if (base / "results.json").exists() else []
    completed = {r["id"] for r in rows}
    # A resumable smoke ends before L4; never replay conversation outputs as input.
    assert not any(q.get("conversation") for q in questions if q["id"] in completed)
    save(base / f"startup-{len(rows)}.json", dict(startup_ms=startup_ms))
    count = 0
    for q in questions:
        if q["id"] in completed:
            continue
        if limit and count >= limit:
            break
        row = dict(id=q["id"], execution_mode="deterministic", startup_excluded=True)
        started = perf_counter()
        try:
            request = FinancialQARequest(
                question=q["question"],
                force_refresh=q.get("force_refresh", False),
                allow_gateway=False,
                execution_mode="deterministic",
            )
            if q.get("conversation"):
                key = q["conversation"]
                if key not in sessions:
                    sessions[key] = service.create().conversation_id
                turn = service.send(sessions[key], request)
                row["conversation"] = turn.model_dump(mode="json")
                response = turn.response
            else:
                response = pipeline.run(request)
            row["actual"] = response.model_dump(mode="json")
        except Exception as error:
            row["runtime_error"] = dict(type=type(error).__name__, message=str(error))
        row["elapsed_ms"] = (perf_counter() - started) * 1000
        save(base / "turns" / f"{q['id']}.json", row)
        rows.append(row)
        save(base / "results.json", rows)
        print(
            q["id"],
            round(row["elapsed_ms"]),
            row.get("actual", {}).get("status", "RUNTIME_FAILURE"),
            flush=True,
        )
        count += 1
    save(
        base / "traces.json",
        [
            dict(
                id=r["id"],
                trace=r.get("actual", {}).get("trace"),
                runtime_error=r.get("runtime_error"),
            )
            for r in rows
        ],
    )
    save(
        base / "integrity.json",
        dict(
            protected_files=len(frozen["protected"]),
            protected_unchanged=frozen["protected"] == protected(root),
            references_unchanged=all(
                digest(base / name) == value for name, value in frozen["files"].items()
            ),
            completed=len(rows),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "run"])
    parser.add_argument("--base", type=Path, default=Path("artifacts/evidence/E2E-02"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze(Path.cwd(), args.base)
    else:
        run(Path.cwd(), args.base, args.limit)


if __name__ == "__main__":
    main()
