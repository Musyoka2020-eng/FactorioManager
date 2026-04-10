# Testing Patterns

**Analysis Date:** 2026-04-09

## Test Framework

**Runner:**
- Declared dependency: `pytest ^7.4.0` in `pyproject.toml`.
- Config: Not detected (`pytest.ini`, `tox.ini`, and `[tool.pytest.ini_options]` are absent).

**Assertion Library:**
- Not detected in repository source files (no project test files currently present).

**Run Commands:**
```bash
poetry run pytest                 # Run all tests (when tests are added)
poetry run pytest -q              # Quieter output
poetry run pytest --maxfail=1     # Stop early on first failure
```

## Test File Organization

**Location:**
- Not detected. No `tests/` directory and no matching test files (`test_*.py`, `*_test.py`) in source tree.

**Naming:**
- No in-repo test naming pattern currently established.

**Structure:**
```
Not detected
```

## Test Structure

**Suite Organization:**
```python
# Not detected in current codebase.
# Recommended baseline for consistency with current architecture:
# tests/core/test_downloader.py
# tests/core/test_checker.py
# tests/core/test_portal.py
# tests/ui/test_checker_presenter.py
# tests/utils/test_helpers.py
```

**Patterns:**
- Setup pattern: Not detected.
- Teardown pattern: Not detected.
- Assertion pattern: Not detected.

## Mocking

**Framework:**
- Not detected in repository tests (no test files currently).

**Patterns:**
```python
# Not detected in current codebase.
```

**What to Mock:**
- External HTTP calls in `factorio_mod_manager/core/portal.py` and `factorio_mod_manager/core/downloader.py` (requests session/get/head).
- Filesystem effects in `factorio_mod_manager/core/checker.py`, `factorio_mod_manager/core/downloader.py`, and `factorio_mod_manager/utils/config.py`.
- Time-dependent behavior in cache freshness logic (`datetime.now()` in `factorio_mod_manager/core/checker.py`).

**What NOT to Mock:**
- Pure data formatting/filtering logic in `factorio_mod_manager/ui/checker_presenter.py`.
- Deterministic helpers in `factorio_mod_manager/utils/helpers.py` that do not require network I/O.

## Fixtures and Factories

**Test Data:**
```python
# Not detected in current codebase.
```

**Location:**
- Not detected.

## Coverage

**Requirements:**
- None enforced in repository configuration.
- No coverage configuration detected (`.coveragerc` not present).

**View Coverage:**
```bash
poetry run pytest --cov=factorio_mod_manager --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Not currently implemented.
- Best fit candidates: `factorio_mod_manager/core/mod.py`, `factorio_mod_manager/ui/checker_presenter.py`, `factorio_mod_manager/utils/helpers.py`.

**Integration Tests:**
- Not currently implemented.
- Best fit candidates: portal API workflows in `factorio_mod_manager/core/portal.py` with mocked network boundaries.

**E2E Tests:**
- Not used.
- No GUI automation framework configured for Tkinter UI flows.

## Common Patterns

**Async Testing:**
```python
# Not detected. The codebase uses threads and callbacks rather than asyncio.
```

**Error Testing:**
```python
# Not detected. Recommended pattern for new tests:
# - assert custom exception typing for portal failures (PortalAPIError)
# - assert fallback behavior and status updates on broad exception boundaries
```

## CI/CD and Quality Automation

- No GitHub Actions workflows detected under `.github/workflows/`.
- No pre-commit configuration detected (`.pre-commit-config.yaml` absent).
- Lint/format tools are declared in `pyproject.toml` but no CI enforcement is configured.

## Current Testing Reality

- Dev dependencies indicate intended testing/linting stack (`pytest`, `black`, `ruff`) in `pyproject.toml`.
- The project currently has an implementation-first codebase without committed tests.
- `.gitignore` includes `.pytest_cache/`, which is consistent with pytest usage intent.

## Practical Guidance For Consistency

- Adopt `pytest` as the canonical framework because it is already declared in `pyproject.toml`.
- Add tests under `tests/` mirroring package layout (`tests/core/`, `tests/ui/`, `tests/utils/`).
- Prioritize deterministic unit tests first, then integration tests with mocked network/filesystem boundaries.
- Add CI workflow to run `ruff`, `black --check`, and `pytest` on pushes and pull requests.

---

*Testing analysis: 2026-04-09*
