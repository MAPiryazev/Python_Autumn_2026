from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AIDeclaration:
    used: bool
    details: str | None = None


@dataclass(frozen=True, slots=True)
class Submission:
    submission_id: str
    assignment_id: str
    student_id: str
    submitted_at: datetime
    text_answer: str
    code: str
    language: str | None
    ai_declaration: AIDeclaration
    content_hash: str

    def content_by_source(self) -> dict[str, str]:
        return {
            "text_answer": self.text_answer,
            "code": self.code,
        }


@dataclass(frozen=True, slots=True)
class Assignment:
    assignment_id: str
    title: str
    allowed_templates: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    source: str
    line_start: int
    line_end: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    analyzer_id: str
    analyzer_version: str
    score: float | None
    rubric_feedback: str
    evidence: tuple[Evidence, ...] = ()
    similarity: float | None = None
    metadata: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    status: str
    submission: Submission


@dataclass(frozen=True, slots=True)
class ImportIssue:
    line_number: int
    error: Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class ImportBatchResult:
    accepted: tuple[Submission, ...]
    duplicates: tuple[str, ...]
    errors: tuple[ImportIssue, ...]
