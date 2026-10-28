import { FileUp, Plus } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

export function UploadDropzone() {
  return (
    <section className="upload-zone" aria-labelledby="upload-title">
      <div className="upload-tag">
        <StatusBadge>Tải PDF · Sắp ra mắt</StatusBadge>
      </div>
      <span className="upload-icon">
        <FileUp size={30} strokeWidth={1.6} />
      </span>
      <h2 id="upload-title">Tải báo cáo tài chính lên</h2>
      <p>Khởi đầu hành trình khám phá dữ liệu từ tài liệu gốc của bạn.</p>
      <button
        className="button primary"
        disabled
        aria-describedby="upload-note"
      >
        <Plus size={17} /> Chọn tệp PDF
      </button>
      <p id="upload-note" className="upload-note">
        Chức năng tải PDF sẽ được bổ sung trong W-03. Hiện chưa nhận tệp.
      </p>
    </section>
  );
}
