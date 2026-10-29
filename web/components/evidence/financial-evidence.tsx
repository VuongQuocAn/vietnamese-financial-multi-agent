"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/documents";
import { type EvidencePage, groupEvidence } from "@/lib/evidence";
import { FinancialTable } from "./financial-table";
import { type EvidenceSelection } from "./source-details";

export function FinancialEvidence({
  documentId,
  attemptId,
  statement,
  metadataRevision,
  selection,
  onSelect,
}: {
  documentId: string;
  attemptId: string;
  statement: string;
  metadataRevision: number;
  selection: EvidenceSelection | null;
  onSelect: (selection: EvidenceSelection) => void;
}) {
  const [data, setData] = useState<EvidencePage | null>(null);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    const path = `/documents/${encodeURIComponent(documentId)}/evidence?attempt_id=${encodeURIComponent(attemptId)}&statement=${statement}&limit=100&offset=`;
    async function load() {
      setLoading(true);
      setError("");
      try {
        let next = await api<EvidencePage>(path + offset);
        const validate = (value: EvidencePage) => {
          if (
            value.document_id !== documentId ||
            value.attempt_id !== attemptId
          )
            throw new Error(
              "Dữ liệu không thuộc phiên đang xem. Hãy tải lại dữ liệu.",
            );
        };
        validate(next);
        if (cancelled) return;
        if (
          offset > 0 &&
          data &&
          (next.snapshot_revision !== data.snapshot_revision ||
            next.metadata_revision !== data.metadata_revision)
        ) {
          // Read the first slice of the new snapshot instead of mixing revisions.
          next = await api<EvidencePage>(path + 0);
          validate(next);
          if (cancelled) return;
          setData(next);
        } else {
          setData((previous) =>
            offset === 0
              ? next
              : { ...next, items: [...(previous?.items ?? []), ...next.items] },
          );
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Không tải được evidence.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
    // data is the already loaded slice; a new slice is requested only by user action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, attemptId, statement, offset, refresh]);
  const grouped = groupEvidence(data?.items ?? []);
  return (
    <div>
      {data && (
        <p className="muted">
          {data.items.length}/{data.total} observations · Metadata revision{" "}
          {data.metadata_revision} · Snapshot revision {data.snapshot_revision}
        </p>
      )}
      {data && data.metadata_revision !== metadataRevision && (
        <p role="status" className="notice">
          Metadata phiên cũ — dữ liệu không thuộc metadata hiện hành.
        </p>
      )}
      {data &&
        selection?.attemptId === attemptId &&
        selection.snapshotRevision !== data.snapshot_revision && (
          <p role="status" className="notice">
            Chi tiết đang chọn thuộc snapshot {selection.snapshotRevision}. Chọn
            lại ô để xem nguồn của snapshot {data.snapshot_revision}.
          </p>
        )}
      {data && data.invalid_pages.length > 0 && (
        <p role="status" className="notice">
          Kết quả một phần: trang chưa hợp lệ{" "}
          {data.invalid_pages.map((p) => p.pdf_page).join(", ")}. Các số liệu đã
          lưu vẫn được hiển thị.
        </p>
      )}
      {error && (
        <p role="alert" className="notice error-message">
          {error}
        </p>
      )}
      {loading && <p role="status">Đang tải evidence…</p>}
      <p className="muted">
        Giá trị gốc; không tự quy đổi đơn vị. Quality không chứng minh độ chính
        xác tài chính.
      </p>
      <FinancialTable
        {...grouped}
        selectedCellId={
          selection?.attemptId === attemptId ? selection.item.evidence_id : null
        }
        onSelect={({ rowKey, cellId }) => {
          const item = data?.items.find(
            (i) => i.evidence_id === (cellId ?? rowKey),
          );
          if (item && data)
            onSelect({
              item,
              attemptId,
              metadataRevision: data.metadata_revision,
              snapshotRevision: data.snapshot_revision,
            });
        }}
      />
      <div className="evidence-actions">
        {data && data.items.length < data.total && (
          <button
            className="button"
            disabled={loading}
            onClick={() => {
              const nextOffset = data.items.length;
              if (nextOffset === offset) setRefresh((r) => r + 1);
              else setOffset(nextOffset);
            }}
          >
            Tải thêm số liệu
          </button>
        )}
        <button
          className="button"
          disabled={loading}
          onClick={() => {
            setOffset(0);
            setRefresh((r) => r + 1);
          }}
        >
          Tải lại số liệu
        </button>
      </div>
    </div>
  );
}
