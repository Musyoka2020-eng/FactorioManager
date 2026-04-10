# Testing Patterns

**Analysis Date:** 2026-04-10

## Test Framework

**Runner:**
- Declared dependency: `pytest ^7.4.0` in `pyproject.toml`.
- Config: Not detected (`pytest.ini`, `tox.ini`, and `[tool.pytest.ini_options]` are absent).

**Assertion Library:**
- pytest built-in assertions (no separate assertion library needed).

**Run Commands:**
```bash
poetry run pytest                              # Run all tests
poetry run pytest -q                           # Quieter output
poetry run pytest --maxfail=1                  # Stop on first failure
poetry run pytest -k "test_portal"             # Run specific test subset
poetry run pytest --cov=factorio_mod_manager --cov-report=term-missing  # With coverage
```

## Test File Organization

**Current state:** No test files exist. No `tests/` directory.

**Recommended layout** (mirrors package structure):
```
tests/
├── conftest.py                  # Shared fixtures (Mod objects, mock portal, tmp config)
├── core/
│   ├── test_portal.py           # FactorioPortalAPI, PortalAPIError
│   ├── test_downloader.py       # ModDownloader download/dependency resolution
│   ├── test_checker.py          # ModChecker scan/update logic
│   └── test_mod.py              # Mod dataclass, ModStatus enum
├── ui/
│   ├── test_checker_presenter.py  # filter_mods(), get_statistics() — pure logic, no Tk
│   └── test_checker_logic.py      # CheckerLogic operations with mocked ModChecker
└── utils/
    ├── test_helpers.py            # parse_mod_info, format_file_size, validate_mod_url, is_online
    └── test_config.py             # Config load/save/defaults/auto-detect
```

**Naming:**
- Files: `test_<module>.py`
- Functions: `test_<what>_<condition>` e.g. `test_get_mod_returns_none_on_404`, `test_filter_mods_outdated_only`

## Test Structure

**Recommended suite organization:**
```python
# tests/core/test_portal.py
import pytest
from unittest.mock import MagicMock, patch
from factorio_mod_manager.core.portal import FactorioPortalAPI, PortalAPIError

class TestGetMod:
    def test_returns_dict_on_200(self, mock_session):
        ...
    def test_raises_portal_api_error_on_404(self, mock_session):
        ...
    def test_raises_offline_error_on_connection_error(self, mock_session):
        ...
```

**Patterns:**
- Setup: `@pytest.fixture` in `conftest.py` for reusable objects
- Teardown: `tmp_path` pytest built-in for filesystem cleanup
- Assertions: `assert result == expected`, `with pytest.raises(PortalAPIError) as exc_info:`

## Mocking

**Framework:** `unittest.mock` (stdlib) — `MagicMock`, `patch`, `patch.object`. No third-party mock library needed.

**What to Mock:**

- **HTTP calls** — `requests.Session.get` / `requests.Session.head` in `factorio_mod_manager/core/portal.py` and `factorio_mod_manager/core/downloader.py`. Never let tests hit the real `mods.factorio.com`.
  ```python
  @patch("factorio_mod_manager.core.portal.requests.Session.get")
  def test_get_mod_404(self, mock_get):
      mock_get.return_value.status_code = 404
      with pytest.raises(PortalAPIError) as exc_info:
          api.get_mod("nonexistent")
      assert exc_info.value.error_type == "not_found"
  ```

- **Filesystem** — use pytest's `tmp_path` fixture for any test involving `factorio_mod_manager/utils/config.py` (`CONFIG_DIR`, `CONFIG_FILE`) or mod zip reading in `factorio_mod_manager/utils/helpers.py`. Patch `Path.home()` to return `tmp_path`.

- **`datetime.now()`** — patch in `factorio_mod_manager/core/checker.py` to test cache freshness logic deterministically.

- **`socket.gethostbyname`** — patch for `is_online()` in `factorio_mod_manager/utils/helpers.py`.

- **`tkinter`** — do not import or instantiate real Tk widgets in tests. Test UI logic classes (`CheckerLogic`, `CheckerPresenter`) by injecting mock callbacks:
  ```python
  logged = []
  logic = CheckerLogic(checker=mock_checker, logger=lambda msg, lvl="info": logged.append((msg, lvl)))
  ```

**What NOT to Mock:**
- `CheckerPresenter.filter_mods()` — pure function with no I/O; test directly with real `Mod` objects and `ModStatus` values.
- `format_file_size()`, `validate_mod_url()`, `extract_version_from_filename()` — pure functions in `factorio_mod_manager/utils/helpers.py`; test with plain inputs.
- The `Mod` dataclass and `ModStatus` enum from `factorio_mod_manager/core/mod.py`.

## Fixtures and Factories

**Recommended `conftest.py` fixtures:**

```python
# tests/conftest.py
import pytest
from pathlib import Path
from factorio_mod_manager.core.mod import Mod, ModStatus

@pytest.fixture
def sample_mod():
    """A basic Mod object for testing."""
    return Mod(
        name="some-mod",
        title="Some Mod",
        version="1.2.3",
        author="TestAuthor",
        status=ModStatus.UP_TO_DATE,
        downloads=5000,
    )

@pytest.fixture
def outdated_mod(sample_mod):
    """A Mod with OUTDATED status and a newer available version."""
    sample_mod.status = ModStatus.OUTDATED
    sample_mod.latest_version = "1.3.0"
    return sample_mod

@pytest.fixture
def mods_dict(sample_mod, outdated_mod):
    """A dict of mixed-status mods for filter/sort tests."""
    return {"some-mod": sample_mod, "old-mod": outdated_mod}

@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Config instance pointing to a temp directory."""
    monkeypatch.setattr("factorio_mod_manager.utils.config.Config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("factorio_mod_manager.utils.config.Config.CONFIG_FILE", tmp_path / "config.json")
    from factorio_mod_manager.utils.config import Config
    return Config()

@pytest.fixture
def mock_portal_response():
    """Minimal valid portal API JSON for a mod."""
    return {
        "name": "some-mod",
        "title": "Some Mod",
        "owner": "TestAuthor",
        "releases": [
            {"version": "1.2.3", "filename": "mods/some-mod_1.2.3.zip"},
        ],
    }
```

**Location:** All shared fixtures in `tests/conftest.py`; module-specific fixtures in the relevant `tests/core/` or `tests/utils/` file.

## Coverage

**Requirements:** None enforced in repository configuration.

**View Coverage:**
```bash
poetry run pytest --cov=factorio_mod_manager --cov-report=term-missing
```

**Priority targets (highest ROI):**
1. `factorio_mod_manager/core/portal.py` — all HTTP error branches for `PortalAPIError`
2. `factorio_mod_manager/ui/checker_presenter.py` — filter/sort permutations (pure, fast)
3. `factorio_mod_manager/utils/helpers.py` — `format_file_size`, `validate_mod_url`, `parse_mod_info`
4. `factorio_mod_manager/utils/config.py` — load/save/defaults/auto-detect

## Test Types

**Unit Tests — highest priority, start here:**
- `factorio_mod_manager/ui/checker_presenter.py` — `filter_mods()` with every `filter_mode` and `sort_by` combination; `get_statistics()`; `format_statistics()`. No Tkinter needed.
- `factorio_mod_manager/utils/helpers.py` — `format_file_size()`, `validate_mod_url()`, `extract_version_from_filename()`, `parse_mod_info()` (use a real test zip via `tmp_path`).
- `factorio_mod_manager/core/portal.py` — each `PortalAPIError.error_type` branch, all HTTP status codes, connection/timeout exceptions.
- `factorio_mod_manager/utils/config.py` — auto-detect logic, load from corrupted file, save round-trip.

**Integration Tests:**
- `ModDownloader` + `FactorioPortalAPI` with mocked `requests.Session`: test full dependency resolution flow returning correct `Mod` objects without any real HTTP.
- `CheckerLogic` + `ModChecker` with mocked portal responses: verify `scan_mods()` → `check_updates()` → `update_mods()` state transitions.

**E2E Tests:**
- Not applicable. Tkinter UI is not suitable for automated end-to-end testing without a GUI automation framework (e.g., pyautogui), which adds significant complexity and flakiness.

## Common Patterns

**Error/exception testing:**
```python
def test_get_mod_raises_on_connection_error(self):
    with patch("factorio_mod_manager.core.portal.requests.Session.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(PortalAPIError) as exc_info:
            self.api.get_mod("some-mod")
        assert exc_info.value.error_type == "offline"
```

**Tuple return testing:**
```python
# ModDownloader.update_mods returns (successful_list, failed_list)
successful, failed = logic.update_mods(["mod-a", "mod-b"])
assert "mod-a" in successful
assert len(failed) == 0
```

**Filter/sort testing:**
```python
def test_filter_outdated_only(mods_dict):
    result = CheckerPresenter.filter_mods(
        mods_dict, search_query="", filter_mode="outdated",
        selected_mods=set(), sort_by="name"
    )
    names = [name for name, _ in result]
    assert "old-mod" in names
    assert "some-mod" not in names
```

## Integration Tests

**Recommended integration test scenarios:**

1. **Portal API → Downloader pipeline:** Mock `requests.Session` to return realistic release JSON; verify `ModDownloader.resolve_dependencies()` correctly builds the dependency tree and calls `mod_progress_callback` for each mod.

2. **Checker scan + update cycle:** Set up a `tmp_path` directory with real mod zip files named `modname_version.zip`; run `ModChecker.scan_mods()` and verify `Mod` objects are created with correct names and versions.

3. **Config persistence:** Write a config via `Config.set()`, create a new `Config()` instance pointing to the same `tmp_path`, verify values are reloaded correctly.

4. **`CheckerLogic.delete_mods()`:** Create real zip files in `tmp_path`; call `delete_mods()`; assert files are removed from disk and from the checker's mod dict.

## Testing Challenges

**Tkinter requires main thread:**
Tkinter widgets can only be created and manipulated from the main thread. Any test that tries to instantiate `CheckerTab`, `DownloaderTab`, `MainWindow`, or `StatusManager` will either hang or raise a `RuntimeError` in CI (no display). Work around this by:
- Testing logic classes (`CheckerLogic`, `CheckerPresenter`) without Tkinter entirely — inject mock callbacks instead of real widgets.
- Treating `StatusManager` as infrastructure; test only its queue push/drain contract with a mock callback, no real `root.after_idle`.

**Background thread testing:**
`ModDownloader` and `ModChecker` spawn `Thread` objects. In unit tests, use `MagicMock` to replace `self.checker.scan_mods()` return value directly — never allow real threads during tests. If thread behavior must be tested, call the thread target function synchronously.

**Queue-based UI updates:**
The `status_queue` in `StatusManager` (`factorio_mod_manager/ui/status_manager.py`) is drained in a daemon thread calling `root.after_idle`. In tests, replace the `update_callback` with a plain list append and drain the queue manually:
```python
received = []
manager = StatusManager(update_callback=lambda msg, t: received.append((msg, t)))
manager.push_status("hello", "info")
# Drain queue synchronously in test:
while not manager.status_queue.empty():
    msg, t = manager.status_queue.get_nowait()
    received.append((msg, t))
```

**No display in CI:**
If CI runs on a headless server, any test that touches Tkinter will fail at import time or `tk.Tk()` creation. Guard with:
- Keep all Tkinter imports inside the classes themselves (not at module top-level in test files).
- Use `pytest.importorskip("tkinter")` or a CI-specific skip marker if GUI tests are ever added.

## CI/CD and Quality Automation

- No GitHub Actions workflows detected under `.github/workflows/`.
- No pre-commit configuration detected (`.pre-commit-config.yaml` absent).
- Recommended CI pipeline: run `ruff check .`, `black --check .`, and `pytest` on push and pull request.

---

*Testing analysis: 2026-04-10*
