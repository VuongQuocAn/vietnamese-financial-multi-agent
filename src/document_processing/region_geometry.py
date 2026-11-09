"""Image-bound region metadata. No OCR, fuzzy matching or inferred coordinate frames."""

import hashlib
import io
import re
from dataclasses import replace

from PIL import Image

from .vision_ocr import valid_bbox


def geometry_header(image, *, method, regions=(), reason=None):
    return dict(
        version="region_geometry_v1",
        page=image.identity.model_dump(mode="json"),
        image_sha256=image.sha256,
        width=image.width,
        height=image.height,
        coordinate_space="original_image_pixels",
        method=method,
        regions=list(regions),
        selectors={},
        reason=reason,
    )


def pdf_text_geometry(page, bitmap, image):
    """PDFium's render position converter handles PDF rotation and render scaling."""
    converter = bitmap.get_posconv(page)
    regions, chars, boxes = [], [], []

    def flush():
        if chars and boxes and "".join(chars).strip():
            bbox = [
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            ]
            regions.append(
                dict(
                    id=f"pdf_text_line:{len(regions)}",
                    text="".join(chars),
                    bbox=bbox,
                    kind="text",
                    reading_order=len(regions),
                )
            )
        chars.clear()
        boxes.clear()

    textpage = page.get_textpage()
    try:
        for i in range(textpage.count_chars()):
            char = textpage.get_text_range(i, 1)
            if char in {"\r", "\n"}:
                flush()
                continue
            left, bottom, right, top = textpage.get_charbox(i)
            corners = [converter.to_bitmap(x, y) for x in (left, right) for y in (bottom, top)]
            box = [
                min(p[0] for p in corners),
                min(p[1] for p in corners),
                max(p[0] for p in corners),
                max(p[1] for p in corners),
            ]
            chars.append(char)
            if not char.isspace() and valid_bbox(box, image.width, image.height):
                boxes.append(box)
        flush()
    finally:
        textpage.close()
    return geometry_header(
        image,
        method="pdf_text_layer_render_transform",
        regions=regions,
        reason=None if regions else "pdf_has_no_text_layer",
    )


def raw_ocr_geometry(raw, image):
    """Retain IDs/order/boxes, but require an explicit same-image coordinate contract."""
    metadata = raw["page"]
    regions = [
        dict(id=e["id"], text=e.get("text", ""), bbox=e["bbox"], kind=e["type"], reading_order=i)
        for i, e in enumerate(raw["elements"])
    ]
    geometry = geometry_header(image, method="raw_ocr_same_image", regions=regions)
    if (
        metadata.get("image_sha256") != image.sha256
        or metadata.get("coordinate_space") != "original_image_pixels"
        or (metadata.get("width"), metadata.get("height")) != (image.width, image.height)
        or (metadata.get("symbol"), metadata.get("year"), metadata.get("page"))
        != (image.identity.symbol, image.identity.year, image.identity.page)
    ):
        geometry["reason"] = "raw_image_hash_or_coordinate_frame_unverified"
    return geometry


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def bind_selectors(geometry, selectors):
    """Exact, unique complete line runs. Partial/fuzzy text is never region authority.

    Caller may supply raw IDs from a source pointer; those still need exact text and
    layout validation. No single-element index is interpreted as an OCR element ID.
    """
    import copy

    result = copy.deepcopy(geometry)
    regions = result["regions"]
    for selector, text, raw_ids in selectors:
        matches = []
        if text and not result.get("reason"):
            for start, region in enumerate(regions):
                if region["kind"] != "text":
                    continue
                for end in range(start, min(len(regions), start + 12)):
                    run = regions[start : end + 1]
                    if any(r["kind"] != "text" for r in run):
                        break
                    ids = [r["id"] for r in run]
                    if raw_ids and ids != raw_ids:
                        continue
                    if normalized(" ".join(r["text"] for r in run)) == normalized(text):
                        matches.append(ids)
        result["selectors"][selector] = dict(
            text_sha256=hashlib.sha256((text or "").encode()).hexdigest(),
            raw_element_ids=matches[0] if len(matches) == 1 else [],
            status="mapped" if len(matches) == 1 else "unresolved",
            reason=None
            if len(matches) == 1
            else result.get("reason") or "no_unique_exact_region_run",
        )
    return result


def resolve_region(image, geometry, selector, text):
    """Validate binding, paragraph continuity and crop isolation before image access."""
    if not geometry or geometry.get("version") != "region_geometry_v1":
        return dict(status="unresolved", reason="geometry_binding_missing")
    if (
        geometry.get("page") != image.identity.model_dump(mode="json")
        or geometry.get("image_sha256") != image.sha256
        or (geometry.get("width"), geometry.get("height")) != (image.width, image.height)
        or geometry.get("coordinate_space") != "original_image_pixels"
    ):
        return dict(status="unresolved", reason="geometry_image_or_frame_mismatch")
    mapping = geometry.get("selectors", {}).get(selector, {})
    if geometry.get("method") not in {"pdf_text_layer_render_transform", "raw_ocr_same_image"}:
        return dict(status="unresolved", reason="unsupported_geometry_provenance")
    if geometry.get("reason") or mapping.get("status") != "mapped":
        return dict(
            status="unresolved",
            reason=geometry.get("reason") or mapping.get("reason") or "selector_not_mapped",
        )
    if mapping.get("text_sha256") != hashlib.sha256(text.encode()).hexdigest():
        return dict(status="unresolved", reason="geometry_text_version_mismatch")
    ids = mapping.get("raw_element_ids", [])
    rows = [r for r in geometry["regions"] if r["id"] in ids]
    if not ids or len(rows) != len(ids) or [r["id"] for r in rows] != ids:
        return dict(status="unresolved", reason="geometry_element_identity_ambiguous")
    if any(
        r["kind"] != "text" or not valid_bbox(r["bbox"], image.width, image.height) for r in rows
    ):
        return dict(status="unresolved", reason="invalid_text_region")
    # Only adjacent lines in one horizontal paragraph. Unknown/vertical OCR frames
    # must be resolved by the producer, never repaired by swapping axes here.
    for a, b in zip(rows, rows[1:], strict=False):
        x, y = a["bbox"], b["bbox"]
        height = max(x[3] - x[1], y[3] - y[1])
        if (
            b["reading_order"] != a["reading_order"] + 1
            or y[1] < x[1]
            or y[1] - x[3] > height
            or abs(y[0] - x[0]) > height * 2
        ):
            return dict(status="unresolved", reason="paragraph_layout_discontinuous")
    box = [
        min(r["bbox"][0] for r in rows),
        min(r["bbox"][1] for r in rows),
        max(r["bbox"][2] for r in rows),
        max(r["bbox"][3] for r in rows),
    ]
    margin = max(1, min(4, min(r["bbox"][3] - r["bbox"][1] for r in rows) // 8))
    crop = [
        max(0, box[0] - margin),
        max(0, box[1] - margin),
        min(image.width, box[2] + margin),
        min(image.height, box[3] + margin),
    ]

    def intersects(a, b):
        return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])

    if any(r["id"] not in ids and intersects(crop, r["bbox"]) for r in geometry["regions"]):
        return dict(status="unresolved", reason="crop_contains_unselected_region")
    # Reject empty boxes and regions cutting ink at the proposed crop boundary.
    # This is a layout guard, never proof that the recognized words are correct.
    image.inline()
    with Image.open(io.BytesIO(image.content)) as original:
        if original.size != (image.width, image.height):
            return dict(status="unresolved", reason="region_image_dimensions_mismatch")
        pixels = original.convert("L").crop(tuple(crop))
        if pixels.getextrema()[0] >= 160:
            return dict(status="unresolved", reason="region_has_no_visible_ink")
        edges = [
            pixels.crop((0, 0, pixels.width, 1)),
            pixels.crop((0, pixels.height - 1, pixels.width, pixels.height)),
            pixels.crop((0, 0, 1, pixels.height)),
            pixels.crop((pixels.width - 1, 0, pixels.width, pixels.height)),
        ]
        if any(edge.getextrema()[0] < 160 for edge in edges):
            return dict(status="unresolved", reason="region_boundary_cuts_visible_ink")
    return dict(
        status="resolved",
        bbox=crop,
        raw_element_ids=ids,
        reading_order=[r["reading_order"] for r in rows],
        image_sha256=image.sha256,
        coordinate_space="original_image_pixels",
    )


def crop_region(image, resolved):
    if resolved.get("status") != "resolved" or resolved.get("image_sha256") != image.sha256:
        raise ValueError("resolved_region_required")
    image.inline()  # Recheck bytes; no reuse after source replacement.
    with Image.open(io.BytesIO(image.content)) as original:
        if original.size != (image.width, image.height):
            raise ValueError("region_image_dimensions_mismatch")
        cropped = original.crop(tuple(resolved["bbox"]))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        width, height = cropped.size
    content = buffer.getvalue()
    return replace(
        image,
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
        content=content,
        parent_sha256=image.sha256,
        crop_bbox=tuple(resolved["bbox"]),
        source_element_id="|".join(resolved["raw_element_ids"]),
    )
