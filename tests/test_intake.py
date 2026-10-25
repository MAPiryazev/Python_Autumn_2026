from __future__ import annotations

import copy

import pytest

from lab1_backend.exceptions import SubmissionConflictError, SubmissionSchemaError
from lab1_backend.intake import (
    InMemorySubmissionRepository,
    SubmissionIntakeAdapter,
    SubmissionIntakeService,
)


@pytest.fixture
def valid_payload() -> dict[str, object]:
    return {
        "submission_id": "sub-001",
        "assignment_id": "lab-01",
        "student_id": "student-42",
        "submitted_at": "2026-10-25T12:00:00+03:00",
        "text_answer": "First line\n\nSecond line",
        "code": "print('ok')\n",
        "language": "python",
        "ai_declaration": {
            "used": True,
            "details": "",
        },
    }


@pytest.fixture
def adapter() -> SubmissionIntakeAdapter:
    repository = InMemorySubmissionRepository()
    service = SubmissionIntakeService(repository)
    return SubmissionIntakeAdapter(service)


def test_accepts_valid_submission(
    adapter: SubmissionIntakeAdapter,
) -> None:
    result = adapter.accept_payload(
        {
            "submission_id": "sub-001",
            "assignment_id": "lab-01",
            "student_id": "student-42",
            "submitted_at": "2026-10-25T12:00:00+03:00",
            "text_answer": "ok",
            "code": "print('ok')",
            "language": "python",
            "ai_declaration": {"used": False, "details": None},
        }
    )

    assert result.status == "accepted"
    assert result.submission.student_id == "student-42"


def test_rejects_invalid_timestamp(
    adapter: SubmissionIntakeAdapter,
    valid_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["submitted_at"] = "2026-10-25T12:00:00"

    with pytest.raises(SubmissionSchemaError) as exc_info:
        adapter.accept_payload(payload)

    assert exc_info.value.field == "submitted_at"


def test_rejects_empty_student_id(
    adapter: SubmissionIntakeAdapter,
    valid_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["student_id"] = "   "

    with pytest.raises(SubmissionSchemaError) as exc_info:
        adapter.accept_payload(payload)

    assert exc_info.value.field == "student_id"


def test_rejects_unknown_field(
    adapter: SubmissionIntakeAdapter,
    valid_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["unexpected"] = "boom"

    with pytest.raises(SubmissionSchemaError) as exc_info:
        adapter.accept_payload(payload)

    assert exc_info.value.field == "unexpected"


def test_rejects_wrong_types(
    adapter: SubmissionIntakeAdapter,
    valid_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(valid_payload)
    payload["code"] = 7

    with pytest.raises(SubmissionSchemaError) as exc_info:
        adapter.accept_payload(payload)

    assert exc_info.value.field == "code"


def test_duplicate_does_not_increase_submission_count(
    valid_payload: dict[str, object],
) -> None:
    repository = InMemorySubmissionRepository()
    adapter = SubmissionIntakeAdapter(SubmissionIntakeService(repository))

    first = adapter.accept_payload(valid_payload)
    second = adapter.accept_payload(valid_payload)

    assert first.status == "accepted"
    assert second.status == "duplicate"
    assert repository.count() == 1


def test_conflict_does_not_overwrite_original_submission(
    valid_payload: dict[str, object],
) -> None:
    repository = InMemorySubmissionRepository()
    adapter = SubmissionIntakeAdapter(SubmissionIntakeService(repository))
    adapter.accept_payload(valid_payload)

    conflict_payload = copy.deepcopy(valid_payload)
    conflict_payload["text_answer"] = "Changed answer"

    with pytest.raises(SubmissionConflictError):
        adapter.accept_payload(conflict_payload)

    stored = repository.get("sub-001")
    assert stored is not None
    assert stored.text_answer == "First line\n\nSecond line"
    assert repository.count() == 1


def test_import_jsonl_continues_after_broken_lines(
    adapter: SubmissionIntakeAdapter,
) -> None:
    result = adapter.import_jsonl(
        [
            '{"submission_id": "broken"',
            (
                '{"submission_id": "sub-002", "assignment_id": "lab-01", '
                '"student_id": "student-77", '
                '"submitted_at": "2026-10-25T13:00:00+03:00", '
                '"text_answer": "ok", "code": "", "language": "python", '
                '"ai_declaration": {"used": false, "details": null}}'
            ),
            (
                '{"submission_id": "sub-003", "assignment_id": "lab-01", '
                '"student_id": "", '
                '"submitted_at": "2026-10-25T14:00:00+03:00", '
                '"text_answer": "bad", "code": "", "language": "python", '
                '"ai_declaration": {"used": false, "details": null}}'
            ),
        ]
    )

    assert [item.submission_id for item in result.accepted] == ["sub-002"]
    assert len(result.errors) == 2
    assert result.errors[0].error["code"] == "format_error"
    assert result.errors[1].error["code"] == "schema_error"


def test_accept_payload_does_not_mutate_input(
    adapter: SubmissionIntakeAdapter,
    valid_payload: dict[str, object],
) -> None:
    original = copy.deepcopy(valid_payload)

    adapter.accept_payload(valid_payload)

    assert valid_payload == original
