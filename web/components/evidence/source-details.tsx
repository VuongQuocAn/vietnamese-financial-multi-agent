"use client";

import {
  type EvidenceItem,
  qualityLabels,
  unknown,
  validSourcePage,
} from "@/lib/evidence";

export type EvidenceSelection = {
  item: EvidenceItem;
  attemptId: string;
  metadataRevision: number;
  snapshotRevision: number;
};

export function SourceDetails({
  selection,
  onPageChange,
  page,
  metadataRevision,
}: {
  selection: EvidenceSelection | null;
  onPageChange: (page: number) => void;
  page: number;
  metadataRevision?: number;
}) {
  if (!selection)
    return (
      <section className="panel source-details">
        <h2>Chi tiết bằng chứng &amp; Nguồn dẫn</h2>
        <p>Chọn một ô số liệu để xem giá trị và nguồn.</p>
      </section>
    );
  const { item, attemptId, snapshotRevision } = selection;
  const c = item.context;
  const fields = [
    ["Chỉ tiêu gốc", item.raw_label],
    ["Mã chỉ tiêu", item.source_item_code],
    ["Header gốc", item.raw_header],
    [
      "Raw value",
      item.value.raw_value === "" ? "Chuỗi rỗng (thiếu)" : item.value.raw_value,
    ],
    ["Normalized value", item.value.normalized_value],
    ["Trạng thái giá trị", item.value.status],
    ["Kỳ", c.period],
    ["Loại kỳ", c.period_type],
    ["Currency", c.currency],
    ["Unit", item.value.unit],
    ["Scale gốc", c.scale],
    ["Reporting scope", c.reporting_scope],
    ["Biểu", c.statement_type],
    ["Canonical ID", item.canonical_item_id],
    ["Mapped item code", c.mapped_item_code],
    ["Quality", qualityLabels[item.quality.decision] ?? item.quality.decision],
    [
      "Financial fact",
      item.financial_fact_verified ? "Đã xác minh" : "Chưa xác minh",
    ],
  ];
  return (
    <section className="panel source-details" aria-label="Chi tiết nguồn">
      <h2>Chi tiết bằng chứng &amp; Nguồn dẫn</h2>
      {metadataRevision !== selection.metadataRevision && (
        <p className="notice" role="status">
          Metadata phiên cũ — bằng chứng thuộc revision{" "}
          {selection.metadataRevision}.
        </p>
      )}
      <dl className="source-fields">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value ?? unknown}</dd>
          </div>
        ))}
      </dl>
      {!item.sources.some((s) => validSourcePage(s.pdf_page)) && (
        <p>Chưa có liên kết trang nguồn</p>
      )}
      <ul className="source-list">
        {item.sources.map((source, index) => (
          <li key={index}>
            {validSourcePage(source.pdf_page) ? (
              <button
                className="button"
                aria-current={page === source.pdf_page ? "page" : undefined}
                onClick={() => onPageChange(source.pdf_page!)}
              >
                Nguồn {index + 1} · PDF trang {source.pdf_page}
              </button>
            ) : (
              <span>Chưa có liên kết trang nguồn</span>
            )}
            <span> · {source.provenance_level}</span>
            <details>
              <summary>Source pointer</summary>
              <code>{source.source_pointer ?? unknown}</code>
              <p>Content ID: {source.content_id}</p>
            </details>
          </li>
        ))}
      </ul>
      <h3>Caveats và issues</h3>
      <ul>
        {[
          ...item.quality.caveats,
          ...item.quality.issues.map(
            (issue) => `${issue.code}: ${issue.detail}`,
          ),
          ...item.extraction_issues,
          ...item.value.issues,
        ].map((issue, index) => (
          <li key={index}>{issue}</li>
        ))}
      </ul>
      {!item.quality.caveats.length &&
        !item.quality.issues.length &&
        !item.extraction_issues.length &&
        !item.value.issues.length && <p>Không có ghi chú được trả về.</p>}
      <details>
        <summary>Phiên dữ liệu và binding</summary>
        <p>
          Attempt: {attemptId} · Metadata revision: {selection.metadataRevision}{" "}
          · Snapshot revision: {snapshotRevision}
        </p>
        <p>Evidence: {item.evidence_id}</p>
        <p>
          Binding:{" "}
          {item.binding
            ? `table ${item.binding.table} / row ${item.binding.row} / column ${item.binding.column}`
            : unknown}
        </p>
      </details>
    </section>
  );
}
