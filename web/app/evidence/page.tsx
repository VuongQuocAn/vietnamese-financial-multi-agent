import { EvidenceExplorer } from "@/components/evidence/evidence-explorer";

export default function EvidencePage() {
  return (
    <div className="page explorer-page">
      <div className="page-heading">
        <p className="eyebrow">Tài liệu gốc & bằng chứng</p>
        <h1>Khám phá dữ liệu</h1>
        <p className="page-description">
          Đọc báo cáo và khám phá bằng chứng tài chính trong cùng một không
          gian.
        </p>
      </div>
      <EvidenceExplorer />
    </div>
  );
}
