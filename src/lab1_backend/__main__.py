from __future__ import annotations

import argparse
import json

from lab1_backend.analysis import (
    AIDeclarationAnalyzer,
    JsonAssignmentSource,
    JsonlSubmissionSource,
    LengthAnalyzer,
    TemplateAnalyzer,
)
from lab1_backend.bootstrap import build_application
from lab1_backend.comparison import (
    ComparisonConfig,
    ComparisonService,
    iter_report_dict,
)
from lab1_backend.experiments import run_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run analyzers and Lab 2 similarity comparison for JSONL input."
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Run Lab 1 analyzers.")
    _add_common_paths(analyze)
    analyze.add_argument(
        "--analyzer",
        action="append",
        dest="analyzers",
        help="Analyzer id to run. Repeat flag to run several analyzers.",
    )

    compare = subparsers.add_parser("compare", help="Run Lab 2 similarity comparison.")
    _add_common_paths(compare, default_submissions="examples/lab2_submissions.jsonl")
    compare.add_argument("--submission-id", required=True, help="Target submission id.")
    compare.add_argument("--top-k", type=int, default=5, help="Number of matches to return.")
    compare.add_argument(
        "--strategy",
        choices=["full_scan", "ngram_index"],
        default="full_scan",
        help="Candidate selection strategy.",
    )
    compare.add_argument(
        "--review-threshold",
        type=float,
        default=0.65,
        help="Similarity threshold for review_required.",
    )

    experiment = subparsers.add_parser("experiment", help="Run Lab 2 quality and speed measurements.")
    _add_common_paths(experiment, default_submissions="examples/lab2_submissions.jsonl")
    experiment.add_argument("--labels", default="examples/lab2_labels.json", help="Path to labeled pairs JSON.")
    experiment.add_argument("--sizes", nargs="+", type=int, default=[100, 1000, 5000])
    experiment.add_argument("--repeats", type=int, default=3)
    experiment.add_argument("--seed", type=int, default=42)
    experiment.add_argument("--review-threshold", type=float, default=0.65)

    _add_common_paths(parser)
    parser.add_argument(
        "--analyzer",
        action="append",
        dest="analyzers",
        help="Analyzer id to run in default analyze mode.",
    )
    return parser


def _add_common_paths(
    parser: argparse.ArgumentParser,
    *,
    default_submissions: str = "examples/submissions.jsonl",
) -> None:
    parser.add_argument(
        "--assignments",
        default="examples/assignments.json",
        help="Path to assignments.json",
    )
    parser.add_argument(
        "--submissions",
        default=default_submissions,
        help="Path to submissions.jsonl",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "analyze"
    if command == "compare":
        return _run_compare(args)
    if command == "experiment":
        return _run_experiment(args)
    return _run_analyze(args)


def _run_analyze(args: argparse.Namespace) -> int:
    analyzer_ids = args.analyzers or ["length", "template", "ai_declaration"]

    assignment_source = JsonAssignmentSource(args.assignments)
    app = build_application(
        assignment_source=assignment_source,
        analyzers=[
            LengthAnalyzer(),
            TemplateAnalyzer(),
            AIDeclarationAnalyzer(),
        ],
    )

    with JsonlSubmissionSource(args.submissions) as submission_source:
        for submission in submission_source.list():
            for analyzer_id in analyzer_ids:
                report = app.analysis_service.analyze(
                    analyzer_id,
                    submission,
                    submission_source=submission_source,
                )
                print(
                    json.dumps(
                        {
                            "submission_id": submission.submission_id,
                            "analyzer_id": report.analyzer_id,
                            "analyzer_version": report.analyzer_version,
                            "score": report.score,
                            "similarity": report.similarity,
                            "rubric_feedback": report.rubric_feedback,
                            "metadata": dict(report.metadata),
                            "evidence": [
                                {
                                    "source": item.source,
                                    "line_start": item.line_start,
                                    "line_end": item.line_end,
                                    "excerpt": item.excerpt,
                                }
                                for item in report.evidence
                            ],
                        },
                        ensure_ascii=False,
                    )
                )
    return 0


def _run_compare(args: argparse.Namespace) -> int:
    assignment_source = JsonAssignmentSource(args.assignments)
    with JsonlSubmissionSource(args.submissions) as submission_source:
        target = submission_source.get(args.submission_id)
        if target is None:
            raise SystemExit(f"Submission '{args.submission_id}' is not available.")
        assignment = assignment_source.get(target.assignment_id)
        if assignment is None:
            raise SystemExit(f"Assignment '{target.assignment_id}' is not available.")
        config = ComparisonConfig(
            top_k=args.top_k,
            candidate_strategy=args.strategy,
            review_threshold=args.review_threshold,
        )
        report = ComparisonService(config=config).compare(
            target=target,
            submissions=submission_source.iter_by_assignment(target.assignment_id),
            assignment=assignment,
        )
    print(json.dumps(iter_report_dict(report), ensure_ascii=False, indent=2))
    return 0


def _run_experiment(args: argparse.Namespace) -> int:
    report = run_experiment(
        assignments_path=args.assignments,
        submissions_path=args.submissions,
        labels_path=args.labels,
        sizes=args.sizes,
        repeats=args.repeats,
        seed=args.seed,
        review_threshold=args.review_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
