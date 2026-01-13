"""Logger tab for displaying application logs in the UI."""
import tkinter as tk
from tkinter import ttk
from queue import Queue
from typing import Optional


class LoggerTab:
    """Tab for displaying application logs in real-time."""

    def __init__(self, parent: ttk.Notebook, log_queue: Queue):
        """
        Initialize logger tab.
        
        Args:
            parent: Parent notebook widget
            log_queue: Queue to receive log messages from
        """
        self.frame = ttk.Frame(parent, style="Dark.TFrame")
        self.log_queue = log_queue
        
        # Create text widget with scrollbar
        scrollbar = ttk.Scrollbar(self.frame)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(
            self.frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            bg="#1a1a1a",
            fg="#e0e0e0",
            font=("Courier", 9),
            state="normal"
        )
        self.log_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.log_text.yview)
        
        # Configure tags for different log levels
        self._configure_tags()
        
        # Start polling for logs
        self._poll_logs()
    
    def _configure_tags(self) -> None:
        """Configure text tags for different log levels."""
        self.log_text.tag_config("INFO", foreground="#b0b0b0")
        self.log_text.tag_config("DEBUG", foreground="#808080")
        self.log_text.tag_config("WARNING", foreground="#ffb700")
        self.log_text.tag_config("ERROR", foreground="#d13438")
        self.log_text.tag_config("SUCCESS", foreground="#4ec952")
    
    def _poll_logs(self) -> None:
        """Poll log queue and update text widget."""
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                
                # Determine log level from message
                level = "INFO"
                if " - ERROR - " in log_message:
                    level = "ERROR"
                elif " - WARNING - " in log_message:
                    level = "WARNING"
                elif " - DEBUG - " in log_message:
                    level = "DEBUG"
                
                # Insert log message with appropriate tag
                self.log_text.config(state="normal")
                self.log_text.insert("end", log_message + "\n", level)
                self.log_text.config(state="normal")
                self.log_text.see("end")  # Auto-scroll to bottom
        except:
            pass
        
        # Schedule next poll (every 100ms)
        self.frame.after(100, self._poll_logs)
    
    def clear_logs(self) -> None:
        """Clear all logs from the display."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="normal")
