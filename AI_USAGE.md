# AI_USAGE

This project does not use an AI model at runtime.

AI assistance was used only as a supporting development tool. It helped with:

- draft the initial project structure
- suggest test scenarios from the laboratory requirements
- help prepare documentation

The final implementation was manually reviewed and adjusted to match the laboratory requirements.

The main focus of this work is the resulting project behavior:

- the package installs correctly
- the intake and analysis workflow runs on the provided example data
- the implementation follows the backend-track requirements from the specification
- the required scenarios are covered by automated tests

Project readiness was verified with reproducible commands before submission:

```bash
python -m pip install -e .[dev]
pytest
python -m lab1_backend
```
