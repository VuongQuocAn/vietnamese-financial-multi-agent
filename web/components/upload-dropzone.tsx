"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileUp, Plus } from "lucide-react";

export function UploadDropzone() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const busy = useRef(false);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  function select(files: File[]) {
    if (busy.current) return;
    setError("");
    setFile(null);
    setProgress(null);
    if (files.length !== 1 || !/\.pdf$/i.test(files[0].name)) {
      setError("Vui lòng chọn đúng một tệp PDF.");
      return;
    }
    setFile(files[0]);
  }

  function upload() {
    if (!file || busy.current) return;
    busy.current = true;
    setUploading(true);
    setError("");
    const data = new FormData();
    data.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/documents");
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        setProgress(Math.round((event.loaded / event.total) * 100));
    };
    const finish = () => {
      busy.current = false;
      setUploading(false);
    };
    xhr.onerror = () => {
      finish();
      setError("Không kết nối được backend. Vui lòng thử lại.");
    };
    xhr.onload = () => {
      finish();
      if (xhr.status === 201 && xhr.response?.id)
        router.push(`/documents/${xhr.response.id}`);
      else
        setError(
          xhr.response?.error?.message ?? "Upload thất bại. Vui lòng thử lại.",
        );
    };
    xhr.send(data);
  }
  return (
    <section
      className={`upload-zone ${dragging ? "dragging" : ""}`}
      aria-labelledby="upload-title"
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        select(Array.from(event.dataTransfer.files));
      }}
    >
      <span className="upload-icon">
        <FileUp size={30} strokeWidth={1.6} />
      </span>
      <h2 id="upload-title">Tải báo cáo tài chính lên</h2>
      <p>Kéo thả PDF tại đây hoặc chọn tệp. Hỗ trợ báo cáo scan.</p>
      <input
        ref={input}
        type="file"
        accept=".pdf,application/pdf"
        aria-label="Tệp PDF"
        hidden
        onChange={(event) => {
          select(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      <button
        className="button primary"
        disabled={uploading}
        onClick={() => input.current?.click()}
        aria-describedby="upload-note"
      >
        <Plus size={17} /> Chọn tệp PDF
      </button>
      {file && (
        <div className="upload-selection">
          <p>
            {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MiB
          </p>
          <button
            className="button primary"
            onClick={upload}
            disabled={uploading}
          >
            {uploading ? "Đang tải lên…" : "Tải lên và nhận diện"}
          </button>
        </div>
      )}
      {uploading && (
        <p role="status">
          {progress === null
            ? "Đang gửi PDF…"
            : progress === 100
              ? "Đã gửi tệp, đang kiểm tra PDF…"
              : `Đã gửi ${progress}%`}
        </p>
      )}
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      <p id="upload-note" className="upload-note">
        Không cần nhập mã chứng khoán, năm hoặc chọn trang trước khi tải lên.
      </p>
    </section>
  );
}
