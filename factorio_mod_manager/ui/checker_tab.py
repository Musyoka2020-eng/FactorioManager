"""Checker tab UI."""
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from typing import Dict, List, Optional
from threading import Thread
from pathlib import Path
from ..core import ModChecker, Mod, ModStatus
from ..utils import config, format_file_size, is_online
from .widgets import PlaceholderEntry, NotificationManager
from .checker_logic import CheckerLogic
from .checker_presenter import CheckerPresenter


class CheckerTab:
    """UI for mod checker/updater."""

    # Colors
    BG_COLOR = "#0e0e0e"
    DARK_BG = "#1a1a1a"
    ACCENT_COLOR = "#0078d4"
    FG_COLOR = "#e0e0e0"
    SECONDARY_FG = "#b0b0b0"
    SUCCESS_COLOR = "#4ec952"
    ERROR_COLOR = "#d13438"
    WARNING_COLOR = "#ffad00"

    def __init__(self, parent: ttk.Notebook, logger: Optional[logging.Logger] = None, status_manager=None):
        """
        Initialize checker tab.
        
        Args:
            parent: Parent notebook widget
            logger: Optional logger instance
            status_manager: StatusManager for updating main window status bar
        """
        self.frame = ttk.Frame(parent, style="Dark.TFrame")
        self.parent = parent
        self.logger = logger or logging.getLogger(__name__)
        self.status_manager = status_manager  # Reference to status manager
        self.notification_manager: Optional[NotificationManager] = None  # Will be initialized on first use
        self.checker: Optional[ModChecker] = None
        self.logic: Optional[CheckerLogic] = None
        self.presenter = CheckerPresenter()
        self.mods: Dict[str, Mod] = {}
        self.selected_mods: set = set()  # Track selected mods for checkboxes
        self.is_scanning = False
        self.filter_var = tk.StringVar()
        self.filter_mode = tk.StringVar(value="all")  # Filter: all, outdated, up_to_date, selected
        self.mod_widgets: Dict[str, tk.Frame] = {}  # Map mod names to frame widgets
        self.auto_scan_timer = None  # Timer for auto-scan with delay
        self.auto_scan_scheduled = False  # Flag to prevent duplicate auto-scans
        
        # Bind to tab visibility to trigger auto-scan
        self.frame.bind("<Visibility>", self._on_tab_visible)
        
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
    
    def _notify(self, message: str, notification_type: str = "info", duration_ms: int = 4000, actions: Optional[list] = None) -> None:
        """
        Show a notification.
        
        Args:
            message: Notification message
            notification_type: Type - "success", "error", "warning", or "info"
            duration_ms: Duration to show (0 = persistent)
            actions: List of tuples (label, callback) for action buttons
        """
        manager = self._get_notification_manager()
        manager.show(message, notification_type=notification_type, duration_ms=duration_ms, actions=actions)
    
    def _setup_ui(self) -> None:
        """Setup the UI components with three-column layout."""
        # Configure frame to use grid
        self.frame.grid_rowconfigure(0, weight=1)  # Main content area (left/center/right)
        self.frame.grid_rowconfigure(1, weight=0)  # Log area
        self.frame.grid_columnconfigure(0, weight=0, minsize=220)  # Left sidebar (fixed width)
        self.frame.grid_columnconfigure(1, weight=1)  # Center (expandable)
        self.frame.grid_columnconfigure(2, weight=0, minsize=280)  # Right sidebar (fixed width)
        
        # Font for headers
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        
        # ============================================
        # LEFT SIDEBAR - SETTINGS & CONTROL BUTTONS
        # ============================================
        left_sidebar = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        left_sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_sidebar.grid_rowconfigure(0, weight=0)  # Settings
        left_sidebar.grid_rowconfigure(1, weight=1)  # Spacer
        left_sidebar.grid_columnconfigure(0, weight=1)
        
        # Settings section
        control_frame = tk.Frame(left_sidebar, bg=self.DARK_BG)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        header = tk.Label(
            control_frame,
            text="⚙️  Settings",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        header.pack(anchor="w", pady=(0, 10))
        
        # Mods folder selection
        folder_label = tk.Label(
            control_frame,
            text="📁 Mods Folder:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9, "bold")
        )
        folder_label.pack(anchor="w", pady=(0, 4))
        
        folder_display_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        folder_display_frame.pack(fill="x", pady=(0, 10))
        
        folder_text_frame = tk.Frame(folder_display_frame, bg="#2a2a2a", relief="sunken", bd=2)
        folder_text_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        
        self.folder_var = tk.StringVar(value=config.get("mods_folder", ""))
        self.folder_display = tk.Label(
            folder_text_frame,
            textvariable=self.folder_var,
            bg="#2a2a2a",
            fg="#c0c0c0",
            font=("Courier New", 9),
            wraplength=125,
            justify="left",
            anchor="w"
        )
        self.folder_display.pack(fill="both", expand=True, padx=6, pady=5)
        
        browse_btn = tk.Button(
            folder_display_frame,
            text="Browse",
            command=self._browse_folder,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            relief="flat",
            padx=8,
            pady=3,
            font=("Segoe UI", 8, "bold")
        )
        browse_btn.pack(side="right")
        
        # Status indicator
        status_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        status_frame.pack(fill="x", pady=(0, 10))
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            bg=self.DARK_BG,
            fg=self.SUCCESS_COLOR,
            font=("Segoe UI", 8)
        )
        self.status_label.pack(anchor="w")
        
        # Control buttons (vertical stack)
        button_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        button_frame.pack(fill="x", pady=(15, 0))
        
        button_frame.grid_columnconfigure(0, weight=1)
        
        self.scan_btn = tk.Button(
            button_frame,
            text="🔍 Scan",
            command=self._start_scan,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            relief="flat",
            pady=6,
            font=("Segoe UI", 9, "bold")
        )
        self.scan_btn.pack(fill="x", pady=2, padx=3)
        
        self.check_btn = tk.Button(
            button_frame,
            text="⬆️ Check Updates",
            command=self._start_check,
            bg=self.WARNING_COLOR,
            fg="#000000",
            activebackground="#ffbb22",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.check_btn.pack(fill="x", pady=2, padx=3)
        
        self.update_btn = tk.Button(
            button_frame,
            text="📥 Update Selected",
            command=self._update_selected,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.update_btn.pack(fill="x", pady=2, padx=3)
        
        self.delete_btn = tk.Button(
            button_frame,
            text="🗑️  Delete",
            command=self._delete_selected,
            bg=self.ERROR_COLOR,
            fg="#ffffff",
            activebackground="#c41c1c",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.delete_btn.pack(fill="x", pady=2, padx=3)
        
        self.update_all_btn = tk.Button(
            button_frame,
            text="📥 Update All",
            command=self._update_all_outdated,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.update_all_btn.pack(fill="x", pady=2, padx=3)
        
        self.delete_backups_btn = tk.Button(
            button_frame,
            text="🧹 Backups",
            command=self._delete_all_backups,
            bg="#8b5a00",
            fg="#ffffff",
            activebackground="#a66d00",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold")
        )
        self.delete_backups_btn.pack(fill="x", pady=2, padx=3)
        
        self.backup_btn = tk.Button(
            button_frame,
            text="💾 Backup",
            command=self._backup_selected,
            bg="#6b5b95",
            fg="#ffffff",
            activebackground="#7b6ba5",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.backup_btn.pack(fill="x", pady=2, padx=3)
        
        self.view_info_btn = tk.Button(
            button_frame,
            text="ℹ️  View Details",
            command=self._show_mod_details,
            bg="#0078d4",
            fg="#ffffff",
            activebackground="#1084d7",
            relief="flat",
            pady=6,
            font=("Segoe UI", 8, "bold"),
            state="disabled"
        )
        self.view_info_btn.pack(fill="x", pady=2, padx=3)
        
        # ============================================
        # CENTER - INSTALLED MODS LIST
        # ============================================
        center_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        center_frame.grid_rowconfigure(0, weight=0)  # Header
        center_frame.grid_rowconfigure(1, weight=1)  # Mods list
        center_frame.grid_columnconfigure(0, weight=1)
        
        # Header with separator
        center_header_frame = tk.Frame(center_frame, bg=self.DARK_BG)
        center_header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))
        center_header_frame.grid_columnconfigure(0, weight=1)
        
        center_header = tk.Label(
            center_header_frame,
            text="📦 Installed Mods",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        center_header.pack(anchor="w")
        
        center_separator = tk.Frame(center_header_frame, bg=self.ACCENT_COLOR, height=2)
        center_separator.pack(anchor="w", fill="x", pady=(5, 0))
        
        # Mods canvas container
        list_container = tk.Frame(center_frame, bg=self.DARK_BG)
        list_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        v_scroll = tk.Scrollbar(list_container)
        v_scroll.grid(row=0, column=1, sticky="ns")
        
        self.mods_canvas = tk.Canvas(
            list_container,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=v_scroll.set
        )
        self.mods_canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.config(command=self.mods_canvas.yview)
        
        # Frame inside canvas to hold mod items
        self.mods_frame = tk.Frame(self.mods_canvas, bg=self.BG_COLOR)
        self.mods_window = self.mods_canvas.create_window((0, 0), window=self.mods_frame, anchor="nw")
        
        def on_frame_configure(event):
            self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))
            # Expand mods_frame to match canvas width
            canvas_width = self.mods_canvas.winfo_width()
            if canvas_width > 1:
                self.mods_canvas.itemconfig(self.mods_window, width=canvas_width)
        
        def on_canvas_configure(event):
            # When canvas resizes, expand mods_frame width
            if event.width > 1:
                self.mods_canvas.itemconfig(self.mods_window, width=event.width)
        
        self.mods_frame.bind("<Configure>", on_frame_configure)
        self.mods_canvas.bind("<Configure>", on_canvas_configure)
        
        # Bind mouse wheel for scrolling (with error handling)
        def on_mousewheel(event):
            try:
                self.mods_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass
        
        self.mods_canvas.bind("<MouseWheel>", on_mousewheel, add="+")
        
        # ============================================
        # RIGHT SIDEBAR - STATISTICS & FILTERS
        # ============================================
        right_sidebar = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1, width=280)
        right_sidebar.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        right_sidebar.grid_propagate(False)  # Prevent frame from expanding beyond set width
        right_sidebar.grid_rowconfigure(0, weight=0)  # Stats (fixed)
        right_sidebar.grid_rowconfigure(1, weight=1)  # Filters (can expand to fill space)
        right_sidebar.grid_columnconfigure(0, weight=1)
        
        # Statistics section
        stats_frame = tk.Frame(right_sidebar, bg=self.DARK_BG)
        stats_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 3))
        stats_frame.grid_columnconfigure(0, weight=0)
        stats_frame.grid_columnconfigure(1, weight=1)
        
        stats_header = tk.Label(
            stats_frame,
            text="📊 Statistics",
            font=("Segoe UI", 9, "bold"),
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        stats_header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        # Stats items - each on its own row (label | value)
        self.stats_items = {}  # Store stat labels for updating
        
        # Initial empty state
        self.no_data_label = tk.Label(
            stats_frame,
            text="No data yet",
            bg=self.DARK_BG,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 8)
        )
        self.no_data_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.stats_frame_ref = stats_frame
        
        # Search & Filter section
        filter_frame = tk.Frame(right_sidebar, bg=self.DARK_BG)
        filter_frame.grid(row=1, column=0, sticky="new", padx=10, pady=(3, 3))
        filter_frame.grid_columnconfigure(0, weight=1)
        
        search_label = tk.Label(
            filter_frame,
            text="🔎 Search",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9, "bold")
        )
        search_label.pack(anchor="w", pady=(0, 2))
        
        # Search entry
        self.search_entry = PlaceholderEntry(
            filter_frame,
            placeholder="by name...",
            placeholder_color="#666666",
            textvariable=self.filter_var,
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            insertbackground=self.FG_COLOR,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 9)
        )
        self.search_entry.pack(fill="x", pady=(0, 3))
        self.filter_var.trace("w", lambda *args: self._filter_mods())
        
        # Status filter label
        tk.Label(
            filter_frame,
            text="Status Filter:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", pady=(0, 2))
        
        # Filter buttons (2x2 grid)
        filter_buttons_frame = tk.Frame(filter_frame, bg=self.DARK_BG)
        filter_buttons_frame.pack(fill="x", pady=(0, 3))
        filter_buttons_frame.grid_columnconfigure([0, 1], weight=1)
        
        filter_buttons = [
            ("All", "all"),
            ("Outdated", "outdated"),
            ("Up to Date", "up_to_date"),
            ("Selected", "selected")
        ]
        
        for idx, (label, value) in enumerate(filter_buttons):
            row = idx // 2
            col = idx % 2
            btn = tk.Button(
                filter_buttons_frame,
                text=label,
                command=lambda v=value: self._set_filter(v),
                bg=self.ACCENT_COLOR,
                fg="#ffffff",
                activebackground="#1084d7",
                relief="flat",
                padx=8,
                pady=4,
                font=("Segoe UI", 8)
            )
            btn.grid(row=row, column=col, sticky="ew", padx=2, pady=2)
            if not hasattr(self, 'filter_buttons'):
                self.filter_buttons = {}
            self.filter_buttons[value] = btn
        
        # Sort label
        tk.Label(
            filter_frame,
            text="Sort By:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", pady=(2, 1))
        
        # Sort options in frame for better alignment
        sort_frame = tk.Frame(filter_frame, bg=self.DARK_BG)
        sort_frame.pack(fill="x")
        sort_frame.grid_columnconfigure(0, weight=1)
        
        self.sort_var = tk.StringVar(value="name")
        sort_options = [
            ("Name", "name"),
            ("Version", "version"),
            ("Downloads", "downloads"),
            ("Date", "date"),
        ]
        
        for idx, (label, value) in enumerate(sort_options):
            tk.Radiobutton(
                sort_frame,
                text=label,
                variable=self.sort_var,
                value=value,
                command=self._filter_mods,
                bg=self.DARK_BG,
                fg=self.FG_COLOR,
                selectcolor=self.ACCENT_COLOR,
                font=("Segoe UI", 8)
            ).grid(row=idx, column=0, sticky="w", pady=0)
        
        # ============================================
        # BOTTOM - PROGRESS LOG (spans all columns)
        # ============================================
        log_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        log_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=(0, 5))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        log_header = tk.Label(
            log_frame,
            text="📝 Operation Log",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        log_header.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Text widget with scrollbar
        log_container = tk.Frame(log_frame, bg=self.DARK_BG)
        log_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_container.grid_rowconfigure(0, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        log_scroll = tk.Scrollbar(log_container)
        log_scroll.grid(row=0, column=1, sticky="ns")
        
        self.progress_log = tk.Text(
            log_container,
            height=5,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            yscrollcommand=log_scroll.set,
            font=("Consolas", 8),
            relief="flat",
            wrap="word"
        )
        log_scroll.config(command=self.progress_log.yview)
        self.progress_log.grid(row=0, column=0, sticky="nsew")
        
        # Configure text tags for different message types
        self.progress_log.tag_configure("success", foreground=self.SUCCESS_COLOR)
        self.progress_log.tag_configure("error", foreground=self.ERROR_COLOR)
        self.progress_log.tag_configure("warning", foreground=self.WARNING_COLOR)
        self.progress_log.tag_configure("info", foreground=self.ACCENT_COLOR)
        self.progress_log.tag_configure("normal", foreground=self.SECONDARY_FG)

    
    def _browse_folder(self) -> None:
        """Browse for mods folder."""
        folder = filedialog.askdirectory(
            title="Select Factorio Mods Folder",
            initialdir=self.folder_var.get() or config.get("mods_folder", "")
        )
        if folder:
            self.folder_var.set(folder)
            config.set("mods_folder", folder)
    
    def _log_progress(self, message: str, tag: str = "normal") -> None:
        """Log progress message to both console and UI."""
        # Log to logger for Logs tab
        if tag == "error":
            self.logger.error(message)
        elif tag == "success":
            self.logger.info(f"✓ {message}")
        elif tag == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)
        
        try:
            # Add to progress log in UI
            # Check if widget still exists before updating
            if self.progress_log.winfo_exists():
                self.progress_log.config(state="normal")
                self.progress_log.insert("end", message + "\n", tag)
                self.progress_log.see("end")  # Auto-scroll to bottom
                self.progress_log.config(state="normal")
                self.progress_log.update()  # Force UI update
        except Exception as e:
            # Widget was destroyed or invalid path, just log to console
            self.logger.debug(f"UI update failed: {e}")
    
    def _update_status(self, message: str, color: Optional[str] = None) -> None:
        """Update the status via the status manager and local label (thread-safe for concurrent operations)."""
        # Update local status label in left sidebar
        try:
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.frame.after_idle(lambda: self.status_label.config(text=message, fg=color or self.SECONDARY_FG))
        except:
            pass
        
        # Push to main window status manager if available
        if not self.status_manager:
            return
        
        # Determine status type based on message and color
        if "Error" in message or "failed" in message:
            status_type = "error"
        elif "✓" in message or "Complete" in message:
            status_type = "success"
        elif "Scanning" in message or "Checking" in message or "Updating" in message:
            status_type = "working"
        else:
            status_type = "info"
        
        self.status_manager.push_status(message, status_type)
    
    def _bind_scroll_recursive(self, widget) -> None:
        """Recursively bind mouse wheel scroll to widget and all children."""
        def on_mousewheel(event):
            try:
                # Use scroll amount that's more responsive
                self.mods_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass
        
        try:
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
        except:
            pass
        
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)
    
    def _update_stats(self) -> None:
        """Update statistics display with multiline layout."""
        if not self.mods:
            return
        
        stats = self.presenter.get_statistics(self.mods)
        stats_items = self.presenter.format_statistics_multiline(stats)
        
        # Clear old stats if any - with error handling
        try:
            for label, value in list(self.stats_items.values()):  # Create list copy
                try:
                    label.destroy()
                except:
                    pass
                try:
                    value.destroy()
                except:
                    pass
            self.stats_items.clear()
        except:
            pass
        
        # Hide "No data yet" label if visible
        try:
            self.no_data_label.grid_forget()
        except:
            pass
        
        # Create stat rows (label on left, value on right)
        for idx, (label_text, value_text) in enumerate(stats_items, start=1):
            try:
                # Label (e.g., "Total")
                label = tk.Label(
                    self.stats_frame_ref,
                    text=label_text,
                    bg=self.DARK_BG,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8),
                    anchor="w"
                )
                label.grid(row=idx, column=0, sticky="w", pady=2)
                
                # Value (e.g., "88")
                value = tk.Label(
                    self.stats_frame_ref,
                    text=value_text,
                    bg=self.DARK_BG,
                    fg=self.ACCENT_COLOR,
                    font=("Segoe UI", 8, "bold"),
                    anchor="e"
                )
                value.grid(row=idx, column=1, sticky="ew", padx=(5, 0), pady=2)
                
                self.stats_items[label_text] = (label, value)
            except:
                pass  # Widget creation failed, skip this stat
    
    def _populate_mods_list(self) -> None:
        """Populate the mods list with click-to-select functionality (optimized with aligned columns)."""
        # Disable updates during population to prevent UI freezing
        try:
            self.mods_canvas.config(state="disabled")
        except:
            pass
        
        try:
            # Clear existing widgets - safer approach
            for widget in list(self.mods_frame.winfo_children()):  # Create list copy
                try:
                    widget.destroy()
                except:
                    pass  # Widget already destroyed, skip
            self.mod_widgets.clear()
            self.selected_mods.clear()
            if hasattr(self, 'check_indicators'):
                self.check_indicators.clear()
            
            # Column widths for alignment
            CHECKBOX_WIDTH = 2
            STATUS_WIDTH = 12
            VERSION_WIDTH = 15
            
            # Build all mod items
            mod_items = []
            for mod_name in sorted(self.mods.keys()):
                mod = self.mods[mod_name]
                
                # Determine status icon/color
                status_map = {
                    ModStatus.UP_TO_DATE: ("✓ Up to date", self.SUCCESS_COLOR),
                    ModStatus.OUTDATED: ("⬆️ Outdated", self.WARNING_COLOR),
                    ModStatus.UNKNOWN: ("❓ Unknown", self.SECONDARY_FG),
                    ModStatus.ERROR: ("✗ Error", self.ERROR_COLOR),
                }
                status_text, status_color = status_map.get(mod.status, ("❓ Unknown", self.SECONDARY_FG))
                
                # Create mod item frame
                item_frame = tk.Frame(self.mods_frame, bg=self.BG_COLOR, relief="solid", bd=1, cursor="hand2")
                self.mod_widgets[mod_name] = item_frame
                
                # Configure grid for columns
                item_frame.grid_columnconfigure(0, minsize=25)   # Checkbox
                item_frame.grid_columnconfigure(1, weight=1)     # Name (expandable)
                item_frame.grid_columnconfigure(2, minsize=95)   # Status
                item_frame.grid_columnconfigure(3, minsize=110)  # Version
                item_frame.grid_columnconfigure(4, minsize=150)  # Author
                
                # Create click handlers
                def create_row_click_handler(mod_n, frame):
                    def on_click(event):
                        ctrl_pressed = event.state & 0x4
                        if not ctrl_pressed and self.selected_mods:
                            self.selected_mods.clear()
                        
                        if mod_n in self.selected_mods:
                            self.selected_mods.discard(mod_n)
                        else:
                            self.selected_mods.add(mod_n)
                        
                        self._refresh_selection_display()
                    return on_click
                
                def create_checkbox_handler(mod_n):
                    def on_click(event):
                        if mod_n in self.selected_mods:
                            self.selected_mods.discard(mod_n)
                        else:
                            self.selected_mods.add(mod_n)
                        self._refresh_selection_display()
                    return on_click
                
                # Bind click handler to frame
                item_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Checkbox
                check_indicator = tk.Label(
                    item_frame,
                    text="☐",
                    bg=self.BG_COLOR,
                    fg=self.ACCENT_COLOR,
                    font=("Segoe UI", 10, "bold"),
                    width=2,
                    anchor="center"
                )
                check_indicator.grid(row=0, column=0, sticky="ns", padx=3)
                check_indicator.bind("<Button-1>", create_checkbox_handler(mod_name))
                if not hasattr(self, 'check_indicators'):
                    self.check_indicators = {}
                self.check_indicators[mod_name] = check_indicator
                
                # Mod name (title + internal name)
                name_text = f"{mod.title or mod.name}"
                if mod.name != (mod.title or mod.name):
                    name_text += f"\n({mod.name})"
                
                name_label = tk.Label(
                    item_frame,
                    text=name_text,
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 9, "bold"),
                    anchor="w",
                    justify="left"
                )
                name_label.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
                name_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Status
                status_label = tk.Label(
                    item_frame,
                    text=status_text,
                    bg=self.BG_COLOR,
                    fg=status_color,
                    font=("Segoe UI", 9),
                    anchor="center",
                    width=STATUS_WIDTH
                )
                status_label.grid(row=0, column=2, sticky="ew", padx=3, pady=3)
                status_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Version
                version_text = f"{mod.version} → {mod.latest_version or '?'}"
                version_label = tk.Label(
                    item_frame,
                    text=version_text,
                    bg=self.BG_COLOR,
                    fg=self.SECONDARY_FG,
                    font=("Segoe UI", 8),
                    anchor="center",
                    width=VERSION_WIDTH
                )
                version_label.grid(row=0, column=3, sticky="ew", padx=3, pady=3)
                version_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Author
                author_text = f"by {mod.author}" if mod.author else "Unknown"
                author_label = tk.Label(
                    item_frame,
                    text=author_text,
                    bg=self.BG_COLOR,
                    fg=self.SECONDARY_FG,
                    font=("Segoe UI", 8),
                    anchor="w"
                )
                author_label.grid(row=0, column=4, sticky="ew", padx=5, pady=3)
                author_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Downloads
                dl_text = f"{mod.downloads:,}" if mod.downloads else "0"
                dl_label = tk.Label(
                    item_frame,
                    text=dl_text,
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8),
                    anchor="center",
                    width=12
                )
                dl_label.grid(row=0, column=5, sticky="ew", padx=3, pady=3)
                dl_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                mod_items.append((item_frame, mod_name))
            
            # Render all items at once
            for idx, (item_frame, mod_name) in enumerate(mod_items):
                item_frame.pack(fill="x", pady=2)
                
        finally:
            # Re-enable canvas
            try:
                self.mods_canvas.config(state="normal")
            except:
                pass
            # Force UI update
            self.mods_frame.update_idletasks()
            # Bind scroll to all mod widgets
            self._bind_scroll_recursive(self.mods_frame)
            # Focus canvas to enable mousewheel scroll
            try:
                self.mods_canvas.focus_set()
            except:
                pass
            self._refresh_selection_display()
    

    
    def _refresh_selection_display(self) -> None:
        """Update visual display of selected mods."""
        if not hasattr(self, 'check_indicators'):
            return
        
        for mod_name, indicator in self.check_indicators.items():
            if mod_name in self.selected_mods:
                indicator.config(text="☑", fg=self.SUCCESS_COLOR)
                # Highlight selected row
                self.mod_widgets[mod_name].config(bg="#1a3a1a", relief="raised")
            else:
                indicator.config(text="☐", fg=self.ACCENT_COLOR)
                # Normal row
                self.mod_widgets[mod_name].config(bg=self.BG_COLOR, relief="solid")
        
        # Update button states based on selection
        if self.selected_mods:
            self.update_btn.config(state="normal")
            self.delete_btn.config(state="normal")
            self.backup_btn.config(state="normal")
            # View Details button only enabled when exactly one mod is selected
            if len(self.selected_mods) == 1:
                self.view_info_btn.config(state="normal")
            else:
                self.view_info_btn.config(state="disabled")
        else:
            self.update_btn.config(state="disabled")
            self.delete_btn.config(state="disabled")
            self.backup_btn.config(state="disabled")
            self.view_info_btn.config(state="disabled")
    
    def _on_mod_selected(self, mod_name: str) -> None:
        """Handle mod selection (deprecated, kept for compatibility)."""
        if mod_name in self.selected_mods:
            self.selected_mods.discard(mod_name)
        else:
            self.selected_mods.add(mod_name)
        self._refresh_selection_display()
    
    def _set_filter(self, filter_mode: str) -> None:
        """Set filter mode and update display."""
        self.filter_mode.set(filter_mode)
        self._filter_mods()
        # Scroll to top when filter changes
        self.mods_canvas.yview_moveto(0)
    
    def _filter_mods(self) -> None:
        """Filter and display mods based on search query and status filter."""
        query = self.search_entry.get_text().lower() if hasattr(self, 'search_entry') else ""
        filter_mode = self.filter_mode.get()
        sort_by = self.sort_var.get() if hasattr(self, 'sort_var') else "name"
        
        # Clear frame - use safer widget destruction
        try:
            for widget in list(self.mods_frame.winfo_children()):  # Create list copy to avoid iteration issues
                try:
                    widget.destroy()
                except:
                    pass  # Widget already destroyed, skip
        except:
            pass  # Frame was destroyed, skip cleanup
        
        self.mod_widgets.clear()
        if hasattr(self, 'check_indicators'):
            self.check_indicators.clear()
        
        # Scroll to top when filter changes
        try:
            self.mods_canvas.yview_moveto(0)
        except:
            pass  # Canvas was destroyed, skip
        
        # Get filtered and sorted mods from presenter
        filtered_mods = self.presenter.filter_mods(
            self.mods, query, filter_mode, self.selected_mods, sort_by
        )
        
        # Column widths for alignment (SAME AS _populate_mods_list)
        CHECKBOX_WIDTH = 2
        STATUS_WIDTH = 12
        VERSION_WIDTH = 15
        
        # Display filtered mods using GRID layout (SAME AS _populate_mods_list)
        if not filtered_mods:
            placeholder = tk.Label(
                self.mods_frame,
                text="No mods match the current filter",
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 10)
            )
            placeholder.pack(pady=20)
        else:
            # Render all filtered mods with grid layout
            for mod_name, mod in filtered_mods:
                status_text, status_color = self.presenter.get_status_text_and_color(mod.status)
                
                # Create item frame with grid layout
                item_frame = tk.Frame(self.mods_frame, bg=self.BG_COLOR, relief="solid", bd=1, cursor="hand2")
                item_frame.pack(fill="x", pady=2)
                item_frame.columnconfigure(1, weight=1)  # Make name column expandable
                
                self.mod_widgets[mod_name] = item_frame
                
                # Create click handlers
                def create_row_click_handler(mod_n, frame):
                    def on_click(event):
                        ctrl_pressed = event.state & 0x4
                        if not ctrl_pressed and self.selected_mods:
                            self.selected_mods.clear()
                        if mod_n in self.selected_mods:
                            self.selected_mods.discard(mod_n)
                        else:
                            self.selected_mods.add(mod_n)
                        self._refresh_selection_display()
                    return on_click
                
                def create_checkbox_handler(mod_n):
                    def on_click(event):
                        if mod_n in self.selected_mods:
                            self.selected_mods.discard(mod_n)
                        else:
                            self.selected_mods.add(mod_n)
                        self._refresh_selection_display()
                    return on_click
                
                # Checkbox
                check_indicator = tk.Label(
                    item_frame,
                    text="☐",
                    bg=self.BG_COLOR,
                    fg=self.ACCENT_COLOR,
                    font=("Segoe UI", 11, "bold"),
                    width=CHECKBOX_WIDTH
                )
                check_indicator.grid(row=0, column=0, sticky="w", padx=3, pady=3)
                check_indicator.bind("<Button-1>", create_checkbox_handler(mod_name))
                
                if not hasattr(self, 'check_indicators'):
                    self.check_indicators = {}
                self.check_indicators[mod_name] = check_indicator
                
                item_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Mod name
                name_text = f"{mod.title or mod.name} ({mod.name})"
                name_label = tk.Label(
                    item_frame,
                    text=name_text,
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 9, "bold"),
                    anchor="w",
                    justify="left"
                )
                name_label.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
                name_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Status
                status_label = tk.Label(
                    item_frame,
                    text=status_text,
                    bg=self.BG_COLOR,
                    fg=status_color,
                    font=("Segoe UI", 9),
                    anchor="center",
                    width=STATUS_WIDTH
                )
                status_label.grid(row=0, column=2, sticky="ew", padx=3, pady=3)
                status_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Version
                version_text = f"{mod.version} → {mod.latest_version or '?'}"
                version_label = tk.Label(
                    item_frame,
                    text=version_text,
                    bg=self.BG_COLOR,
                    fg=self.SECONDARY_FG,
                    font=("Segoe UI", 8),
                    anchor="center",
                    width=VERSION_WIDTH
                )
                version_label.grid(row=0, column=3, sticky="ew", padx=3, pady=3)
                version_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Author
                author_label = tk.Label(
                    item_frame,
                    text=mod.author,
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8),
                    anchor="w"
                )
                author_label.grid(row=0, column=4, sticky="ew", padx=3, pady=3)
                author_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                # Downloads
                dl_text = f"{mod.downloads:,}" if mod.downloads else "0"
                dl_label = tk.Label(
                    item_frame,
                    text=dl_text,
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8),
                    anchor="center",
                    width=12
                )
                dl_label.grid(row=0, column=5, sticky="ew", padx=3, pady=3)
                dl_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
        
        # Bind scroll to all widgets
        self._bind_scroll_recursive(self.mods_frame)
    

    
    def _on_tab_visible(self, event=None) -> None:
        """Called when tab becomes visible. Schedules auto-scan with delay."""
        # Only schedule if not already scheduled and no mods loaded
        if self.auto_scan_scheduled or self.mods or self.is_scanning:
            return
        
        # Cancel any existing timer first
        if self.auto_scan_timer:
            self.parent.after_cancel(self.auto_scan_timer)
        
        # Mark as scheduled and schedule auto-scan after 3 second delay
        self.auto_scan_scheduled = True
        self.auto_scan_timer = self.parent.after(3000, self._start_scan)

    def _start_scan(self) -> None:
        """Start scanning mods in background."""
        mods_folder = self.folder_var.get()
        
        if not mods_folder:
            self._notify("❌ Please select a mods folder", notification_type="error")
            return
        
        self.is_scanning = True
        self.scan_btn.config(state="disabled")
        self.check_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self.update_all_btn.config(state="disabled")
        
        thread = Thread(
            target=self._scan_thread,
            args=(mods_folder,),
            daemon=True
        )
        thread.start()
    
    def _scan_thread(self, mods_folder: str) -> None:
        """Background thread for scanning mods."""
        try:
            # Check network connectivity first
            is_online_status, _ = is_online()
            if not is_online_status:
                self._log_progress("[SCAN] ✗ Network error: You are offline", "error")
                self._update_status("Offline - Cannot scan", self.ERROR_COLOR)
                self.frame.after(500, lambda: self._notify(
                    "📡 You are offline. Mods cannot be scanned for updates without internet connection.",
                    notification_type="warning"
                ))
                return
            
            self._update_status("Scanning mods...", self.ACCENT_COLOR)
            self._log_progress("[SCAN] Starting mod scan...", "info")
            
            # Create checker and logic layer
            username = config.get("username")
            token = config.get("token")
            self.checker = ModChecker(mods_folder, username, token)
            self.checker.set_progress_callback(lambda msg: self._log_progress(msg, "normal"))
            self.logic = CheckerLogic(self.checker, self._log_progress)
            
            # Scan mods using logic layer
            self.mods = self.logic.scan_mods()
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            self._update_status(f"Ready - {len(self.mods)} mods", self.SUCCESS_COLOR)
            # Show notification instead of messagebox (schedule on main thread)
            self.frame.after(500, lambda: self._notify(
                f"✓ Scan complete! Found {len(self.mods)} mod(s) with latest information.",
                notification_type="success",
                duration_ms=5000
            ))
        
        except Exception as e:
            self._log_progress(f"[SCAN] ✗ Error: {e}", "error")
            self._update_status("Scan failed", self.ERROR_COLOR)
            error_msg = str(e)
            self.frame.after(500, lambda: self._notify(
                f"Scan failed: {error_msg}",
                notification_type="error",
                duration_ms=6000
            ))
        
        finally:
            self.is_scanning = False
            self.auto_scan_scheduled = False  # Reset flag so auto-scan can run again if tab becomes visible
            self.scan_btn.config(state="normal")
            self.check_btn.config(state="normal")
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
            self.delete_btn.config(state="normal")
    
    def _start_check(self) -> None:
        """Start checking for updates."""
        if not self.checker:
            self._notify("❌ Please scan mods first", notification_type="error")
            return
        
        self.check_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self.update_all_btn.config(state="disabled")
        
        thread = Thread(target=self._check_thread, daemon=True)
        thread.start()
    
    def _check_thread(self) -> None:
        """Background thread for checking updates."""
        try:
            self._update_status("Checking for updates...", self.ACCENT_COLOR)
            self._log_progress("[CHECK] Starting update check...", "info")
            
            if not self.logic:
                raise RuntimeError("Logic layer not initialized. Please scan mods first.")
            
            outdated, was_refreshed = self.logic.check_updates()
            self._populate_mods_list()
            self._update_stats()
            
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            if was_refreshed:
                self.frame.after(500, lambda: self._notify(f"✓ Check finished. {len(outdated)} update(s) available", notification_type="success", duration_ms=5000))
            else:
                self.frame.after(500, lambda: self._notify("✓ Data is fresh. No refresh needed.", notification_type="info", duration_ms=4000))
        
        except Exception as e:
            self._log_progress(f"[CHECK] ✗ Error: {e}", "error")
            self._update_status("Check failed", self.ERROR_COLOR)
            self.frame.after(500, lambda: self._notify(f"Check failed: {e}", notification_type="error", duration_ms=6000))
        
        finally:
            self.check_btn.config(state="normal")
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
    
    def _update_selected(self) -> None:
        """Update selected mods."""
        if not self.selected_mods:
            self._notify("Please select at least one mod", notification_type="warning")
            return
        
        self._do_update(list(self.selected_mods))
    
    def _update_all_outdated(self) -> None:
        """Update all outdated mods."""
        if not self.checker:
            return
        
        # Get all outdated mods
        outdated = [name for name, mod in self.mods.items() if mod.is_outdated]
        
        if not outdated:
            self._notify("ℹ️ No outdated mods found", notification_type="info")
            return
        
        self._do_update(outdated)
    
    def _do_update(self, mod_names: List[str]) -> None:
        """Execute update for given mods."""
        if not self.checker:
            return
        
        self.update_btn.config(state="disabled")
        self.update_all_btn.config(state="disabled")
        self.check_btn.config(state="disabled")
        
        thread = Thread(
            target=self._update_thread,
            args=(mod_names,),
            daemon=True
        )
        thread.start()
    
    def _update_thread(self, mod_names: List[str]) -> None:
        """Background thread for updating mods."""
        try:
            self._update_status("Updating mods...", self.ACCENT_COLOR)
            self._log_progress(f"[UPDATE] Starting update of {len(mod_names)} mod(s)...", "info")
            
            if not self.logic:
                raise RuntimeError("Logic layer not initialized. Please scan mods first.")
            
            successful, failed = self.logic.update_mods(mod_names)
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"✓ Updated {len(successful)} mod(s)"
            if failed:
                msg += f" ({len(failed)} failed)"
            
            self.frame.after(500, lambda: self._notify(msg, notification_type="success" if not failed else "warning", duration_ms=5000))
        
        except Exception as e:
            self._log_progress(f"[UPDATE] ✗ Error: {e}", "error")
            self._update_status("Update failed", self.ERROR_COLOR)
            self.frame.after(500, lambda: self._notify(f"Update failed: {e}", notification_type="error", duration_ms=6000))
        
        finally:
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
            self.check_btn.config(state="normal")
    def _delete_selected(self) -> None:
        """Delete selected mods."""
        if not self.selected_mods:
            self._notify("Please select at least one mod to delete", notification_type="warning")
            return
        
        selected_mods = list(self.selected_mods)
        
        # Show confirmation notification with action buttons
        mod_list = ", ".join(selected_mods[:3]) + (f" and {len(selected_mods)-3} more..." if len(selected_mods) > 3 else "")
        confirm_msg = f"Delete {len(selected_mods)} mod(s): {mod_list}? This cannot be undone!"
        
        # Define confirmation callback
        def on_confirm():
            self.delete_btn.config(state="disabled")
            thread = Thread(
                target=self._delete_thread,
                args=(selected_mods,),
                daemon=True
            )
            thread.start()
        
        # Show confirmation with action buttons
        self._notify(
            confirm_msg,
            notification_type="warning",
            duration_ms=0,  # Persistent - don't auto-dismiss
            actions=[("Delete", on_confirm), ("Cancel", lambda: None)]
        )
    
    def _delete_thread(self, mod_names: List[str]) -> None:
        """Background thread for deleting mods."""
        try:
            self._update_status("Deleting mods...", self.WARNING_COLOR)
            self._log_progress(f"[DELETE] Deleting {len(mod_names)} mod(s)...", "warning")
            
            if not self.logic:
                raise RuntimeError("Logic layer not initialized.")
            
            deleted, failed = self.logic.delete_mods(mod_names, self.folder_var.get())
            
            # Remove from mods dict (already done in logic, but sync UI)
            for name in deleted:
                self.mods.pop(name, None)
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"✓ Deleted {len(deleted)} mod(s)"
            if failed:
                msg += f" ({len(failed)} failed)"
            
            self.frame.after(500, lambda: self._notify(msg, notification_type="success" if not failed else "warning", duration_ms=5000))
        
        except Exception as e:
            self._log_progress(f"[DELETE] ✗ Error: {e}", "error")
            self._update_status("Delete failed", self.ERROR_COLOR)
            self.frame.after(500, lambda: self._notify(f"Delete failed: {e}", notification_type="error", duration_ms=6000))
        
        finally:
            self.delete_btn.config(state="normal")
    
    def _delete_all_backups(self) -> None:
        """Delete all backup folders."""
        mods_folder = Path(self.folder_var.get())
        
        if not mods_folder.exists():
            self._notify("Mods folder not found", notification_type="error")
            return
        
        # Check for the main backup folder inside mods
        backup_folder = mods_folder / "backup"
        
        if not backup_folder.exists():
            self._notify("ℹ️ No backup folder found", notification_type="info")
            return
        
        # Calculate backup folder size
        backup_size = sum(f.stat().st_size for f in backup_folder.rglob("*") if f.is_file())
        backup_size_mb = backup_size / (1024 * 1024)
        
        # Show confirmation with action buttons
        confirm_msg = f"Delete backup folder? ({backup_size_mb:.2f} MB) This cannot be undone!"
        
        def on_confirm():
            self.delete_backups_btn.config(state="disabled")
            thread = Thread(
                target=self._delete_backups_thread,
                args=(backup_folder,),
                daemon=True
            )
            thread.start()
        
        self._notify(
            confirm_msg,
            notification_type="warning",
            duration_ms=0,
            actions=[("Delete", on_confirm), ("Cancel", lambda: None)]
        )
    
    def _delete_backups_thread(self, backup_folder: Path) -> None:
        """Background thread for deleting backup folder."""
        try:
            self._update_status("Cleaning backups...", self.WARNING_COLOR)
            self._log_progress(f"[CLEANUP] Deleting backup folder...", "warning")
            
            if not self.logic:
                raise RuntimeError("Logic layer not initialized.")
            
            folder_size_mb = self.logic.clean_backups(str(backup_folder))
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"✓ Backup deleted - Freed {folder_size_mb:.2f} MB"
            self.frame.after(500, lambda: self._notify(msg, notification_type="success"))
        
        except Exception as e:
            self._log_progress(f"[CLEANUP] ✗ Error: {e}", "error")
            self._update_status("Cleanup failed", self.ERROR_COLOR)
            error_msg = f"❌ Cleanup failed: {e}"
            self.frame.after(500, lambda: self._notify(error_msg, notification_type="error"))
        
        finally:
            self.delete_backups_btn.config(state="normal")

    def _backup_selected(self) -> None:
        """Backup selected mods to the backup folder inside mods folder."""
        if not self.selected_mods:
            self._notify("⚠️ Please select at least one mod to backup", notification_type="warning")
            return
        
        # Create backup folder inside mods folder
        mods_folder = Path(self.folder_var.get())
        backup_folder = mods_folder / "backup"
        
        selected_mods = list(self.selected_mods)
        self.backup_btn.config(state="disabled")
        
        thread = Thread(
            target=self._backup_thread,
            args=(selected_mods, str(backup_folder)),
            daemon=True
        )
        thread.start()

    def _backup_thread(self, mod_names: List[str], backup_folder: str) -> None:
        """Background thread for backing up mods."""
        try:
            if not self.checker:
                raise RuntimeError("Checker not initialized. Please scan mods first.")
            
            self._update_status("Backing up mods...", self.ACCENT_COLOR)
            self._log_progress(f"[BACKUP] Backing up {len(mod_names)} mod(s) to {backup_folder}...", "info")
            
            backed_up = []
            failed = []
            
            for i, mod_name in enumerate(mod_names, 1):
                try:
                    if self.checker.backup_mod(mod_name, backup_folder):
                        backed_up.append(mod_name)
                    else:
                        failed.append(mod_name)
                except Exception as e:
                    self._log_progress(f"  [{i}/{len(mod_names)}] ✗ Error backing up {mod_name}: {e}", "error")
                    failed.append(mod_name)
            
            self._log_progress(f"[BACKUP] ✓ Complete! Backed up {len(backed_up)} mod(s)", "success")
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"✓ Backed up {len(backed_up)} mod(s)"
            if failed:
                msg += f" ({len(failed)} failed)"
            
            self.frame.after(500, lambda: self._notify(msg, notification_type="success"))
        
        except Exception as e:
            self._log_progress(f"[BACKUP] ✗ Error: {e}", "error")
            self._update_status("Backup failed", self.ERROR_COLOR)
            error_msg = f"❌ Backup failed: {e}"
            self.frame.after(500, lambda: self._notify(error_msg, notification_type="error"))
        
        finally:
            self.backup_btn.config(state="normal")
    
    def _show_mod_details(self) -> None:
        """Show detailed information about selected mod in a popup window."""
        if not self.selected_mods:
            self._notify("⚠️ Please select a mod to view details", notification_type="warning")
            return
        
        # Get the first selected mod
        mod_name = list(self.selected_mods)[0]
        if mod_name not in self.mods:
            self._notify("Mod not found", notification_type="error")
            return
        
        mod = self.mods[mod_name]
        
        # Create popup window
        popup = tk.Toplevel(self.frame.winfo_toplevel())
        popup.title(f"Mod Details - {mod.title or mod.name}")
        popup.configure(bg=self.DARK_BG)
        
        # Set larger size and center the window
        window_width = 1000
        window_height = 800
        
        # Update window to get screen dimensions
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set geometry with position
        popup.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Make it stay on top
        popup.attributes("-topmost", True)
        
        # Main scrollable frame
        main_frame = tk.Frame(popup, bg=self.DARK_BG)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(main_frame)
        scrollbar.pack(side="right", fill="y")
        
        canvas = tk.Canvas(
            main_frame,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=canvas.yview)
        
        # Content frame inside canvas
        content_frame = tk.Frame(canvas, bg=self.BG_COLOR)
        canvas.create_window((0, 0), window=content_frame, anchor="nw", tags="content")
        
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig("content", width=event.width)
        
        content_frame.bind("<Configure>", on_frame_configure)
        
        # Bind mousewheel to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", on_mousewheel)
        content_frame.bind("<MouseWheel>", on_mousewheel)
        popup.bind("<MouseWheel>", on_mousewheel)
        
        # Title section
        title_label = tk.Label(
            content_frame,
            text=mod.title or mod.name,
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            font=("Segoe UI", 14, "bold"),
            wraplength=650,
            justify="left"
        )
        title_label.pack(anchor="w", pady=(0, 5))
        
        # Mod name (internal)
        if mod.name != (mod.title or mod.name):
            name_label = tk.Label(
                content_frame,
                text=f"Internal: {mod.name}",
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 9)
            )
            name_label.pack(anchor="w", pady=(0, 10))
        
        # Info section
        info_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        info_frame.pack(anchor="w", fill="x", pady=(0, 10))
        
        info_items = [
            ("Author:", mod.author or "Unknown"),
            ("Current Version:", mod.version or "Unknown"),
            ("Latest Version:", mod.latest_version or mod.version or "Unknown"),
            ("Status:", "Up to Date" if mod.status == ModStatus.UP_TO_DATE else "Outdated" if mod.status == ModStatus.OUTDATED else "Unknown"),
            ("Downloads:", f"{mod.downloads:,}" if mod.downloads else "0"),
            ("URL:", mod.url or "N/A"),
        ]
        
        for label, value in info_items:
            item_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
            item_frame.pack(fill="x", pady=2)
            
            label_widget = tk.Label(
                item_frame,
                text=label,
                bg=self.BG_COLOR,
                fg=self.FG_COLOR,
                font=("Segoe UI", 9, "bold"),
                width=15,
                anchor="w"
            )
            label_widget.pack(side="left", padx=(0, 10))
            
            value_widget = tk.Label(
                item_frame,
                text=value,
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 9),
                wraplength=550,
                justify="left",
                anchor="w"
            )
            value_widget.pack(side="left", fill="x", expand=True)
        
        # Separator
        tk.Frame(content_frame, bg=self.ACCENT_COLOR, height=1).pack(fill="x", pady=10)
        
        # Description section
        desc_header = tk.Label(
            content_frame,
            text="📝 Description",
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            font=("Segoe UI", 11, "bold")
        )
        desc_header.pack(anchor="w", pady=(0, 5))
        
        if mod.description:
            desc_label = tk.Label(
                content_frame,
                text=mod.description,
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 9),
                wraplength=650,
                justify="left",
                anchor="nw"
            )
            desc_label.pack(anchor="w", fill="x", pady=(0, 10))
        else:
            no_desc = tk.Label(
                content_frame,
                text="No description available",
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 9, "italic")
            )
            no_desc.pack(anchor="w", pady=(0, 10))
        
        # Changelog section - fetch from portal
        tk.Frame(content_frame, bg=self.ACCENT_COLOR, height=1).pack(fill="x", pady=10)
        
        changelog_header = tk.Label(
            content_frame,
            text="📋 Changelog",
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            font=("Segoe UI", 11, "bold")
        )
        changelog_header.pack(anchor="w", pady=(0, 5))
        
        # Show loading message while fetching
        loading_label = tk.Label(
            content_frame,
            text="Loading changelog...",
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 9, "italic")
        )
        loading_label.pack(anchor="w", pady=(0, 10))
        
        # Fetch changelog in background thread
        def fetch_changelog_thread():
            try:
                from ..core.portal import FactorioPortalAPI
                portal = FactorioPortalAPI()
                changelog_data = portal.get_mod_changelog(mod.name)
                
                # Clear loading label
                loading_label.pack_forget()
                
                if changelog_data:
                    # Show last 5 versions
                    versions = sorted(changelog_data.keys(), key=lambda v: [int(x) for x in v.split('.')], reverse=True)[:5]
                    for version in versions:
                        version_label = tk.Label(
                            content_frame,
                            text=f"Version {version}",
                            bg=self.BG_COLOR,
                            fg=self.ACCENT_COLOR,
                            font=("Segoe UI", 10, "bold")
                        )
                        version_label.pack(anchor="w", pady=(5, 2))
                        
                        changelog_text = changelog_data[version]
                        changelog_label = tk.Label(
                            content_frame,
                            text=changelog_text if changelog_text else "No changelog provided",
                            bg=self.BG_COLOR,
                            fg=self.SECONDARY_FG,
                            font=("Segoe UI", 9),
                            wraplength=630,
                            justify="left",
                            anchor="nw"
                        )
                        changelog_label.pack(anchor="w", fill="x", padx=(10, 0), pady=(0, 5))
                else:
                    no_changelog = tk.Label(
                        content_frame,
                        text="No changelog available",
                        bg=self.BG_COLOR,
                        fg=self.SECONDARY_FG,
                        font=("Segoe UI", 9, "italic")
                    )
                    no_changelog.pack(anchor="w", pady=(0, 10))
            except Exception as e:
                loading_label.config(text=f"Error loading changelog: {e}")
        
        thread = Thread(target=fetch_changelog_thread, daemon=True)
        thread.start()

