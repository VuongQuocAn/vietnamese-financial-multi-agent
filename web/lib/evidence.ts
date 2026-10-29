export type EvidenceSource = {
  content_id: string;
  pdf_page: number | null;
  source_pointer: string | null;
  provenance_level: string;
};
export type EvidenceItem = {
  evidence_id: string;
  source_item_code: string | null;
  canonical_item_id: string | null;
  raw_label: string;
  raw_header: string | null;
  value: {
    raw_value: string | null;
    normalized_value: string | null;
    unit: string | null;
    status: string;
    issues: string[];
  };
  context: {
    period: string | null;
    period_type: string | null;
    currency: string | null;
    scale: string | null;
    reporting_scope: string | null;
    statement_type: string | null;
    mapped_item_code?: string | null;
  };
  binding: { table: number; row: number; column: number } | null;
  sources: EvidenceSource[];
  extraction_issues: string[];
  quality: {
    decision: string;
    caveats: string[];
    issues: { code: string; detail: string }[];
  };
  financial_fact_verified: boolean;
};
export type EvidencePage = {
  document_id: string;
  attempt_id: string;
  metadata_revision: number;
  snapshot_revision: number;
  items: EvidenceItem[];
  invalid_pages: { pdf_page: number; issues: string[] }[];
  offset: number;
  limit: number;
  total: number;
};
export const qualityLabels: Record<string, string> = {
  usable: "Có thể sử dụng",
  usable_with_caveat: "Có lưu ý",
  insufficient: "Chưa đủ cơ sở",
  conflicted: "Xung đột — giá trị ứng viên",
};
export const unknown = "Chưa xác định";
export function contextLabel(item: EvidenceItem) {
  const c = item.context;
  return [
    c.period ?? unknown,
    c.period_type ?? unknown,
    c.reporting_scope ?? unknown,
    `Tiền tệ: ${c.currency ?? unknown}`,
    `Đơn vị: ${item.value.unit ?? unknown}`,
    `Scale: ${c.scale ?? unknown}`,
    item.raw_header === null ? null : `Header gốc: ${item.raw_header}`,
  ]
    .filter((v) => v !== null)
    .join(" · ");
}

// Each observation remains addressable; grouping never relies on item code alone.
export function groupEvidence(items: EvidenceItem[]) {
  const periods = new Map<
    string,
    { key: string; label: string; detail: string; unitLabel: string }
  >();
  const rows: {
    key: string;
    sourceItemCode: string | null;
    rawLabel: string;
    cells: Record<
      string,
      { id: string; rawValue: string | null; statuses: string[] }
    >;
  }[] = [];
  const boundRows = new Map<string, (typeof rows)[number]>();
  for (const item of items) {
    const c = item.context;
    const periodKey = JSON.stringify([
      c.period,
      c.period_type,
      c.reporting_scope,
      c.currency,
      c.scale,
      item.value.unit,
      item.raw_header,
      item.binding?.column ?? null,
    ]);
    periods.set(periodKey, {
      key: periodKey,
      label: item.raw_header || c.period || unknown,
      detail: contextLabel(item),
      unitLabel: [
        item.value.unit ?? c.currency ?? unknown,
        `Scale: ${c.scale ?? unknown}`,
        c.reporting_scope,
      ]
        .filter(Boolean)
        .join(" · "),
    });
    const pages = [
      ...new Set(
        item.sources.map((s) => JSON.stringify([s.content_id, s.pdf_page])),
      ),
    ].sort();
    const bound =
      item.binding &&
      pages.length > 0 &&
      item.sources.every((s) => validSourcePage(s.pdf_page));
    const rowKey = bound
      ? JSON.stringify([
          pages,
          item.binding!.table,
          item.binding!.row,
          item.source_item_code,
          item.raw_label,
          c.statement_type,
          c.reporting_scope,
          c.currency,
          c.scale,
          item.value.unit,
        ])
      : item.evidence_id;
    let row = boundRows.get(rowKey);
    // A repeated slot is another observation, never an overwrite or chosen winner.
    if (!row || row.cells[periodKey]) {
      row = {
        key: item.evidence_id,
        sourceItemCode: item.source_item_code,
        rawLabel: item.raw_label,
        cells: {},
      };
      rows.push(row);
      if (!boundRows.has(rowKey)) boundRows.set(rowKey, row);
    }
    row.cells[periodKey] = {
      id: item.evidence_id,
      rawValue: item.value.raw_value,
      statuses: [qualityLabels[item.quality.decision] ?? item.quality.decision],
    };
  }
  return { periods: [...periods.values()], rows };
}
export function validSourcePage(page: number | null): page is number {
  return page !== null && Number.isSafeInteger(page) && page >= 1;
}
