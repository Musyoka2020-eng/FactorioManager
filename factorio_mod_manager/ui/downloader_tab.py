"""Downloader tab UI."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from typing import Optional, Dict, Any
from threading import Thread
import time
from ..core import ModDownloader
from ..core.portal import FactorioPortalAPI, PortalAPIError
from ..utils import config, validate_mod_url, format_file_size, is_online
from .widgets import PlaceholderEntry, NotificationManager


class DownloaderTab:
    """UI for mod downloader."""

    # Colors
    BG_COLOR = "#0e0e0e"
    DARK_BG = "#1a1a1a"
    ACCENT_COLOR = "#0078d4"
    FG_COLOR = "#e0e0e0"
    SECONDARY_FG = "#b0b0b0"
    SUCCESS_COLOR = "#4ec952"
    ERROR_COLOR = "#d13438"

    def __init__(self, parent: ttk.Notebook, status_manager=None):
        """
        Initialize downloader tab.

        Args:
            parent: Parent notebook widget
            status_manager: StatusManager for updating main window status bar
        """
        self.frame = ttk.Frame(parent, style="Dark.TFrame")
        self.parent = parent
        self.status_manager = status_manager  # Reference to status manager
        self.notification_manager: Optional[NotificationManager] = None
        self.downloader: Optional[ModDownloader] = None
        self.portal = FactorioPortalAPI()
        self.is_downloading = False
        self.last_search_time = 0
        self.search_timer = None

        # Track which widgets have captured mouse scroll
        self._info_text_captured = False
        self._progress_text_captured = False
        self._mods_canvas_captured = False

        # Setup UI
        self._setup_ui()

    def _get_notification_manager(self) -> NotificationManager:
        """Get or create notification manager."""
        if self.notification_manager is None:
            root = self.frame.winfo_toplevel()
            self.notification_manager = NotificationManager(root)
        return self.notification_manager

    def set_notification_manager(self, manager: NotificationManager) -> None:
        """Set the notification manager (called by main window)."""
        self.notification_manager = manager

    def _notify(
        self,
        message: str,
        notification_type: str = "info",
        duration_ms: int = 4000,
        actions: Optional[list] = None,
    ) -> None:
        """
        Show a notification.

        Args:
            message: Notification message
            notification_type: Type - "success", "error", "warning", or "info"
            duration_ms: Duration to show (0 = persistent)
            actions: List of tuples (label, callback) for action buttons
        """
        manager = self._get_notification_manager()
        manager.show(
            message,
            notification_type=notification_type,
            duration_ms=duration_ms,
            actions=actions,
        )

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        # Create main scrollable area
        main_scroll = ttk.Scrollbar(self.frame)
        main_scroll.pack(side="right", fill="y")

        canvas = tk.Canvas(
            self.frame,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=main_scroll.set,
        )
        canvas.pack(side="left", fill="both", expand=True)
        main_scroll.config(command=canvas.yview)

        # Bind mousewheel to main canvas for scrolling
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except:
                pass
            return "break"

        def _on_mousewheel_linux(event):
            try:
                if event.num == 4:
                    canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    canvas.yview_scroll(3, "units")
            except:
                pass
            return "break"

        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", _on_mousewheel_linux)
        canvas.bind("<Button-5>", _on_mousewheel_linux)

        # Create frame inside canvas
        content_frame = tk.Frame(canvas, bg=self.BG_COLOR)
        canvas.create_window(
            (0, 0), window=content_frame, anchor="nw", tags="content_frame"
        )

        self._main_scrollbar = main_scroll

        # Store individual mod progress widgets
        self.mod_progress_widgets = {}

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make canvas window width match canvas width
            canvas.itemconfig("content_frame", width=event.width)

        canvas.bind("<Configure>", on_configure)

        # Store canvas and content_frame for later binding
        self._scroll_canvas = canvas
        self._scroll_content_frame = content_frame

        # === INPUT SECTION ===
        input_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        input_frame.pack(fill="x", padx=10, pady=10)

        # Header
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")

        # Header with separator line
        header_sep_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        header_sep_frame.pack(anchor="w", padx=15, pady=(10, 8), fill="x")

        header = tk.Label(
            header_sep_frame,
            text="Download Mod",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
        )
        header.pack(anchor="w")

        separator = tk.Frame(header_sep_frame, bg=self.ACCENT_COLOR, height=2)
        separator.pack(anchor="w", fill="x", pady=(5, 0))

        # Mod URL with icon
        url_label_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        url_label_frame.pack(anchor="w", padx=15, pady=(5, 0))

        url_label = tk.Label(
            url_label_frame,
            text="🔗 Mod URL:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10),
        )
        url_label.pack(anchor="w")
        # URL input frame with button
        url_input_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        url_input_frame.pack(fill="x", padx=15, pady=(5, 10))

        self.url_entry = PlaceholderEntry(
            url_input_frame,
            placeholder="https://mods.factorio.com/mod/",
            placeholder_color="#666666",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            insertbackground=self.FG_COLOR,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10),
        )
        self.url_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.get_details_btn = tk.Button(
            url_input_frame,
            text="Load Mod",
            command=self._load_dependencies,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            font=("Segoe UI", 9, "bold"),
        )
        self.get_details_btn.pack(side="right", padx=0)

        # Bind URL changes to trigger auto-search (light search only)
        self.url_entry.bind("<KeyRelease>", lambda e: self._schedule_search())

        # Mods folder
        folder_label_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        folder_label_frame.pack(anchor="w", padx=15, pady=(8, 0))

        folder_label = tk.Label(
            folder_label_frame,
            text="Mods Folder:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10, "bold"),
        )
        folder_label.pack(anchor="w")

        # Folder display frame with better styling
        folder_display_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        folder_display_frame.pack(fill="x", padx=15, pady=(6, 12))

        folder_text_frame = tk.Frame(
            folder_display_frame, bg="#2a2a2a", relief="sunken", bd=2
        )
        folder_text_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.folder_var = tk.StringVar(value=config.get("mods_folder", ""))
        self.folder_display = tk.Label(
            folder_text_frame,
            textvariable=self.folder_var,
            bg="#2a2a2a",
            fg="#c0c0c0",
            font=("Courier New", 10),
            wraplength=400,
            justify="left",
            anchor="w",
        )
        self.folder_display.pack(fill="both", expand=True, padx=10, pady=8)

        browse_btn = tk.Button(
            folder_display_frame,
            text="Browse",
            command=self._browse_folder,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            activeforeground="#ffffff",
            relief="flat",
            padx=15,
            font=("Segoe UI", 9, "bold"),
        )
        browse_btn.pack(side="right", padx=5)

        # === MOD INFO SECTION ===
        info_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        info_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Info header with separator
        info_header_frame = tk.Frame(info_frame, bg=self.DARK_BG)
        info_header_frame.pack(anchor="w", padx=15, pady=(10, 8), fill="x")

        info_header = tk.Label(
            info_header_frame,
            text="Mod Information",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
        )
        info_header.pack(anchor="w")

        info_separator = tk.Frame(info_header_frame, bg=self.ACCENT_COLOR, height=2)
        info_separator.pack(anchor="w", fill="x", pady=(5, 0))

        # Info display area with optional scrollbar
        info_scroll_frame = tk.Frame(info_frame, bg=self.DARK_BG)
        info_scroll_frame.pack(fill="both", expand=True, padx=15, pady=(10, 10))

        self.info_scrollbar = tk.Scrollbar(info_scroll_frame)

        self.mod_info_text = tk.Text(
            info_scroll_frame,
            height=8,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 9),
            relief="flat",
            state="disabled",
            wrap="word",
            cursor="arrow",
            insertwidth=0,
        )
        self.info_scrollbar.config(command=self.mod_info_text.yview)
        self.mod_info_text.pack(fill="both", expand=True)
        self.info_scroll_frame = info_scroll_frame

        # Configure text tags for colors
        self.mod_info_text.tag_configure(
            "title", font=("Segoe UI", 11, "bold"), foreground=self.ACCENT_COLOR
        )
        self.mod_info_text.tag_configure(
            "label", font=("Segoe UI", 9, "bold"), foreground=self.FG_COLOR
        )
        self.mod_info_text.tag_configure("value", foreground=self.SECONDARY_FG)
        self.mod_info_text.tag_configure("success", foreground=self.SUCCESS_COLOR)
        self.mod_info_text.tag_configure("error", foreground=self.ERROR_COLOR)
        self.mod_info_text.tag_configure("warning", foreground="#ffad00")

        # Initial message
        self.mod_info_text.config(state="normal")
        self.mod_info_text.insert("end", "Enter a mod URL to see details...", "value")
        self.mod_info_text.config(state="disabled")

        # === OPTIONS SECTION ===
        options_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        options_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Options header with separator
        options_header_frame = tk.Frame(options_frame, bg=self.DARK_BG)
        options_header_frame.pack(anchor="w", padx=15, pady=(10, 8), fill="x")

        options_header = tk.Label(
            options_header_frame,
            text="Options",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
        )
        options_header.pack(anchor="w")

        options_separator = tk.Frame(
            options_header_frame, bg=self.ACCENT_COLOR, height=2
        )
        options_separator.pack(anchor="w", fill="x", pady=(5, 0))

        self.include_optional_var = tk.BooleanVar(
            value=config.get("download_optional", False)
        )

        checkbox = tk.Checkbutton(
            options_frame,
            text="Include optional dependencies (⚠️ may increase download size)",
            variable=self.include_optional_var,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            activebackground=self.DARK_BG,
            activeforeground=self.ACCENT_COLOR,
            selectcolor=self.DARK_BG,
            font=("Segoe UI", 9),
        )
        checkbox.pack(anchor="w", padx=15, pady=(5, 10))

        # === ACTION BUTTONS ===
        button_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.download_btn = tk.Button(
            button_frame,
            text="Download",
            command=self._start_download,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            activeforeground="#000000",
            relief="flat",
            padx=20,
            pady=10,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        self.download_btn.pack(side="left", padx=5)

        # === PROGRESS SECTION ===
        progress_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Progress header with separator
        progress_header_frame = tk.Frame(progress_frame, bg=self.DARK_BG)
        progress_header_frame.pack(anchor="w", padx=15, pady=(10, 8), fill="x")

        progress_header = tk.Label(
            progress_header_frame,
            text="Download Progress",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
        )
        progress_header.pack(anchor="w")

        progress_separator = tk.Frame(
            progress_header_frame, bg=self.ACCENT_COLOR, height=2
        )
        progress_separator.pack(anchor="w", fill="x", pady=(5, 0))

        # Main progress bar
        progress_info_frame = tk.Frame(progress_frame, bg=self.DARK_BG)
        progress_info_frame.pack(fill="x", padx=15, pady=(10, 0))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_info_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(side="left", fill="both", expand=True, pady=(5, 0))

        # Progress percentage label
        self.progress_label = tk.Label(
            progress_info_frame,
            text="0%",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9, "bold"),
            width=5,
        )
        self.progress_label.pack(side="right", padx=(10, 0), pady=(5, 0))

        # Main content area with console on left and individual downloads on right
        content_area = tk.Frame(progress_frame, bg=self.DARK_BG)
        content_area.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        # Progress text area with scrollbar (LEFT SIDE)
        scroll_frame = tk.Frame(content_area, bg=self.DARK_BG)
        scroll_frame.pack(side="left", fill="both", expand=True)
        self.progress_scroll_frame = scroll_frame  # Store reference

        scrollbar = tk.Scrollbar(scroll_frame)
        scrollbar.pack(side="right", fill="y")

        self.progress_text = tk.Text(
            scroll_frame,
            height=15,
            width=80,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            insertbackground=self.FG_COLOR,
            yscrollcommand=scrollbar.set,
            relief="solid",
            borderwidth=1,
            font=("Consolas", 9),
            cursor="arrow",
            insertwidth=0,
        )
        self.progress_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.progress_text.yview)

        # Configure text tags for colors
        self.progress_text.tag_config("success", foreground=self.SUCCESS_COLOR)
        self.progress_text.tag_config("error", foreground=self.ERROR_COLOR)
        self.progress_text.tag_config("info", foreground=self.ACCENT_COLOR)
        self.progress_text.tag_config("warning", foreground="#ffad00")

        # Individual downloads sidebar (RIGHT SIDE)
        sidebar_frame = tk.Frame(content_area, bg=self.DARK_BG, width=250)
        sidebar_frame.pack(side="right", fill="both", padx=(10, 0))
        sidebar_frame.pack_propagate(False)

        sidebar_header = tk.Label(
            sidebar_frame,
            text="📥 Downloads",
            font=("Segoe UI", 10, "bold"),
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
        )
        sidebar_header.pack(anchor="w", padx=5, pady=(5, 5))

        # Create a canvas with scrollbar for individual mod downloads
        sidebar_scroll = tk.Scrollbar(sidebar_frame)
        sidebar_scroll.pack(side="right", fill="y")

        self.mods_canvas = tk.Canvas(
            sidebar_frame,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=sidebar_scroll.set,
            relief="solid",
            borderwidth=1,
        )
        self.mods_canvas.pack(side="left", fill="both", expand=True)
        sidebar_scroll.config(command=self.mods_canvas.yview)

        # Frame inside canvas to hold individual mod progress items
        self.mods_frame = tk.Frame(self.mods_canvas, bg=self.BG_COLOR)
        self.mods_canvas_window = self.mods_canvas.create_window(
            (0, 0), window=self.mods_frame, anchor="nw"
        )

        def on_canvas_configure(event):
            self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))
            # Make frame width match canvas width
            self.mods_canvas.itemconfig(self.mods_canvas_window, width=event.width)

        self.mods_canvas.bind("<Configure>", on_canvas_configure)

        # Bind frame configure event to update scroll region when items are added
        def on_frame_configure(event):
            self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))

        self.mods_frame.bind("<Configure>", on_frame_configure)

        # Dictionary to store mod progress widgets
        self.mod_progress_widgets = {}

        # Initial placeholder message
        self.progress_text.insert(
            "end", "Ready to download - enter a mod URL and click Download", "info"
        )

        # Bind mousewheel to all child widgets to propagate to canvas
        self._bind_mousewheel_recursive(
            content_frame, _on_mousewheel, _on_mousewheel_linux
        )

        # Set up click-capture scrolling - bind to content_frame to detect mouse position
        # This approach works because disabled widgets don't receive events, so we detect position instead
        content_frame.bind("<Button-1>", self._on_click)
        content_frame.bind("<Button-3>", self._on_right_click)
        content_frame.bind("<Leave>", self._on_leave)
        content_frame.bind("<MouseWheel>", self._on_global_mousewheel)
        content_frame.bind(
            "<Button-4>", lambda e: self._on_global_mousewheel_linux(e, -3)
        )
        content_frame.bind(
            "<Button-5>", lambda e: self._on_global_mousewheel_linux(e, 3)
        )

    def _bind_mousewheel_recursive(self, widget, handler_win, handler_linux):
        """Recursively bind mousewheel to all child widgets."""
        try:
            # Skip Text widgets and Scrollbars - they handle their own events
            if isinstance(widget, (tk.Text, tk.Scrollbar, ttk.Scrollbar)):
                return

            # Skip frames that contain scrollable content (they have scrollbars and Text widgets)
            if hasattr(self, "info_scroll_frame") and widget is self.info_scroll_frame:
                return
            if (
                hasattr(self, "progress_scroll_frame")
                and widget is self.progress_scroll_frame
            ):
                return

            # Bind to this widget
            widget.bind("<MouseWheel>", handler_win)
            widget.bind("<Button-4>", handler_linux)
            widget.bind("<Button-5>", handler_linux)

            # Recursively bind to all children
            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child, handler_win, handler_linux)
        except:
            pass

    def _on_text_mousewheel(self, event, widget_type: str, text_widget: tk.Text) -> str:
        """Handle mouse wheel scroll for text widgets only when captured."""
        is_captured = False
        if widget_type == "info":
            is_captured = self._info_text_captured
        elif widget_type == "progress":
            is_captured = self._progress_text_captured

        if is_captured:
            text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # Block main canvas from scrolling
        # If not captured, let event propagate to main canvas
        return ""

    def _on_text_mousewheel_linux(
        self, event, widget_type: str, text_widget: tk.Text, scroll_units: int
    ) -> str:
        """Handle mouse wheel scroll for text widgets on Linux."""
        is_captured = False
        if widget_type == "info":
            is_captured = self._info_text_captured
        elif widget_type == "progress":
            is_captured = self._progress_text_captured

        if is_captured:
            text_widget.yview_scroll(scroll_units, "units")
            return "break"  # Block main canvas from scrolling
        # If not captured, let event propagate to main canvas
        return ""

    def _on_canvas_mousewheel(
        self, event, widget_type: str, canvas_widget: tk.Canvas
    ) -> str:
        """Handle mouse wheel scroll for canvas widgets only when captured."""
        is_captured = False
        if widget_type == "mods":
            is_captured = self._mods_canvas_captured

        if is_captured:
            canvas_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # Block main canvas from scrolling
        # If not captured, let event propagate to main canvas
        return ""

    def _on_canvas_mousewheel_linux(
        self, event, widget_type: str, canvas_widget: tk.Canvas, scroll_units: int
    ) -> str:
        """Handle mouse wheel scroll for canvas widgets on Linux."""
        is_captured = False
        if widget_type == "mods":
            is_captured = self._mods_canvas_captured

        if is_captured:
            canvas_widget.yview_scroll(scroll_units, "units")
            return "break"  # Block main canvas from scrolling
        # If not captured, let event propagate to main canvas
        return ""

    def _browse_folder(self) -> None:
        """Browse for mods folder."""
        folder = filedialog.askdirectory(
            title="Select Factorio Mods Folder",
            initialdir=self.folder_var.get() or config.get("mods_folder", ""),
        )
        if folder:
            self.folder_var.set(folder)
            config.set("mods_folder", folder)

    def _log_progress(self, message: str, tag: str = "") -> None:
        """Log progress message to text widget."""
        self.progress_text.insert("end", message + "\n", tag)
        self.progress_text.see("end")
        self.progress_text.update_idletasks()

    def _update_overall_progress(self, completed: int, total: int) -> None:
        """Update overall download progress bar."""
        if total == 0:
            pct = 0
        else:
            pct = (completed / total) * 100

        self.progress_var.set(pct)
        self.progress_label.config(text=f"{int(pct)}%")
        self.progress_bar.update_idletasks()

        # Update main status bar
        if self.status_manager:
            status_msg = f"Downloading: {completed}/{total} mods ({int(pct)}%)"
            self.status_manager.push_status(status_msg, "working")

    def _update_mod_download_progress(
        self, mod_name: str, status: str, progress_pct: int
    ) -> None:
        """Update progress for a specific mod download."""
        # Ensure mod item exists
        if mod_name not in self.mod_progress_widgets:
            self._add_mod_progress_item(mod_name)

        # Update status
        self._update_mod_status(mod_name, status)

        # Mark as complete if status indicates completion
        if "✓" in status or "✗" in status:
            success = "✓" in status
            self._complete_mod_progress(mod_name, success)

    def _add_mod_progress_item(self, mod_name: str) -> None:
        """Add a new mod to the individual downloads sidebar."""
        if mod_name in self.mod_progress_widgets:
            return

        # Create frame for this mod
        mod_item = tk.Frame(
            self.mods_frame, bg=self.BG_COLOR, relief="solid", borderwidth=1
        )
        mod_item.pack(fill="x", pady=3, padx=3)

        # Mod name label
        name_label = tk.Label(
            mod_item,
            text=mod_name,
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9, "bold"),
            wraplength=200,
            justify="left",
        )
        name_label.pack(anchor="w", padx=5, pady=(5, 2))

        # Status/progress label
        status_label = tk.Label(
            mod_item,
            text="Preparing...",
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 8),
        )
        status_label.pack(anchor="w", padx=5, pady=(0, 3))

        # Store widgets
        self.mod_progress_widgets[mod_name] = {
            "frame": mod_item,
            "name_label": name_label,
            "status_label": status_label,
        }

        # Update canvas scroll region
        self.mods_frame.update_idletasks()
        self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))

    def _update_mod_status(self, mod_name: str, status: str) -> None:
        """Update status for a specific mod."""
        if mod_name not in self.mod_progress_widgets:
            self._add_mod_progress_item(mod_name)

        widget = self.mod_progress_widgets[mod_name]
        widget["status_label"].config(text=status)
        widget["status_label"].update_idletasks()

    def _complete_mod_progress(self, mod_name: str, success: bool = True) -> None:
        """Mark a mod as completed."""
        if mod_name in self.mod_progress_widgets:
            widget = self.mod_progress_widgets[mod_name]
            if success:
                widget["status_label"].config(
                    text="✓ Downloaded", fg=self.SUCCESS_COLOR
                )
                widget["name_label"].config(fg=self.SUCCESS_COLOR)
            else:
                widget["status_label"].config(text="✗ Failed", fg=self.ERROR_COLOR)
                widget["name_label"].config(fg=self.ERROR_COLOR)
            widget["status_label"].update_idletasks()

    def _start_download(self) -> None:
        """Start downloading mods in background thread."""
        url = self.url_entry.get().strip()
        mods_folder = self.folder_var.get()

        # Validate input
        if not url or url == "https://mods.factorio.com/mod/":
            self._notify(
                "Please enter a mod URL or mod name", notification_type="error"
            )
            return

        # If URL doesn't contain full path, treat it as mod name and auto-complete
        if "/mod/" not in url:
            # User entered just the mod name, construct full URL
            mod_name = url.split("?")[0].strip()  # Remove query parameters
        else:
            # Validate full URL format
            if not validate_mod_url(url):
                self._notify(
                    "Invalid URL. Please use: https://mods.factorio.com/mod/ModName",
                    notification_type="error",
                )
                return
            # Extract mod name from URL (remove query parameters)
            mod_name = url.split("/mod/")[-1].strip("/")
            mod_name = mod_name.split("?")[
                0
            ]  # Remove query parameters like ?from=search

        if not mods_folder:
            self._notify("Please select a mods folder", notification_type="error")
            return

        # Disable button and start download
        self.download_btn.config(state="disabled")
        self.is_downloading = True

        # Clear progress
        self.progress_text.delete("1.0", "end")
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        self.mod_progress_widgets.clear()
        # Clear mods frame
        for widget in self.mods_frame.winfo_children():
            widget.destroy()
        self._log_progress(f"Starting download for {mod_name}...\n", "info")

        # Check network connectivity
        is_online_status, _ = is_online()
        if not is_online_status:
            self._log_progress("Network error: You are offline\n", "error")
            self.frame.after(
                500,
                lambda: self._notify(
                    "📡 You are offline. Cannot download mods without internet connection.",
                    notification_type="error",
                ),
            )
            return

        # Start download in background thread
        thread = Thread(
            target=self._download_thread, args=(mod_name, mods_folder), daemon=True
        )
        thread.start()

    def _download_thread(self, mod_name: str, mods_folder: str) -> None:
        """Background thread for downloading mods."""
        try:
            # Get credentials from config
            username = config.get("username")
            token = config.get("token")

            # Create downloader
            self.downloader = ModDownloader(mods_folder, username, token)
            self.downloader.set_progress_callback(
                lambda msg: self._log_progress(msg, "info")
            )
            self.downloader.set_overall_progress_callback(self._update_overall_progress)
            self.downloader.set_mod_progress_callback(
                self._update_mod_download_progress
            )

            # Update main status bar
            if self.status_manager:
                self.status_manager.push_status("Resolving dependencies...", "working")

            self._log_progress("Resolving dependencies...", "info")

            # Download mod
            include_optional = self.include_optional_var.get()

            if self.status_manager:
                self.status_manager.push_status("Starting download...", "working")

            downloaded, failed = self.downloader.download_mods(
                [mod_name], include_optional=include_optional
            )

            # Show results
            if downloaded:
                msg = f"✓ Successfully downloaded {len(downloaded)} mod(s)"
                self._log_progress(f"\n{msg}\n", "success")
                if self.status_manager:
                    self.status_manager.push_status(
                        f"Downloaded {len(downloaded)} mod(s) successfully", "success"
                    )
                self.frame.after(
                    500,
                    lambda: self._notify(
                        msg, notification_type="success", duration_ms=5000
                    ),
                )

            if failed:
                msg = f"✗ Failed to download: {', '.join(failed)}"
                self._log_progress(f"\n{msg}\n", "error")
                if self.status_manager:
                    self.status_manager.push_status(
                        f"Failed to download {len(failed)} mod(s)", "error"
                    )
                self.frame.after(
                    500,
                    lambda: self._notify(
                        msg, notification_type="error", duration_ms=6000
                    ),
                )

        except PortalAPIError as e:
            error_msg = str(e.message)
            self._log_progress(f"\n✗ {error_msg}\n", "error")
            if self.status_manager:
                self.status_manager.push_status(f"Download error: {error_msg}", "error")
            self.frame.after(
                500,
                lambda: self._notify(
                    error_msg, notification_type="error", duration_ms=6000
                ),
            )
        except Exception as e:
            error_msg = str(e)
            self._log_progress(f"\n✗ Error: {error_msg}\n", "error")
            if self.status_manager:
                self.status_manager.push_status(f"Download error: {error_msg}", "error")
            self.frame.after(
                500,
                lambda: self._notify(
                    f"Download failed: {error_msg}",
                    notification_type="error",
                    duration_ms=6000,
                ),
            )

        finally:
            self.is_downloading = False
            self.download_btn.config(state="normal")

    def _schedule_search(self) -> None:
        """Schedule a search with debouncing to avoid too many requests."""
        # Cancel previous timer if exists
        if self.search_timer:
            self.parent.after_cancel(self.search_timer)

        # Schedule new search after 0.5 seconds of inactivity
        self.search_timer = self.parent.after(500, self._search_mod)

    def _search_mod(self) -> None:
        """Search for mod info based on URL entry."""
        url = self.url_entry.get().strip()

        # Extract mod name from URL
        if not url or url == "https://mods.factorio.com/mod/":
            self._display_mod_info(None, "Enter a mod URL to see details...")
            return

        # Try to extract mod name - preserve case as API is case-sensitive
        if "/mod/" in url:
            mod_name = url.split("/mod/")[-1].strip("/")
            mod_name = mod_name.split("?")[
                0
            ]  # Remove query parameters like ?from=search
        else:
            mod_name = url.split("?")[0]  # Remove query parameters from direct name

        if not mod_name:
            self._display_mod_info(None, "Invalid mod URL format")
            return

        # Start search in background thread to avoid freezing UI
        thread = Thread(target=self._search_thread, args=(mod_name,), daemon=True)
        thread.start()

    def _search_thread(self, mod_name: str) -> None:
        """Background thread for searching mod info."""
        try:
            # Fetch mod info from portal - light operation, just basic mod data
            mod_data = self.portal.get_mod(mod_name)

            # Note: We DO NOT resolve dependencies during auto-search as it's too slow
            # and blocks the UI. Dependencies will be resolved on-demand if user downloads.
            # This keeps the auto-search responsive while typing.

            self._display_mod_info(mod_data, mod_name)
        except Exception as e:
            self._display_mod_info(None, f"Error searching for mod: {e}")

    def _load_dependencies(self) -> None:
        """Load and display mod dependencies when user clicks 'Load Dependencies' button."""
        url = self.url_entry.get().strip()

        # Extract mod name from URL
        if not url or url == "https://mods.factorio.com/mod/":
            self._notify(
                "Please enter a mod URL to see details", notification_type="warning"
            )
            return

        # Try to extract mod name
        if "/mod/" in url:
            mod_name = url.split("/mod/")[-1].strip("/")
            mod_name = mod_name.split("?")[0]
        else:
            mod_name = url.split("?")[0]

        if not mod_name:
            self._notify("Invalid mod URL format", notification_type="error")
            return

        # Show loading status
        self.mod_info_text.config(state="normal")
        self.mod_info_text.delete("1.0", "end")
        self.mod_info_text.insert("end", "Loading dependencies...", "value")
        self.mod_info_text.config(state="disabled")

        # Start dependency resolution in background thread
        thread = Thread(
            target=self._load_dependencies_thread, args=(mod_name,), daemon=True
        )
        thread.start()

    def _load_dependencies_thread(self, mod_name: str) -> None:
        """Background thread for loading and resolving mod dependencies."""
        try:
            # Fetch mod info from portal
            mod_data = self.portal.get_mod(mod_name)

            # Resolve ALL dependencies (including optional) to show what COULD be downloaded
            if mod_data:
                from ..core.downloader import ModDownloader
                from pathlib import Path

                # Get mods folder from UI
                mods_folder = self.folder_var.get()
                if mods_folder and Path(mods_folder).exists():
                    downloader = ModDownloader(mods_folder)
                else:
                    downloader = ModDownloader("")  # Empty path, we're not downloading

                try:
                    # Resolve dependencies WITH optional to show full dependency tree
                    all_deps, incompats, expansions = downloader.resolve_dependencies(
                        mod_name,
                        include_optional=True,  # Include optional so user can see full tree
                        visited=set(),
                    )
                    # Store for display
                    if "resolved_dependencies" not in mod_data:
                        mod_data["resolved_dependencies"] = list(all_deps.keys())
                    if "resolved_incompatibilities" not in mod_data:
                        mod_data["resolved_incompatibilities"] = incompats
                    if "resolved_expansions" not in mod_data:
                        mod_data["resolved_expansions"] = expansions

                    # Check for conflicts with installed mods
                    if mods_folder and Path(mods_folder).exists():
                        installed_mods = downloader.get_installed_mods()
                        conflicts = [m for m in incompats if m in installed_mods]
                        if conflicts:
                            mod_data["installed_conflicts"] = conflicts
                except:
                    pass  # If resolution fails, just show direct dependencies

            self._display_mod_info(mod_data, mod_name)
        except Exception as e:
            self._display_mod_info(None, f"Error fetching details: {e}")

    def _display_mod_info(
        self, mod_data: Optional[Dict[str, Any]], mod_name: str
    ) -> None:
        """Display mod information in the info text widget."""
        self.mod_info_text.config(state="normal")
        self.mod_info_text.delete("1.0", "end")

        if mod_data is None:
            # Display error/empty message
            self.mod_info_text.insert("end", mod_name, "value")
            self.mod_info_text.config(state="disabled")
            return

        try:
            # Title
            title = mod_data.get("title", mod_name)
            self.mod_info_text.insert("end", f"{title}\n", "title")
            self.mod_info_text.insert("end", "=" * 50 + "\n\n", "value")

            # Author
            author = mod_data.get("owner") or mod_data.get("author", "Unknown")
            self.mod_info_text.insert("end", "Author: ", "label")
            self.mod_info_text.insert("end", f"{author}\n", "value")

            # Downloads
            downloads = mod_data.get("downloads_count", 0)
            self.mod_info_text.insert("end", "Downloads: ", "label")
            self.mod_info_text.insert("end", f"{downloads:,}\n", "success")

            # Latest Version
            releases = mod_data.get("releases", [])
            if releases:
                latest = releases[-1]  # Latest is last
                version = latest.get("version", "Unknown")
                released = latest.get("released_at", "Unknown")

                self.mod_info_text.insert("end", "Latest Version: ", "label")
                self.mod_info_text.insert(
                    "end", f"{version} (Released: {released})\n", "value"
                )

            # Homepage
            homepage = mod_data.get("homepage", None)
            if homepage:
                self.mod_info_text.insert("end", "Homepage: ", "label")
                self.mod_info_text.insert("end", f"{homepage}\n", "value")

            # GitHub
            github = mod_data.get("github_path", None)
            if github:
                self.mod_info_text.insert("end", "GitHub: ", "label")
                self.mod_info_text.insert(
                    "end", f"https://github.com/{github}\n", "value"
                )

            self.mod_info_text.insert("end", "\n", "value")

            # Description
            description = mod_data.get("description", "No description available")
            self.mod_info_text.insert("end", "Description:\n", "label")
            self.mod_info_text.insert("end", f"{description}\n\n", "value")

            # Dependencies from info_json
            if releases:
                latest_release = releases[-1]
                info_json = latest_release.get("info_json", {})
                all_deps = info_json.get("dependencies", [])

                if all_deps:
                    self.mod_info_text.insert("end", "Dependencies:\n", "label")

                    required = []
                    optional = []
                    incompatible = []
                    expansions = []

                    # Known Factorio expansions
                    EXPANSIONS = {"space-age", "elevated-rails", "aquilo"}

                    for dep in all_deps:
                        dep = dep.strip()

                        if not dep or dep == "base":
                            continue

                        # Parse dependency format
                        if dep.startswith("!"):
                            # Incompatible
                            dep_name = dep[1:].strip()
                            incompatible.append(dep_name)
                        elif dep.startswith("(?)") or dep.startswith("?"):
                            # Optional
                            dep_name = dep.replace("(?)", "").replace("?", "").strip()
                            # Extract just mod name (before constraints)
                            dep_name = (
                                dep_name.split()[0]
                                if " " in dep_name
                                else dep_name.split(">")[0]
                                .split("=")[0]
                                .split("<")[0]
                                .split("!")[0]
                                .strip()
                            )
                            if dep_name:
                                optional.append(dep_name)
                        else:
                            # Required
                            dep_name = (
                                dep.split()[0]
                                if " " in dep
                                else dep.split(">")[0]
                                .split("=")[0]
                                .split("<")[0]
                                .strip()
                            )
                            if dep_name and dep_name != "base":
                                # Check if it's an expansion
                                if dep_name in EXPANSIONS:
                                    expansions.append(dep_name)
                                else:
                                    required.append(dep_name)

                    if required:
                        self.mod_info_text.insert("end", "  🔗 Required: ", "label")
                        self.mod_info_text.insert(
                            "end", ", ".join(required) + "\n", "value"
                        )

                    if optional:
                        self.mod_info_text.insert("end", "  ❓ Optional: ", "label")
                        self.mod_info_text.insert(
                            "end", ", ".join(optional) + "\n", "warning"
                        )

                    if incompatible:
                        self.mod_info_text.insert("end", "  ❌ Incompatible: ", "label")
                        self.mod_info_text.insert(
                            "end", ", ".join(incompatible) + "\n", "error"
                        )

                    if expansions:
                        self.mod_info_text.insert("end", "  💿 Requires DLC: ", "label")
                        self.mod_info_text.insert(
                            "end", ", ".join(expansions) + "\n", "error"
                        )
                else:
                    self.mod_info_text.insert(
                        "end", "✓ No direct dependencies\n", "success"
                    )

            # Show all dependencies (including transitive ones) that will be downloaded
            resolved_deps = mod_data.get("resolved_dependencies", [])
            if resolved_deps:
                self.mod_info_text.insert("end", "\n", "value")
                self.mod_info_text.insert(
                    "end", "All Dependencies (including transitive):\n", "label"
                )
                # Remove the main mod from the list
                resolved_mods = [m for m in resolved_deps if m != mod_name]
                if resolved_mods:
                    self.mod_info_text.insert(
                        "end", "  📦 " + ", ".join(sorted(resolved_mods)) + "\n", "info"
                    )
                    self.mod_info_text.insert(
                        "end",
                        f"  Total: {len(resolved_mods)} additional mod(s) will be downloaded\n",
                        "success",
                    )
                    self.mod_info_text.insert(
                        "end",
                        "  (includes optional dependencies and their dependencies)\n",
                        "warning",
                    )
                else:
                    self.mod_info_text.insert(
                        "end", "  ✓ Only this mod (no dependencies)\n", "success"
                    )

            resolved_incompats = mod_data.get("resolved_incompatibilities", [])
            if resolved_incompats:
                self.mod_info_text.insert("end", "\n⚠️  Incompatible with:\n", "warning")
                self.mod_info_text.insert(
                    "end", "  " + ", ".join(resolved_incompats) + "\n", "error"
                )

            # Check for conflicts with installed mods
            installed_conflicts = mod_data.get("installed_conflicts", [])
            if installed_conflicts:
                self.mod_info_text.insert(
                    "end", "\n🚨 CONFLICTS WITH INSTALLED MODS:\n", "error"
                )
                for conflict in installed_conflicts:
                    self.mod_info_text.insert(
                        "end", f"  ⚠️  {conflict} (already installed)\n", "error"
                    )
                self.mod_info_text.insert(
                    "end", "  Installing this mod may cause issues!\n", "error"
                )

        except Exception as e:
            self.mod_info_text.insert("end", f"Error displaying mod info: {e}", "error")

        finally:
            self.mod_info_text.config(state="disabled")

    def _get_widget_at_position(self, x, y):
        """Get which scrollable widget the mouse is over."""
        # Get the actual widget at the event position
        try:
            widget = self.mod_info_text.winfo_containing(x, y)
            if widget is self.mod_info_text or (
                hasattr(widget, "master")
                and self._is_descendant_of(widget, self.info_scroll_frame)
            ):
                return "info"

            widget = self.progress_text.winfo_containing(x, y)
            if widget is self.progress_text or (
                hasattr(widget, "master")
                and self._is_descendant_of(widget, self.progress_scroll_frame)
            ):
                return "progress"

            widget = self.mods_canvas.winfo_containing(x, y)
            if widget is self.mods_canvas or (
                hasattr(widget, "master")
                and self._is_descendant_of(widget, self.mods_canvas)
            ):
                return "mods"
        except:
            pass
        return None

    def _is_descendant_of(self, widget, parent):
        """Check if widget is a descendant of parent."""
        current = widget
        while current:
            if current is parent:
                return True
            try:
                current = current.master
            except:
                break
        return False

    def _capture_scroll(self, widget_type: str) -> None:
        """Engage scrolling for a specific widget type."""
        if widget_type == "info":
            self._info_text_captured = True
        elif widget_type == "progress":
            self._progress_text_captured = True
        elif widget_type == "mods":
            self._mods_canvas_captured = True

    def _release_scroll(self, widget_type: str) -> None:
        """Disengage scrolling for a specific widget type."""
        if widget_type == "info":
            self._info_text_captured = False
        elif widget_type == "progress":
            self._progress_text_captured = False
        elif widget_type == "mods":
            self._mods_canvas_captured = False

    def _on_click(self, event):
        """Handle left-click to engage scrolling."""
        widget_type = self._get_widget_at_position(event.x_root, event.y_root)
        if widget_type:
            self._capture_scroll(widget_type)

    def _on_right_click(self, event):
        """Handle right-click to disengage scrolling."""
        widget_type = self._get_widget_at_position(event.x_root, event.y_root)
        if widget_type:
            self._release_scroll(widget_type)

    def _on_leave(self, event):
        """Release all captured scrolling on mouse leave."""
        self._release_scroll("info")
        self._release_scroll("progress")
        self._release_scroll("mods")

    def _on_global_mousewheel(self, event):
        """Handle global mousewheel - check which widget is captured."""
        widget_type = self._get_widget_at_position(event.x_root, event.y_root)

        if widget_type == "info" and self._info_text_captured:
            self.mod_info_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        elif widget_type == "progress" and self._progress_text_captured:
            self.progress_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        elif widget_type == "mods" and self._mods_canvas_captured:
            self.mods_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        # Allow main canvas to scroll
        return ""

    def _on_global_mousewheel_linux(self, event, scroll_units):
        """Handle global mousewheel on Linux."""
        widget_type = self._get_widget_at_position(event.x_root, event.y_root)

        if widget_type == "info" and self._info_text_captured:
            self.mod_info_text.yview_scroll(scroll_units, "units")
            return "break"
        elif widget_type == "progress" and self._progress_text_captured:
            self.progress_text.yview_scroll(scroll_units, "units")
            return "break"
        elif widget_type == "mods" and self._mods_canvas_captured:
            self.mods_canvas.yview_scroll(scroll_units, "units")
            return "break"
        # Allow main canvas to scroll
        return ""
