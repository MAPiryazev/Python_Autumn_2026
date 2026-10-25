from __future__ import annotations

import pytest

from lab1_backend.analysis import InMemoryAssignmentSource, LengthAnalyzer
from lab1_backend.bootstrap import build_application
from lab1_backend.domain import Assignment
from lab1_backend.exceptions import ConfigurationError


def make_assignment_source() -> InMemoryAssignmentSource:
    return InMemoryAssignmentSource(
        [Assignment(assignment_id="lab-01", title="Lab 1")]
    )


def test_build_application_rejects_empty_analyzer_list() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        build_application(
            assignment_source=make_assignment_source(),
            analyzers=[],
        )

    assert exc_info.value.field == "analyzers"


def test_build_application_rejects_duplicate_analyzer_ids() -> None:
    analyzer_a = LengthAnalyzer()
    analyzer_b = LengthAnalyzer()

    with pytest.raises(ConfigurationError) as exc_info:
        build_application(
            assignment_source=make_assignment_source(),
            analyzers=[analyzer_a, analyzer_b],
        )

    assert exc_info.value.field == "analyzers"
