from __future__ import annotations

from lab1_backend.experiments import ConfusionMatrix, evaluate_labeled_pairs, LabeledPair
from lab1_backend.comparison import ComparisonConfig
from lab1_backend.domain import Assignment, Submission
from lab1_backend.intake import SubmissionPayload, submission_from_payload


def make_submission(
    submission_id: str,
    code: str,
    student_id: str,
) -> Submission:
    payload = SubmissionPayload.model_validate(
        {
            "submission_id": submission_id,
            "assignment_id": "lab-02",
            "student_id": student_id,
            "submitted_at": "2026-11-01T10:00:00+03:00",
            "text_answer": "",
            "code": code,
            "language": "python",
            "ai_declaration": {"used": False, "details": None},
        }
    )
    return submission_from_payload(payload)


def test_confusion_matrix_metrics() -> None:
    matrix = ConfusionMatrix(
        true_positive=3,
        false_positive=1,
        true_negative=5,
        false_negative=1,
    )

    assert matrix.precision == 0.75
    assert matrix.recall == 0.75
    assert matrix.f1 == 0.75


def test_evaluate_labeled_pairs_reports_quality_metrics() -> None:
    left = make_submission("a", "def f(x):\n    return x + 1", "student-a")
    right = make_submission("b", "def f(y):\n    return y + 1", "student-b")
    empty = make_submission("c", "", "student-c")
    comments = make_submission("d", "# no code", "student-d")
    assignment = Assignment(assignment_id="lab-02", title="Lab 2")

    result = evaluate_labeled_pairs(
        labels=(
            LabeledPair("a", "b", True, "renamed_variables"),
            LabeledPair("c", "d", False, "insufficient_data"),
        ),
        submissions={item.submission_id: item for item in (left, right, empty, comments)},
        assignments={"lab-02": assignment},
        config=ComparisonConfig(review_threshold=0.5, top_k=1),
    )

    assert result["evaluated_pairs"] == 2
    assert result["uncertain_share"] == 0.5
    assert result["confusion_matrix"]["true_positive"] == 1
    assert result["confusion_matrix"]["true_negative"] == 1
