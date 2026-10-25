# Kiểm thử và đánh giá

## Kiểm tra trong M0-01

- Cài môi trường phát triển từ `pyproject.toml` bằng `pip install -e ".[dev]"`.
- Ruff kiểm tra lint và định dạng.
- `tests/unit/test_package.py` kiểm tra import 10 package và metadata distribution.
- CI cài package thường bằng `pip install ".[dev]"` để kiểm tra cả đóng gói,
  sau đó chạy lint, định dạng và unit tests trên Python 3.11 và 3.12.

Các kiểm tra này không cần secrets, dịch vụ bên ngoài hoặc dữ liệu tài chính.
Chưa có logic nghiệp vụ nên chưa có integration tests hoặc bài đánh giá chất
lượng. Những thư mục tương ứng chỉ chứa `.gitkeep`.

## Định hướng từ báo cáo giữa kỳ

Chương 7 mô tả hai nhánh đánh giá: Interactive Financial QA và Grounded Report
Generation, cùng so sánh baseline và ablation trong điều kiện cùng model nền,
dữ liệu và ngân sách suy luận. Đây là định hướng thực nghiệm, chưa có benchmark
được triển khai hoặc kết quả đo trong repository.

| Nhóm | Các chỉ số được nêu trong báo cáo |
| --- | --- |
| Trích xuất và chuẩn hóa | Value Exact Match, Item Mapping F1 |
| Hỏi đáp | Exact Match, Numerical Accuracy, Answer Correctness |
| Bằng chứng và trích dẫn | Evidence Recall, Citation Precision/Recall |
| Hội thoại | Reference Resolution Accuracy, Multi-turn Consistency |
| Kiểm chứng claim | Supported Claim Precision, Unsupported Claim Rate |
| Phân tích tài chính | Insight Coverage, Risk Recall |
| Không kết luận khi thiếu bằng chứng | Abstention Precision/Recall, Accuracy–Coverage |
| Báo cáo | Coherence, Analytical Depth, Readability |
| Hiệu quả | Tokens, LLM Calls, Latency, Cost |

Dataset chuẩn, tập chia, nhãn tham chiếu, công thức đo, dung sai số học, baseline
chốt triển khai, ngân sách và ngưỡng đạt là `TBD`. Không đưa các con số dự kiến
thành acceptance criteria tự đặt hoặc kết quả thực nghiệm.

`tests/evaluation/` sẽ chứa code kiểm tra đánh giá khi có task; `evaluation/`
sẽ chứa cấu hình và tài liệu thực nghiệm đã duyệt. Dữ liệu và kết quả chạy lớn
ở vị trí được Git bỏ qua. Kết quả kiểm tra thực tế của task được ghi tại
[`planning/current-status.md`](../planning/current-status.md).
