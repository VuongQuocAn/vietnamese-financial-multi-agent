"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Files } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { api, stateLabels, type DocumentSummary } from "@/lib/documents";

export function DocumentList({ recent = false }: { recent?: boolean }) {
  const [data, setData] = useState<{
    items: DocumentSummary[];
    total: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const limit = recent ? 5 : 20;
  useEffect(() => {
    let cancelled = false;
    api<{ items: DocumentSummary[]; total: number }>(
      `/documents?offset=${offset}&limit=${limit}`,
    )
      .then((value) => {
        if (!cancelled) {
          setData(value);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [offset, limit, reload]);
  return (
    <section aria-labelledby="documents-title">
      <div className="section-heading">
        <h2 id="documents-title">
          {recent ? "Tài liệu gần đây" : "Danh sách tài liệu"}
        </h2>
        {recent && (
          <Link className="text-link" href="/documents">
            Xem tất cả <ArrowRight size={15} />
          </Link>
        )}
      </div>
      <div className="panel document-list">
        <div className="document-columns" aria-hidden="true">
          <span>Tên tài liệu</span>
          <span>Kỳ báo cáo</span>
          <span>Trạng thái xử lý</span>
          <span>Thao tác</span>
        </div>
        {error ? (
          <div className="list-feedback">
            <p role="alert">{error}</p>
            <button className="button" onClick={() => setReload(reload + 1)}>
              Thử lại
            </button>
          </div>
        ) : !data ? (
          <p className="list-feedback" role="status">
            Đang tải danh sách…
          </p>
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={Files}
            title="Chưa có tài liệu nào."
            description="Tài liệu và trạng thái xử lý sẽ xuất hiện tại đây sau khi tải lên."
          />
        ) : (
          data.items.map((doc) => (
            <div className="document-row" key={doc.id}>
              <Link href={`/documents/${doc.id}`} className="document-filename">
                {doc.filename}
                {doc.company_name && <small>{doc.company_name}</small>}
              </Link>
              <span>{doc.reporting_year ?? "Chưa xác nhận"}</span>
              <span>{stateLabels[doc.state] ?? doc.state}</span>
              <Link href={`/documents/${doc.id}`} className="text-link">
                Xem thông tin <ArrowRight size={15} />
              </Link>
            </div>
          ))
        )}
      </div>
      {!recent && data && data.total > limit && (
        <div className="form-actions">
          <button
            className="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Trang trước
          </button>
          <span>
            {offset + 1}–{Math.min(offset + limit, data.total)} / {data.total}
          </span>
          <button
            className="button"
            disabled={offset + limit >= data.total}
            onClick={() => setOffset(offset + limit)}
          >
            Trang sau
          </button>
        </div>
      )}
    </section>
  );
}
