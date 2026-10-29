"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { api, type Document } from "@/lib/documents";
import { validSourcePage } from "@/lib/evidence";
import { PdfViewer } from "./pdf-viewer";
import { FinancialEvidence } from "./financial-evidence";
import { SourceDetails, type EvidenceSelection } from "./source-details";
import { DocumentPicker } from "./document-picker";
import { EvidenceLayout } from "./evidence-layout";
import { FileText, ScanSearch } from "lucide-react";

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
  ["graph", "Evidence Graph · Sắp ra mắt"],
];

export function DocumentExplorer({ documentId }: { documentId: string }) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [error, setError] = useState("");
  const [pages, setPages] = useState<InventoryPage[]>([]);
  const [inventoryMessage, setInventoryMessage] = useState(
    "Đang tải danh mục trang…",
  );
  const [inventoryRevision, setInventoryRevision] = useState<number | null>(
    null,
  );
  const [refresh, setRefresh] = useState(0);
  const [tab, setTab] = useState("B01");
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const params = useSearchParams();
  const pathname = usePathname();
  const parsed = Number(params.get("page") ?? 1);
  const page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  const attemptId =
    doc?.latest_result?.attempt_id ??
    (doc?.job?.operation === "extract" ? doc.job.id : null);
  const visibleSelection =
    selection?.attemptId === attemptId ? selection : null;
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
      setError("");
      setPages([]);
      setInventoryRevision(null);
      setInventoryMessage("Đang tải danh mục trang…");
      try {
        const value = await api<Document>(
          `/documents/${encodeURIComponent(documentId)}`,
        );
        if (cancelled) return;
        setDoc(value);
        const attempt =
          value.latest_result?.attempt_id ??
          (value.job?.operation === "extract" ? value.job.id : null);
        if (!attempt) {
          setInventoryMessage(
            "Chưa có danh mục trích xuất. Bạn vẫn có thể xem mọi trang PDF.",
          );
          return;
        }
        try {
          const inventory = await api<{
            pages: InventoryPage[];
            metadata_revision: number;
          }>(
            `/documents/${encodeURIComponent(documentId)}/inventory?attempt_id=${encodeURIComponent(attempt)}`,
          );
          if (cancelled) return;
          setPages(inventory.pages);
          setInventoryRevision(inventory.metadata_revision);
          setInventoryMessage(
            inventory.pages.length
              ? ""
              : "Chưa có trang được phân loại. Điều hướng PDF thủ công vẫn hoạt động.",
          );
        } catch {
          if (!cancelled)
            setInventoryMessage(
              "Danh mục trang chưa sẵn sàng hoặc tải lỗi. Bạn vẫn có thể xem PDF và tải lại dữ liệu.",
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
  }, [documentId, refresh]);

  return (
    <div className="page explorer-page">
      <div className="page-heading">
        <p className="eyebrow">Tài liệu gốc &amp; bằng chứng</p>
        <h1>Khám phá dữ liệu</h1>
        <p className="page-description">
          Đọc báo cáo và khám phá bằng chứng tài chính trong cùng một không
          gian.
        </p>
      </div>
      <DocumentPicker
        selectedLabel={
          doc
            ? `${doc.metadata.values.company_name ?? doc.filename} · ${doc.metadata.values.reporting_year ?? "Chưa xác định năm"}`
            : "Đang tải tài liệu…"
        }
      />
      <div className="explorer-document-actions">
        <Link
          className="text-link"
          href={`/documents/${encodeURIComponent(documentId)}`}
        >
          Thông tin tài liệu
        </Link>
        <button
          className="button secondary"
          onClick={() => setRefresh((r) => r + 1)}
        >
          Tải lại dữ liệu
        </button>
      </div>
      {error && (
        <p role="alert" className="notice error-message">
          {error}
        </p>
      )}
      {doc &&
        ["partial", "failed", "interrupted", "queued", "processing"].includes(
          doc.state,
        ) && (
          <p role="status" className="notice">
            Trạng thái: {doc.state}. Hiển thị snapshot đã lưu nếu có; kết quả có
            thể chưa đầy đủ. Tải lại thủ công để cập nhật.
          </p>
        )}
      <EvidenceLayout
        pdf={
          <section className="panel pdf-source-panel">
            <div className="panel-toolbar">
              <FileText size={17} />
              <h2>Tài liệu PDF gốc</h2>
              <span className="muted document-filename">{doc?.filename}</span>
            </div>
            <PdfViewer
              documentId={documentId}
              page={page}
              onPageChange={changePage}
            />
          </section>
        }
      >
        <section
          className="panel evidence-panel evidence-content"
          aria-labelledby="financial-panel-title"
        >
          <div className="panel-toolbar">
            <ScanSearch size={17} />
            <h2 id="financial-panel-title">Bằng chứng tài chính</h2>
          </div>
          <div
            className="statement-tabs"
            role="tablist"
            aria-label="Loại báo cáo"
          >
            {groups.map(([code, label], index) => (
              <button
                key={code}
                ref={(node) => {
                  tabs.current[index] = node;
                }}
                role="tab"
                id={`tab-${code}`}
                aria-controls="financial-panel"
                aria-selected={tab === code}
                tabIndex={tab === code ? 0 : -1}
                onClick={() => setTab(code)}
                onKeyDown={(event) => {
                  let next = index;
                  if (event.key === "ArrowRight")
                    next = (index + 1) % groups.length;
                  else if (event.key === "ArrowLeft")
                    next = (index + groups.length - 1) % groups.length;
                  else if (event.key === "Home") next = 0;
                  else if (event.key === "End") next = groups.length - 1;
                  else return;
                  event.preventDefault();
                  setTab(groups[next][0]);
                  tabs.current[next]?.focus();
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div
            id="financial-panel"
            role="tabpanel"
            aria-labelledby={`tab-${tab}`}
          >
            <div className="statement-heading">
              <h3>{groups.find(([code]) => code === tab)?.[1]}</h3>
            </div>
            {tab === "graph" ? (
              <p className="notice">Evidence Graph · Sắp ra mắt</p>
            ) : tab === "B09" ? (
              <p className="notice">
                Chưa trích xuất nội dung thuyết minh. B09 chỉ hiển thị danh mục
                trang.
              </p>
            ) : tab === "other" ? (
              <p>Danh mục trang khác / chưa xác định.</p>
            ) : attemptId && doc ? (
              <FinancialEvidence
                key={`${documentId}:${attemptId}:${tab}:${refresh}`}
                documentId={documentId}
                attemptId={attemptId}
                statement={tab}
                metadataRevision={doc.metadata_revision}
                selection={visibleSelection}
                onSelect={(next) => {
                  setSelection(next);
                  const source = next.item.sources.find((s) =>
                    validSourcePage(s.pdf_page),
                  );
                  if (source && validSourcePage(source.pdf_page))
                    changePage(source.pdf_page);
                }}
              />
            ) : (
              <p>Chưa có dữ liệu tài chính được trích xuất. PDF vẫn mở được.</p>
            )}
            <details
              className="explorer-inventory"
              open={tab === "B09" || tab === "other"}
              hidden={tab === "graph"}
            >
              <summary>Danh mục trang nguồn</summary>
              <aside className="inventory-panel" aria-label="Danh mục trang">
                <h2>Điều hướng theo biểu</h2>
                {inventoryMessage && <p role="status">{inventoryMessage}</p>}
                {inventoryRevision !== null &&
                  inventoryRevision !== doc?.metadata_revision && (
                    <p className="notice">
                      Metadata phiên cũ — danh mục thuộc revision{" "}
                      {inventoryRevision}.
                    </p>
                  )}
                {groups
                  .filter(([code]) => code !== "graph")
                  .map(([code, label]) => (
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
                              aria-current={
                                page === p.pdf_page ? "page" : undefined
                              }
                              onClick={() => changePage(p.pdf_page)}
                            >
                              Trang {p.pdf_page}
                            </button>
                          ))}
                      </div>
                    </section>
                  ))}
                <p className="muted">
                  B09 chỉ là danh mục trang; chưa trích xuất nội dung thuyết
                  minh. Phân loại AI chưa được xác minh.
                </p>
              </aside>
            </details>
          </div>
          <SourceDetails
            selection={visibleSelection}
            page={page}
            onPageChange={changePage}
            metadataRevision={doc?.metadata_revision}
          />
        </section>
      </EvidenceLayout>
    </div>
  );
}
