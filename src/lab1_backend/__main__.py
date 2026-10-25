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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run analyzers for submissions from JSONL input."
    )
    parser.add_argument(
        "--assignments",
        default="examples/assignments.json",
        help="Path to assignments.json",
    )
    parser.add_argument(
        "--submissions",
        default="examples/submissions.jsonl",
        help="Path to submissions.jsonl",
    )
    parser.add_argument(
        "--analyzer",
        action="append",
        dest="analyzers",
        help="Analyzer id to run. Repeat flag to run several analyzers.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
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


if __name__ == "__main__":
    raise SystemExit(main())
