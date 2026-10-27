# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-12 REVIEW**, chờ Tech Lead; M1-11/M1-11b DONE, M1-13 TODO.
- Đã thêm deterministic `reconstruct_table` / `SpanEvidence`, output DU v1.
  Grid/merged annotations/placeholders giữ source anchors, text/bbox/ID;
  ambiguity/conflict trả unresolved, không sinh ô/số liệu hoặc sửa OCR.
- Local: **14 focused +205 regression =219 passed**; Ruff lint/format đạt.
  Planning/diff đạt; full unit suite CI 3.11/3.12 đạt.
- Frozen M1-04b: 4 pages/8 tables/310 cells, **1 resolved/7 unresolved**;
  5 gaps, 32 cell bbox out-of-bounds, 2265 pairwise geometry conflicts,
  47 observed empty cells. DU anchors không source/status issues, chỉ empty_text.
- 8 selected input snapshots và manifest/raw fingerprints bất biến.
  Không ground truth merges/accuracy; B09 token observed trên 3 pages.
- **0 Gemini requests/tokens**. Gemini-assisted/checkpoint stage chưa triển khai;
  explicit span annotations cần caller review, extras producer semantics TBD.
- Baseline verified `0dd9bd1e7ee8aa9c8e458e49182e7d01624b2c46` = origin/main trước sửa.
  Implementation `01b235cc83f08e3df86ac8341370ee43ebc866e8` đã push main;
  [CI 40514937586](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40514937586) success exact SHA, mọi steps/full unit suite 3.11/3.12.
  Checkpoint evidence cuối chỉ docs/planning, SHA/CI kiểm tra riêng sau push.
- [Spec](tasks/M1/M1-12.md), [usage](../docs/table-reconstruction.md),
  [evidence](../docs/reviews/M1-12-evidence.md).
- Next action: **Tech Lead review M1-12; không DONE/M1-13.**
