"""D-01: checkpointed real PDFs through the existing discovery/extraction Gateway."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pypdfium2 as pdfium
from vietnamese_financial_multi_agent.accounting.automated_extraction import run_automated_pdf
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.document_processing.financial_discovery import (
    discover_financial_pages,
)
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    facts_from_persisted_result,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CheckpointService:
    def __init__(self, service, pool, output):
        self.service, self.pool, self.output = service, pool, output
        self.last_call = 0

    def generate(self, *args, **kwargs):
        # Pace the existing application cap; never retry a failed provider response.
        time.sleep(max(0, 4.5 - (time.monotonic() - self.last_call)))
        self.last_call = time.monotonic()
        result = self.service.generate(*args, **kwargs)
        with (self.output / "usage.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(attempts=self.service.last_attempts)) + "\n")
        return result


def run(root, output, live):
    output.mkdir(parents=True, exist_ok=True)
    inputs = [
        p
        for year in range(2021, 2026)
        for folder, pattern in (
            (root / f"data/raw/Financial_Report_pdf/BBS/{year}", "*.pdf"),
            (root / f"data/processed/Financial_Report_OCR/BBS/{year}/ocr_json", "*.json"),
        )
        for p in folder.glob(pattern)
    ]
    inputs.append(root / "web/next-env.d.ts")
    baseline = {p.relative_to(root).as_posix(): digest(p) for p in inputs}
    baseline_path = output / "hashes-before.json"
    if baseline_path.exists():
        if load(baseline_path) != baseline:
            raise ValueError("source_changed_since_checkpoint")
    else:
        atomic_json(baseline_path, baseline)
    inventory = []
    for year in range(2021, 2026):
        pdfs = list((root / f"data/raw/Financial_Report_pdf/BBS/{year}").glob("*.pdf"))
        if len(pdfs) != 1:
            raise ValueError("ambiguous_pdf")
        pdf = pdfs[0]
        with pdfium.PdfDocument(pdf) as document:
            count = len(document)
        ocr = list(
            (root / f"data/processed/Financial_Report_OCR/BBS/{year}/ocr_json").glob("*.json")
        )
        inventory.append(
            dict(
                year=year,
                pdf=pdf.relative_to(root).as_posix(),
                sha256=digest(pdf),
                pages=count,
                ocr_pages=len(ocr),
                ocr_binding="not_verified",
            )
        )
    atomic_json(output / "inventory.json", inventory)
    if not live:
        return
    service, pool, options = compose_metadata_service(SimpleNamespace(root=output))
    if service is None:
        raise ValueError("existing_gateway_configuration_unavailable")
    metered = CheckpointService(service, pool, output)
    try:
        for row in inventory:
            year = row["year"]
            folder = output / str(year)
            folder.mkdir(exist_ok=True)
            pdf = root / row["pdf"]
            if year == 2025:
                sources = list((root / "artifacts/w07/fresh-storage").rglob("result.json"))
                if len(sources) != 1:
                    raise ValueError("existing_2025_result_unavailable")
                original = sources[0].parents[2] / "original.pdf"
                if digest(original) != row["sha256"]:
                    raise ValueError("existing_2025_pdf_mismatch")
                atomic_json(folder / "result.json", load(sources[0]))
                continue
            completed = folder / "result.json"
            if completed.exists():
                previous = load(completed)
                if (
                    previous["document_id"] != "sha256:" + row["sha256"]
                    or len(previous["inventory"]) != row["pages"]
                ):
                    raise ValueError("completed_document_binding_mismatch")
                print(f"reuse completed filing {year}", flush=True)
                continue
            cache = {p["page"]: p for f in folder.glob("discovery-*.json") if (p := load(f))}

            def checkpoint(page, folder=folder, year=year):
                atomic_json(folder / f"discovery-{page['page']}.json", page)
                print(f"discovery {year}/{page['page']}: {page['statement_type']}", flush=True)

            discovered = discover_financial_pages(
                pdf,
                symbol="BBS",
                year=str(year),
                service=metered,
                credential_ref=options["credential_ref"],
                cached_predictions=cache,
                on_page=checkpoint,
            )
            atomic_json(folder / "discovery.json", discovered)
            records = []
            for page in discovered:
                if not page["selected"]:
                    continue
                number = page["page"]
                path = folder / f"extraction-{number}.json"
                records.extend(
                    run_automated_pdf(
                        pdf,
                        symbol="BBS",
                        year=str(year),
                        pages=[number],
                        service=metered,
                        credential_ref=options["credential_ref"],
                        cached_records={number: load(path)} if path.exists() else None,
                    )
                )
                atomic_json(path, records[-1])
                print(
                    f"extraction {year}/{number}: {len(records[-1]['extraction']['links'])}",
                    flush=True,
                )
            valid = [
                r for r in records if "invalid_extraction_response" not in r["extraction"]["issues"]
            ]
            quality = assess_evidence_for_task(evidence_from_automated_records(valid))
            result = dict(
                document_id="sha256:" + row["sha256"],
                attempt_id="D-01/extraction-v1",
                records=records,
                inventory=discovered,
                quality=quality.model_dump(mode="json"),
            )
            atomic_json(folder / "result.json", result)
            repo = CanonicalFactRepository(folder / "canonical-baseline")
            for fact in facts_from_persisted_result(result):
                repo.put(fact)
    finally:
        pool.close()
        after = {name: digest(root / name) for name in baseline}
        atomic_json(output / "hashes-after.json", after)
        if after != baseline:
            raise ValueError("source_mutation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-01"))
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts"):
        parser.error("output must be under ignored artifacts storage")
    run(root, output, args.live)
