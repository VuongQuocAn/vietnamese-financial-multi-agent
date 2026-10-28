"""Synthetic verification of manual image review, never financial accuracy."""

import copy
import hashlib
import io

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.accounting import ManualReview, link_reviewed_candidate
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    ComponentQuality,
    UnifiedPage,
    UnifiedRegion,
    UnifiedTable,
)
from vietnamese_financial_multi_agent.document_processing.vision_ocr import VerifiedPageImage


@pytest.fixture
def sample():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    content = buffer.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    identity = RawPageIdentity(
        symbol="TEST", year="2025", page=7, image=f"sha256:{digest}", source_ref="synthetic"
    )
    image = VerifiedPageImage(identity, digest, 100, 100, content)
    page = UnifiedPage(
        identity=identity,
        source_type="existing_ocr",
        source_sha256=digest,
        source_references={"identity_checked": True},
        schema_valid=True,
        text_regions=[],
        tables=[
            UnifiedTable(
                source_pointer="/tables/0",
                raw_table_id="table",
                status="unresolved",
                layout_accepted=False,
                source_component={},
                cells=[
                    UnifiedRegion(
                        source_pointer=f"/tables/0/cells/{i}",
                        raw_element_id="table",
                        raw_table_id="table",
                        raw_cell_id=f"cell{i}",
                        provenance_level="cell",
                        text=text,
                        status="accepted",
                        quality=ComponentQuality(text_accepted=True),
                        source_component={"row": 1},
                    )
                    for i, text in enumerate(("Giá vốn hàng bán", "11", "1.234"))
                ],
            )
        ],
        classification={},
        issues=[],
        processing_history=[],
    )

    def cell(text, row, column, bbox):
        return dict(text=text, row=row, column=column, bbox=bbox)

    review = ManualReview(
        image_sha256=digest,
        reviewer="human",
        statement_type="B02",
        statement=cell("BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", 0, 0, [1, 1, 50, 9]),
        unit=cell("Đơn vị tính: VND", 0, 0, [70, 1, 99, 9]),
        label=cell("4. Giá vốn hàng bán", 1, 0, [1, 40, 30, 50]),
        code=cell("11", 1, 1, [40, 40, 50, 50]),
        header=cell("Năm 2025", 0, 2, [70, 20, 95, 30]),
        value=cell("1.234", 1, 2, [70, 40, 95, 50]),
    )

    def candidate(c):
        return {
            "text": c.text,
            "reading": "observed",
            "bbox": None,
            "row": c.row,
            "column": c.column,
        }

    recovery = {
        "source": {"image_sha256": digest},
        "response": {
            "status": "success",
            "finish_reason": "stop",
            "request_id": "synthetic-request",
            "provenance": {"requested_model": {"model": "mock"}},
            "output": {
                "format": "json",
                "payload": {
                    "disposition": "assessed",
                    "text_elements": [],
                    "limitations": [],
                    "tables": [
                        {
                            "rows": 2,
                            "columns": 4,
                            "cells": [
                                candidate(c)
                                for c in (review.label, review.code, review.header, review.value)
                            ],
                        }
                    ],
                },
            },
        },
    }
    return page, image, recovery, review


def test_link_preserves_source_and_does_not_verify_fact(sample):
    page, image, recovery, review = sample
    before = page.model_dump_json()
    result = link_reviewed_candidate(page, image, recovery, review)
    assert result.status == "accepted"
    assert result.result.value.raw_value == "1.234"
    assert result.result.context.period == "2025"
    assert result.result.context.mapped_item_code == "b02.cost_of_sales"
    assert not result.result.financial_fact_verified
    assert all(
        ref.provenance_level == "page" and ref.anchor.observed_bbox
        for ref in result.result.provenance[:6]
    )
    assert all(
        ref.provenance_level == "cell" and ref.anchor.observed_bbox is None
        for ref in result.result.provenance[6:]
    )
    assert page.model_dump_json() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "hallucinated",
        "swapped",
        "code",
        "bbox",
        "source",
        "identity",
        "overlap",
        "ocr",
        "invalid_schema",
        "ocr_page_only",
        "period",
    ],
)
def test_conflicts_remain_unresolved(sample, mutation):
    page, image, recovery, review = sample
    recovery = copy.deepcopy(recovery)
    cells = recovery["response"]["output"]["payload"]["tables"][0]["cells"]
    if mutation == "missing":
        cells.pop()
    elif mutation == "duplicate":
        cells.append(copy.deepcopy(cells[-1]))
    elif mutation == "hallucinated":
        cells[-1]["text"] = "999"
    elif mutation == "swapped":
        cells[-1]["column"] = 3
    elif mutation == "code":
        cells[1]["text"] = "12"
        review = review.model_copy(update={"code": review.code.model_copy(update={"text": "12"})})
    elif mutation == "bbox":
        review = review.model_copy(update={"value": review.value.model_copy(update={"bbox": []})})
    elif mutation == "source":
        recovery["source"]["image_sha256"] = "other"
    elif mutation == "identity":
        page.identity = page.identity.model_copy(update={"image": "sha256:wrong"})
    elif mutation == "ocr":
        page.tables[0].cells[-1].text = "conflict"
    elif mutation == "invalid_schema":
        del cells[-1]["reading"]
    elif mutation == "ocr_page_only":
        page.tables[0].cells[-1].provenance_level = "page"
    elif mutation == "period":
        review = review.model_copy(
            update={"header": review.header.model_copy(update={"column": 3})}
        )
    else:
        review = review.model_copy(
            update={"value": review.value.model_copy(update={"bbox": review.label.bbox})}
        )
    result = link_reviewed_candidate(page, image, recovery, review)
    assert result.status == "unresolved" and result.result is None
