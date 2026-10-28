import Link from "next/link";
import {
  ArrowRight,
  Bot,
  FileCheck2,
  FileText,
  MessagesSquare,
  Network,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

export function ComingSoonCard() {
  return (
    <section className="ai-preview">
      <span className="feature-icon">
        <Bot size={24} />
      </span>
      <div>
        <div className="inline-heading">
          <h2>Trợ lý AI phân tích tài chính</h2>
          <StatusBadge>Sắp ra mắt</StatusBadge>
        </div>
        <p>
          Hỏi đáp, phân tích và kiểm tra nguồn dẫn ngay trong không gian làm
          việc.
        </p>
      </div>
      <Link href="/ai-workspace" className="text-link">
        Tìm hiểu thêm <ArrowRight size={16} />
      </Link>
    </section>
  );
}

export function ComingSoonPanel() {
  const features = [
    {
      icon: MessagesSquare,
      title: "Hỏi đáp báo cáo tài chính",
      text: "Khám phá thông tin bằng câu hỏi tiếng Việt.",
    },
    {
      icon: Network,
      title: "Phân tích bằng nhiều AI agents",
      text: "Phối hợp các góc nhìn phân tích chuyên sâu.",
    },
    {
      icon: FileCheck2,
      title: "Kiểm tra nguồn dẫn",
      text: "Đối chiếu nhận định với bằng chứng trong tài liệu.",
    },
    {
      icon: FileText,
      title: "Tạo báo cáo phân tích",
      text: "Tổng hợp kết quả phân tích có dẫn nguồn.",
    },
  ];
  return (
    <section className="panel coming-soon-panel">
      <span className="ai-hero-icon">
        <Bot size={38} strokeWidth={1.4} />
      </span>
      <StatusBadge>Sắp ra mắt</StatusBadge>
      <h2>Một không gian, nhiều góc nhìn tài chính.</h2>
      <p className="muted">
        Trợ lý AI đang được phát triển. Các chức năng dưới đây chưa khả dụng.
      </p>
      <div className="future-features">
        {features.map(({ icon: Icon, title, text }) => (
          <div key={title}>
            <Icon size={21} />
            <div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          </div>
        ))}
      </div>
      <Link className="button secondary" href="/">
        Về tổng quan <ArrowRight size={16} />
      </Link>
    </section>
  );
}
