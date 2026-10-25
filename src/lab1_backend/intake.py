from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from lab1_backend.domain import (
    AIDeclaration,
    AcceptanceResult,
    ImportBatchResult,
    ImportIssue,
    Submission,
)
from lab1_backend.exceptions import (
    SubmissionConflictError,
    SubmissionFormatError,
    SubmissionSchemaError,
)
from lab1_backend.protocols import SubmissionRepository


class AIDeclarationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    used: bool
    details: str | None = None


class SubmissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_id: str
    assignment_id: str
    student_id: str
    submitted_at: datetime
    text_answer: str = ""
    code: str = ""
    language: str | None = None
    ai_declaration: AIDeclarationPayload

    @field_validator("submission_id", "assignment_id", "student_id")
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be empty.")
        return value

    @field_validator("submitted_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include timezone information.")
        return value


def submission_from_payload(payload: SubmissionPayload) -> Submission:
    canonical_payload = payload.model_dump(mode="json")
    content_hash = sha256(
        json.dumps(canonical_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return Submission(
        submission_id=payload.submission_id,
        assignment_id=payload.assignment_id,
        student_id=payload.student_id,
        submitted_at=payload.submitted_at,
        text_answer=payload.text_answer,
        code=payload.code,
        language=payload.language,
        ai_declaration=AIDeclaration(
            used=payload.ai_declaration.used,
            details=payload.ai_declaration.details,
        ),
        content_hash=content_hash,
    )


def _to_schema_error(error: ValidationError) -> SubmissionSchemaError:
    first_error = error.errors()[0]
    location = ".".join(str(part) for part in first_error["loc"]) or None
    return SubmissionSchemaError(location, first_error["msg"])


@dataclass
class InMemorySubmissionRepository:
    _storage: dict[str, Submission]

    def __init__(self) -> None:
        self._storage = {}

    def get(self, submission_id: str) -> Submission | None:
        return self._storage.get(submission_id)

    def save(self, submission: Submission) -> Submission:
        self._storage[submission.submission_id] = submission
        return submission

    def count(self) -> int:
        return len(self._storage)


class SubmissionIntakeService:
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def accept(self, submission: Submission) -> AcceptanceResult:
        existing = self._repository.get(submission.submission_id)
        if existing is None:
            self._repository.save(submission)
            return AcceptanceResult(status="accepted", submission=submission)
        if existing.content_hash == submission.content_hash:
            return AcceptanceResult(status="duplicate", submission=existing)
        raise SubmissionConflictError(submission.submission_id)


class SubmissionIntakeAdapter:
    def __init__(self, service: SubmissionIntakeService) -> None:
        self._service = service

    def accept_payload(
        self,
        payload: SubmissionPayload | Mapping[str, Any],
    ) -> AcceptanceResult:
        try:
            model = (
                payload
                if isinstance(payload, SubmissionPayload)
                else SubmissionPayload.model_validate(dict(payload))
            )
        except ValidationError as error:
            raise _to_schema_error(error) from error
        return self._service.accept(submission_from_payload(model))

    def import_jsonl(self, lines: Iterable[str]) -> ImportBatchResult:
        accepted: list[Submission] = []
        duplicates: list[str] = []
        errors: list[ImportIssue] = []
        for line_number, raw_line in enumerate(lines, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as error:
                issue = SubmissionFormatError("line", f"Line {line_number}: {error.msg}")
                errors.append(
                    ImportIssue(line_number=line_number, error=issue.as_dict())
                )
                continue
            try:
                result = self.accept_payload(payload)
            except (SubmissionSchemaError, SubmissionConflictError) as error:
                errors.append(
                    ImportIssue(line_number=line_number, error=error.as_dict())
                )
                continue
            if result.status == "accepted":
                accepted.append(result.submission)
            else:
                duplicates.append(result.submission.submission_id)
        return ImportBatchResult(
            accepted=tuple(accepted),
            duplicates=tuple(duplicates),
            errors=tuple(errors),
        )
