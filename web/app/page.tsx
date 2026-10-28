import { ComingSoonCard } from "@/components/coming-soon";
import { DocumentList } from "@/components/document-list";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function Dashboard() {
  return (
    <div className="page dashboard">
      <div className="page-heading">
        <p className="eyebrow">
          Bàn làm việc tài chính <span>·</span> Dữ liệu có nguồn dẫn
        </p>
        <h1>Chào mừng quay trở lại</h1>
        <p className="page-description">
          Không gian khám phá báo cáo tài chính tiếng Việt, bắt đầu từ tài liệu
          của bạn.
        </p>
      </div>
      <UploadDropzone />
      <DocumentList recent />
      <ComingSoonCard />
    </div>
  );
}
