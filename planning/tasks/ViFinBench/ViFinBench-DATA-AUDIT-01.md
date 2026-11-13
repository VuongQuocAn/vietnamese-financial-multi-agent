# TASK ViFinBench-DATA-AUDIT-01 — Khảo sát Neutral Corpus và đánh giá khả năng xây dựng benchmark

## Metadata

- Milestone: ViFinBench
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: M
- Related Modules: ViFinBench/neutral, tài liệu benchmark độc lập

## Objective

Audit corpus thực tế và đánh giá độc lập khả năng tạo Gold QA Single-hop,
Multi-hop, Numerical; không coi số QA có thể sinh là số QA độc lập đã xác minh.

## Context

Owner giao ngày13/11/2026 theo task đính kèm. Đọc AGENTS, current-status và registry.
ViFinBench độc lập DACNTT. Task M giữ một audit thống nhất vì cùng corpus/đầu ra;
thực hiện tuần tự inventory → mẫu/nguồn → khả thi → bàn giao, không chia module mới.

## Inputs

`ViFinBench/neutral`; PDF/PNG local sẵn có trong storage. Mốc15doanh nghiệp/41báo
cáo là giả thuyết cần kiểm chứng. Raw/OCR/ảnh và neutral read-only.

## Outputs

- `docs/vifinbench-data-audit-01.md` với thống kê, ví dụ lỗi, giới hạn và kết luận
  READY / READY_WITH_CAVEATS / NOT_READY.
- Script kiểm kê nhỏ; evidence local ở `artifacts/evidence/ViFinBench-DATA-AUDIT-01/`.
- Đề xuất Pilot45 (mỗi subset5Easy/7Medium/3Hard); Full600 (mỗi subset60/100/40).

## Allowed Changes

Báo cáo/script audit, spec/registry/dashboard/current-status tối thiểu và checker
để nhận Task ID mới. Owner cho phép riêng corpus neutral vào Git và commit/push
nhánh hiện tại sau kiểm dung lượng/ignore/secrets; ngoại lệ này áp dụng riêng corpus
được giao, không áp dụng PDF/PNG/raw hoặc local edits ngoài task.

## Out of Scope

Không sinh45/600QA, không Gemini/API trả phí, không tải lại/sửa/xóa dữ liệu,
không đổi pipeline DACNTT, không framework/schema/evaluation mới, không full CI.

## Implementation Steps

1. Kiểm Git/local edits; thống kê bằng Python và hash nguồn.
2. Kiểm đối ứng định dạng, metadata, thiếu/trùng/lỗi cấu trúc.
3. Đọc mẫu nhiều doanh nghiệp/năm, đối chiếu ảnh/PDF sẵn có và số học.
4. Ước lượng độc lập từng subset, quota tương đối, blockers và Pilot; REVIEW rồi dừng.

## Acceptance Criteria

- [x] Kiểm kê doanh nghiệp/năm/trang/file/bytes và completeness thực tế.
- [x] Có ví dụ chất lượng bảng/văn bản, provenance và phép đối chiếu số học.
- [x] Ước lượng QA tách candidate với Gold đã xác minh; đánh giá Codex trung thực.
- [x] Đề xuất Pilot và kết luận có giới hạn; không tự bắt đầu ViFinBench-P1.
- [x] Hash corpus giữ nguyên; Git chỉ gồm phạm vi được Owner cho phép.

## Required Tests

Chạy script audit trên corpus thật; kiểm tra công thức bằng Python; Ruff file Python
đã sửa, planning checker và git diff --check. Không full CI hoặc pipeline smoke.

## Risks and Blockers

Thiếu nguồn gốc có thể chặn chứng nhận Gold. REVIEW chờ Tech Lead nghiệm thu audit
và quyết định Pilot; không tự chuyển DONE.

## Implementation Evidence

- Implementation SHA: `b613c5894acc4258ad0693ddeb56350dd60c07c3`; đã push main,
  remote SHA verified. Baseline `75631ec022b54ca6d7eb274237f87c0f9eb51044`.
- Main Changes: [báo cáo](../../../docs/vifinbench-data-audit-01.md), script audit,
  corpus được Owner cho phép và Git attributes giữ snapshot byte-exact.
  15doanh nghiệp/41tài liệu/1.488trang/9.861.632bytes;37BCTC complete theo export,
  3partial/4trang thiếu và1công văn;358probe:354khớp/4mâu thuẫn.
- Test Results: 3targeted PASS; Ruff/planning/diff PASS local. 123corpus
  working/index hashes khớp;27tracked local edits ngoài task giữ nguyên.
  Engineering checks không chứng nhận financial accuracy; không fullCI/API/QA generation.
- Review Notes: READY_WITH_CAVEATS cho Pilot có kiểm nguồn; Full600chưa chứng minh.
  Chờ Tech Lead nghiệm thu audit; không tự chuyển DONE.

## Handoff Notes

Next action: Tech Lead review audit và quyết định phạm vi ViFinBench-P1.
