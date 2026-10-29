"use client";

import dynamic from "next/dynamic";
import { Component, Suspense, type ReactNode } from "react";

export type PdfViewerProps = {
  documentId: string;
  page: number;
  onPageChange: (page: number) => void;
};

const ClientViewer = dynamic(() => import("./pdf-viewer-client"), {
  ssr: false,
  loading: () => <p role="status">Đang tải trình xem PDF…</p>,
});

export function PdfViewer(props: PdfViewerProps) {
  return (
    <ViewerErrorBoundary key={props.documentId} documentId={props.documentId}>
      <Suspense fallback={<p role="status">Đang tải PDF…</p>}>
        <ClientViewer {...props} />
      </Suspense>
    </ViewerErrorBoundary>
  );
}

class ViewerErrorBoundary extends Component<
  { documentId: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="panel metadata-section">
          <p role="alert">
            Không tải được PDF. Vui lòng thử tải lại hoặc mở PDF gốc.
          </p>
          <a
            className="text-link"
            href={`/api/documents/${encodeURIComponent(this.props.documentId)}/file`}
            target="_blank"
            rel="noreferrer"
          >
            Mở PDF gốc
          </a>
        </div>
      );
    return this.props.children;
  }
}
