import { Suspense } from "react";
import { DocumentExplorer } from "@/components/evidence/document-explorer";

export default async function EvidenceDocumentPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <Suspense fallback={<p role="status">Đang tải tài liệu…</p>}>
      <DocumentExplorer key={documentId} documentId={documentId} />
    </Suspense>
  );
}
