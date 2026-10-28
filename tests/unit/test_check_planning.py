"""Planning regressions: W branch uses the same dependency/spec checks as M tasks."""

import runpy
from pathlib import Path

import pytest

CHECKER = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_planning.py"))


@pytest.fixture
def planning_root(tmp_path):
    planning = tmp_path / "planning"
    (planning / "tasks" / "W").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    for name in ("README.md", "AGENTS.md"):
        (tmp_path / name).write_text("", encoding="utf-8")
    (planning / "tasks.md").write_text(
        "## Registry\n\n"
        "| Task ID | Name | Milestone | Status | Priority | Dependencies | Spec | Evidence |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| M0-01 | Baseline | M0 | DONE | P0 | - | [baseline](tasks.md) | "
        f"https://example.test/commit/{'a' * 40} |\n"
        "| W-01 | Web Design | W | REVIEW | P1 | M0-01 | [W-01](tasks/W/W-01.md) | review |\n",
        encoding="utf-8",
    )
    rows = ["| M0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |"]
    rows += [f"| M{i} | 0 | 0 | 0 | 0 | 0 | 0 | 0 |" for i in range(1, 9)]
    rows += ["| W | 1 | 0 | 0 | 0 | 0 | 0 | 1 |", "| TOTAL | 2 | 1 | 0 | 0 | 0 | 0 | 1 |"]
    (planning / "progress.md").write_text(
        "## Số task theo milestone và trạng thái\n\n"
        "| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    headings = (
        "Metadata",
        "Objective",
        "Context",
        "Inputs",
        "Outputs",
        "Allowed Changes",
        "Out of Scope",
        "Implementation Steps",
        "Acceptance Criteria",
        "Required Tests",
        "Risks and Blockers",
        "Implementation Evidence",
        "Handoff Notes",
    )
    metadata = (
        "- Milestone: W\n- Status: REVIEW\n- Priority: P1\n"
        "- Dependencies: M0-01\n- Estimated Complexity: S\n"
    )
    (planning / "tasks" / "W" / "W-01.md").write_text(
        "# TASK W-01 — Web Design\n\n"
        + "\n".join(f"## {h}\n\n{metadata if h == 'Metadata' else 'Evidence'}\n" for h in headings),
        encoding="utf-8",
    )
    handoff_headings = (
        "Active Task",
        "Status",
        "Last Verified State",
        "Completed Work",
        "Remaining Work",
        "Modified Files",
        "Tests",
        "Blockers",
        "Git Checkpoint",
        "Exact Next Action",
    )
    values = {"Active Task": "W-01", "Status": "REVIEW"}
    (planning / "handoff.md").write_text(
        "\n".join(f"## {h}\n\n{values.get(h, 'Evidence')}\n" for h in handoff_headings),
        encoding="utf-8",
    )
    return tmp_path


def test_web_branch_is_counted_and_validated(planning_root):
    assert CHECKER["check"](planning_root) == 2


def test_web_dependency_must_be_done(planning_root):
    path = planning_root / "planning" / "tasks.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("M0 | DONE", "M0 | TODO"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Unfinished dependency: W-01"):
        CHECKER["check"](planning_root)


def test_web_spec_status_must_match_registry(planning_root):
    path = planning_root / "planning" / "tasks" / "W" / "W-01.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Status: REVIEW", "Status: DONE"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Spec metadata mismatch: W-01/Status"):
        CHECKER["check"](planning_root)
