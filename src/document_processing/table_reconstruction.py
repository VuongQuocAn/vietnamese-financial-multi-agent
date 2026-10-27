"""Deterministic, evidence-first table structure; không sửa nội dung OCR."""

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from .contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
    UnderstandingIssue,
    UnderstoodCell,
    UnderstoodTable,
)
from .contracts.raw_ocr import OCRPage, OCRTable


@dataclass(frozen=True)
class SpanEvidence:
    """Chú giải caller đã review, bind exact raw cell; không phải prediction.

    Placeholder IDs phải được chú giải riêng, không suy từ text rỗng/bbox trùng.
    Anchors của placeholders được giữ trên merged output cell.
    """

    anchor: SourceAnchor
    rowspan: int
    colspan: int
    placeholder_ids: tuple[str, ...] = ()


def _valid_box(box):
    return box[0] < box[2] and box[1] < box[3]


def _contains(outer, inner):
    return outer[0] <= inner[0] < inner[2] <= outer[2] and (
        outer[1] <= inner[1] < inner[3] <= outer[3]
    )


def _overlaps(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def reconstruct_table(
    page: OCRPage,
    table_id: str,
    *,
    source_ref: str | None = None,
    shape: tuple[int, int] | None = None,
    spans: tuple[SpanEvidence, ...] = (),
) -> UnderstoodTable:
    """Trả DU v1, không I/O/LLM/cache; source_ref do caller bind với đúng page.

    Row/col zero-based. Default extent từ max raw positions + 1; caller cung cấp
    shape đã review khi merged cell vượt extent đó. Không materialize grid lớn.
    Không có evidence merge: mỗi raw cell là candidate 1x1. Chỉ chốt spans khi
    toàn bộ grid/geometry/source nhất quán. Text rỗng là observed empty, không missing.
    """
    identity = RawPageIdentity(
        **{key: getattr(page.page, key) for key in ("symbol", "year", "page", "image")},
        source_ref=source_ref,
    )
    issues: list[UnderstandingIssue] = []

    def add(code, path=(), message="Structure requires review"):
        issues.append(UnderstandingIssue(code=code, path=list(path), message=message))

    def anchor(cell=None):
        return SourceAnchor(
            page=identity.model_copy(deep=True),
            element_id=table_id,
            table_id=table_id,
            cell_id=cell.id if cell is not None else None,
            observed_bbox=list(cell.bbox if cell is not None else table.bbox),
            status="resolved",
        )

    matches = [element for element in page.elements if element.id == table_id]
    if len(matches) != 1 or not isinstance(matches[0], OCRTable):
        return UnderstoodTable(
            id=table_id,
            origin="ocr_table",
            anchors=[SourceAnchor(page=identity, table_id=table_id, status="unresolved")],
            cells=[],
            status="unresolved",
            issues=[
                UnderstandingIssue(
                    code="invalid_table_reference", path=[], message="Expected exactly one OCRTable"
                )
            ],
        )
    table = matches[0]
    if not all(
        value.strip() for value in (identity.symbol, identity.year, identity.image, table.id)
    ):
        add("invalid_source_identity")
    if source_ref is not None and not source_ref.strip():
        add("invalid_source_identity")
    page_box = [0, 0, page.page.width, page.page.height]
    if not _valid_box(table.bbox) or not _contains(page_box, table.bbox):
        add("invalid_table_bbox")
    counts = Counter(cell.id for cell in table.cells)
    by_id = {cell.id: cell for cell in table.cells if counts[cell.id] == 1}
    if any(count != 1 for count in counts.values()):
        add("duplicate_cell_id")
    positions = Counter((cell.row, cell.col) for cell in table.cells)
    if any(count != 1 for count in positions.values()):
        add("duplicate_cell_position")
    if not table.cells:
        add("empty_table")
    if shape is None:
        shape = (
            max((cell.row for cell in table.cells), default=-1) + 1,
            max((cell.col for cell in table.cells), default=-1) + 1,
        )
    if (
        not isinstance(shape, tuple)
        or len(shape) != 2
        or any(type(value) is not int or value <= 0 for value in shape)
    ):
        add("invalid_grid_shape")
        shape = (0, 0)

    accepted: dict[str, SpanEvidence] = {}
    placeholders: dict[str, str] = {}
    evidence_counts = Counter(e.anchor.cell_id for e in spans)
    for evidence in spans:
        cell = by_id.get(evidence.anchor.cell_id)
        if cell is None or evidence_counts[evidence.anchor.cell_id] != 1:
            add("invalid_span_reference")
            continue
        expected = anchor(cell)
        if evidence.anchor != expected:
            add("span_source_mismatch", ("cells", cell.id))
            continue
        if any(type(v) is not int or v <= 0 for v in (evidence.rowspan, evidence.colspan)):
            add("invalid_span", ("cells", cell.id))
            continue
        local = []
        for placeholder_id in evidence.placeholder_ids:
            candidate = by_id.get(placeholder_id)
            if (
                candidate is None
                or placeholder_id == cell.id
                or placeholder_id in local
                or placeholder_id in placeholders
                or placeholder_id in evidence_counts
                or candidate.text != ""
                or candidate.lines
                or candidate.line_count != 0
                or not (cell.row <= candidate.row < cell.row + evidence.rowspan)
                or not (cell.col <= candidate.col < cell.col + evidence.colspan)
                or (candidate.row, candidate.col) == (cell.row, cell.col)
                or not _contains(cell.bbox, candidate.bbox)
            ):
                add("invalid_placeholder", ("cells", cell.id))
                break
            local.append(placeholder_id)
        else:
            accepted[cell.id] = evidence
            placeholders.update(dict.fromkeys(local, cell.id))

    cells = []
    rectangles = []
    for index, raw in enumerate(table.cells):
        path = ("cells", index)
        if not raw.id.strip():
            add("invalid_cell_id", path)
        if raw.row < 0 or raw.col < 0:
            add("negative_cell_position", path)
        if not _valid_box(raw.bbox):
            add("invalid_cell_bbox", path)
        elif not _contains(table.bbox, raw.bbox):
            add("cell_bbox_out_of_bounds", path)
        if set(raw.model_extra or {}) & {"rowspan", "colspan", "is_placeholder", "merged_with"}:
            add("unreviewed_structure_metadata", path)
        if raw.id in placeholders:
            continue
        evidence = accepted.get(raw.id)
        rs, cs = (evidence.rowspan, evidence.colspan) if evidence else (1, 1)
        rect = (raw.col, raw.row, raw.col + cs, raw.row + rs)
        if rect[2] > shape[1] or rect[3] > shape[0]:
            add("span_out_of_bounds", path)
        anchors = [anchor(raw)]
        if evidence:
            anchors.extend(anchor(by_id[pid]) for pid in evidence.placeholder_ids)
        if raw.text == "":
            add("observed_empty_cell", path, "Observed empty text preserved; not a missing cell")
        cells.append(
            UnderstoodCell(
                id=raw.id,
                row=raw.row,
                col=raw.col,
                text=raw.text,
                anchors=anchors,
                status="resolved",
                rowspan=rs,
                colspan=cs,
            )
        )
        rectangles.append((rect, raw))

    collision = False
    for (a, raw_a), (b, raw_b) in combinations(rectangles, 2):
        if _overlaps(a, b):
            collision = True
            add("grid_collision", ("cells", raw_a.id, raw_b.id))
        # Disjoint logical intervals must have consistent physical ordering.
        if (
            (a[2] <= b[0] and raw_a.bbox[2] > raw_b.bbox[0])
            or (b[2] <= a[0] and raw_b.bbox[2] > raw_a.bbox[0])
            or (a[3] <= b[1] and raw_a.bbox[3] > raw_b.bbox[1])
            or (b[3] <= a[1] and raw_b.bbox[3] > raw_a.bbox[1])
        ):
            add("metadata_bbox_conflict", ("cells", raw_a.id, raw_b.id))
    # Area equality proves coverage only for disjoint, in-bounds rectangles.
    invalid_grid = {"negative_cell_position", "span_out_of_bounds", "invalid_grid_shape"}
    if not collision and not any(issue.code in invalid_grid for issue in issues):
        area = sum((r[2] - r[0]) * (r[3] - r[1]) for r, _ in rectangles)
        if area != shape[0] * shape[1]:
            add("missing_grid_positions", message="Grid has gaps; no cells or merges invented")
    unresolved = any(issue.code != "observed_empty_cell" for issue in issues)
    status = "unresolved" if unresolved else "resolved"
    table_anchor = anchor()
    table_anchor.status = status
    for cell in cells:
        cell.status = status
        if unresolved:
            cell.rowspan = cell.colspan = None
        for source in cell.anchors:
            source.status = status
    return UnderstoodTable(
        id=table.id,
        origin="ocr_table",
        anchors=[table_anchor],
        cells=sorted(cells, key=lambda cell: (cell.row, cell.col, cell.id)),
        status=status,
        issues=issues,
    )
