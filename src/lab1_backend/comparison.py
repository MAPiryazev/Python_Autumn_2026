from __future__ import annotations

import io
import json
import keyword
import tokenize
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Protocol

from lab1_backend.domain import (
    Assignment,
    ComparisonReport,
    Evidence,
    FeatureSet,
    SimilarityMatch,
    Submission,
)

CandidateStrategy = Literal["full_scan", "ngram_index"]


@dataclass(frozen=True, slots=True)
class ComparisonConfig:
    ngram_size: int = 3
    top_k: int = 5
    review_threshold: float = 0.65
    include_code: bool = True
    include_text_answer: bool = False
    candidate_strategy: CandidateStrategy = "full_scan"
    analyzer_version: str = "2.0.0"

    def config_hash(self) -> str:
        payload = {
            "analyzer_version": self.analyzer_version,
            "candidate_strategy": self.candidate_strategy,
            "include_code": self.include_code,
            "include_text_answer": self.include_text_answer,
            "ngram_size": self.ngram_size,
            "review_threshold": self.review_threshold,
            "top_k": self.top_k,
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class TokenFeature:
    value: str
    source: str
    line_start: int
    line_end: int
    excerpt: str
    is_template: bool = False


class ComparisonCache(Protocol):
    def get(self, key: str) -> FeatureSet | None:
        ...

    def set(self, key: str, value: FeatureSet) -> None:
        ...


class InMemoryComparisonCache:
    def __init__(self) -> None:
        self._items: dict[str, FeatureSet] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> FeatureSet | None:
        item = self._items.get(key)
        if item is None:
            self.misses += 1
        else:
            self.hits += 1
        return item

    def set(self, key: str, value: FeatureSet) -> None:
        self._items[key] = value


class FeatureExtractor:
    def __init__(self, config: ComparisonConfig) -> None:
        if config.ngram_size < 1:
            raise ValueError("ngram_size must be positive")
        self._config = config

    def extract(self, submission: Submission, assignment: Assignment) -> FeatureSet:
        template_lines = frozenset(
            line.strip()
            for template in assignment.allowed_templates
            for line in template.splitlines()
            if line.strip()
        )
        tokens: list[TokenFeature] = []
        diagnostics: dict[str, object] = {
            "language": submission.language,
            "sources": {},
        }

        for source, content in submission.content_by_source().items():
            if source == "code" and not self._config.include_code:
                continue
            if source == "text_answer" and not self._config.include_text_answer:
                continue
            source_tokens = self._tokenize_source(
                source=source,
                content=content,
                language=submission.language,
                template_lines=template_lines,
            )
            diagnostics["sources"] = {
                **dict(diagnostics["sources"]),
                source: {
                    "raw_lines": len(content.splitlines()),
                    "tokens": len(source_tokens),
                },
            }
            tokens.extend(source_tokens)

        suspicious, template, evidence = self._ngrams(tokens)
        metadata = {
            **diagnostics,
            "token_count": len(tokens),
            "suspicious_ngram_count": len(suspicious),
            "template_ngram_count": len(template),
            "empty_after_normalization": not suspicious and not template,
        }
        return FeatureSet(
            submission_id=submission.submission_id,
            assignment_id=submission.assignment_id,
            suspicious_ngrams=frozenset(suspicious),
            template_ngrams=frozenset(template),
            ngram_evidence=evidence,
            metadata=metadata,
        )

    def _tokenize_source(
        self,
        *,
        source: str,
        content: str,
        language: str | None,
        template_lines: frozenset[str],
    ) -> list[TokenFeature]:
        if not content.strip():
            return []
        if source == "code" and language == "python":
            return self._tokenize_python(source, content, template_lines)
        return self._tokenize_text(source, content, template_lines)

    def _tokenize_python(
        self,
        source: str,
        content: str,
        template_lines: frozenset[str],
    ) -> list[TokenFeature]:
        tokens: list[TokenFeature] = []
        try:
            stream = io.StringIO(content).readline
            generated = tokenize.generate_tokens(stream)
            for token in generated:
                if token.type in {
                    tokenize.COMMENT,
                    tokenize.ENCODING,
                    tokenize.ENDMARKER,
                    tokenize.INDENT,
                    tokenize.DEDENT,
                    tokenize.NEWLINE,
                    tokenize.NL,
                }:
                    continue
                value = _normalize_token(token.string)
                if value is None:
                    continue
                line = token.start[0]
                excerpt = _line_excerpt(content, line)
                tokens.append(
                    TokenFeature(
                        value=value,
                        source=source,
                        line_start=line,
                        line_end=max(line, token.end[0]),
                        excerpt=excerpt,
                        is_template=excerpt.strip() in template_lines,
                    )
                )
        except (IndentationError, SyntaxError, tokenize.TokenError):
            return self._tokenize_text(source, _strip_hash_comments(content), template_lines)
        return tokens

    def _tokenize_text(
        self,
        source: str,
        content: str,
        template_lines: frozenset[str],
    ) -> list[TokenFeature]:
        tokens: list[TokenFeature] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            without_comment = line.split("#", 1)[0]
            for raw_value in without_comment.replace("(", " ( ").replace(")", " ) ").replace(",", " , ").replace(":", " : ").split():
                value = _normalize_token(raw_value)
                if value is None:
                    continue
                tokens.append(
                    TokenFeature(
                        value=value,
                        source=source,
                        line_start=line_number,
                        line_end=line_number,
                        excerpt=line,
                        is_template=line.strip() in template_lines,
                    )
                )
        return tokens

    def _ngrams(
        self,
        tokens: list[TokenFeature],
    ) -> tuple[set[str], set[str], dict[str, Evidence]]:
        suspicious: set[str] = set()
        template: set[str] = set()
        evidence: dict[str, Evidence] = {}
        size = self._config.ngram_size
        if len(tokens) < size:
            return suspicious, template, evidence

        for index in range(0, len(tokens) - size + 1):
            window = tokens[index : index + size]
            key = " ".join(item.value for item in window)
            if all(item.is_template for item in window):
                template.add(key)
                continue
            suspicious.add(key)
            first = window[0]
            last = window[-1]
            evidence.setdefault(
                key,
                Evidence(
                    source=first.source,
                    line_start=first.line_start,
                    line_end=max(first.line_end, last.line_end),
                    excerpt=first.excerpt,
                ),
            )
        return suspicious, template, evidence


def jaccard(left: frozenset[str], right: frozenset[str]) -> tuple[float | None, int, int]:
    union = left | right
    intersection = left & right
    if not union:
        return None, len(intersection), 0
    return len(intersection) / len(union), len(intersection), len(union)


def feature_cache_key(
    submission: Submission,
    assignment: Assignment,
    config: ComparisonConfig,
) -> str:
    payload = {
        "allowed_templates": assignment.allowed_templates,
        "analyzer_version": config.analyzer_version,
        "assignment_id": assignment.assignment_id,
        "config_hash": config.config_hash(),
        "content_hash": submission.content_hash,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class NgramCandidateIndex:
    index_version = "ngram-index-v1"

    def __init__(
        self,
        *,
        submissions: Iterable[Submission],
        assignment: Assignment,
        service: "ComparisonService",
    ) -> None:
        self._assignment = assignment
        self._service = service
        self._submissions: dict[str, Submission] = {}
        self._inverted: dict[str, set[str]] = defaultdict(set)
        self.corpus_count = 0
        for submission in submissions:
            if submission.assignment_id != assignment.assignment_id:
                continue
            self._submissions[submission.submission_id] = submission
            self.corpus_count += 1
            feature = service.features_for(submission, assignment)
            for ngram in feature.suspicious_ngrams:
                self._inverted[ngram].add(submission.submission_id)

    def candidates_for(
        self,
        *,
        target: Submission,
        target_feature: FeatureSet,
    ) -> tuple[list[Submission], Mapping[str, object]]:
        available = [
            item
            for item in self._submissions.values()
            if item.submission_id != target.submission_id
        ]
        if not target_feature.suspicious_ngrams:
            ordered = available
        else:
            overlap_counts: dict[str, int] = defaultdict(int)
            for ngram in target_feature.suspicious_ngrams:
                for submission_id in self._inverted.get(ngram, ()):
                    if submission_id != target.submission_id:
                        overlap_counts[submission_id] += 1
            ordered = [
                self._submissions[submission_id]
                for submission_id, _ in sorted(
                    overlap_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]
        return ordered, {
            "candidate_strategy": "ngram_index",
            "index_version": self.index_version,
            "candidate_count": len(ordered),
            "corpus_count": len(available),
            "filtered_out_count": len(available) - len(ordered),
            "index_prebuilt": True,
        }


class ComparisonService:
    def __init__(
        self,
        config: ComparisonConfig | None = None,
        cache: ComparisonCache | None = None,
    ) -> None:
        self._config = config or ComparisonConfig()
        self._cache = cache or InMemoryComparisonCache()
        self._extractor = FeatureExtractor(self._config)

    def features_for(self, submission: Submission, assignment: Assignment) -> FeatureSet:
        return self._features(submission, assignment)

    def compare(
        self,
        *,
        target: Submission,
        submissions: Iterable[Submission],
        assignment: Assignment,
    ) -> ComparisonReport:
        target_feature = self._features(target, assignment)
        same_assignment = [
            item
            for item in submissions
            if item.assignment_id == target.assignment_id
            and item.submission_id != target.submission_id
        ]
        if self._config.candidate_strategy == "ngram_index":
            candidates, strategy_metadata = self._indexed_candidates(
                target_feature,
                same_assignment,
                assignment,
            )
        else:
            candidates = same_assignment
            strategy_metadata = {
                "candidate_strategy": "full_scan",
                "candidate_count": len(candidates),
                "corpus_count": len(same_assignment),
                "filtered_out_count": 0,
            }

        return self.compare_with_candidates(
            target=target,
            target_feature=target_feature,
            candidates=candidates,
            assignment=assignment,
            strategy_metadata=strategy_metadata,
        )

    def compare_with_candidates(
        self,
        *,
        target: Submission,
        target_feature: FeatureSet,
        candidates: Iterable[Submission],
        assignment: Assignment,
        strategy_metadata: Mapping[str, object],
    ) -> ComparisonReport:
        matches = [
            self._match(target, target_feature, candidate, assignment)
            for candidate in candidates
        ]
        matches.sort(
            key=lambda item: (
                item.insufficient_data,
                -(item.similarity if item.similarity is not None else -1.0),
                item.submission_id,
            )
        )
        top_matches = tuple(matches[: self._config.top_k])
        return ComparisonReport(
            target_submission_id=target.submission_id,
            assignment_id=target.assignment_id,
            analyzer_version=self._config.analyzer_version,
            config_hash=self._config.config_hash(),
            strategy=self._config.candidate_strategy,
            matches=top_matches,
            rubric_feedback=(
                "Similarity is a review signal for educational analysis, not proof "
                "of plagiarism or misconduct."
            ),
            metadata={
                **strategy_metadata,
                "comparison_count": len(matches),
                "target_suspicious_ngram_count": len(target_feature.suspicious_ngrams),
                "cache_hits": getattr(self._cache, "hits", None),
                "cache_misses": getattr(self._cache, "misses", None),
            },
        )

    def _features(self, submission: Submission, assignment: Assignment) -> FeatureSet:
        key = feature_cache_key(submission, assignment, self._config)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        feature_set = self._extractor.extract(submission, assignment)
        self._cache.set(key, feature_set)
        return feature_set

    def _match(
        self,
        target: Submission,
        target_feature: FeatureSet,
        candidate: Submission,
        assignment: Assignment,
    ) -> SimilarityMatch:
        candidate_feature = self._features(candidate, assignment)
        score, intersection_size, union_size = jaccard(
            target_feature.suspicious_ngrams,
            candidate_feature.suspicious_ngrams,
        )
        common_ngrams = sorted(
            target_feature.suspicious_ngrams & candidate_feature.suspicious_ngrams
        )
        evidence = tuple(
            target_feature.ngram_evidence[item]
            for item in common_ngrams[:5]
            if item in target_feature.ngram_evidence
        )
        insufficient = score is None
        same_student = target.student_id == candidate.student_id
        review_required = (
            score is not None
            and score >= self._config.review_threshold
            and not same_student
        )
        return SimilarityMatch(
            submission_id=candidate.submission_id,
            student_id=candidate.student_id,
            same_student=same_student,
            similarity=score,
            intersection_size=intersection_size,
            union_size=union_size,
            review_required=review_required,
            insufficient_data=insufficient,
            evidence=evidence,
            metadata={
                "template_intersection_size": len(
                    target_feature.template_ngrams & candidate_feature.template_ngrams
                ),
                "candidate_suspicious_ngram_count": len(
                    candidate_feature.suspicious_ngrams
                ),
                "relation_note": (
                    "same_student_repeated_version" if same_student else "different_student"
                ),
            },
        )

    def _indexed_candidates(
        self,
        target_feature: FeatureSet,
        submissions: list[Submission],
        assignment: Assignment,
    ) -> tuple[list[Submission], Mapping[str, object]]:
        features_by_id: dict[str, FeatureSet] = {}
        submissions_by_id: dict[str, Submission] = {}
        inverted: dict[str, set[str]] = defaultdict(set)
        for submission in submissions:
            feature = self._features(submission, assignment)
            features_by_id[submission.submission_id] = feature
            submissions_by_id[submission.submission_id] = submission
            for ngram in feature.suspicious_ngrams:
                inverted[ngram].add(submission.submission_id)

        overlap_counts: dict[str, int] = defaultdict(int)
        for ngram in target_feature.suspicious_ngrams:
            for submission_id in inverted.get(ngram, ()):
                overlap_counts[submission_id] += 1

        if not target_feature.suspicious_ngrams:
            ordered = submissions
        else:
            ordered = [
                submissions_by_id[submission_id]
                for submission_id, _ in sorted(
                    overlap_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]

        return ordered, {
            "candidate_strategy": "ngram_index",
            "index_version": "ngram-index-v1",
            "candidate_count": len(ordered),
            "corpus_count": len(submissions),
            "filtered_out_count": len(submissions) - len(ordered),
        }


def iter_report_dict(report: ComparisonReport) -> Mapping[str, object]:
    return {
        "target_submission_id": report.target_submission_id,
        "assignment_id": report.assignment_id,
        "analyzer_version": report.analyzer_version,
        "config_hash": report.config_hash,
        "strategy": report.strategy,
        "rubric_feedback": report.rubric_feedback,
        "metadata": dict(report.metadata),
        "matches": [
            {
                "submission_id": match.submission_id,
                "student_id": match.student_id,
                "same_student": match.same_student,
                "similarity": match.similarity,
                "intersection_size": match.intersection_size,
                "union_size": match.union_size,
                "review_required": match.review_required,
                "insufficient_data": match.insufficient_data,
                "metadata": dict(match.metadata),
                "evidence": [
                    {
                        "source": item.source,
                        "line_start": item.line_start,
                        "line_end": item.line_end,
                        "excerpt": item.excerpt,
                    }
                    for item in match.evidence
                ],
            }
            for match in report.matches
        ],
    }


def _normalize_token(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if value.isidentifier() and not keyword.iskeyword(value):
        return "<identifier>"
    if value.isdecimal():
        return "<number>"
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return "<string>"
    return value.lower()


def _line_excerpt(content: str, line_number: int) -> str:
    lines = content.splitlines()
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return ""


def _strip_hash_comments(content: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in content.splitlines())


def submission_lookup(submissions: Iterable[Submission]) -> dict[str, Submission]:
    return {item.submission_id: item for item in submissions}
