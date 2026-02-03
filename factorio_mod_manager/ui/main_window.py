"""Main application window."""
import logging
import tkinter as tk
from tkinter import ttk, font
from typing import Optional
from queue import Queue
from .status_manager import StatusManager
from .downloader_tab import DownloaderTab
from .checker_tab import CheckerTab
from .logger_tab import LoggerTab
from .widgets import NotificationManager
from ..utils import config


class MainWindow:
    """Main application window."""

    # Color scheme
    BG_COLOR = "#0e0e0e"
    DARK_BG = "#1a1a1a"
    ACCENT_COLOR = "#0078d4"
    ACCENT_HOVER = "#1084d7"
    FG_COLOR = "#e0e0e0"
    SECONDARY_FG = "#b0b0b0"
    SUCCESS_COLOR = "#4ec952"
    ERROR_COLOR = "#d13438"

    def __init__(self, root: tk.Tk, log_queue: Optional[Queue] = None):
        """
        Initialize main window.
        
        Args:
            root: Root Tkinter window
            log_queue: Queue for receiving log messages
        """
        self.root = root
        self.root.title("🏭 Factorio Mod Manager v1.1.0")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)
        # Start application maximized
        self.root.state('zoomed')
        self.log_queue = log_queue
        self.logger = logging.getLogger("factorio_mod_manager")
        
        self.root.configure(bg=self.BG_COLOR)
        
        # Configure styles
        self._setup_styles()
        
        # Create notification manager (will overlay on top of content)
        self.notification_manager = NotificationManager(self.root)
        
        # Create header
        self._create_header()
        
        # Create main container
        main_container = ttk.Frame(self.root, style="Dark.TFrame")
        main_container.pack(side="top", fill="both", expand=True, padx=0, pady=0)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_container, style="Dark.TNotebook")
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Create status bar first (so tabs can reference it)
        self._create_status_bar()
        
        # Create and start status manager for concurrent tab operations
        self.status_manager = StatusManager(self.update_status)
        self.status_manager.start(self.root)
        
        # Create tabs and pass status manager reference
        self.downloader_tab = DownloaderTab(self.notebook, status_manager=self.status_manager)
        self.checker_tab = CheckerTab(self.notebook, logger=self.logger, status_manager=self.status_manager)
        
        # Pass notification manager to tabs
        self.downloader_tab.set_notification_manager(self.notification_manager)
        self.checker_tab.set_notification_manager(self.notification_manager)
        
        self.notebook.add(self.downloader_tab.frame, text="⬇️  Downloader")
        self.notebook.add(self.checker_tab.frame, text="✓  Checker & Updates")
        
        # Add logger tab if queue is available
        if log_queue:
            self.logger_tab = LoggerTab(self.notebook, log_queue)
            self.notebook.add(self.logger_tab.frame, text="📋 Logs")
    
    def _create_header(self) -> None:
        """Create application header."""
        header_frame = tk.Frame(self.root, bg=self.DARK_BG, height=60)
        header_frame.pack(side="top", fill="x", pady=0)
        header_frame.pack_propagate(False)
        
        # Title
        title_font = font.Font(family="Segoe UI", size=14, weight="bold")
        title_label = tk.Label(
            header_frame,
            text="🏭 Factorio Mod Manager",
            font=title_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        title_label.pack(side="left", padx=15, pady=10)
        
        # Subtitle
        subtitle_font = font.Font(family="Segoe UI", size=9)
        subtitle_label = tk.Label(
            header_frame,
            text="Download mods with dependencies • Check for updates • Manage your Factorio mods",
            font=subtitle_font,
            bg=self.DARK_BG,
            fg=self.SECONDARY_FG
        )
        subtitle_label.pack(side="left", padx=15, pady=5)
        
        # Separator line
        separator = tk.Frame(self.root, bg=self.ACCENT_COLOR, height=2)
        separator.pack(side="top", fill="x")
    
    def _setup_styles(self) -> None:
        """Setup custom Tkinter styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure frame styles
        style.configure("Dark.TFrame", background=self.BG_COLOR)
        style.configure("Card.TFrame", background=self.DARK_BG, relief="flat", borderwidth=1)
        
        # Configure label styles
        style.configure("TLabel", background=self.BG_COLOR, foreground=self.FG_COLOR, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=self.BG_COLOR, foreground=self.FG_COLOR, font=("Segoe UI", 11, "bold"))
        style.configure("Small.TLabel", background=self.BG_COLOR, foreground=self.SECONDARY_FG, font=("Segoe UI", 9))
        
        # Configure button styles
        style.configure(
            "Accent.TButton",
            background=self.ACCENT_COLOR,
            foreground=self.FG_COLOR,
            borderwidth=0,
            focuscolor='none',
            padding=6
        )
        style.map(
            "Accent.TButton",
            background=[
                ('pressed', '#005a9e'),
                ('active', self.ACCENT_HOVER),
                ('disabled', '#404040')
            ],
            foreground=[('disabled', '#808080')]
        )
        
        style.configure(
            "Success.TButton",
            background=self.SUCCESS_COLOR,
            foreground="#000000",
            borderwidth=0,
            focuscolor='none',
            padding=6
        )
        style.map(
            "Success.TButton",
            background=[
                ('pressed', '#3db842'),
                ('active', '#5cd65f'),
                ('disabled', '#404040')
            ]
        )
        
        # Configure notebook styles
        style.configure("Dark.TNotebook", background=self.BG_COLOR, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=self.DARK_BG,
            foreground=self.FG_COLOR,
            padding=[20, 10],
            borderwidth=0
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[
                ('selected', self.ACCENT_COLOR),
                ('active', self.ACCENT_HOVER)
            ],
            foreground=[('selected', '#ffffff')]
        )
        
        # Configure labelframe styles
        style.configure(
            "Dark.TLabelframe",
            background=self.BG_COLOR,
            foreground=self.FG_COLOR,
            borderwidth=1,
            relief="solid"
        )
        style.configure("Dark.TLabelframe.Label", background=self.BG_COLOR, foreground=self.FG_COLOR)
        
        # Configure entry styles
        style.configure("Dark.TEntry", fieldbackground=self.DARK_BG, background=self.DARK_BG, foreground=self.FG_COLOR)
        
        # Configure treeview
        style.configure(
            "Dark.Treeview",
            background=self.DARK_BG,
            foreground=self.FG_COLOR,
            fieldbackground=self.DARK_BG,
            borderwidth=0
        )
        style.configure("Dark.Treeview.Heading", background=self.ACCENT_COLOR, foreground=self.FG_COLOR, borderwidth=0)
        style.map("Dark.Treeview", background=[('selected', self.ACCENT_COLOR)])
    
    def _create_status_bar(self) -> None:
        """Create status bar at bottom."""
        # Top separator line
        separator = tk.Frame(self.root, bg="#0078d4", height=2)
        separator.pack(side="bottom", fill="x", padx=0, pady=0)
        
        # Status bar frame with better styling
        status_frame = tk.Frame(self.root, bg="#1a2a3a", height=40)
        status_frame.pack(side="bottom", fill="x", padx=0, pady=(5, 0))
        status_frame.pack_propagate(False)
        
        # Status icon and text
        status_inner = tk.Frame(status_frame, bg="#1a2a3a")
        status_inner.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        
        self.status_icon = tk.Label(
            status_inner,
            text="●",
            bg="#1a2a3a",
            fg=self.SUCCESS_COLOR,
            font=("Segoe UI", 12, "bold")
        )
        self.status_icon.pack(side="left", padx=(0, 8))
        
        self.status_label = tk.Label(
            status_inner,
            text="Ready",
            bg="#1a2a3a",
            fg=self.FG_COLOR,
            font=("Segoe UI", 10)
        )
        self.status_label.pack(side="left", fill="both", expand=True)
    
    def update_status(self, message: str, status_type: str = "info") -> None:
        """
        Update status bar message.
        
        Args:
            message: Status message
            status_type: Type of status (info, success, error, working)
        """
        self.status_label.config(text=message)
        
        # Update icon
        if status_type == "success":
            self.status_icon.config(text="✓", fg=self.SUCCESS_COLOR)
        elif status_type == "error":
            self.status_icon.config(text="✗", fg=self.ERROR_COLOR)
        elif status_type == "working":
            self.status_icon.config(text="◌", fg=self.ACCENT_COLOR)
        else:  # info
            self.status_icon.config(text="ℹ", fg=self.ACCENT_COLOR)
        
        self.root.update_idletasks()
    
    def run(self) -> None:
        """Run the application."""
        self.root.mainloop()
