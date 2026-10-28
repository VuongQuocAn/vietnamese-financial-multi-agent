"""Opt-in tiny W-03 live scan smoke, synthetic document, at most 3 SDK attempts."""

import argparse
import json
import os
import re
import time
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
from fastapi.testclient import TestClient
from google.genai import errors
from PIL import Image, ImageDraw, ImageFont
from vietnamese_financial_multi_agent.api.main import create_app
from vietnamese_financial_multi_agent.document_processing.metadata_preflight import (
    DEFAULT_METADATA_MODEL,
)


def make_scan(path):
    pages = []
    for lines in (
        ["SYNTHETIC SCAN TEST", "Metadata is on the next page.", "Not a real financial report."],
        [
            "SYNTHETIC LOTUS RESEARCH COMPANY",
            "SEPARATE FINANCIAL STATEMENTS",
            "For the fiscal year ended 31 December 2025",
            "Synthetic test fixture. No financial values.",
        ],
    ):
        image = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf" if os.name == "nt" else "DejaVuSans.ttf", 32)
        except OSError:
            font = ImageFont.load_default(size=28)
        for index, line in enumerate(lines):
            draw.text((80, 160 + index * 100), line, fill="black", font=font)
        pages.append(image)
    pages[0].save(path, format="PDF", save_all=True, append_images=pages[1:], resolution=150)
    for page in pages:
        page.close()
    with pdfium.PdfDocument(path) as pdf:
        for page in pdf:
            text = page.get_textpage()
            try:
                assert text.get_text_range() == ""
            finally:
                text.close()
            page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--attempt-cap", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument(
        "--diagnose", action="store_true", help="Safe API error for this synthetic fixture only"
    )
    args = parser.parse_args()
    if not args.live:
        print(json.dumps(dict(status="NOT_RUN", reason="explicit_live_flag_required")))
        return 0
    root = Path("artifacts/w-03-refinement-live") / str(uuid4())
    root.mkdir(parents=True, exist_ok=False)
    pdf = root / "synthetic-scan.pdf"
    make_scan(pdf)
    # Task authorization: Free Tier only, no paid model fallback. Cap attempts for
    # the whole smoke, including rotation, not per key. No intentional quota burn.
    os.environ["WEB_GEMINI_RPD"] = str(args.attempt_cap)
    os.environ["WEB_GEMINI_MAX_ATTEMPTS"] = str(args.attempt_cap)
    app = create_app(storage_root=root / "store", job_options=dict(max_pages=2, request_limit=1))
    report = dict(synthetic=True, model=DEFAULT_METADATA_MODEL, calls=0, analyzed_pages=[])
    with TestClient(app) as client:
        diagnostics = []
        if args.diagnose and app.state.jobs.service is not None:
            for key in app.state.jobs.service.pool.keys:
                models = key.adapter._client.models
                generate = models.generate_content

                def diagnostic(*call_args, _generate=generate, **call_kwargs):
                    try:
                        return _generate(*call_args, **call_kwargs)
                    except errors.APIError as error:
                        message = re.sub(r"AIza[0-9A-Za-z_-]{35}", "[redacted]", str(error.message))
                        diagnostics.append(dict(code=error.code, message=message[:1000]))
                        raise

                models.generate_content = diagnostic
        with pdf.open("rb") as source:
            uploaded = client.post(
                "/api/documents", files={"file": (pdf.name, source, "application/pdf")}
            )
        uploaded.raise_for_status()
        identifier = uploaded.json()["id"]
        deadline = time.monotonic() + 390
        while time.monotonic() < deadline:
            doc = client.get(f"/api/documents/{identifier}").json()
            if doc["state"] not in ("queued", "processing"):
                break
            time.sleep(0.2)
        preflight = doc["metadata"]["preflight"] or {}
        attempts = [a for batch in preflight.get("batches", []) for a in batch.get("attempts", [])]
        values = doc["metadata"]["values"]
        report.update(
            calls=len(attempts),
            analyzed_pages=preflight.get("analyzed_pages", []),
            stop_reason=preflight.get("stop_reason"),
            document_state=doc["state"],
            metadata=values,
            suggestions=doc["metadata"]["suggestions"],
            acceptance_origin=doc["metadata"].get("acceptance_origin"),
            batches=preflight.get("batches", []),
        )
        valid = (
            doc["state"] == "ready"
            and doc["metadata"].get("acceptance_origin") == "auto"
            and values["reporting_year"] == 2025
            and "LOTUS" in (values["company_name"] or "").upper()
            and values["reporting_scope"] == "separate"
            and all(
                any(
                    s["pdf_page"] == 2
                    for c in doc["metadata"]["suggestions"][field]["candidates"]
                    for s in c["sources"]
                )
                for field in ("company_name", "reporting_year", "reporting_scope")
            )
        )
        if valid:
            edited = dict(values, company_name=values["company_name"] + " (user edit)")
            response = client.patch(
                f"/api/documents/{identifier}/metadata",
                json=dict(
                    metadata_revision=doc["metadata_revision"], confirmed=True, values=edited
                ),
            )
            result = response.json()
            report["user_edit_pass"] = (
                response.status_code == 200
                and result["state"] == "ready"
                and result["metadata"]["acceptance_origin"] == "user"
                and result["metadata_revision"] == doc["metadata_revision"] + 1
                and result["metadata"]["suggestions"] == doc["metadata"]["suggestions"]
            )
            valid = report["user_edit_pass"]
        report["status"] = "PASS" if valid else "BLOCKED" if doc["state"] == "failed" else "FAIL"
        report["issues"] = preflight.get("issues", [])
        report["diagnostics"] = diagnostics
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("suggestions", "batches")},
            ensure_ascii=False,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
