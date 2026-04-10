"""Main application entry point."""
import sys
from pathlib import Path
from queue import Queue

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from factorio_mod_manager.ui import MainWindow
from factorio_mod_manager.ui.styles import load_stylesheet
from factorio_mod_manager.utils import setup_logger
from factorio_mod_manager.utils.logger import LogSignalBridge


def main() -> None:
    """Main application entry point."""
    log_dir = Path.home() / ".factorio_mod_manager" / "logs"
    log_file = log_dir / "app.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_queue = Queue()

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(load_stylesheet())

    # Create Qt log bridge — connects Python logging to LoggerTab signal
    log_bridge = LogSignalBridge()
    logger = setup_logger(
        "factorio_mod_manager",
        log_queue=log_queue,
        log_file=log_file,
        qt_bridge=log_bridge,
    )
    logger.info("=" * 60)
    logger.info("🏭 Factorio Mod Manager started")
    logger.info("=" * 60)

    window = MainWindow(log_queue=log_queue, log_bridge=log_bridge)
    window.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Application closed")


if __name__ == "__main__":
    main()

