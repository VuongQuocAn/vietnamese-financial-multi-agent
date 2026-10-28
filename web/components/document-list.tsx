import Link from "next/link";
import { ArrowRight, Files } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

export function DocumentList({ recent = false }: { recent?: boolean }) {
  return (
    <section aria-labelledby="documents-title">
      <div className="section-heading">
        <h2 id="documents-title">
          {recent ? "Tài liệu gần đây" : "Danh sách tài liệu"}
        </h2>
        {recent && (
          <Link className="text-link" href="/documents">
            Xem tất cả <ArrowRight size={15} />
          </Link>
        )}
      </div>
      <div className="panel document-list">
        <div className="document-columns" aria-hidden="true">
          <span>Tên tài liệu</span>
          <span>Kỳ báo cáo</span>
          <span>Trạng thái xử lý</span>
          <span>Thao tác</span>
        </div>
        <EmptyState
          icon={Files}
          title="Chưa có tài liệu nào."
          description="Tài liệu và trạng thái xử lý sẽ xuất hiện tại đây sau khi tải lên."
        />
      </div>
    </section>
  );
}
