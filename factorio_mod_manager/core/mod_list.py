"""mod-list.json read/write service."""
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional


class ModListStore:
    """Read and atomically write Factorio mod-list.json enabled states.

    The `mod-list.json` format is::

        {"mods": [{"name": "base", "enabled": true}, ...]}

    Rules enforced:
    - ``base`` is always kept enabled regardless of what callers request.
    - Unknown entries (not in the provided mod set) are preserved as-is.
    - Writes are atomic: a temp file is written next to the target then
      renamed so a crash mid-write cannot corrupt the existing file.
    """

    MOD_LIST_FILENAME = "mod-list.json"

    def __init__(self, mods_folder: Path) -> None:
        self._mods_folder = Path(mods_folder)

    @property
    def _mod_list_path(self) -> Path:
        return self._mods_folder / self.MOD_LIST_FILENAME

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def load(self) -> Dict[str, bool]:
        """Return enabled states keyed by mod name.

        Handles missing / malformed files by returning an empty dict so
        callers treat every mod as enabled by default.
        """
        path = self._mod_list_path
        if not path.exists():
            return {}
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return {
                entry["name"]: bool(entry.get("enabled", True))
                for entry in data.get("mods", [])
                if "name" in entry
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            return {}

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def save(self, states: Dict[str, bool]) -> None:
        """Atomically write *states* to mod-list.json.

        Preserves entries whose names are not in *states* (unknown mods).
        Ensures ``base`` stays enabled.
        """
        # Load current raw list to preserve unknown entries
        path = self._mod_list_path
        try:
            if path.exists():
                raw = path.read_text(encoding="utf-8")
                current_mods = json.loads(raw).get("mods", [])
            else:
                current_mods = []
        except (json.JSONDecodeError, TypeError):
            current_mods = []

        # Build a merged map: unknown entries survive unchanged
        merged: Dict[str, bool] = {
            entry["name"]: bool(entry.get("enabled", True))
            for entry in current_mods
            if "name" in entry
        }
        merged.update(states)
        # Enforce base is always enabled
        merged["base"] = True

        new_list = [{"name": name, "enabled": enabled} for name, enabled in merged.items()]
        payload = json.dumps({"mods": new_list}, indent=2)

        # Atomic write via temp file in the same directory (same filesystem)
        self._mods_folder.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self._mods_folder,
            prefix=".mod-list-tmp-",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Convenience toggle helpers
    # ------------------------------------------------------------------

    def toggle(self, mod_name: str, enabled: bool) -> None:
        """Set *mod_name* enabled state, preserving all other entries.

        Raises:
            ValueError: if caller tries to disable ``base``.
        """
        if mod_name == "base" and not enabled:
            raise ValueError("The 'base' mod cannot be disabled.")
        states = self.load()
        states[mod_name] = enabled
        self.save(states)

    def enable(self, mod_name: str) -> None:
        """Enable *mod_name*."""
        self.toggle(mod_name, True)

    def disable(self, mod_name: str) -> None:
        """Disable *mod_name*."""
        self.toggle(mod_name, False)
