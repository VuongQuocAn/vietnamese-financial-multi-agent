# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-13 REVIEW**, user cho triển khai/API/commit/push theo Research MVP Lean v3;
  M1-12a DONE. Không tự DONE/M1-14.
- Full-page Gemini structured proposal, exact source-ID/original gate, DU v1 anchors,
  corrected view riêng. Raw/bbox/IDs/provenance bất biến. Không independent verifier,
  vì vậy không phát sinh confirmed; effective_text giữ raw, proposed tách riêng.
- 11 focused +47 related regression passed; final focused11 passed sau source refinement.
  Ruff/planning/diff trước commit; CI một lần trên exact implementation SHA sau push.
- Live2 pages/2 requests: 0 corrections/proposed/confirmed/unresolved, page failures0;
  17450 input/40 output/17490 total tokens, unknown0, raw snapshots/manifest bất biến.
- Model bỏ sót lỗi chữ thấy trên ảnh; không ground truth/accuracy hoặc số được xác nhận.
  Quota owner-attested15 RPM/250000 TPM/500 RPD; billing/remaining chưa independently
  verified; guard money NOT_CONFIGURED. Không retry/rotation/tổng input cap.
- Baseline `9e93606`, main sạch trước triển khai. Implementation là commit chứa spec
  và evidence này; SHA/CI exact được báo trong bàn giao sau push, không publication commit.
- [Spec](tasks/M1/M1-13.md), [usage/evidence](../docs/reviews/M1-13-evidence.md).
- Next action: **Tech Lead review M1-13 và CI exact SHA trong bàn giao.**
