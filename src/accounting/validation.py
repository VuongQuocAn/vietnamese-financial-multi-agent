"""Quality signals riêng với Pydantic structural validation; không sửa dữ liệu."""

from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    UnderstandingIssue,
)

from .contracts import FinancialNormalizationResult


def validate_financial_quality(result: FinancialNormalizationResult) -> list[UnderstandingIssue]:
    issues: list[UnderstandingIssue] = []

    def add(code: str, path: list[str | int], message: str) -> None:
        issues.append(UnderstandingIssue(code=code, path=path, message=message))

    if not result.value.raw_value.strip():
        add("missing_raw_value", ["value", "raw_value"], "Thiếu giá trị gốc.")
    if result.value.normalized_value is None:
        add("missing_normalized_value", ["value", "normalized_value"], "Chưa có giá trị số.")
    if result.value.status != "resolved":
        add("value_not_resolved", ["value", "status"], "Giá trị chưa được xác định rõ.")
    if not result.value.unit or not result.value.unit.strip():
        add("missing_unit", ["value", "unit"], "Chưa xác định đơn vị.")
    for field in (
        "period",
        "period_type",
        "currency",
        "scale",
        "reporting_scope",
        "statement_type",
    ):
        value = getattr(result.context, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            add("missing_context", ["context", field], "Thiếu ngữ cảnh; không tự suy luận.")
    if not result.provenance:
        add("missing_provenance", ["provenance"], "Chưa có tham chiếu nguồn.")
    for index, reference in enumerate(result.provenance):
        anchor = reference.anchor
        path: list[str | int] = ["provenance", index]
        if anchor.status != "resolved" or not anchor.page.source_ref:
            add("provenance_unverified", path, "Trạng thái hoặc identity nguồn chưa đủ.")
        # Không resolve IDs/bbox hoặc coi source_pointer là cell identity.
        if reference.provenance_level == "page":
            add(
                "page_level_provenance",
                path,
                "Nguồn chỉ tới trang; chưa xác minh liên kết giá trị.",
            )
        if (
            (reference.provenance_level == "cell" and not (anchor.table_id and anchor.cell_id))
            or (
                reference.provenance_level == "element"
                and not (anchor.element_id or anchor.table_id)
            )
            or (anchor.cell_id and not anchor.table_id)
            or (anchor.line_id and not (anchor.table_id and anchor.cell_id))
            or (anchor.element_id and anchor.table_id and anchor.element_id != anchor.table_id)
            or (
                reference.provenance_level == "page"
                and any((anchor.element_id, anchor.table_id, anchor.cell_id, anchor.line_id))
            )
        ):
            add("inconsistent_provenance", path, "Mức provenance và IDs chưa nhất quán.")
    return issues
