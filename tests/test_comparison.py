from __future__ import annotations

from lab1_backend.analysis import JsonAssignmentSource, JsonlSubmissionSource
from lab1_backend.comparison import (
    ComparisonConfig,
    ComparisonService,
    FeatureExtractor,
    InMemoryComparisonCache,
    jaccard,
)
from lab1_backend.domain import Assignment, Submission
from lab1_backend.intake import SubmissionPayload, submission_from_payload


def make_submission(
    *,
    submission_id: str,
    assignment_id: str = "lab-02",
    student_id: str = "student-1",
    code: str,
) -> Submission:
    payload = SubmissionPayload.model_validate(
        {
            "submission_id": submission_id,
            "assignment_id": assignment_id,
            "student_id": student_id,
            "submitted_at": "2026-11-01T10:00:00+03:00",
            "text_answer": "",
            "code": code,
            "language": "python",
            "ai_declaration": {"used": False, "details": None},
        }
    )
    return submission_from_payload(payload)


def test_jaccard_returns_none_for_empty_union() -> None:
    score, intersection, union = jaccard(frozenset(), frozenset())

    assert score is None
    assert intersection == 0
    assert union == 0


def test_full_scan_excludes_self_and_other_assignments() -> None:
    target = make_submission(submission_id="target", code="def f(x):\n    return x + 1")
    similar = make_submission(
        submission_id="similar",
        student_id="student-2",
        code="def f(y):\n    return y + 1",
    )
    other_assignment = make_submission(
        submission_id="other",
        assignment_id="other-lab",
        student_id="student-3",
        code=target.code,
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    report = ComparisonService(ComparisonConfig(top_k=5)).compare(
        target=target,
        submissions=[target, similar, other_assignment],
        assignment=assignment,
    )

    assert [match.submission_id for match in report.matches] == ["similar"]
    assert report.matches[0].similarity is not None


def test_repeated_same_student_version_is_marked_not_review_required() -> None:
    target = make_submission(
        submission_id="v1",
        student_id="same-student",
        code="def f(x):\n    return x + 1",
    )
    repeated = make_submission(
        submission_id="v2",
        student_id="same-student",
        code="def f(x):\n    return x + 1",
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    report = ComparisonService(ComparisonConfig(review_threshold=0.1)).compare(
        target=target,
        submissions=[repeated],
        assignment=assignment,
    )

    assert report.matches[0].same_student is True
    assert report.matches[0].review_required is False


def test_comments_and_whitespace_do_not_break_similarity() -> None:
    target = make_submission(
        submission_id="a",
        student_id="student-a",
        code="def f(x):\n    return x + 1\n",
    )
    commented = make_submission(
        submission_id="b",
        student_id="student-b",
        code="# comment\ndef f( x ):\n    # another comment\n    return x + 1\n",
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    report = ComparisonService(ComparisonConfig(review_threshold=0.6)).compare(
        target=target,
        submissions=[commented],
        assignment=assignment,
    )

    assert report.matches[0].similarity is not None
    assert report.matches[0].similarity >= 0.6
    assert report.matches[0].review_required is True


def test_empty_and_comment_only_inputs_are_insufficient_data() -> None:
    target = make_submission(submission_id="empty", code="")
    candidate = make_submission(
        submission_id="comments",
        student_id="student-2",
        code="# no code\n# no tokens",
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    report = ComparisonService().compare(
        target=target,
        submissions=[candidate],
        assignment=assignment,
    )

    assert report.matches[0].similarity is None
    assert report.matches[0].insufficient_data is True


def test_template_only_overlap_is_not_review_required() -> None:
    target = make_submission(
        submission_id="template-a",
        student_id="student-a",
        code="def solve():\n    data = input().strip()\n    result = data\n    print(result)",
    )
    candidate = make_submission(
        submission_id="template-b",
        student_id="student-b",
        code=target.code,
    )
    assignment = Assignment(
        assignment_id="lab-02",
        title="Lab 2",
        allowed_templates=(
            "def solve():",
            "    data = input().strip()",
            "    result = data",
            "    print(result)",
        ),
    )

    report = ComparisonService(ComparisonConfig(review_threshold=0.1)).compare(
        target=target,
        submissions=[candidate],
        assignment=assignment,
    )

    assert report.matches[0].review_required is False
    assert report.matches[0].insufficient_data is True
    assert report.matches[0].metadata["template_intersection_size"] > 0


def test_cache_key_changes_with_configuration() -> None:
    submission = make_submission(
        submission_id="target",
        code="def f(x):\n    return x + 1",
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")
    cache = InMemoryComparisonCache()

    FeatureExtractor(ComparisonConfig(ngram_size=3)).extract(submission, assignment)
    service_a = ComparisonService(config=ComparisonConfig(ngram_size=3), cache=cache)
    service_a.compare(target=submission, submissions=[], assignment=assignment)
    service_a.compare(target=submission, submissions=[], assignment=assignment)
    service_b = ComparisonService(config=ComparisonConfig(ngram_size=4), cache=cache)
    service_b.compare(target=submission, submissions=[], assignment=assignment)

    assert cache.hits >= 1
    assert cache.misses >= 2


def test_ngram_index_reports_index_metadata() -> None:
    target = make_submission(
        submission_id="target",
        student_id="student-a",
        code="def f(x):\n    return x + 1",
    )
    similar = make_submission(
        submission_id="similar",
        student_id="student-b",
        code="def f(y):\n    return y + 1",
    )
    unrelated = make_submission(
        submission_id="unrelated",
        student_id="student-c",
        code="def g(items):\n    return list(reversed(items))",
    )
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    report = ComparisonService(
        ComparisonConfig(candidate_strategy="ngram_index", top_k=5)
    ).compare(target=target, submissions=[similar, unrelated], assignment=assignment)

    assert report.metadata["candidate_strategy"] == "ngram_index"
    assert report.metadata["index_version"] == "ngram-index-v1"
    assert report.matches[0].submission_id == "similar"


def test_lab2_example_dataset_can_be_loaded() -> None:
    assignment_source = JsonAssignmentSource("examples/lab2_assignments.json")
    with JsonlSubmissionSource("examples/lab2_submissions.jsonl") as source:
        target = source.get("lab2-sub-001")
        assert target is not None
        assignment = assignment_source.get(target.assignment_id)
        assert assignment is not None
        report = ComparisonService(ComparisonConfig(top_k=3)).compare(
            target=target,
            submissions=source.iter_by_assignment(target.assignment_id),
            assignment=assignment,
        )

    assert report.matches
    assert report.matches[0].submission_id in {"lab2-sub-002", "lab2-sub-016"}
