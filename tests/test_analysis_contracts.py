from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab1_backend.analysis import (
    AIDeclarationAnalyzer,
    AnalysisService,
    InMemoryAssignmentSource,
    InMemorySubmissionSource,
    JsonlSubmissionSource,
    LengthAnalyzer,
    TemplateAnalyzer,
)
from lab1_backend.domain import Assignment, Submission
from lab1_backend.exceptions import AnalyzerExecutionError
from lab1_backend.intake import SubmissionPayload, submission_from_payload


def make_submission(
    *,
    submission_id: str = "sub-100",
    text_answer: str = "allowed()\nanswer line",
    code: str = "allowed()\nprint('ok')\n",
) -> Submission:
    payload = SubmissionPayload.model_validate(
        {
            "submission_id": submission_id,
            "assignment_id": "lab-01",
            "student_id": "student-1",
            "submitted_at": "2026-10-25T15:00:00+03:00",
            "text_answer": text_answer,
            "code": code,
            "language": "python",
            "ai_declaration": {"used": False, "details": None},
        }
    )
    return submission_from_payload(payload)


def write_jsonl(path: Path, submissions: list[Submission]) -> None:
    payloads = []
    for submission in submissions:
        payloads.append(
            {
                "submission_id": submission.submission_id,
                "assignment_id": submission.assignment_id,
                "student_id": submission.student_id,
                "submitted_at": submission.submitted_at.isoformat(),
                "text_answer": submission.text_answer,
                "code": submission.code,
                "language": submission.language,
                "ai_declaration": {
                    "used": submission.ai_declaration.used,
                    "details": submission.ai_declaration.details,
                },
            }
        )
    path.write_text(
        "\n".join(json.dumps(item) for item in payloads),
        encoding="utf-8",
    )


@pytest.mark.parametrize("source_kind", ["in_memory", "jsonl"])
def test_submission_sources_follow_common_contract(
    tmp_path: Path,
    source_kind: str,
) -> None:
    submissions = [make_submission(submission_id="sub-100")]

    if source_kind == "in_memory":
        source = InMemorySubmissionSource(submissions)
    else:
        path = tmp_path / "submissions.jsonl"
        write_jsonl(path, submissions)
        source = JsonlSubmissionSource(path)

    try:
        listed = source.list()
        loaded = source.get("sub-100")

        assert len(listed) == 1
        assert listed[0].submission_id == "sub-100"
        assert loaded == submissions[0]
    finally:
        source.close()


@pytest.mark.parametrize(
    ("analyzer", "expected_id"),
    [
        (LengthAnalyzer(), "length"),
        (TemplateAnalyzer(), "template"),
    ],
)
def test_analyzers_follow_common_contract(
    analyzer: object,
    expected_id: str,
) -> None:
    submission = make_submission()
    original = submission
    assignment = Assignment(
        assignment_id="lab-01",
        title="Lab 1",
        allowed_templates=("allowed()",),
    )
    service = AnalysisService(
        analyzer_registry={
            "length": LengthAnalyzer(),
            "template": TemplateAnalyzer(),
        },
        assignment_source=InMemoryAssignmentSource([assignment]),
    )

    report = service.analyze(expected_id, submission)

    assert report.analyzer_id == expected_id
    assert report.analyzer_version
    assert submission == original
    assert isinstance(report.rubric_feedback, str)
    for evidence in report.evidence:
        source_lines = submission.content_by_source()[evidence.source].splitlines()
        assert 1 <= evidence.line_start <= evidence.line_end <= len(source_lines)


def test_analysis_service_wraps_analyzer_errors() -> None:
    class BrokenAnalyzer:
        analyzer_id = "broken"
        analyzer_version = "1.0.0"

        def analyze(self, submission: Submission, context: object) -> object:
            raise RuntimeError("boom")

    assignment = Assignment(
        assignment_id="lab-01",
        title="Lab 1",
        allowed_templates=(),
    )
    service = AnalysisService(
        analyzer_registry={"broken": BrokenAnalyzer()},
        assignment_source=InMemoryAssignmentSource([assignment]),
    )

    with pytest.raises(AnalyzerExecutionError) as exc_info:
        service.analyze("broken", make_submission())

    assert exc_info.value.code == "analyzer_error"


def test_jsonl_source_releases_resource(tmp_path: Path) -> None:
    path = tmp_path / "submissions.jsonl"
    write_jsonl(path, [make_submission()])
    source = JsonlSubmissionSource(path)

    source.close()

    assert source.closed is True


def test_template_analyzer_reports_similarity_and_evidence() -> None:
    submission = make_submission(
        text_answer="allowed()\nanswer line",
        code="print('x')\nallowed()",
    )
    assignment = Assignment(
        assignment_id="lab-01",
        title="Lab 1",
        allowed_templates=("allowed()", "import this"),
    )
    service = AnalysisService(
        analyzer_registry={"template": TemplateAnalyzer()},
        assignment_source=InMemoryAssignmentSource([assignment]),
    )

    report = service.analyze("template", submission)

    assert report.similarity == 0.5
    assert len(report.evidence) == 2


def test_ai_declaration_analyzer_can_be_added_without_service_changes() -> None:
    submission = make_submission()
    payload = SubmissionPayload.model_validate(
        {
            "submission_id": "sub-ai",
            "assignment_id": "lab-01",
            "student_id": "student-2",
            "submitted_at": "2026-10-25T15:30:00+03:00",
            "text_answer": "answer",
            "code": "print('ok')",
            "language": "python",
            "ai_declaration": {"used": True, "details": ""},
        }
    )
    submission = submission_from_payload(payload)
    assignment = Assignment(
        assignment_id="lab-01",
        title="Lab 1",
        allowed_templates=(),
    )
    service = AnalysisService(
        analyzer_registry={"ai_declaration": AIDeclarationAnalyzer()},
        assignment_source=InMemoryAssignmentSource([assignment]),
    )

    report = service.analyze("ai_declaration", submission)

    assert report.analyzer_id == "ai_declaration"
    assert report.metadata["used_ai"] is True
    assert report.metadata["has_details"] is False
