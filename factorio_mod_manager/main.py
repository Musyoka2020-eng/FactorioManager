"""Main application entry point."""
import sys
import tkinter as tk
from pathlib import Path
from queue import Queue

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from factorio_mod_manager.ui import MainWindow
from factorio_mod_manager.utils import setup_logger


def enable_dpi_awareness() -> None:
    """Enable DPI awareness for crisp text rendering on Windows."""
    try:
        # Windows 10/11 DPI awareness
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        # Fallback for older Windows versions
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass  # Not on Windows or API unavailable


def main() -> None:
    """Main application entry point."""
    # Enable DPI awareness for crisp rendering
    enable_dpi_awareness()
    
    # Setup logging directory
    log_dir = Path.home() / ".factorio_mod_manager" / "logs"
    log_file = log_dir / "app.log"
    
    # Create logging queue for UI integration
    log_queue = Queue()
    
    # Setup logging with both console and file output
    logger = setup_logger(
        "factorio_mod_manager",
        log_queue=log_queue,
        log_file=log_file
    )
    logger.info("=" * 60)
    logger.info("🏭 Factorio Mod Manager started")
    logger.info("=" * 60)
    
    # Create root window
    root = tk.Tk()
    
    # Create and run main window with log queue
    try:
        app = MainWindow(root, log_queue=log_queue)
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Application closed")


if __name__ == "__main__":
    main()

