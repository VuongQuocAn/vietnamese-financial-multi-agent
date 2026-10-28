"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/ui/status-badge";

// Presentation props only, not a replacement for the W-01 API DTO.
// Values are source strings; this component never parses, scales or formats them.
export type FinancialPeriod = { key: string; label: string };
export type FinancialCell = {
  id: string;
  rawValue: string | null;
  statuses?: string[];
};
export type FinancialRow = {
  key: string;
  sourceItemCode: string | null;
  rawLabel: string;
  cells: Record<string, FinancialCell | undefined>;
  statuses?: string[];
};

export function FinancialTable({
  periods,
  rows,
  onSelect,
}: {
  periods: FinancialPeriod[];
  rows: FinancialRow[];
  onSelect?: (selection: { rowKey: string; cellId: string | null }) => void;
}) {
  const [selected, setSelected] = useState<{
    rowKey: string;
    cellId: string | null;
  } | null>(null);
  function select(rowKey: string, cellId: string | null) {
    const next = { rowKey, cellId };
    setSelected(next);
    onSelect?.(next);
  }
  return (
    <div
      className="financial-table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Bảng bằng chứng tài chính, có thể cuộn ngang"
    >
      <table className="financial-table">
        <caption className="sr-only">
          Số liệu nguyên bản theo kỳ báo cáo
        </caption>
        <thead>
          <tr>
            <th scope="col">Mã số</th>
            <th scope="col">Chỉ tiêu tài chính</th>
            {periods.map((period) => (
              <th scope="col" className="numeric" key={period.key}>
                {period.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={periods.length + 2} className="table-empty">
                Chưa có dữ liệu tài chính.
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.key} data-selected={selected?.rowKey === row.key}>
                <td>{row.sourceItemCode ?? "—"}</td>
                <th scope="row">
                  <button
                    className="row-select"
                    aria-pressed={
                      selected?.rowKey === row.key && selected.cellId === null
                    }
                    onClick={() => select(row.key, null)}
                  >
                    {row.rawLabel}
                  </button>
                  {row.statuses?.map((status) => (
                    <StatusBadge key={status} tone="warning">
                      {status}
                    </StatusBadge>
                  ))}
                </th>
                {periods.map((period) => {
                  const cell = row.cells[period.key];
                  return (
                    <td className="numeric" key={period.key}>
                      {cell ? (
                        <button
                          className="cell-select"
                          data-selected={selected?.cellId === cell.id}
                          aria-pressed={selected?.cellId === cell.id}
                          onClick={() => select(row.key, cell.id)}
                          aria-label={`${row.rawLabel}, ${period.label}: ${cell.rawValue === null || cell.rawValue === "" ? "Thiếu" : cell.rawValue}`}
                        >
                          <span className="raw-value">
                            {cell.rawValue === null || cell.rawValue === ""
                              ? "Thiếu"
                              : cell.rawValue}
                          </span>
                          {cell.statuses?.map((status) => (
                            <StatusBadge key={status} tone="warning">
                              {status}
                            </StatusBadge>
                          ))}
                        </button>
                      ) : (
                        <span className="muted">Thiếu</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
