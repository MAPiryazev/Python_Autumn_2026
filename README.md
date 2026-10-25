# Python_Autumn_2026

Backend implementation for laboratory work 1: submission intake, validation, and extensible analyzers.

## What is included

- `src`-layout Python package `lab1_backend`
- Pydantic input models separated from immutable domain models
- In-memory intake repository with duplicate and conflict handling
- `LengthAnalyzer` and `TemplateAnalyzer`
- In-memory and JSONL submission sources
- JSON assignment source
- Reproducible CLI-style run via `python -m lab1_backend`
- Tests for intake scenarios, analyzer contracts, configuration, and resource release

## Project structure

```text
src/lab1_backend/
  analysis.py
  bootstrap.py
  domain.py
  exceptions.py
  intake.py
  protocols.py
tests/
examples/
```

## Requirements

- Python 3.11+

## Install

```bash
python -m pip install -e .[dev]
```

## Run tests

```bash
pytest
```

## Quick example

```python
from lab1_backend import (
    InMemoryAssignmentSource,
    LengthAnalyzer,
    TemplateAnalyzer,
    Assignment,
    build_application,
)

app = build_application(
    assignment_source=InMemoryAssignmentSource(
        [
            Assignment(
                assignment_id="lab-01",
                title="Laboratory work 1",
                allowed_templates=("allowed()",),
            )
        ]
    ),
    analyzers=[LengthAnalyzer(), TemplateAnalyzer()],
)

result = app.intake_adapter.accept_payload(
    {
        "submission_id": "sub-001",
        "assignment_id": "lab-01",
        "student_id": "student-42",
        "submitted_at": "2026-10-25T12:00:00+03:00",
        "text_answer": "allowed()\nOwn answer",
        "code": "print('ok')",
        "language": "python",
        "ai_declaration": {"used": False, "details": None},
    }
)

report = app.analysis_service.analyze("template", result.submission)
print(result.status)
print(report.similarity)
```

## Reproducible run

Run analyzers for the bundled example data:

```bash
python -m lab1_backend
```

Run a single analyzer:

```bash
python -m lab1_backend --analyzer template
```

Custom input files:

```bash
python -m lab1_backend --assignments examples/assignments.json --submissions examples/submissions.jsonl
```

## Example data

- `examples/assignments.json`
- `examples/submissions.jsonl`
- `examples/invalid_submissions.jsonl`

## Notes

- The domain layer does not read `stdin`, call HTTP, or execute submitted code.
- Validation errors expose `code`, `field`, and `message`.
- A duplicate with the same `submission_id` and hash returns the stored submission.
- A duplicate with the same `submission_id` and different content raises a conflict.
- The analyzer registry can be extended without changing the central analysis service.