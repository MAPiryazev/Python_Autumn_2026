from __future__ import annotations

from dataclasses import dataclass

from lab1_backend.analysis import AnalysisService
from lab1_backend.exceptions import ConfigurationError
from lab1_backend.intake import (
    InMemorySubmissionRepository,
    SubmissionIntakeAdapter,
    SubmissionIntakeService,
)
from lab1_backend.protocols import Analyzer, AssignmentSource, SubmissionRepository


@dataclass(frozen=True, slots=True)
class Application:
    intake_adapter: SubmissionIntakeAdapter
    analysis_service: AnalysisService
    repository: SubmissionRepository


def build_application(
    *,
    assignment_source: AssignmentSource,
    analyzers: list[Analyzer],
    repository: SubmissionRepository | None = None,
) -> Application:
    if not analyzers:
        raise ConfigurationError("analyzers", "At least one analyzer is required.")

    registry: dict[str, Analyzer] = {}
    for analyzer in analyzers:
        if analyzer.analyzer_id in registry:
            raise ConfigurationError(
                "analyzers",
                f"Analyzer id '{analyzer.analyzer_id}' is registered more than once.",
            )
        registry[analyzer.analyzer_id] = analyzer

    effective_repository = repository or InMemorySubmissionRepository()
    intake_service = SubmissionIntakeService(effective_repository)
    intake_adapter = SubmissionIntakeAdapter(intake_service)
    analysis_service = AnalysisService(registry, assignment_source)
    return Application(
        intake_adapter=intake_adapter,
        analysis_service=analysis_service,
        repository=effective_repository,
    )
