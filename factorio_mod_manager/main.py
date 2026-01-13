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


def main() -> None:
    """Main application entry point."""
    # Create logging queue for UI integration
    log_queue = Queue()
    
    # Setup logging with UI queue
    logger = setup_logger("factorio_mod_manager", log_queue=log_queue)
    logger.info("Application started")
    
    # Create root window
    root = tk.Tk()
    
    # Create and run main window with log queue
    app = MainWindow(root, log_queue=log_queue)
    app.run()


if __name__ == "__main__":
    main()
