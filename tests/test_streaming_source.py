from __future__ import annotations

import json
from pathlib import Path

from lab1_backend.analysis import JsonlSubmissionSource


def payload(submission_id: str, assignment_id: str) -> dict[str, object]:
    return {
        "submission_id": submission_id,
        "assignment_id": assignment_id,
        "student_id": f"student-{submission_id}",
        "submitted_at": "2026-11-01T10:00:00+03:00",
        "text_answer": "answer",
        "code": "print('ok')",
        "language": "python",
        "ai_declaration": {"used": False, "details": None},
    }


def test_jsonl_source_iterates_by_assignment(tmp_path: Path) -> None:
    path = tmp_path / "submissions.jsonl"
    rows = [
        payload("a", "lab-1"),
        payload("b", "lab-2"),
        payload("c", "lab-1"),
    ]
    path.write_text(
        "\n".join(json.dumps(item) for item in rows),
        encoding="utf-8",
    )

    with JsonlSubmissionSource(path) as source:
        selected = tuple(source.iter_by_assignment("lab-1"))

    assert [item.submission_id for item in selected] == ["a", "c"]
