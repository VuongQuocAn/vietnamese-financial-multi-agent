export type Period = {
  value: string;
  type:
    | "as_of"
    | "fiscal_year"
    | "fiscal_year_end"
    | "date_range"
    | "quarter"
    | "year_to_month";
};
export type MetadataValues = {
  company_name: string | null;
  stock_ticker: string | null;
  reporting_year: number | null;
  reporting_period: Period | null;
  reporting_scope: "separate" | "consolidated" | null;
};
export type Candidate = {
  value: string | number | Period;
  raw_text: string;
  sources: { pdf_page: number; content_id: string }[];
};
export type Suggestion = {
  status: "resolved" | "uncertain" | "unresolved";
  candidates: Candidate[];
  issues: string[];
};
export type Job = {
  id: string;
  state: string;
  revision: number;
  error: string | null;
  progress: { preflight: { completed_pages: number; total_pages: number } };
};
export type DocumentSummary = {
  id: string;
  filename: string;
  state: string;
  metadata_revision: number;
  company_name: string | null;
  stock_ticker: string | null;
  reporting_year: number | null;
};
export type Document = DocumentSummary & {
  content_id: string;
  page_count: number;
  size_bytes: number;
  metadata: {
    values: MetadataValues;
    suggestions: Record<keyof MetadataValues, Suggestion>;
    confirmed: boolean;
    accepted: boolean;
    acceptance_origin: "auto" | "user" | null;
    edits: { field: string; origin: string }[];
    preflight: {
      analyzed_pages: number[];
      stop_reason: string | null;
      issues: string[];
    } | null;
  };
  job: Job | null;
};
export const stateLabels: Record<string, string> = {
  uploaded: "Đã tải lên",
  queued: "Đang chờ nhận diện",
  processing: "Đang phân tích tài liệu",
  needs_metadata: "Cần bổ sung thông tin",
  ready: "Sẵn sàng",
  failed: "Nhận diện thất bại",
  interrupted: "Đã gián đoạn",
};
export const fieldLabels: Record<keyof MetadataValues, string> = {
  company_name: "Tên công ty",
  stock_ticker: "Mã chứng khoán (không bắt buộc)",
  reporting_year: "Năm báo cáo",
  reporting_period: "Kỳ báo cáo",
  reporting_scope: "Phạm vi báo cáo",
};
export function displayValue(value: Candidate["value"]) {
  if (typeof value === "object") return value.value;
  if (value === "separate") return "Riêng lẻ";
  if (value === "consolidated") return "Hợp nhất";
  return String(value);
}
export function active(doc: { state: string }) {
  return ["queued", "processing"].includes(doc.state);
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new Error("Không kết nối được backend. Vui lòng thử lại.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message ?? "Không thực hiện được yêu cầu. Vui lòng thử lại.",
    );
  }
  return response.json();
}
