import { DocumentList } from "@/components/document-list";
import { UploadDropzone } from "@/components/upload-dropzone";

export default function DocumentsPage() {
  return (
    <div className="page">
      <div className="page-heading heading-with-action">
        <div>
          <p className="eyebrow">Không gian làm việc</p>
          <h1>Tài liệu</h1>
          <p className="page-description">
            Quản lý báo cáo tài chính và theo dõi trạng thái xử lý.
          </p>
        </div>
      </div>
      <UploadDropzone />
      <DocumentList />
    </div>
  );
}
