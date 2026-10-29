"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { api, stateLabels, type DocumentSummary } from "@/lib/documents";

const limit = 20;

export function DocumentPicker({ selectedLabel }: { selectedLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<{
    items: DocumentSummary[];
    total: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const result = await api<{ items: DocumentSummary[]; total: number }>(
          `/documents?offset=${offset}&limit=${limit}`,
        );
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled)
          setError(
            e instanceof Error
              ? e.message
              : "Không tải được danh sách tài liệu.",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, offset, refresh]);

  return (
    <>
      <div className="document-picker panel">
        <FileText size={18} />
        <span className="document-picker-label" title={selectedLabel}>
          {selectedLabel ?? "Chưa chọn tài liệu"}
        </span>
        <button
          className="button secondary"
          aria-expanded={open}
          aria-controls="evidence-document-options"
          onClick={() => setOpen((value) => !value)}
        >
          Chọn tài liệu <ChevronDown size={15} />
        </button>
      </div>
      {open && (
        <section
          id="evidence-document-options"
          className="panel evidence-document-options"
          aria-label="Chọn tài liệu hiện có"
        >
          <h2>Tài liệu hiện có</h2>
          {loading && <p role="status">Đang tải danh sách tài liệu…</p>}
          {error && <p role="alert">{error}</p>}
          {!loading &&
            !error &&
            data &&
            (data.items.length ? (
              <ul>
                {data.items.map((doc) => (
                  <li key={doc.id}>
                    <Link
                      className="text-link"
                      href={`/evidence/${encodeURIComponent(doc.id)}`}
                    >
                      {doc.company_name ?? doc.filename} ·{" "}
                      {doc.reporting_year ?? "Chưa xác định năm"} ·{" "}
                      {doc.filename}
                    </Link>
                    <span className="muted">
                      {stateLabels[doc.state] ?? doc.state}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                Chưa có tài liệu nào.{" "}
                <Link className="text-link" href="/documents">
                  Tải tài liệu PDF
                </Link>
              </p>
            ))}
          <div className="evidence-actions">
            <button
              className="button"
              disabled={loading}
              onClick={() => setRefresh((value) => value + 1)}
            >
              Tải lại danh sách
            </button>
            {data && (
              <>
                <button
                  className="button"
                  disabled={loading || offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                >
                  Danh sách trước
                </button>
                <button
                  className="button"
                  disabled={loading || offset + limit >= data.total}
                  onClick={() => setOffset(offset + limit)}
                >
                  Danh sách tiếp
                </button>
              </>
            )}
          </div>
          <p className="muted">
            Tài liệu chưa trích xuất vẫn mở được PDF; bảng số liệu xuất hiện khi
            có kết quả đã lưu.
          </p>
        </section>
      )}
    </>
  );
}
