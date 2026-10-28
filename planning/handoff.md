# Codex Handoff

## Active Task
M1-15 — Gemini-Native OCR Ingestion

## Status
REVIEW

## Last Verified State
Baseline `160de34cd06c8d500c2159be6a93f0f964f594e4` sạch trước sửa.
PDF24 trang thật, selected5/7/8/14/15 render200 DPI, live5/5, hash trước/sau khớp.

## Completed Work
PDF/PNG ingestion, provenance, component validation reuse, partial DU text adapter.
58 text/505 cell texts accepted;61 cell texts unresolved;tables0/10 accepted.
5 partial DU schema pages, raw loader/DU quality0/5; geometry unresolved624.
Đối chiếu pages5/14 thấy mẫu số đúng nhưng dấu `-` thành `_`, column/row counts sai.
5 Gemini requests,7723 input/42818 output/50541 total tokens, provider failures0.
PNG cũ dry-run qua cùng CLI; không live PNG bổ sung, không sửa dữ liệu nguồn.

## Remaining Work
Tech Lead nghiệm thu; CI exact SHA kiểm sau implementation push và ghi bàn giao cuối phiên.
Không publication commit chỉ ghi CI. Chưa DONE, không M2/demo.

## Modified Files
gemini_ingestion.py, run_gemini_ingestion.py, test_gemini_ingestion.py, pyproject.toml;
planning registry/spec/dashboard/current-status/handoff; docs/reviews/M1-15-evidence.md.

## Tests
8 focused passed; Ruff changed files, planning checker, diff check đạt.
CI hiện có full unit3.11/3.12 sau push; không chạy full local regression.

## Blockers
DU chỉ schema text; thiếu region provenance nên quality unresolved/raw loader chưa tương thích.
Bảng/geometry giữ intermediate, không gán bbox/IDs giả. Chưa human second review/accuracy.

## Git Checkpoint
Stable baseline `160de34cd06c8d500c2159be6a93f0f964f594e4`; một implementation commit
chứa handoff này, lấy SHA bằng `git log -1 --format=%H`. Private evidence dưới
`artifacts/gemini-ingestion/M1-15/`; không stage data/secrets. CI receipt sau push
giữ private và trong bàn giao cuối phiên, không publication commit.

## Exact Next Action
Tech Lead review implementation, CI exact SHA và giới hạn adapter trước nghiệm thu.
