# Lab 1 Report

## Track and level

- Track: Backend
- Level: Main requirements completed
- Additional depth: configuration validation is checked during application bootstrap, before the first request

## Implemented requirements

- `src`-layout installable package
- immutable domain models and typed public API
- Pydantic models for input validation
- separate intake adapter and domain service
- in-memory submission repository
- duplicate and conflict detection by `submission_id` and payload hash
- JSONL batch import that continues after broken lines
- analyzer protocol and analyzer registry
- `LengthAnalyzer` and `TemplateAnalyzer`
- `AIDeclarationAnalyzer`, connected through the registry without changing the central service
- in-memory and JSONL submission sources
- assignment source from JSON
- configuration assembly without global mutable container state
- reproducible run through `python -m lab1_backend`

## Verification commands

```bash
python -m pip install -e .[dev]
pytest
python -m lab1_backend
```

## Known limitations

- there is no HTTP API yet; the test adapter is used instead
- only synchronous analyzers are supported in this laboratory
- the repository is intentionally in-memory, so data is not persisted between runs
