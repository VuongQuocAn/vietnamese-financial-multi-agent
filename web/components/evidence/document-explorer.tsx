"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { api, type Document } from "@/lib/documents";
import { PdfViewer } from "./pdf-viewer";

type InventoryPage = {
  pdf_page: number;
  statement_type: string | null;
  classification: string;
  uncertainty: string | null;
};
const groups = [
  ["B01", "B01 — Bảng cân đối kế toán"],
  ["B02", "B02 — Kết quả hoạt động kinh doanh"],
  ["B03", "B03 — Lưu chuyển tiền tệ"],
  ["B09", "B09 — Thuyết minh"],
  ["other", "Khác / Chưa xác định"],
];

export function DocumentExplorer({ documentId }: { documentId: string }) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [error, setError] = useState("");
  const [pages, setPages] = useState<InventoryPage[]>([]);
  const [inventoryMessage, setInventoryMessage] = useState(
    "Đang tải danh mục trang…",
  );
  const params = useSearchParams();
  const pathname = usePathname();
  const parsed = Number(params.get("page") ?? 1);
  const page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  const changePage = useCallback(
    (next: number) => {
      const query = new URLSearchParams(window.location.search);
      if (query.get("page") === String(next)) return;
      query.set("page", String(next));
      window.history.replaceState(null, "", `${pathname}?${query}`);
    },
    [pathname],
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const value = await api<Document>(
          `/documents/${encodeURIComponent(documentId)}`,
        );
        if (cancelled) return;
        setDoc(value);
        if (value.job?.operation !== "extract") {
          setInventoryMessage(
            "Chưa có danh mục trích xuất. Bạn vẫn có thể xem mọi trang PDF.",
          );
          return;
        }
        try {
          const inventory = await api<{ pages: InventoryPage[] }>(
            `/documents/${encodeURIComponent(documentId)}/inventory?attempt_id=${encodeURIComponent(value.job.id)}`,
          );
          if (cancelled) return;
          setPages(inventory.pages);
          setInventoryMessage(
            inventory.pages.length
              ? ""
              : "Chưa có trang được phân loại. Điều hướng PDF thủ công vẫn hoạt động.",
          );
        } catch {
          if (!cancelled)
            setInventoryMessage(
              "Danh mục trang chưa sẵn sàng. Bạn vẫn có thể xem PDF và tải lại trang sau.",
            );
        }
      } catch {
        if (!cancelled)
          setError(
            "Không tải được thông tin tài liệu. Vui lòng kiểm tra tài liệu và kết nối backend.",
          );
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  return (
    <div className="page">
      <Link
        className="text-link"
        href={`/documents/${encodeURIComponent(documentId)}`}
      >
        ← Thông tin tài liệu
      </Link>
      <div className="page-heading">
        <p className="eyebrow">Document Explorer</p>
        <h1>{doc?.metadata.values.company_name ?? "Xem tài liệu PDF"}</h1>
        {doc && (
          <p className="page-description document-filename">
            {doc.metadata.values.reporting_year ?? "Chưa xác định năm"} ·{" "}
            {doc.filename}
          </p>
        )}
      </div>
      {error && (
        <p role="alert" className="notice error-message">
          {error}
        </p>
      )}
      <div className="document-explorer">
        <aside className="panel inventory-panel" aria-label="Danh mục trang">
          <h2>Điều hướng theo biểu</h2>
          {inventoryMessage && <p role="status">{inventoryMessage}</p>}
          {groups.map(([code, label]) => (
            <section key={code}>
              <h3>{label}</h3>
              <div className="inventory-pages">
                {pages
                  .filter((p) => {
                    const group =
                      p.classification === "uncertain" ||
                      p.uncertainty ||
                      !groups
                        .slice(0, 4)
                        .some(([key]) => key === p.statement_type)
                        ? "other"
                        : p.statement_type;
                    return group === code;
                  })
                  .map((p) => (
                    <button
                      key={p.pdf_page}
                      className="button"
                      aria-current={page === p.pdf_page ? "page" : undefined}
                      onClick={() => changePage(p.pdf_page)}
                    >
                      Trang {p.pdf_page}
                    </button>
                  ))}
              </div>
            </section>
          ))}
          <p className="muted">
            B09 chỉ là danh mục trang; chưa trích xuất nội dung thuyết minh.
            Phân loại AI chưa được xác minh.
          </p>
        </aside>
        <PdfViewer
          documentId={documentId}
          page={page}
          onPageChange={changePage}
        />
      </div>
    </div>
  );
}
