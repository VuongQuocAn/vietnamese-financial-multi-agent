"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  active,
  api,
  displayValue,
  fieldLabels,
  stateLabels,
  type Document,
  type MetadataValues,
  type Period,
} from "@/lib/documents";

const suggestionLabels = {
  resolved: "Đã nhận diện",
  uncertain: "Cần xem xét",
  unresolved: "Chưa xác định",
};
const stopLabels: Record<string, string> = {
  sufficient_evidence: "Đã nhận diện thông tin cốt lõi theo nguồn PDF.",
  pages_exhausted: "Đã xem hết PDF",
  page_limit: "Đạt giới hạn trang",
  budget_limit: "Tạm dừng nhận diện. Vui lòng thử lại sau.",
  provider_error: "Chưa hoàn tất được nhận diện. Vui lòng thử lại.",
  configuration_required:
    "Hệ thống chưa sẵn sàng nhận diện. Vui lòng kiểm tra cấu hình server.",
  interrupted: "Đã gián đoạn",
};

export function MetadataReview({ id }: { id: string }) {
  const [doc, setDoc] = useState<Document | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function load() {
      try {
        const value = await api<Document>(
          `/documents/${encodeURIComponent(id)}`,
        );
        if (cancelled) return;
        setDoc(value);
        setError("");
        failures = 0;
        if (active(value)) timer = setTimeout(load, 2000);
      } catch (e) {
        if (cancelled) return;
        setError((e as Error).message);
        failures += 1;
        if (failures < 5)
          timer = setTimeout(load, Math.min(30000, 2000 * 2 ** failures));
      }
    }
    void load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, reload]);

  async function retry(operation: "preflight" | "extract" = "preflight") {
    if (!doc || retrying) return;
    setRetrying(true);
    setError("");
    try {
      await api(`/documents/${id}/process`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          operation,
          metadata_revision: doc.metadata_revision,
        }),
      });
      setReload((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="page metadata-page">
      <Link href="/documents" className="text-link">
        ← Danh sách tài liệu
      </Link>
      <div className="page-heading">
        <p className="eyebrow">Thông tin tài liệu</p>
        <h1>Thông tin tài liệu</h1>
        {doc && (
          <p className="page-description document-filename">
            {doc.filename} · {doc.page_count} trang ·{" "}
            {(doc.size_bytes / 1024 / 1024).toFixed(2)} MiB
          </p>
        )}
      </div>
      {error && (
        <div role="alert" className="notice error-message">
          {error}{" "}
          <button className="button" onClick={() => setReload((n) => n + 1)}>
            Tải lại
          </button>
        </div>
      )}
      {!doc ? (
        !error && <p role="status">Đang tải thông tin tài liệu…</p>
      ) : (
        <>
          <section
            className="panel metadata-section"
            aria-label="Trạng thái nhận diện"
          >
            <strong role="status">{stateLabels[doc.state] ?? doc.state}</strong>
            {active(doc) && doc.job?.operation !== "extract" && (
              <p>
                Đã phân tích {doc.job?.progress.preflight?.completed_pages ?? 0}/
                {doc.page_count} trang.
              </p>
            )}
            {doc.job?.operation === "extract" && (
              <div>
                {active(doc) && <p>Hệ thống đang phân tích… {doc.job.phase === "discovery" ? "Nhận diện trang báo cáo" : "Trích xuất số liệu"}</p>}
                {doc.job.progress.discovery && <p>Đã nhận diện {doc.job.progress.discovery.completed_pages}/{doc.job.progress.discovery.total_pages} trang.</p>}
                {doc.job.progress.extraction && <p>Đã xử lý {doc.job.progress.extraction.completed_pages}/{doc.job.progress.extraction.selected_pages} trang được chọn; {doc.job.progress.extraction.invalid_pages} trang lỗi.</p>}
                {doc.job.summary && <p>B01: {doc.job.summary.statement_pages.B01} trang · B02: {doc.job.summary.statement_pages.B02} trang · B03: {doc.job.summary.statement_pages.B03} trang · B09: {doc.job.summary.statement_pages.B09} trang (chỉ danh mục). {doc.job.summary.evidence_items} mục dữ liệu có nguồn.</p>}
                {doc.job.error && <p className="error-message">{typeof doc.job.error === "string" ? "Phân tích chưa hoàn tất. Kết quả đã lưu được giữ lại." : doc.job.error.message}</p>}
                {!!doc.job.page_errors?.length && <p>Trang cần thử lại: {doc.job.page_errors.map(e => e.pdf_page).join(", ")}.</p>}
                <p className="muted">Số liệu trích xuất chưa được xác minh; cần đối chiếu PDF gốc.</p>
              </div>
            )}
            {doc.job?.operation !== "extract" && doc.metadata.preflight?.stop_reason && (
              <p>
                {stopLabels[doc.metadata.preflight.stop_reason] ??
                  "Nhận diện đã dừng"}
              </p>
            )}
            {doc.state === "interrupted" && (
              <p>
                Phiên trước đã gián đoạn. Nhận diện chỉ chạy lại khi bạn yêu cầu
                và ngân sách server cho phép.
              </p>
            )}
            {doc.state === "needs_metadata" && (
              <p>
                Chưa thể xác định đầy đủ thông tin tài liệu. Bạn có thể thử nhận
                diện lại hoặc bổ sung thông tin.
              </p>
            )}
            {doc.state === "failed" && doc.job?.operation !== "extract" && (
              <p>
                Không hoàn tất được nhận diện. PDF đã được giữ lại; bạn có thể
                thử lại hoặc điền thông tin.
              </p>
            )}
            <div className="form-actions">
              <Link className="button" href={`/evidence/${id}`}>Xem PDF</Link>
              <a
                className="button"
                href={`/api/documents/${id}/file`}
                target="_blank"
                rel="noreferrer"
              >
                Mở PDF gốc
              </a>
              {!active(doc) && doc.metadata.accepted && (
                <button className="button primary" disabled={retrying} onClick={() => retry("extract")}>
                  {retrying ? "Đang gửi yêu cầu…" : ["partial", "failed", "interrupted"].includes(doc.state) && doc.job?.operation === "extract" ? "Thử phân tích lại" : "Phân tích báo cáo"}
                </button>
              )}
              {!active(doc) && (
                <button
                  className={`button ${doc.state !== "ready" ? "primary" : ""}`}
                  disabled={retrying}
                  onClick={() => retry()}
                >
                  {retrying ? "Đang gửi yêu cầu…" : "Thử nhận diện lại"}
                </button>
              )}
            </div>
          </section>
          <div className="metadata-layout">
            <section
              className="panel metadata-section"
              aria-labelledby="suggestions-title"
            >
              <h2 id="suggestions-title">Hệ thống đề xuất</h2>
              <p className="muted">
                Kết quả nhận diện có nguồn trang để đối chiếu; không phải xác
                minh tuyệt đối.
              </p>
              {(Object.keys(fieldLabels) as (keyof MetadataValues)[]).map(
                (key) => {
                  const suggestion = doc.metadata.suggestions[key];
                  return (
                    <div className="metadata-suggestion" key={key}>
                      <h3>{fieldLabels[key]}</h3>
                      <span className={`suggestion-state ${suggestion.status}`}>
                        {suggestionLabels[suggestion.status]}
                      </span>
                      {suggestion.candidates.length === 0 ? (
                        <p>Chưa có căn cứ đọc được.</p>
                      ) : (
                        suggestion.candidates.map((candidate, index) => (
                          <div className="metadata-candidate" key={index}>
                            <strong>{displayValue(candidate.value)}</strong>
                            <blockquote>{candidate.raw_text}</blockquote>
                            {candidate.sources.map((source) => (
                              <a
                                key={source.pdf_page}
                                className="text-link"
                                href={`/api/documents/${id}/file#page=${source.pdf_page}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Trang {source.pdf_page}
                              </a>
                            ))}
                          </div>
                        ))
                      )}
                      {suggestion.status === "uncertain" && (
                        <p className="error-message">
                          Có nội dung chưa rõ hoặc candidates mâu thuẫn; hãy đối
                          chiếu PDF.
                        </p>
                      )}
                      {suggestion.issues.length > 0 && (
                        <p className="muted">
                          Lưu ý từ nhận diện: {suggestion.issues.join("; ")}
                        </p>
                      )}
                    </div>
                  );
                },
              )}
            </section>
            <section
              className="panel metadata-section"
              aria-labelledby="confirmation-title"
            >
              <h2 id="confirmation-title">Thông tin tài liệu</h2>
              <dl className="metadata-values">
                {(Object.keys(fieldLabels) as (keyof MetadataValues)[]).map(
                  (key) => (
                    <div key={key}>
                      <dt>{fieldLabels[key]}</dt>
                      <dd>
                        {doc.metadata.values[key] === null
                          ? "Chưa xác định"
                          : displayValue(doc.metadata.values[key]!)}
                      </dd>
                    </div>
                  ),
                )}
              </dl>
              <p className="muted">
                {doc.metadata.acceptance_origin === "auto" &&
                !doc.metadata.accepted
                  ? "Thông tin phiên trước, chưa được chấp nhận lại"
                  : doc.metadata.acceptance_origin === "auto"
                    ? "Hệ thống tự chấp nhận theo nguồn PDF"
                    : doc.metadata.acceptance_origin === "user"
                      ? "Thông tin do người dùng cập nhật"
                      : "Chưa đủ thông tin cốt lõi"}{" "}
                · Revision {doc.metadata_revision}
              </p>
              {doc.state === "ready" && (
                <p className="notice">
                  Tài liệu sẵn sàng cho bước xử lý tài chính; chưa có kết quả
                  trích xuất.
                </p>
              )}
              {!active(doc) && (
                <button
                  className="button"
                  aria-expanded={editing}
                  onClick={() => setEditing(!editing)}
                >
                  {editing ? "Đóng chỉnh sửa" : "Chỉnh sửa thông tin"}
                </button>
              )}
              {editing && !active(doc) && (
                <MetadataForm
                  key={`${doc.id}:${doc.metadata_revision}:${doc.job?.id}`}
                  doc={doc}
                  onSaved={(value) => {
                    setDoc(value);
                    setEditing(false);
                  }}
                />
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function initialValues(doc: Document): MetadataValues {
  const values = { ...doc.metadata.values };
  if (doc.metadata_revision === 0) {
    for (const key of Object.keys(fieldLabels) as (keyof MetadataValues)[]) {
      const suggestion = doc.metadata.suggestions[key];
      if (suggestion.status === "resolved" && suggestion.candidates.length > 0)
        Object.assign(values, { [key]: suggestion.candidates[0].value });
    }
  }
  return values;
}

function MetadataForm({
  doc,
  onSaved,
}: {
  doc: Document;
  onSaved: (doc: Document) => void;
}) {
  const [values, setValues] = useState<MetadataValues>(() =>
    initialValues(doc),
  );
  const [periodType, setPeriodType] = useState<Period["type"]>(
    () => initialValues(doc).reporting_period?.type ?? "fiscal_year",
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  function update<K extends keyof MetadataValues>(
    key: K,
    value: MetadataValues[K],
  ) {
    setValues((previous) => ({ ...previous, [key]: value }));
  }
  async function save(confirmed: boolean) {
    setSaving(true);
    setError("");
    try {
      const value = await api<Document>(`/documents/${doc.id}/metadata`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata_revision: doc.metadata_revision,
          confirmed,
          values,
        }),
      });
      onSaved(value);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void save(true);
  }
  return (
    <form className="metadata-form" onSubmit={submit}>
      <fieldset disabled={saving}>
        <label>
          Tên công ty
          <input
            required
            maxLength={500}
            value={values.company_name ?? ""}
            onChange={(e) => update("company_name", e.target.value || null)}
          />
        </label>
        <label>
          Năm báo cáo
          <input
            required
            type="number"
            min={1}
            max={9999}
            step={1}
            value={values.reporting_year ?? ""}
            onChange={(e) =>
              update(
                "reporting_year",
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
          />
        </label>
        <label>
          Mã chứng khoán (không bắt buộc)
          <input
            maxLength={40}
            value={values.stock_ticker ?? ""}
            onChange={(e) => update("stock_ticker", e.target.value || null)}
          />
        </label>
        <label>
          Kỳ báo cáo
          <input
            maxLength={500}
            value={values.reporting_period?.value ?? ""}
            onChange={(e) =>
              update(
                "reporting_period",
                e.target.value
                  ? { value: e.target.value, type: periodType }
                  : null,
              )
            }
          />
        </label>
        <label>
          Loại kỳ
          <select
            value={periodType}
            onChange={(e) => {
              const type = e.target.value as Period["type"];
              setPeriodType(type);
              if (values.reporting_period)
                update("reporting_period", {
                  ...values.reporting_period,
                  type,
                });
            }}
          >
            <option value="fiscal_year">Năm tài chính</option>
            <option value="as_of">Tại ngày</option>
            <option value="fiscal_year_end">Cuối năm tài chính</option>
            <option value="date_range">Khoảng thời gian</option>
            <option value="quarter">Quý</option>
            <option value="year_to_month">Lũy kế đến tháng</option>
          </select>
        </label>
        <label>
          Phạm vi báo cáo
          <select
            value={values.reporting_scope ?? ""}
            onChange={(e) =>
              update(
                "reporting_scope",
                (e.target.value || null) as MetadataValues["reporting_scope"],
              )
            }
          >
            <option value="">Chưa xác định</option>
            <option value="separate">Riêng lẻ</option>
            <option value="consolidated">Hợp nhất</option>
          </select>
        </label>
        <p className="muted">
          Revision {doc.metadata_revision} ·{" "}
          {doc.metadata.confirmed
            ? "Đã xác nhận bởi người dùng"
            : "Chưa xác nhận"}
          . Những thay đổi của bạn được lưu riêng với gợi ý AI.
        </p>
        <div className="form-actions">
          <button type="button" className="button" onClick={() => save(false)}>
            Lưu nháp
          </button>
          <button className="button primary" type="submit">
            {saving ? "Đang lưu…" : "Lưu thông tin"}
          </button>
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
    </form>
  );
}
