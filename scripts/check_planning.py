"""Kiểm tra tài liệu tracking bằng standard library, không đọc dataset hoặc gọi API."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

STATUSES = {"TODO", "READY", "IN_PROGRESS", "BLOCKED", "REVIEW", "DONE"}
TASK_ID = re.compile(r"(?:M[0-8]|W)-\d{2}[a-z]?")
COUNT_ORDER = ("DONE", "IN_PROGRESS", "BLOCKED", "TODO", "READY", "REVIEW")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def table_rows(text: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("|") and not re.match(r"^\|[ :\-]+\|", line)
    ]


def section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    require(text.count(marker) == 1, f"Missing/duplicate section: {heading}")
    return text.split(marker, 1)[1].split("\n## ", 1)[0].strip()


def check(root: Path) -> int:
    planning = root / "planning"
    registry = (planning / "tasks.md").read_text(encoding="utf-8")
    rows = table_rows(section(registry, "Registry"))
    require(len(rows) > 1 and len(rows[0]) == 8, "Invalid registry table")
    tasks = {}
    dependencies = {}
    for row in rows[1:]:
        require(len(row) == 8, "Registry row must have eight columns")
        task_id, name, milestone, status, priority, deps, spec, evidence = row
        require(bool(TASK_ID.fullmatch(task_id)), f"Invalid Task ID: {task_id}")
        require(task_id not in tasks, f"Duplicate Task ID: {task_id}")
        require(bool(name) and milestone == task_id.split("-")[0], f"Bad metadata: {task_id}")
        require(status in STATUSES, f"Invalid status: {task_id}")
        require(priority in {"P0", "P1", "P2"}, f"Invalid priority: {task_id}")
        require(bool(re.fullmatch(r"\[[^\]]+\]\([^)]+\)", spec)), f"Missing spec: {task_id}")
        dependencies[task_id] = [] if deps == "-" else [value.strip() for value in deps.split(",")]
        require(
            len(set(dependencies[task_id])) == len(dependencies[task_id]),
            f"Repeated dependency: {task_id}",
        )
        if status == "DONE":
            require(
                bool(re.search(r"/commit/[0-9a-f]{40}", evidence)),
                f"Missing DONE evidence: {task_id}",
            )
        if status == "READY":
            require(
                f"tasks/{milestone}/" in spec and "#" not in spec,
                f"READY needs full specification: {task_id}",
            )
        tasks[task_id] = row

    require(sum(row[3] == "IN_PROGRESS" for row in tasks.values()) <= 1, "Multiple active tasks")
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        require(task_id not in visiting, f"Dependency cycle: {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in dependencies[task_id]:
            require(dependency in tasks, f"Unknown dependency: {task_id} -> {dependency}")
            visit(dependency)
            if tasks[task_id][3] in {"READY", "IN_PROGRESS", "REVIEW", "DONE"}:
                require(
                    tasks[dependency][3] == "DONE",
                    f"Unfinished dependency: {task_id} -> {dependency}",
                )
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)

    dashboard = (planning / "progress.md").read_text(encoding="utf-8")
    counts = table_rows(section(dashboard, "Số task theo milestone và trạng thái"))[1:]
    milestones = [f"M{i}" for i in range(9)]
    if any(task[2] == "W" for task in tasks.values()):
        milestones.append("W")
    require(len(counts) == len(milestones) + 1, "Dashboard must contain milestones and TOTAL")
    for row, milestone in zip(counts, [*milestones, "TOTAL"], strict=True):
        subset = [task for task in tasks.values() if milestone == "TOTAL" or task[2] == milestone]
        counter = Counter(task[3] for task in subset)
        expected = [milestone, str(len(subset)), *(str(counter[status]) for status in COUNT_ORDER)]
        require(row == expected, f"Dashboard mismatch: {milestone}")

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
    for path in sorted((planning / "tasks").glob("*/*.md")):
        if path.parent.name not in milestones:
            continue
        text = path.read_text(encoding="utf-8")
        match = re.match(rf"# TASK ({TASK_ID.pattern}) — (.+)\n", text)
        require(match is not None, f"Invalid specification title: {path.name}")
        assert match is not None
        task_id, name = match.groups()
        require(
            task_id in tasks and name == tasks[task_id][1], f"Unknown/mismatched spec: {task_id}"
        )
        require(path.stem == task_id, f"Specification filename mismatch: {task_id}")
        for heading in headings:
            section(text, heading)
        metadata = section(text, "Metadata")
        for label, expected in (
            ("Milestone", tasks[task_id][2]),
            ("Status", tasks[task_id][3]),
            ("Priority", tasks[task_id][4]),
            ("Dependencies", tasks[task_id][5]),
        ):
            require(
                f"- {label}: {expected}\n" in metadata + "\n",
                f"Spec metadata mismatch: {task_id}/{label}",
            )
        require(
            bool(re.search(r"^- Estimated Complexity: (XS|S|M|L)$", metadata, re.M)),
            f"Missing complexity: {task_id}",
        )
        if tasks[task_id][3] == "DONE":
            require(
                "- [ ]" not in section(text, "Acceptance Criteria"), f"Open criteria: {task_id}"
            )
            require(
                bool(re.search(r"[0-9a-f]{40}", section(text, "Implementation Evidence"))),
                f"Missing spec evidence: {task_id}",
            )

    handoff = (planning / "handoff.md").read_text(encoding="utf-8")
    for heading in (
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
    ):
        section(handoff, heading)
    active = TASK_ID.search(section(handoff, "Active Task"))
    require(active is not None and active.group() in tasks, "Missing handoff task")
    assert active is not None
    require(section(handoff, "Status") == tasks[active.group()][3], "Handoff status mismatch")

    documents = [
        root / "README.md",
        root / "AGENTS.md",
        *sorted((root / "docs").glob("*.md")),
        *sorted((root / "docs" / "web-demo-v1").glob("*.md")),
        *sorted(planning.rglob("*.md")),
    ]
    for path in documents:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", text):
            if target.startswith(("https://", "http://", "mailto:")):
                continue
            filename, _, anchor = unquote(target).partition("#")
            destination = (path.parent / filename).resolve() if filename else path.resolve()
            require(
                destination.is_relative_to(root.resolve()) and destination.is_file(),
                f"Broken link: {path.name} -> {target}",
            )
            if anchor:
                content = destination.read_text(encoding="utf-8")
                anchors = set(re.findall(r'<a\s+id="([^"]+)"', content))
                for heading in re.findall(r"^#{1,6} (.+)$", content, re.M):
                    anchors.add(re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-"))
                require(anchor in anchors, f"Broken anchor: {path.name} -> {target}")
    return len(tasks)


if __name__ == "__main__":
    try:
        count = check(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as error:
        raise SystemExit(f"Planning check failed: {error}") from error
    print(
        f"Planning check passed: {count} tasks; dependencies, statuses, evidence, dashboard, specs and links are consistent."
    )
