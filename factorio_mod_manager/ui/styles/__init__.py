"""Style system for Factorio Mod Manager Qt UI."""
from pathlib import Path
from . import tokens


def load_stylesheet() -> str:
    """Load and parameterize dark_theme.qss with token values.

    Returns:
        Fully-resolved QSS string ready for QApplication.setStyleSheet().
    """
    qss_path = Path(__file__).parent / "dark_theme.qss"
    template = qss_path.read_text(encoding="utf-8")
    token_map = {k: str(v) for k, v in vars(tokens).items() if not k.startswith("_")}
    return template.format_map(token_map)


__all__ = ["load_stylesheet", "tokens"]
