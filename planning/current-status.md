# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-07 REVIEW — đã triển khai task-aware quality annotations theo yêu cầu 2026-10-28.
APIs assess_evidence_for_task/assess_automated_records và raw adapter; bốn task types.
Pilot BBS2025 trang5/7/8:136 slots,121 numeric (28 canonical/93 ngoài catalog).
Direct QA20 usable/101 usable_with_caveat/15 insufficient/0 conflicted thực.
Ba analytical/accounting scenarios đầy đủ usable_with_caveat; partial giữ item usable;
synthetic conflict giới hạn hai items, không coi là mâu thuẫn tài chính thực.
28 accepted extraction giữ nguyên;0 Gemini calls; PDF/cache/records không đổi.
20 focused +114 regression =134 targeted PASS; Ruff/planning/diff local.
Không verified financial facts, không accuracy toàn dataset; không bắt đầu M2-08/M3.
[API/pilot](../docs/task-aware-quality.md), [spec](tasks/M2/M2-07.md).

Baseline sạch `0474617b4b3a07c0fa29ed713fea09aa00817246`. Implementation chưa commit; CI exact SHA đang chờ.
Next action: Chờ Tech Lead review M2-07.
