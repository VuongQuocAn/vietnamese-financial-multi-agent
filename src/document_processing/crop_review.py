"""Local source/bbox versus reconstruction sheets; no source writes or approval."""

import io

from PIL import Image, ImageDraw

from .crop_audit import CropError, read_image, reference_request
from .crop_expansion import (
    approval_template,
    artifact_root,
    inspect_outputs,
    recovery_id,
    write_once,
)
from .crop_recovery import _check_components, _read_output


def create_review_sheets(config, records, states, requests, mappings, images, plan, reviewed):
    fresh = inspect_outputs(records, requests, config, mappings, images)
    if fresh != states:
        raise CropError("review_outputs_changed")
    root = artifact_root(config) / "review"
    lookup = {recovery_id(r): r for r in records}
    results = {s["recovery_id"]: s for s in states}
    manifest = []
    for item in reviewed:
        rid = item["recovery_id"]
        record, result = lookup[rid], results[rid]
        if result["status"] != "already_recovered":
            raise CropError("pilot_output_changed")
        request = reference_request(
            record.source_image, "raw_page_image", record.ocr_source, ["page", "image"], mappings
        )
        source, hashed = read_image(request, config)
        output = config.project_root / "data/recovered_crops" / (rid + ".png")
        with source, Image.open(io.BytesIO(_read_output(output, 64 * 1024 * 1024))) as crop:
            if hashed != result["source_image_hash"]:
                raise CropError("source_changed")
            page = source.convert("RGB")
            ImageDraw.Draw(page).rectangle(record.bbox, outline="red", width=10)
            page.thumbnail((580, 720))
            shown = crop.convert("RGB")
            shown.thumbnail((580, 720))
            sheet = Image.new("RGB", (1200, 840), "white")
            sheet.paste(page, (10 + (580 - page.width) // 2, 10))
            sheet.paste(shown, (610 + (580 - shown.width) // 2, 10))
            caption = (
                f"Page: {record.page_identity} | {record.element_type}.{record.field} "
                f"element={record.element_id}\nBbox: {record.bbox} | "
                f"crop: {crop.width} x {crop.height} | recovery: {rid[:16]}"
            )
            ImageDraw.Draw(sheet).text((10, 750), caption, fill="black")
            path = root / (rid + ".png")
            # Review output is also exclusive. Rerun validates the exact bytes.
            buffer = io.BytesIO()
            sheet.save(buffer, format="PNG")
            content = buffer.getvalue()
            _check_components(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if _read_output(path, len(content)) != content:
                    raise CropError("review_sheet_conflict")
            else:
                with path.open("xb") as stream:
                    stream.write(content)
        manifest.append(
            dict(
                **item,
                page_identity=record.page_identity,
                element_id=record.element_id,
                bbox=record.bbox,
                width=result["width"],
                height=result["height"],
                sheet=path.name,
            )
        )
    write_once(root / "review-manifest.json", dict(plan_id=plan["plan_id"], items=manifest))
    write_once(
        root.parent / "visual-review-approval.template.json", approval_template(plan, reviewed)
    )
    return manifest
