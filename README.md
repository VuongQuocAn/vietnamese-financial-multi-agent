# DACNTT — EO Frozen Benchmark 600

Prototype nghiên cứu hỏi đáp báo cáo tài chính Việt Nam, gpt-4o-mini. Bản A + SH-only đã chạy 600 QA: SH 157/200, MH 46/200, NR 96/200. Đây là điểm nội dung, không phải mọi câu đều có nguồn đúng. Grounded FULL lần lượt 154, 25, 82. Không có ablation trong bản phát hành này.

## Chạy bằng PowerShell

Cần Python 3.12 (tối thiểu 3.11); cài từ **checkout hiện tại** để tránh editable install trỏ nhầm mã nguồn.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[rag,dev,benchmark]'
Copy-Item .env.example .env
# Điền OPENAI_API_KEY trong .env cục bộ, không commit file đó.
$assets = 'D:\DuAnCNTT\multi_agent' # thay bằng root kho dữ liệu đã có trên máy
.\.venv\Scripts\python.exe scripts/run_agent_v2.py --question 'Tổng tài sản của VICEM Bao bì Bút Sơn cuối năm 2025 là bao nhiêu?' --assets $assets --workers 1 --budget 0.05
```

Manifest là JSON có trường `selected`, mỗi phần tử gồm `id`, `type` (SH/MH/NR), `question`. Mỗi batch tối đa 90 ID duy nhất. Giữ 1 worker và guide mặc định để tương ứng benchmark; không dùng paired-guide hoặc no-formula-guide.

```powershell
.\.venv\Scripts\python.exe scripts/run_agent_v2.py --manifest 'D:\path\batch-manifest.json' --assets $assets --workers 1 --budget 0.10 --output 'D:\path\new-output'
```

Đường dẫn output phải mới. Mọi request/response, proof, Final và usage được lưu theo ID. CLI vẫn có chế độ pilot lịch sử, cần selection.json bên ngoài; hai entry point hỗ trợ của release là **question** và **manifest**.

## Dữ liệu local (không nằm trong Git)

Root `--assets` chứa các thư mục benchmark gốc:

- `ViFinBench/refined/<symbol>/<year>/page_*.json`
- `artifacts/evidence/VFB-IMPORT-03/full-final` (catalog-index và bundle EF-EG)
- `artifacts/evidence/RAG-CHUNK-01/run-02` (projection)
- `artifacts/evidence/RAG-HYBRID-01/index-01` (index)
- `artifacts/models/huggingface` (cache E5 ONNX/tokenizer revision được pin trong mã)

Metadata đã track tại `ViFinBench/benchmark/document_metadata.json`; có thể chỉ định `--metadata` nếu dùng snapshot ngoài repo. Giữ đúng dữ liệu benchmark; không tải model từ mạng khi runtime truy xuất. Không chép corpus, cache, raw trace, Gold, API key vào Git.

## Phiên bản, đánh giá, kiểm thử

`configs/eo-frozen-release.json` nhận diện hash EO, các dependency Python còn dùng, guide và CLI. EO source không thay đổi; launcher bỏ kiểm tra tên branch thí nghiệm để manifest chạy trên main/tag. NR dùng ranked excerpt; MH top2; SH guide lưu nhưng không nạp.

Rubric: [hướng dẫn chấm SH/NR/MH](docs/Huong_dan_cham_diem_SH_NR_MH.md). Chấm **Final** đã khóa. Scorer trong `scripts/benchmark_scoring` là bản tái tạo phép chấm đã nghiệm thu, chạy từ thư mục artifact scoring chứa review-packet, judgments, manifest, usage và output-lock, cạnh thư mục benchmark gốc. Sao chép script từ checkout vào thư mục scoring nếu cần rồi chạy `python score.py`; không gọi API judge. Gold/nhận định chấm vẫn lưu local, không đưa vào request runtime. Không dùng scorer của benchmark cũ để chấm batch chưa hậu kiểm.

```powershell
.\.venv\Scripts\python.exe scripts/run_agent_v2.py --help
.\.venv\Scripts\python.exe -m pytest tests/unit
```

Tài liệu planning/docs cũ chỉ là lịch sử, không phải hướng dẫn chạy runtime hiện tại.
