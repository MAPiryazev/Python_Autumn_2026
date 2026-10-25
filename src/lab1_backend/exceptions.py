from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class LabError(Exception):
    code: str
    field: str | None
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }


class SubmissionFormatError(LabError):
    def __init__(self, field: str | None, message: str) -> None:
        super().__init__("format_error", field, message)


class SubmissionSchemaError(LabError):
    def __init__(self, field: str | None, message: str) -> None:
        super().__init__("schema_error", field, message)


class SubmissionConflictError(LabError):
    def __init__(self, submission_id: str) -> None:
        super().__init__(
            "conflict",
            "submission_id",
            f"Submission '{submission_id}' already exists with different content.",
        )


class AnalyzerExecutionError(LabError):
    def __init__(self, analyzer_id: str, message: str) -> None:
        super().__init__("analyzer_error", analyzer_id, message)


class ConfigurationError(LabError):
    def __init__(self, field: str | None, message: str) -> None:
        super().__init__("configuration_error", field, message)
