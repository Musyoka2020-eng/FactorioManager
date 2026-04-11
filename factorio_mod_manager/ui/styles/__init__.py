"""Style system for Factorio Mod Manager Qt UI."""
from pathlib import Path
from . import tokens
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def load_stylesheet() -> str:
    """Load and parameterize dark_theme.qss with token values.

    Returns:
        Fully-resolved QSS string ready for QApplication styling.
    """
    qss_path = Path(__file__).parent / "dark_theme.qss"
    template = qss_path.read_text(encoding="utf-8")
    token_map = {k: str(v) for k, v in vars(tokens).items() if not k.startswith("_")}
    return template.format_map(token_map)


def load_and_apply_theme(theme: str, app=None) -> None:
    """Load and apply the QSS for the given theme ('dark', 'light', 'system').

    'system' reads the OS color scheme; falls back to 'dark' if undetectable.
    Calls QApplication.instance().setStyleSheet() with the resolved QSS.
    """
    if theme == "system":
        app_instance = app or QApplication.instance()
        if app_instance:
            hints = app_instance.styleHints()
            scheme = getattr(hints, "colorScheme", lambda: None)()
            theme = "light" if scheme == Qt.ColorScheme.Light else "dark"
        else:
            theme = "dark"

    qss_filename = "light_theme.qss" if theme == "light" else "dark_theme.qss"
    qss_path = Path(__file__).parent / qss_filename
    template = qss_path.read_text(encoding="utf-8")
    token_map = {k: str(v) for k, v in vars(tokens).items() if not k.startswith("_")}
    result = template.format_map(token_map)

    target = app or QApplication.instance()
    if target:
        target.setStyleSheet(result)


__all__ = ["load_stylesheet", "load_and_apply_theme", "tokens"]
