# vietnamese-financial-multi-agent

Khung đa tác nhân thích ứng cho kiểm tra báo cáo tài chính và tuân thủ quy định,
hỏi đáp và tạo báo cáo phân tích có dẫn nguồn bằng tiếng Việt.

Repository nghiên cứu sử dụng Python 3.11+ và kiến trúc modular monolith. M0-01
khởi tạo cấu trúc, cấu hình phát triển và tài liệu nền tảng; M0-02 tổ chức lại
dataset local vào `data/`. Các package hiện chỉ có docstring; chưa có chức năng
nghiệp vụ, server, CLI, OCR, Agent hoặc LLM Gateway.

## Mục tiêu và kiến trúc

- Chuẩn hóa báo cáo tài chính và duy trì nguồn gốc của từng bằng chứng.
- Dùng chung Executable Financial Evidence Graph (EF-EG) cho hỏi đáp và báo cáo.
- Điều phối tác nhân theo nhu cầu bằng chứng và tín hiệu rủi ro.
- Kiểm chứng từng nhận định trước khi tạo kết quả bằng tiếng Việt có dẫn nguồn.


<img width="797" height="844" alt="image" src="https://github.com/user-attachments/assets/a005b329-7e28-499d-ac4e-516910481eeb" />

Gemini và các LLM khác sẽ đi qua LLM Gateway dùng chung để đổi model, hỗ trợ
structured outputs và quản lý chi phí. Chưa chọn SDK, model hoặc triển khai Gateway.
Phạm vi kiểm tra tuân thủ quy định cụ thể là **TBD**; xem
[các quyết định và điểm cần làm rõ](planning/decisions.md).

## Cấu trúc repository

```text
.
├── .github/workflows/ci.yml
├── .env.example
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── README.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── core/__init__.py
│   ├── document_processing/__init__.py
│   ├── accounting/__init__.py
│   ├── evidence/__init__.py
│   ├── tools/__init__.py
│   ├── agents/__init__.py
│   ├── verification/__init__.py
│   ├── outputs/__init__.py
│   └── api/__init__.py
├── tests/
│   ├── unit/test_package.py
│   ├── integration/.gitkeep
│   └── evaluation/.gitkeep
├── configs/.gitkeep
├── scripts/
│   ├── .gitkeep
│   └── check_planning.py
├── docs/
│   ├── architecture.md
│   ├── module-boundaries.md
│   ├── data-contracts.md
│   ├── dataset.md
│   └── evaluation.md
├── planning/
│   ├── roadmap.md
│   ├── tasks.md
│   ├── current-status.md
│   ├── decisions.md
│   ├── progress.md
│   ├── handoff.md
│   ├── task-template.md
│   └── tasks/
│       ├── M0/M0-04.md
│       ├── M1/M1-01.md
│       ├── M2/.gitkeep
│       ├── M3/.gitkeep
│       ├── M4/.gitkeep
│       ├── M5/.gitkeep
│       ├── M6/.gitkeep
│       ├── M7/.gitkeep
│       └── M8/.gitkeep
├── data/
│   ├── raw/Financial_Report/                 # dữ liệu local, Git bỏ qua
│   ├── processed/Financial_Report_OCR/       # dữ liệu local, Git bỏ qua
│   ├── normalized/                          # đang rỗng, Git bỏ qua
│   ├── canonical/                           # đang rỗng, Git bỏ qua
│   └── samples/.gitkeep
├── evaluation/.gitkeep
└── prompts/.gitkeep
```

Cây trên thể hiện cả cấu trúc Git và dataset local. Trong `data/`, Git chỉ theo
dõi `samples/.gitkeep`; clone repository không tải dataset hoặc tạo các thư mục
dữ liệu bị bỏ qua. `.venv/` và tài liệu tham chiếu `docs/report_midterm.docx` cũng
được Git bỏ qua và không cần để chạy skeleton.

## Dataset local

Hai thư mục dữ liệu được bảo toàn và di chuyển trong M0-02:

- `Financial_Report/` → `data/raw/Financial_Report/`.
- `Financial_Report_OCR/` → `data/processed/Financial_Report_OCR/`.

Dataset hiện có ba mã BBS, BCC, BED, mỗi mã năm kỳ 2021–2025. Thư mục raw hiện
chứa ảnh PNG; thư mục processed giữ kết quả OCR đã có. Không chạy lại OCR, không
sửa JSON/ảnh gốc. `normalized/` và `canonical/` đang rỗng, dành cho các task sau.

Các biến sau đã có trong `.env.example`; khi cần cấu hình local, sao chép sang
`.env` nếu file đó chưa tồn tại và dùng đường dẫn tương đối với gốc repository:

```ini
FINANCIAL_REPORT_DIR=data/raw/Financial_Report
FINANCIAL_OCR_DIR=data/processed/Financial_Report_OCR
NORMALIZED_DATA_DIR=data/normalized
CANONICAL_DATA_DIR=data/canonical
```

Skeleton chưa có bộ nạp cấu hình trung tâm và chưa tự đọc `.env`. Không hardcode
đường dẫn Windows/Colab trong code. JSON OCR có thể giữ đường dẫn `/content/drive/...`;
giữ nguyên JSON và đối chiếu ánh xạ với thư mục local theo
[hướng dẫn dataset](docs/dataset.md#ánh-xạ-đường-dẫn-colab-sang-local).
Repository public chỉ chứa code, cấu hình và tài liệu; dataset không được commit.

## Thiết lập môi trường

Cần Git và Python 3.11 trở lên. Lệnh dưới đây chạy tại thư mục gốc repository.
Không cần API key, cơ sở dữ liệu hoặc dữ liệu tài chính để cài đặt và kiểm tra.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest tests/unit
```

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
test -e .env || cp .env.example .env
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest tests/unit
```

`.env.example` chỉ khai báo cấu hình dự kiến; skeleton chưa tự nạp `.env`.
Để định dạng code, chạy `python -m ruff format .` trong môi trường phát triển.
Để kiểm tra toàn bộ tập test hiện có, chạy `python -m pytest`.

Distribution có tên `vietnamese-financial-multi-agent`; namespace import là
`vietnamese_financial_multi_agent`, ví dụ
`import vietnamese_financial_multi_agent.evidence`. `pyproject.toml` ánh xạ
namespace này vào `src/`. Khi thêm package, cần cập nhật danh sách đóng gói.
Các thư mục `tests/` không phải package ứng dụng nên không cần `__init__.py`.

CI cài package thường (không editable), kiểm tra Ruff và unit tests trên Python
3.11/3.12, kèm kiểm tra tính nhất quán tracking qua `scripts/check_planning.py`.
Unit tests hiện chỉ kiểm tra khả năng cài và import các package;
không đại diện cho kiểm thử nghiệp vụ hoặc kết quả benchmark.

## Tài liệu và quy trình làm việc

Đọc [AGENTS.md](AGENTS.md), [kiến trúc](docs/architecture.md),
[ranh giới module](docs/module-boundaries.md) và
[data contracts](docs/data-contracts.md) trước khi thay đổi code.
Nguồn và cách quản lý dữ liệu ở [dataset.md](docs/dataset.md);
định hướng kiểm thử ở [evaluation.md](docs/evaluation.md).

Theo dõi [roadmap M0–M8](planning/roadmap.md), [Master Task Registry](planning/tasks.md),
[dashboard](planning/progress.md) và [trạng thái hiện tại](planning/current-status.md).
Registry là nguồn trạng thái chính, Task ID bất biến. Các task M1–M8 là kế hoạch,
chưa phải implementation hoặc quyền tự bắt đầu task.

Khi tiếp tục phiên: đọc AGENTS → current-status → [handoff](planning/handoff.md)
→ active task spec, kiểm tra Git/checkpoint thực tế rồi chỉ làm remaining work.
Dùng [task template](planning/task-template.md) cho task mới; ưu tiên task nhỏ,
ghi checkpoint sau phần độc lập đã kiểm thử. Không làm lại phần đã xác minh khi
không có lý do, không chờ đến lúc hết quota mới cập nhật handoff.

Chạy `python scripts/check_planning.py` để kiểm tra IDs, dependencies, states,
evidence, dashboard, specs và links; script chỉ đọc tài liệu, không đọc dataset
hoặc gọi API. Những quyết định thiếu thông tin ghi `TBD`; không đưa dữ liệu
Google Drive, dataset, secrets hoặc tài liệu riêng tư vào Git.
