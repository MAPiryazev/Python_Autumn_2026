from __future__ import annotations

import json
import random
import statistics
import time
import tracemalloc
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from lab1_backend.analysis import JsonAssignmentSource, JsonlSubmissionSource
from lab1_backend.comparison import (
    ComparisonConfig,
    ComparisonService,
    NgramCandidateIndex,
    iter_report_dict,
)
from lab1_backend.domain import Assignment, Submission
from lab1_backend.intake import SubmissionPayload, submission_from_payload


@dataclass(frozen=True, slots=True)
class LabeledPair:
    left_submission_id: str
    right_submission_id: str
    review_required: bool
    relation: str


@dataclass(frozen=True, slots=True)
class ConfusionMatrix:
    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def load_labels(path: str | Path) -> tuple[LabeledPair, ...]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(
        LabeledPair(
            left_submission_id=item["left_submission_id"],
            right_submission_id=item["right_submission_id"],
            review_required=bool(item["review_required"]),
            relation=item.get("relation", "unknown"),
        )
        for item in payload
    )


def evaluate_labeled_pairs(
    *,
    labels: Iterable[LabeledPair],
    submissions: Mapping[str, Submission],
    assignments: Mapping[str, Assignment],
    config: ComparisonConfig,
) -> Mapping[str, object]:
    matrix = ConfusionMatrix()
    uncertain = 0
    evaluated = 0
    details: list[Mapping[str, object]] = []

    for label in labels:
        left = submissions[label.left_submission_id]
        right = submissions[label.right_submission_id]
        assignment = assignments[left.assignment_id]
        service = ComparisonService(config=config)
        report = service.compare(target=left, submissions=[right], assignment=assignment)
        match = report.matches[0] if report.matches else None
        prediction = bool(match and match.review_required)
        is_uncertain = bool(match and match.insufficient_data)
        if is_uncertain:
            uncertain += 1
        evaluated += 1

        if prediction and label.review_required:
            matrix = ConfusionMatrix(
                matrix.true_positive + 1,
                matrix.false_positive,
                matrix.true_negative,
                matrix.false_negative,
            )
        elif prediction and not label.review_required:
            matrix = ConfusionMatrix(
                matrix.true_positive,
                matrix.false_positive + 1,
                matrix.true_negative,
                matrix.false_negative,
            )
        elif not prediction and not label.review_required:
            matrix = ConfusionMatrix(
                matrix.true_positive,
                matrix.false_positive,
                matrix.true_negative + 1,
                matrix.false_negative,
            )
        else:
            matrix = ConfusionMatrix(
                matrix.true_positive,
                matrix.false_positive,
                matrix.true_negative,
                matrix.false_negative + 1,
            )
        details.append(
            {
                "left_submission_id": label.left_submission_id,
                "right_submission_id": label.right_submission_id,
                "relation": label.relation,
                "expected_review_required": label.review_required,
                "predicted_review_required": prediction,
                "similarity": match.similarity if match else None,
                "insufficient_data": is_uncertain,
            }
        )

    return {
        "confusion_matrix": matrix.as_dict(),
        "uncertain_share": uncertain / evaluated if evaluated else 0.0,
        "evaluated_pairs": evaluated,
        "details": details,
    }


def run_experiment(
    *,
    assignments_path: str | Path,
    submissions_path: str | Path,
    labels_path: str | Path | None,
    sizes: Iterable[int],
    repeats: int,
    seed: int,
    review_threshold: float = 0.65,
) -> Mapping[str, object]:
    assignment_source = JsonAssignmentSource(assignments_path)
    with JsonlSubmissionSource(submissions_path) as source:
        base_submissions = source.list()
    assignments = {
        submission.assignment_id: assignment_source.get(submission.assignment_id)
        for submission in base_submissions
    }
    assignment_map = {
        key: value for key, value in assignments.items() if value is not None
    }
    quality = None
    if labels_path is not None:
        labels = load_labels(labels_path)
        quality = evaluate_labeled_pairs(
            labels=labels,
            submissions={item.submission_id: item for item in base_submissions},
            assignments=assignment_map,
            config=ComparisonConfig(review_threshold=review_threshold, top_k=1),
        )

    benchmark = []
    for size in sizes:
        corpus = synthetic_corpus(size=size, seed=seed, base=base_submissions)
        target = corpus[0]
        assignment = assignment_source.get(target.assignment_id) or Assignment(
            assignment_id=target.assignment_id,
            title="Synthetic assignment",
        )
        for strategy in ("full_scan", "ngram_index"):
            runs = []
            for repeat in range(repeats):
                config = ComparisonConfig(
                    candidate_strategy=strategy,  # type: ignore[arg-type]
                    top_k=5,
                    review_threshold=review_threshold,
                )
                service = ComparisonService(config=config)
                index_build_time = None
                if strategy == "ngram_index":
                    build_started = time.perf_counter()
                    index = NgramCandidateIndex(
                        submissions=corpus,
                        assignment=assignment,
                        service=service,
                    )
                    target_feature = service.features_for(target, assignment)
                    candidates, strategy_metadata = index.candidates_for(
                        target=target,
                        target_feature=target_feature,
                    )
                    index_build_time = time.perf_counter() - build_started
                    tracemalloc.start()
                    started = time.perf_counter()
                    report = service.compare_with_candidates(
                        target=target,
                        target_feature=target_feature,
                        candidates=candidates,
                        assignment=assignment,
                        strategy_metadata=strategy_metadata,
                    )
                else:
                    tracemalloc.start()
                    started = time.perf_counter()
                    report = service.compare(
                        target=target,
                        submissions=corpus,
                        assignment=assignment,
                    )
                wall_time = time.perf_counter() - started
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                runs.append(
                    {
                        "repeat": repeat + 1,
                        "wall_time_seconds": wall_time,
                        "index_build_time_seconds": index_build_time,
                        "peak_memory_bytes": peak,
                        "comparison_count": report.metadata["comparison_count"],
                        "candidate_count": report.metadata["candidate_count"],
                    }
                )
            times = [item["wall_time_seconds"] for item in runs]
            peaks = [item["peak_memory_bytes"] for item in runs]
            build_times = [
                item["index_build_time_seconds"]
                for item in runs
                if item["index_build_time_seconds"] is not None
            ]
            benchmark.append(
                {
                    "size": size,
                    "strategy": strategy,
                    "seed": seed,
                    "repeats": repeats,
                    "timing_scope": (
                        "query_only_prebuilt_index"
                        if strategy == "ngram_index"
                        else "full_scan_query"
                    ),
                    "average_wall_time_seconds": statistics.fmean(times),
                    "median_wall_time_seconds": statistics.median(times),
                    "average_peak_memory_bytes": statistics.fmean(peaks),
                    "median_peak_memory_bytes": statistics.median(peaks),
                    "average_index_build_time_seconds": (
                        statistics.fmean(build_times) if build_times else None
                    ),
                    "median_index_build_time_seconds": (
                        statistics.median(build_times) if build_times else None
                    ),
                    "runs": runs,
                }
            )

    return {
        "parameters": {
            "sizes": tuple(sizes),
            "repeats": repeats,
            "seed": seed,
            "review_threshold": review_threshold,
            "corpus_profile": (
                "Manual labeled examples for quality; deterministic synthetic "
                "copies and variants for load measurements."
            ),
        },
        "quality": quality,
        "benchmark": benchmark,
    }


def synthetic_corpus(
    *,
    size: int,
    seed: int,
    base: tuple[Submission, ...],
) -> tuple[Submission, ...]:
    if not base:
        raise ValueError("base corpus must not be empty")
    rng = random.Random(seed)
    items: list[Submission] = []
    templates = [item for item in base if item.assignment_id == "lab2-python"] or list(base)
    for index in range(size):
        original = templates[index % len(templates)]
        code = _variant_code(original.code, index, rng)
        payload = SubmissionPayload.model_validate(
            {
                "submission_id": f"synthetic-{index:05d}",
                "assignment_id": original.assignment_id,
                "student_id": f"synthetic-student-{index:05d}",
                "submitted_at": "2026-11-02T09:00:00+03:00",
                "text_answer": f"Synthetic load sample {index}",
                "code": code,
                "language": original.language,
                "ai_declaration": {"used": False, "details": None},
            }
        )
        items.append(submission_from_payload(payload))
    return tuple(items)


def _variant_code(code: str, index: int, rng: random.Random) -> str:
    if index % 5 == 0:
        return code
    prefix = "# synthetic variant\n" if index % 2 == 0 else ""
    suffix = f"\n# seed noise {rng.randrange(1000)}" if index % 3 == 0 else ""
    return prefix + code.replace("result", f"result_{index}").replace("number", f"number_{index}") + suffix


def experiment_dict_to_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def compact_report(report: Mapping[str, object]) -> str:
    return json.dumps(report, ensure_ascii=False)


__all__ = [
    "ConfusionMatrix",
    "LabeledPair",
    "evaluate_labeled_pairs",
    "experiment_dict_to_json",
    "iter_report_dict",
    "load_labels",
    "run_experiment",
    "synthetic_corpus",
]
