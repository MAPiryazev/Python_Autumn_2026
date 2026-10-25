from __future__ import annotations

from typing import Protocol, runtime_checkable

from lab1_backend.domain import AnalysisReport, Assignment, Submission


@runtime_checkable
class SubmissionRepository(Protocol):
    def get(self, submission_id: str) -> Submission | None:
        ...

    def save(self, submission: Submission) -> Submission:
        ...

    def count(self) -> int:
        ...


@runtime_checkable
class SubmissionSource(Protocol):
    def get(self, submission_id: str) -> Submission | None:
        ...

    def list(self) -> tuple[Submission, ...]:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class AssignmentSource(Protocol):
    def get(self, assignment_id: str) -> Assignment | None:
        ...


@runtime_checkable
class Analyzer(Protocol):
    analyzer_id: str
    analyzer_version: str

    def analyze(
        self,
        submission: Submission,
        context: object,
    ) -> AnalysisReport:
        ...
