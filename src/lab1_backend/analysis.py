from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lab1_backend.domain import AnalysisReport, Assignment, Evidence, Submission
from lab1_backend.exceptions import AnalyzerExecutionError, ConfigurationError
from lab1_backend.intake import SubmissionPayload, submission_from_payload
from lab1_backend.protocols import Analyzer, AssignmentSource, SubmissionSource


@dataclass(frozen=True, slots=True)
class AnalyzerContext:
    assignment: Assignment
    submission_source: SubmissionSource | None = None


class InMemorySubmissionSource:
    def __init__(self, submissions: list[Submission] | tuple[Submission, ...]) -> None:
        self._submissions = {item.submission_id: item for item in submissions}
        self.closed = False

    def get(self, submission_id: str) -> Submission | None:
        return self._submissions.get(submission_id)

    def list(self) -> tuple[Submission, ...]:
        return tuple(self._submissions.values())

    def close(self) -> None:
        self.closed = True


class JsonlSubmissionSource:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle = self._path.open("r", encoding="utf-8")
        self.closed = False
        self._submissions = self._load_submissions()

    def _load_submissions(self) -> dict[str, Submission]:
        items: dict[str, Submission] = {}
        for raw_line in self._handle:
            if not raw_line.strip():
                continue
            payload = SubmissionPayload.model_validate_json(raw_line)
            submission = submission_from_payload(payload)
            items[submission.submission_id] = submission
        self._handle.seek(0)
        return items

    def get(self, submission_id: str) -> Submission | None:
        return self._submissions.get(submission_id)

    def list(self) -> tuple[Submission, ...]:
        return tuple(self._submissions.values())

    def close(self) -> None:
        if not self.closed:
            self._handle.close()
            self.closed = True

    def __enter__(self) -> "JsonlSubmissionSource":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class InMemoryAssignmentSource:
    def __init__(self, assignments: list[Assignment] | tuple[Assignment, ...]) -> None:
        self._assignments = {item.assignment_id: item for item in assignments}

    def get(self, assignment_id: str) -> Assignment | None:
        return self._assignments.get(assignment_id)


class JsonAssignmentSource:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        with self._path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self._assignments = {
            item["assignment_id"]: Assignment(
                assignment_id=item["assignment_id"],
                title=item["title"],
                allowed_templates=tuple(item.get("allowed_templates", [])),
            )
            for item in payload
        }

    def get(self, assignment_id: str) -> Assignment | None:
        return self._assignments.get(assignment_id)


class LengthAnalyzer:
    analyzer_id = "length"
    analyzer_version = "1.0.0"

    def analyze(self, submission: Submission, context: AnalyzerContext) -> AnalysisReport:
        counts = {
            source: sum(1 for line in content.splitlines() if line.strip())
            for source, content in submission.content_by_source().items()
        }
        return AnalysisReport(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            score=None,
            rubric_feedback=(
                "Counted non-empty lines in text and code without executing user input."
            ),
            metadata=counts,
        )


class TemplateAnalyzer:
    analyzer_id = "template"
    analyzer_version = "1.0.0"

    def analyze(self, submission: Submission, context: AnalyzerContext) -> AnalysisReport:
        allowed = set(context.assignment.allowed_templates)
        evidence: list[Evidence] = []
        matched_templates: set[str] = set()

        for source, content in submission.content_by_source().items():
            for line_number, line in enumerate(content.splitlines(), start=1):
                if line in allowed:
                    matched_templates.add(line)
                    evidence.append(
                        Evidence(
                            source=source,
                            line_start=line_number,
                            line_end=line_number,
                            excerpt=line,
                        )
                    )

        similarity = (
            len(matched_templates) / len(allowed) if allowed else 0.0
        )
        feedback = (
            "Exact matches with approved template lines were found and treated as allowed."
            if evidence
            else "No exact matches with approved template lines were found."
        )
        return AnalysisReport(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            score=None,
            rubric_feedback=feedback,
            evidence=tuple(evidence),
            similarity=similarity,
            metadata={
                "matched_templates": tuple(sorted(matched_templates)),
                "template_count": len(allowed),
            },
        )


class AIDeclarationAnalyzer:
    analyzer_id = "ai_declaration"
    analyzer_version = "1.0.0"

    def analyze(self, submission: Submission, context: AnalyzerContext) -> AnalysisReport:
        details = (submission.ai_declaration.details or "").strip()
        if not submission.ai_declaration.used:
            feedback = "Submission does not declare AI usage."
        elif details:
            feedback = "AI declaration is present and non-empty for a submission that uses AI."
        else:
            feedback = "Submission declares AI usage but the AI declaration details are empty."
        return AnalysisReport(
            analyzer_id=self.analyzer_id,
            analyzer_version=self.analyzer_version,
            score=None,
            rubric_feedback=feedback,
            metadata={
                "used_ai": submission.ai_declaration.used,
                "has_details": bool(details),
            },
        )


class AnalysisService:
    def __init__(
        self,
        analyzer_registry: dict[str, Analyzer],
        assignment_source: AssignmentSource,
    ) -> None:
        self._analyzer_registry = dict(analyzer_registry)
        self._assignment_source = assignment_source

    def analyze(
        self,
        analyzer_id: str,
        submission: Submission,
        submission_source: SubmissionSource | None = None,
    ) -> AnalysisReport:
        analyzer = self._analyzer_registry.get(analyzer_id)
        if analyzer is None:
            raise ConfigurationError(
                "analyzer_id",
                f"Analyzer '{analyzer_id}' is not registered.",
            )

        assignment = self._assignment_source.get(submission.assignment_id)
        if assignment is None:
            raise ConfigurationError(
                "assignment_id",
                f"Assignment '{submission.assignment_id}' is not available.",
            )

        context = AnalyzerContext(
            assignment=assignment,
            submission_source=submission_source,
        )
        try:
            return analyzer.analyze(submission, context)
        except Exception as error:  # pragma: no cover - defensive wrapper
            raise AnalyzerExecutionError(
                analyzer_id,
                f"Analyzer '{analyzer_id}' failed: {error}",
            ) from error
