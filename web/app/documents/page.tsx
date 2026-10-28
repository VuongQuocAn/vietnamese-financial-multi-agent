import { Plus } from "lucide-react";
import { DocumentList } from "@/components/document-list";

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
        <button
          className="button primary"
          disabled
          aria-describedby="documents-upload-note"
        >
          <Plus size={17} />
          Thêm tài liệu
        </button>
      </div>
      <p className="notice" id="documents-upload-note">
        Chức năng thêm tài liệu chưa khả dụng; sẽ được bổ sung trong W-03.
      </p>
      <DocumentList />
    </div>
  );
}
