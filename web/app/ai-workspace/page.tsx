import { ComingSoonPanel } from "@/components/coming-soon";

export default function AiWorkspacePage() {
  return (
    <div className="page">
      <div className="page-heading">
        <p className="eyebrow">Từ bằng chứng đến góc nhìn</p>
        <h1>Trợ lý AI tài chính</h1>
        <p className="page-description">
          Không gian hỏi đáp và phân tích báo cáo tài chính có dẫn nguồn.
        </p>
      </div>
      <ComingSoonPanel />
    </div>
  );
}
