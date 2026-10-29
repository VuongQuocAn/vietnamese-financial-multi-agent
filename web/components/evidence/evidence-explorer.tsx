"use client";

import { useRef, useState } from "react";
import { FileSearch, FileText, Network, ScanSearch } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { FinancialTable } from "@/components/evidence/financial-table";
import { DocumentPicker } from "./document-picker";
import { EvidenceLayout } from "./evidence-layout";

const statements = [
  { id: "B01", label: "Cân đối kế toán" },
  { id: "B02", label: "Kết quả HĐKD" },
  { id: "B03", label: "Lưu chuyển tiền tệ" },
  { id: "B09", label: "Thuyết minh" },
  { id: "graph", label: "Evidence Graph · Sắp ra mắt" },
];

export function EvidenceExplorer() {
  const [tab, setTab] = useState("B01");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <>
      <DocumentPicker />
      <p id="picker-note" className="notice">
        Chọn một tài liệu đã xử lý để khám phá dữ liệu tài chính.
      </p>
      <EvidenceLayout
        pdf={
          <section
            className="pdf-panel panel"
            aria-labelledby="pdf-panel-title"
          >
            <div className="panel-toolbar">
              <FileText size={17} />
              <h2 id="pdf-panel-title">Tài liệu PDF gốc</h2>
              <span className="muted">Chưa có tài liệu</span>
            </div>
            <div className="pdf-canvas">
              <EmptyState
                icon={FileText}
                title="Chưa có PDF để hiển thị"
                description="Tài liệu gốc sẽ xuất hiện tại đây khi bạn chọn một báo cáo."
              />
            </div>
          </section>
        }
      >
        <section
          className="evidence-panel panel"
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
            {statements.map((item, index) => (
              <button
                key={item.id}
                ref={(element) => {
                  tabs.current[index] = element;
                }}
                id={`tab-${item.id}`}
                role="tab"
                aria-selected={tab === item.id}
                aria-controls="statement-panel"
                tabIndex={tab === item.id ? 0 : -1}
                onClick={() => setTab(item.id)}
                onKeyDown={(event) => {
                  let next = index;
                  if (event.key === "ArrowRight")
                    next = (index + 1) % statements.length;
                  else if (event.key === "ArrowLeft")
                    next = (index + statements.length - 1) % statements.length;
                  else if (event.key === "Home") next = 0;
                  else if (event.key === "End") next = statements.length - 1;
                  else return;
                  event.preventDefault();
                  setTab(statements[next].id);
                  tabs.current[next]?.focus();
                }}
              >
                {item.id === "graph"
                  ? item.label
                  : `${item.id} — ${item.label}`}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id="statement-panel"
            aria-labelledby={`tab-${tab}`}
            tabIndex={0}
          >
            {tab === "graph" ? (
              <EmptyState
                icon={Network}
                title="Evidence Graph · Sắp ra mắt"
                description="Đồ thị liên kết bằng chứng sẽ được bổ sung trong các giai đoạn sau."
              />
            ) : tab === "B09" ? (
              <EmptyState
                icon={FileSearch}
                title="Chưa có danh mục trang thuyết minh"
                description="B09 dành cho danh mục trang và xem nguồn PDF; chưa hỗ trợ hỏi đáp thuyết minh."
              />
            ) : (
              <>
                <div className="statement-heading">
                  <h3>{statements.find((item) => item.id === tab)?.label}</h3>
                  <span className="muted">Kỳ báo cáo và đơn vị: chưa có</span>
                </div>
                <FinancialTable periods={[]} rows={[]} />
                <EmptyState
                  icon={ScanSearch}
                  title="Chưa có bằng chứng được chọn"
                  description="Dữ liệu theo kỳ và liên kết nguồn sẽ xuất hiện sau khi xử lý tài liệu."
                />
              </>
            )}
          </div>
          <details className="source-details" open>
            <summary>Chi tiết bằng chứng &amp; Nguồn dẫn</summary>
            <p className="muted">
              Chọn một ô số liệu để xem giá trị gốc, kỳ báo cáo, đơn vị và trang
              nguồn.
            </p>
          </details>
          <details className="source-details">
            <summary>Kiểm tra đối chiếu &amp; Ghi chú</summary>
            <p className="muted">
              Chưa đánh giá. Chỉ hiển thị kết quả khi có kiểm tra thực tế từ
              backend.
            </p>
          </details>
        </section>
      </EvidenceLayout>
    </>
  );
}
