"use client";

import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { PdfViewerProps } from "./pdf-viewer";

// Resolve the worker from the same installed PDF.js version as React-PDF.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export default function PdfViewerClient({
  documentId,
  page,
  onPageChange,
}: PdfViewerProps) {
  const [total, setTotal] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [width, setWidth] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const current = Math.max(1, Math.min(total || 1, Math.trunc(page) || 1));
  const file = `/api/documents/${encodeURIComponent(documentId)}/file`;

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(1, entry.contentRect.width - 32)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (total && page !== current) onPageChange(current);
  }, [page, current, total, onPageChange]);

  useEffect(() => {
    viewport.current?.scrollTo(0, 0);
  }, [current]);

  function change(next: number) {
    onPageChange(Math.max(1, Math.min(total, next)));
  }

  return (
    <div
      ref={container}
      className={`pdf-viewer panel ${expanded ? "pdf-expanded" : ""}`}
      tabIndex={0}
      aria-label="Trình xem PDF"
      onKeyDown={(event) => {
        if ((event.target as HTMLElement).closest("input, button, a")) return;
        if (event.key === "Escape") setExpanded(false);
        if (!total) return;
        if (
          [
            "ArrowRight",
            "PageDown",
            "ArrowLeft",
            "PageUp",
            "Home",
            "End",
          ].includes(event.key)
        ) {
          event.preventDefault();
          change(
            event.key === "Home"
              ? 1
              : event.key === "End"
                ? total
                : current +
                  (["ArrowRight", "PageDown"].includes(event.key) ? 1 : -1),
          );
        }
      }}
    >
      <div className="pdf-toolbar">
        <button
          className="button"
          disabled={!total || current === 1}
          onClick={() => change(current - 1)}
        >
          Trang trước
        </button>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const input = event.currentTarget.elements.namedItem(
              "page",
            ) as HTMLInputElement;
            change(Number(input.value) || 1);
            input.value = String(
              Math.max(1, Math.min(total, Number(input.value) || 1)),
            );
          }}
        >
          <label>
            Trang{" "}
            <input
              key={current}
              name="page"
              aria-label="Số trang PDF"
              type="number"
              step="1"
              defaultValue={current}
              disabled={!total}
            />
          </label>
          <span aria-live="polite"> / {total || "…"}</span>
        </form>
        <button
          className="button"
          disabled={!total || current === total}
          onClick={() => change(current + 1)}
        >
          Trang sau
        </button>
        <button
          className="button"
          aria-label="Thu nhỏ"
          disabled={zoom <= 0.5}
          onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
        >
          −
        </button>
        <span aria-label="Mức phóng to">{Math.round(zoom * 100)}%</span>
        <button
          className="button"
          aria-label="Phóng to"
          disabled={zoom >= 3}
          onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
        >
          +
        </button>
        <button className="button" onClick={() => setZoom(1)}>
          Vừa chiều rộng
        </button>
        <button
          className="button"
          aria-pressed={expanded}
          onClick={() => {
            setExpanded(!expanded);
            container.current?.focus();
          }}
        >
          {expanded ? "Thu gọn" : "Mở rộng"}
        </button>
        <a className="text-link" href={file} target="_blank" rel="noreferrer">
          Mở PDF gốc
        </a>
      </div>
      <p className="pdf-hint">
        Số trang PDF gốc (bắt đầu từ 1), có thể khác số trang in. Focus khung
        xem để dùng ← / →, Home / End; Esc thu gọn.
      </p>
      <div ref={viewport} className="pdf-viewport">
        <Document
          key={loadAttempt}
          file={file}
          suspense={false}
          onLoadSuccess={({ numPages }) => setTotal(numPages)}
          onLoadError={(error) => {
            setTotal(0);
            // A no-content response cannot contain a PDF. Retry this transient
            // failure once; subsequent failures remain visible for manual retry.
            if (
              "status" in error &&
              error.status === 204 &&
              loadAttempt === 0
            ) {
              setLoadAttempt(1);
            }
          }}
          loading={<p role="status">Đang tải PDF…</p>}
          error={
            <div>
              <p role="alert">
                Không tải được PDF. Hãy thử lại hoặc dùng liên kết “Mở PDF gốc”.
              </p>
              <button
                className="button"
                onClick={() => setLoadAttempt((n) => n + 1)}
              >
                Thử tải PDF lại
              </button>
            </div>
          }
        >
          {width > 0 && total > 0 && (
            <Page
              key={current}
              suspense={false}
              pageNumber={current}
              width={width * zoom}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              loading={<p role="status">Đang dựng trang {current}…</p>}
              error={
                <p role="alert">
                  Không dựng được trang PDF. Hãy dùng liên kết “Mở PDF gốc”.
                </p>
              }
            />
          )}
        </Document>
      </div>
    </div>
  );
}
