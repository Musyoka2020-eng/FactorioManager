"""Checker tab UI."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from typing import Dict, List, Optional
from threading import Thread
from pathlib import Path
from ..core import ModChecker, Mod, ModStatus
from ..utils import config, format_file_size


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

    def __init__(self, parent: ttk.Notebook):
        """
        Initialize checker tab.
        
        Args:
            parent: Parent notebook widget
        """
        self.frame = ttk.Frame(parent, style="Dark.TFrame")
        self.parent = parent
        self.checker: Optional[ModChecker] = None
        self.mods: Dict[str, Mod] = {}
        self.selected_mods: set = set()  # Track selected mods for checkboxes
        self.is_scanning = False
        self.filter_var = tk.StringVar()
        self.filter_mode = tk.StringVar(value="all")  # Filter: all, outdated, up_to_date, selected
        self.mod_widgets: Dict[str, tk.Frame] = {}  # Map mod names to frame widgets
        self.auto_scan_timer = None  # Timer for auto-scan with delay
        
        # Bind to tab visibility to trigger auto-scan
        self.frame.bind("<Visibility>", self._on_tab_visible)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the UI components."""
        # === CONTROL PANEL ===
        control_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Header
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        header = tk.Label(
            control_frame,
            text="⚙️  Settings",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Mods folder selection
        folder_label = tk.Label(
            control_frame,
            text="📁 Mods Folder:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10)
        )
        folder_label.pack(anchor="w", padx=15, pady=(5, 0))
        
        folder_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        folder_frame.pack(fill="x", padx=15, pady=(5, 0))
        
        self.folder_var = tk.StringVar(value=config.get("mods_folder", ""))
        self.folder_display = tk.Label(
            folder_frame,
            textvariable=self.folder_var,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 9),
            wraplength=400,
            justify="left"
        )
        self.folder_display.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        
        browse_btn = tk.Button(
            folder_frame,
            text="Browse",
            command=self._browse_folder,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            relief="flat",
            padx=15,
            font=("Segoe UI", 9, "bold")
        )
        browse_btn.pack(side="right", padx=5)
        
        # Operation status indicator
        status_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        status_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            bg=self.DARK_BG,
            fg=self.SUCCESS_COLOR,
            font=("Segoe UI", 9)
        )
        self.status_label.pack(anchor="w")
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg=self.DARK_BG)
        button_frame.pack(fill="x", padx=15, pady=(10, 10))
        
        self.scan_btn = tk.Button(
            button_frame,
            text="🔍 Scan Mods",
            command=self._start_scan,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold")
        )
        self.scan_btn.pack(side="left", padx=5)
        
        self.check_btn = tk.Button(
            button_frame,
            text="⬆️  Check Updates",
            command=self._start_check,
            bg=self.WARNING_COLOR,
            fg="#000000",
            activebackground="#ffbb22",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold"),
            state="disabled"
        )
        self.check_btn.pack(side="left", padx=5)
        
        self.update_btn = tk.Button(
            button_frame,
            text="📥 Update Selected",
            command=self._update_selected,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold"),
            state="disabled"
        )
        self.update_btn.pack(side="left", padx=5)
        
        self.delete_btn = tk.Button(
            button_frame,
            text="🗑️  Delete Selected",
            command=self._delete_selected,
            bg=self.ERROR_COLOR,
            fg="#ffffff",
            activebackground="#c41c1c",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold"),
            state="disabled"
        )
        self.delete_btn.pack(side="left", padx=5)
        
        self.update_all_btn = tk.Button(
            button_frame,
            text="📥 Update All",
            command=self._update_all_outdated,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold"),
            state="disabled"
        )
        self.update_all_btn.pack(side="left", padx=5)
        
        self.delete_backups_btn = tk.Button(
            button_frame,
            text="🧹 Clean Backups",
            command=self._delete_all_backups,
            bg="#8b5a00",
            fg="#ffffff",
            activebackground="#a66d00",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold")
        )
        self.delete_backups_btn.pack(side="left", padx=5)
        
        self.backup_btn = tk.Button(
            button_frame,
            text="💾 Backup Selected",
            command=self._backup_selected,
            bg="#6b5b95",
            fg="#ffffff",
            activebackground="#7b6ba5",
            relief="flat",
            padx=15,
            font=("Segoe UI", 10, "bold"),
            state="disabled"
        )
        self.backup_btn.pack(side="left", padx=5)
        
        # === STATISTICS SECTION ===
        stats_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        stats_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        stats_header = tk.Label(
            stats_frame,
            text="📊 Statistics",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        stats_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.stats_label = tk.Label(
            stats_frame,
            text="No data - Scan mods to get started",
            bg=self.DARK_BG,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 9),
            wraplength=800,
            justify="left"
        )
        self.stats_label.pack(anchor="w", padx=15, pady=(0, 10))
        
        # === SEARCH/FILTER SECTION ===
        search_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        search_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        search_label = tk.Label(
            search_frame,
            text="🔎 Search & Filter:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10)
        )
        search_label.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Search entry
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.filter_var,
            bg=self.BG_COLOR,
            fg=self.FG_COLOR,
            insertbackground=self.FG_COLOR,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10)
        )
        self.search_entry.pack(fill="x", padx=15, pady=(0, 10))
        self.filter_var.trace("w", lambda *args: self._filter_mods())
        
        # Filter buttons
        filter_btn_frame = tk.Frame(search_frame, bg=self.DARK_BG)
        filter_btn_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        tk.Label(
            filter_btn_frame,
            text="Status Filter:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 10))
        
        filter_buttons = [
            ("All", "all"),
            ("Outdated", "outdated"),
            ("Up to Date", "up_to_date"),
            ("Selected", "selected")
        ]
        
        for label, value in filter_buttons:
            btn = tk.Button(
                filter_btn_frame,
                text=label,
                command=lambda v=value: self._set_filter(v),
                bg=self.ACCENT_COLOR,
                fg="#ffffff",
                activebackground="#1084d7",
                relief="flat",
                padx=10,
                font=("Segoe UI", 8)
            )
            btn.pack(side="left", padx=3)
            # Store reference for later highlighting
            if not hasattr(self, 'filter_buttons'):
                self.filter_buttons = {}
            self.filter_buttons[value] = btn
        
        # Sort options
        sort_frame = tk.Frame(search_frame, bg=self.DARK_BG)
        sort_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        tk.Label(
            sort_frame,
            text="Sort By:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 10))
        
        self.sort_var = tk.StringVar(value="name")
        sort_options = [
            ("Name", "name"),
            ("Version", "version"),
            ("Downloads", "downloads"),
            ("Date Added", "date")
        ]
        
        for label, value in sort_options:
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
            ).pack(side="left", padx=5)
        
        # === MODS LIST SECTION ===
        list_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        list_header = tk.Label(
            list_frame,
            text="📦 Installed Mods",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        list_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Canvas with scrollbar for mod list with checkboxes
        list_container = tk.Frame(list_frame, bg=self.DARK_BG)
        list_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        v_scroll = tk.Scrollbar(list_container)
        v_scroll.pack(side="right", fill="y")
        
        self.mods_canvas = tk.Canvas(
            list_container,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=v_scroll.set
        )
        self.mods_canvas.pack(side="left", fill="both", expand=True)
        v_scroll.config(command=self.mods_canvas.yview)
        
        # Frame inside canvas to hold mod items
        self.mods_frame = tk.Frame(self.mods_canvas, bg=self.BG_COLOR)
        self.mods_canvas.create_window((0, 0), window=self.mods_frame, anchor="nw")
        
        def on_frame_configure(event):
            self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))
        
        self.mods_frame.bind("<Configure>", on_frame_configure)
        
        # Bind mouse wheel for scrolling
        def on_mousewheel(event):
            # Windows uses MouseWheel event
            self.mods_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.mods_canvas.bind("<MouseWheel>", on_mousewheel)
        self.mods_frame.bind("<MouseWheel>", on_mousewheel)
        
        # Also bind to frame children for better scroll propagation
        def bind_scroll_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                bind_scroll_recursive(child)
        
        self.mods_frame.bind("<Configure>", lambda e: bind_scroll_recursive(self.mods_frame) or on_frame_configure(e))
        
        # === PROGRESS LOG SECTION ===
        log_frame = tk.Frame(self.frame, bg=self.DARK_BG, relief="flat", bd=1)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        log_header = tk.Label(
            log_frame,
            text="📝 Operation Log",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        log_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Text widget with scrollbar for progress log
        log_container = tk.Frame(log_frame, bg=self.DARK_BG)
        log_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        log_scroll = tk.Scrollbar(log_container)
        log_scroll.pack(side="right", fill="y")
        
        self.progress_log = tk.Text(
            log_container,
            height=6,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            yscrollcommand=log_scroll.set,
            font=("Consolas", 9),
            relief="flat",
            wrap="word"
        )
        log_scroll.config(command=self.progress_log.yview)
        self.progress_log.pack(fill="both", expand=True)
        
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
        print(message)
        
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
            print(f"  (UI update failed: {e})")
    
    def _update_status(self, message: str, color: Optional[str] = None) -> None:
        """Update the status label."""
        try:
            if self.status_label.winfo_exists():
                self.status_label.config(text=message, fg=color or self.SECONDARY_FG)
                self.status_label.update()
        except:
            pass  # Widget was destroyed, ignore
    
    def _bind_scroll_recursive(self, widget) -> None:
        """Recursively bind mouse wheel scroll to widget and all children."""
        def on_mousewheel(event):
            self.mods_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        widget.bind("<MouseWheel>", on_mousewheel)
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)
    
    def _update_stats(self) -> None:
        """Update statistics display."""
        if not self.checker:
            return
        
        stats = self.checker.get_statistics()
        stats_text = (
            f"Total: {stats['total']} mods  •  "
            f"✓ Up to date: {stats['up_to_date']}  •  "
            f"⬆️  Outdated: {stats['outdated']}  •  "
            f"❓ Unknown: {stats['unknown']}  •  "
            f"✗ Errors: {stats['errors']}"
        )
        self.stats_label.config(text=stats_text)
    
    def _populate_mods_list(self) -> None:
        """Populate the mods list with click-to-select functionality."""
        # Clear existing widgets
        for widget in self.mods_frame.winfo_children():
            widget.destroy()
        self.mod_widgets.clear()
        self.selected_mods.clear()
        
        # Add mods with click selection
        for mod_name in sorted(self.mods.keys()):
            mod = self.mods[mod_name]
            
            # Determine status icon/color
            status_map = {
                ModStatus.UP_TO_DATE: ("✓ Up to date", self.SUCCESS_COLOR),
                ModStatus.OUTDATED: ("⬆️  Outdated", self.WARNING_COLOR),
                ModStatus.UNKNOWN: ("❓ Unknown", self.SECONDARY_FG),
                ModStatus.ERROR: ("✗ Error", self.ERROR_COLOR),
            }
            status_text, status_color = status_map.get(mod.status, ("❓ Unknown", self.SECONDARY_FG))
            
            # Create mod item frame (entire row is clickable)
            item_frame = tk.Frame(self.mods_frame, bg=self.BG_COLOR, relief="solid", bd=1, cursor="hand2")
            item_frame.pack(fill="x", pady=2)
            
            # Store widget reference for selection
            self.mod_widgets[mod_name] = item_frame
            
            # Handler for row clicks (Ctrl behavior applies)
            def create_row_click_handler(mod_n, frame):
                def on_click(event):
                    ctrl_pressed = event.state & 0x4  # Check Ctrl key
                    if not ctrl_pressed and self.selected_mods:
                        # No Ctrl, deselect others
                        self.selected_mods.clear()
                    
                    # Toggle current selection
                    if mod_n in self.selected_mods:
                        self.selected_mods.discard(mod_n)
                    else:
                        self.selected_mods.add(mod_n)
                    
                    # Refresh display to show selection
                    self._refresh_selection_display()
                
                return on_click
            
            # Handler for checkbox clicks (no Ctrl needed, just toggle)
            def create_checkbox_handler(mod_n):
                def on_click(event):
                    # Simply toggle without deselecting others
                    if mod_n in self.selected_mods:
                        self.selected_mods.discard(mod_n)
                    else:
                        self.selected_mods.add(mod_n)
                    
                    # Refresh display to show selection
                    self._refresh_selection_display()
                
                return on_click
            
            # Bind row click to frame
            item_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Info frame
            info_frame = tk.Frame(item_frame, bg=self.BG_COLOR)
            info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            info_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Checkbox indicator (shows selection status)
            check_indicator = tk.Label(
                info_frame,
                text="☐",  # Empty checkbox
                bg=self.BG_COLOR,
                fg=self.ACCENT_COLOR,
                font=("Segoe UI", 11, "bold"),
                width=2
            )
            check_indicator.pack(side="left", padx=(0, 10))
            # Checkbox has independent toggle behavior (no Ctrl needed)
            check_indicator.bind("<Button-1>", create_checkbox_handler(mod_name))
            # Store reference for updating
            if not hasattr(self, 'check_indicators'):
                self.check_indicators = {}
            self.check_indicators[mod_name] = check_indicator
            
            # Mod name and info
            name_text = f"{mod.title or mod.name} ({mod.name})"
            name_label = tk.Label(
                info_frame,
                text=name_text,
                bg=self.BG_COLOR,
                fg=self.FG_COLOR,
                font=("Segoe UI", 9, "bold"),
                anchor="w"
            )
            name_label.pack(side="left", fill="x", expand=True)
            name_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Status
            status_label = tk.Label(
                info_frame,
                text=status_text,
                bg=self.BG_COLOR,
                fg=status_color,
                font=("Segoe UI", 9),
                width=15,
                anchor="center"
            )
            status_label.pack(side="left", padx=5)
            status_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Version info
            version_text = f"{mod.version} → {mod.latest_version or '?'}"
            version_label = tk.Label(
                info_frame,
                text=version_text,
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 8),
                width=20,
                anchor="center"
            )
            version_label.pack(side="left", padx=5)
            version_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Author label and value
            author_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
            author_frame.pack(side="left", padx=5)
            author_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            tk.Label(
                author_frame,
                text="Author:",
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 8)
            ).pack(side="left", padx=(0, 3))
            
            author_label = tk.Label(
                author_frame,
                text=mod.author,
                bg=self.BG_COLOR,
                fg=self.FG_COLOR,
                font=("Segoe UI", 8)
            )
            author_label.pack(side="left")
            author_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Downloads label and value
            if mod.downloads:
                dl_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
                dl_frame.pack(side="left", padx=5)
                dl_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                tk.Label(
                    dl_frame,
                    text="Downloads:",
                    bg=self.BG_COLOR,
                    fg=self.SECONDARY_FG,
                    font=("Segoe UI", 8)
                ).pack(side="left", padx=(0, 3))
                
                dl_label = tk.Label(
                    dl_frame,
                    text=f"{mod.downloads:,}",
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8)
                )
                dl_label.pack(side="left")
                dl_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
        
        # Bind scroll to all widgets after creating
        self._bind_scroll_recursive(self.mods_frame)
    
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
        else:
            self.update_btn.config(state="disabled")
            self.delete_btn.config(state="disabled")
            self.backup_btn.config(state="disabled")
    
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
        query = self.filter_var.get().lower()
        filter_mode = self.filter_mode.get()
        sort_by = self.sort_var.get() if hasattr(self, 'sort_var') else "name"
        
        # Clear frame
        for widget in self.mods_frame.winfo_children():
            widget.destroy()
        self.mod_widgets.clear()
        if hasattr(self, 'check_indicators'):
            self.check_indicators.clear()
        
        # Scroll to top when filter changes
        self.mods_canvas.yview_moveto(0)
        
        # Get filtered mods list
        filtered_mods = []
        for mod_name in self.mods.keys():
            mod = self.mods[mod_name]
            
            # Text search filter
            if query and not (query in mod.name.lower() or 
                            query in (mod.title or "").lower() or
                            query in mod.author.lower()):
                continue
            
            # Status filter
            if filter_mode == "outdated" and mod.status != ModStatus.OUTDATED:
                continue
            elif filter_mode == "up_to_date" and mod.status != ModStatus.UP_TO_DATE:
                continue
            elif filter_mode == "selected" and mod_name not in self.selected_mods:
                continue
            
            filtered_mods.append((mod_name, mod))
        
        # Sort mods
        if sort_by == "name":
            filtered_mods.sort(key=lambda x: x[0].lower())
        elif sort_by == "version":
            filtered_mods.sort(key=lambda x: x[1].version, reverse=True)
        elif sort_by == "downloads":
            filtered_mods.sort(key=lambda x: x[1].downloads or 0, reverse=True)
        elif sort_by == "date":
            filtered_mods.sort(key=lambda x: x[1].release_date or datetime.min, reverse=True)
        
        # Display sorted and filtered mods
        for mod_name, mod in filtered_mods:
            
            # Text search filter
            if query and not (query in mod.name.lower() or 
                            query in (mod.title or "").lower() or
                            query in mod.author.lower()):
                continue
            
            # Status filter
            if filter_mode == "outdated" and mod.status != ModStatus.OUTDATED:
                continue
            elif filter_mode == "up_to_date" and mod.status != ModStatus.UP_TO_DATE:
                continue
            elif filter_mode == "selected" and mod_name not in self.selected_mods:
                continue
            
            # Determine status icon/color
            status_map = {
                ModStatus.UP_TO_DATE: ("✓ Up to date", self.SUCCESS_COLOR),
                ModStatus.OUTDATED: ("⬆️  Outdated", self.WARNING_COLOR),
                ModStatus.UNKNOWN: ("❓ Unknown", self.SECONDARY_FG),
                ModStatus.ERROR: ("✗ Error", self.ERROR_COLOR),
            }
            status_text, status_color = status_map.get(mod.status, ("❓ Unknown", self.SECONDARY_FG))
            
            # Create mod item frame (entire row is clickable)
            item_frame = tk.Frame(self.mods_frame, bg=self.BG_COLOR, relief="solid", bd=1, cursor="hand2")
            item_frame.pack(fill="x", pady=2)
            
            # Store widget reference for selection
            self.mod_widgets[mod_name] = item_frame
            
            # Handler for row clicks (Ctrl behavior applies)
            def create_row_click_handler(mod_n, frame):
                def on_click(event):
                    ctrl_pressed = event.state & 0x4  # Check Ctrl key
                    if not ctrl_pressed and self.selected_mods:
                        # No Ctrl, deselect others
                        self.selected_mods.clear()
                    
                    # Toggle current selection
                    if mod_n in self.selected_mods:
                        self.selected_mods.discard(mod_n)
                    else:
                        self.selected_mods.add(mod_n)
                    
                    # Refresh display to show selection
                    self._refresh_selection_display()
                
                return on_click
            
            # Handler for checkbox clicks (no Ctrl needed, just toggle)
            def create_checkbox_handler(mod_n):
                def on_click(event):
                    # Simply toggle without deselecting others
                    if mod_n in self.selected_mods:
                        self.selected_mods.discard(mod_n)
                    else:
                        self.selected_mods.add(mod_n)
                    
                    # Refresh display to show selection
                    self._refresh_selection_display()
                
                return on_click
            
            item_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Info frame
            info_frame = tk.Frame(item_frame, bg=self.BG_COLOR)
            info_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            info_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Checkbox indicator (shows selection status)
            check_indicator = tk.Label(
                info_frame,
                text="☑" if mod_name in self.selected_mods else "☐",
                bg=self.BG_COLOR,
                fg=self.SUCCESS_COLOR if mod_name in self.selected_mods else self.ACCENT_COLOR,
                font=("Segoe UI", 11, "bold"),
                width=2
            )
            check_indicator.pack(side="left", padx=(0, 10))
            # Checkbox has independent toggle behavior (no Ctrl needed)
            check_indicator.bind("<Button-1>", create_checkbox_handler(mod_name))
            # Store reference for updating
            if not hasattr(self, 'check_indicators'):
                self.check_indicators = {}
            self.check_indicators[mod_name] = check_indicator
            
            # Mod name and info
            name_text = f"{mod.title or mod.name} ({mod.name})"
            name_label = tk.Label(
                info_frame,
                text=name_text,
                bg=self.BG_COLOR,
                fg=self.FG_COLOR,
                font=("Segoe UI", 9, "bold"),
                anchor="w"
            )
            name_label.pack(side="left", fill="x", expand=True)
            name_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Status
            status_label = tk.Label(
                info_frame,
                text=status_text,
                bg=self.BG_COLOR,
                fg=status_color,
                font=("Segoe UI", 9),
                width=15,
                anchor="center"
            )
            status_label.pack(side="left", padx=5)
            status_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Version info
            version_text = f"{mod.version} → {mod.latest_version or '?'}"
            version_label = tk.Label(
                info_frame,
                text=version_text,
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 8),
                width=20,
                anchor="center"
            )
            version_label.pack(side="left", padx=5)
            version_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Author label and value
            author_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
            author_frame.pack(side="left", padx=5)
            author_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            tk.Label(
                author_frame,
                text="Author:",
                bg=self.BG_COLOR,
                fg=self.SECONDARY_FG,
                font=("Segoe UI", 8)
            ).pack(side="left", padx=(0, 3))
            
            author_label = tk.Label(
                author_frame,
                text=mod.author,
                bg=self.BG_COLOR,
                fg=self.FG_COLOR,
                font=("Segoe UI", 8)
            )
            author_label.pack(side="left")
            author_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
            
            # Downloads label and value
            if mod.downloads:
                dl_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
                dl_frame.pack(side="left", padx=5)
                dl_frame.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
                
                tk.Label(
                    dl_frame,
                    text="Downloads:",
                    bg=self.BG_COLOR,
                    fg=self.SECONDARY_FG,
                    font=("Segoe UI", 8)
                ).pack(side="left", padx=(0, 3))
                
                dl_label = tk.Label(
                    dl_frame,
                    text=f"{mod.downloads:,}",
                    bg=self.BG_COLOR,
                    fg=self.FG_COLOR,
                    font=("Segoe UI", 8)
                )
                dl_label.pack(side="left")
                dl_label.bind("<Button-1>", create_row_click_handler(mod_name, item_frame))
        
        # Bind scroll to all widgets after creating
        self._bind_scroll_recursive(self.mods_frame)
    
    def _on_tab_visible(self, event=None) -> None:
        """Called when tab becomes visible. Schedules auto-scan with delay."""
        # Cancel any existing auto-scan timer
        if self.auto_scan_timer:
            self.parent.after_cancel(self.auto_scan_timer)
        
        # Schedule auto-scan after 5 second delay to avoid rapid re-scans
        if not self.is_scanning and not self.mods:
            self.auto_scan_timer = self.parent.after(5000, self._start_scan)

    def _start_scan(self) -> None:
        """Start scanning mods in background."""
        mods_folder = self.folder_var.get()
        
        if not mods_folder:
            messagebox.showerror("Error", "Please select a mods folder")
            return
        
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
            self._update_status("Scanning mods...", self.ACCENT_COLOR)
            self.progress_log.config(state="normal")
            self.progress_log.delete("1.0", "end")
            self.progress_log.config(state="normal")
            
            self._log_progress("[SCAN] Starting mod scan...", "info")
            
            # Create checker
            username = config.get("username")
            token = config.get("token")
            
            self.checker = ModChecker(mods_folder, username, token)
            self.checker.set_progress_callback(lambda msg: self._log_progress(msg, "normal"))
            
            # Scan mods (this now also fetches portal data)
            self.mods = self.checker.scan_mods()
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            self._log_progress(f"[SCAN] ✓ Complete! Found {len(self.mods)} mod(s)", "success")
            self._update_status(f"Ready - {len(self.mods)} mods", self.SUCCESS_COLOR)
            
            messagebox.showinfo("Scan Complete", f"Found {len(self.mods)} mod(s)\n\nStatus, versions, and download counts are now available!")
        
        except Exception as e:
            self._log_progress(f"[SCAN] ✗ Error: {e}", "error")
            self._update_status("Scan failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Scan failed: {e}")
        
        finally:
            self.scan_btn.config(state="normal")
            self.check_btn.config(state="normal")
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
            self.delete_btn.config(state="normal")
    
    def _start_check(self) -> None:
        """Start checking for updates."""
        if not self.checker:
            messagebox.showerror("Error", "Please scan mods first")
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
            
            if not self.checker:
                raise RuntimeError("Checker not initialized. Please scan mods first.")
            
            self.checker.check_updates()
            self._populate_mods_list()
            self._update_stats()
            
            self._log_progress("[CHECK] ✓ Update check complete!", "success")
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            messagebox.showinfo("Check Complete", "Update check finished")
        
        except Exception as e:
            self._log_progress(f"[CHECK] ✗ Error: {e}", "error")
            self._update_status("Check failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Check failed: {e}")
        
        finally:
            self.check_btn.config(state="normal")
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
    
    def _update_selected(self) -> None:
        """Update selected mods."""
        if not self.selected_mods:
            messagebox.showwarning("Warning", "Please select at least one mod")
            return
        
        self._do_update(list(self.selected_mods))
    
    def _update_all_outdated(self) -> None:
        """Update all outdated mods."""
        if not self.checker:
            return
        
        # Get all outdated mods
        outdated = [name for name, mod in self.mods.items() if mod.is_outdated]
        
        if not outdated:
            messagebox.showinfo("Info", "No outdated mods found")
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
            
            if not self.checker:
                raise RuntimeError("Checker not initialized. Please scan mods first.")
            
            successful, failed = self.checker.update_mods(mod_names)
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            success_msg = f"[UPDATE] ✓ Updated {len(successful)} mod(s)"
            self._log_progress(success_msg, "success")
            
            if failed:
                fail_msg = f"[UPDATE] ✗ Failed: {', '.join(failed)}"
                self._log_progress(fail_msg, "error")
            
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"Updated {len(successful)} mod(s)"
            if failed:
                msg += f"\nFailed: {', '.join(failed)}"
            
            messagebox.showinfo("Update Complete", msg)
        
        except Exception as e:
            self._log_progress(f"[UPDATE] ✗ Error: {e}", "error")
            self._update_status("Update failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Update failed: {e}")
        
        finally:
            self.update_btn.config(state="normal")
            self.update_all_btn.config(state="normal")
            self.check_btn.config(state="normal")
    def _delete_selected(self) -> None:
        """Delete selected mods."""
        if not self.selected_mods:
            messagebox.showwarning("Warning", "Please select at least one mod to delete")
            return
        
        selected_mods = list(self.selected_mods)
        
        # Confirm deletion
        mod_list = "\n".join([f"  • {name}" for name in selected_mods])
        response = messagebox.askyesno(
            "Confirm Deletion",
            f"Delete these {len(selected_mods)} mod(s)?\n\n{mod_list}\n\nThis cannot be undone!"
        )
        
        if not response:
            return
        
        self.delete_btn.config(state="disabled")
        thread = Thread(
            target=self._delete_thread,
            args=(selected_mods,),
            daemon=True
        )
        thread.start()
    
    def _delete_thread(self, mod_names: List[str]) -> None:
        """Background thread for deleting mods."""
        try:
            self._update_status("Deleting mods...", self.WARNING_COLOR)
            self._log_progress(f"[DELETE] Deleting {len(mod_names)} mod(s)...", "warning")
            
            deleted = []
            failed = []
            
            for i, mod_name in enumerate(mod_names, 1):
                try:
                    if mod_name not in self.mods:
                        failed.append(f"{mod_name} (not found)")
                        continue
                    
                    mod = self.mods[mod_name]
                    mod_file = Path(self.folder_var.get()) / f"{mod.name}_{mod.version}.zip"
                    
                    if mod_file.exists():
                        mod_file.unlink()
                        deleted.append(mod_name)
                        self._log_progress(f"  [{i}/{len(mod_names)}] ✓ Deleted {mod_name}", "success")
                    else:
                        failed.append(f"{mod_name} (file not found)")
                        self._log_progress(f"  [{i}/{len(mod_names)}] ✗ File not found: {mod_name}", "error")
                
                except Exception as e:
                    failed.append(f"{mod_name} ({str(e)})")
                    self._log_progress(f"  [{i}/{len(mod_names)}] ✗ Error: {mod_name} - {e}", "error")
            
            # Remove from mods dict
            for name in deleted:
                del self.mods[name]
            
            # Update UI
            self._populate_mods_list()
            self._update_stats()
            
            self._log_progress(f"[DELETE] ✓ Complete! Deleted {len(deleted)} mod(s)", "success")
            if failed:
                self._log_progress(f"[DELETE] ✗ Failed: {len(failed)} mod(s)", "error")
            
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"Deleted {len(deleted)} mod(s)"
            if failed:
                msg += f"\n\nFailed ({len(failed)}):\n" + "\n".join([f"  • {f}" for f in failed])
            
            messagebox.showinfo("Delete Complete", msg)
        
        except Exception as e:
            self._log_progress(f"[DELETE] ✗ Error: {e}", "error")
            self._update_status("Delete failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Delete failed: {e}")
        
        finally:
            self.delete_btn.config(state="normal")
    
    def _delete_all_backups(self) -> None:
        """Delete all backup folders."""
        mods_folder = Path(self.folder_var.get())
        
        if not mods_folder.exists():
            messagebox.showerror("Error", "Mods folder not found")
            return
        
        # Check for the main backup folder inside mods
        backup_folder = mods_folder / "backup"
        
        if not backup_folder.exists():
            messagebox.showinfo("Info", "No backup folder found")
            return
        
        # Calculate backup folder size
        backup_size = sum(f.stat().st_size for f in backup_folder.rglob("*") if f.is_file())
        backup_size_mb = backup_size / (1024 * 1024)
        
        # Confirm deletion
        response = messagebox.askyesno(
            "Confirm Deletion",
            f"Delete backup folder?\n\nSize: {backup_size_mb:.2f} MB\n\nThis will free up disk space.\n\nThis cannot be undone!"
        )
        
        if not response:
            return
        
        self.delete_backups_btn.config(state="disabled")
        thread = Thread(
            target=self._delete_backups_thread,
            args=(backup_folder,),
            daemon=True
        )
        thread.start()
    
    def _delete_backups_thread(self, backup_folder: Path) -> None:
        """Background thread for deleting backup folder."""
        try:
            self._update_status("Cleaning backups...", self.WARNING_COLOR)
            self._log_progress(f"[CLEANUP] Deleting backup folder...", "warning")
            
            # Calculate folder size before deletion
            folder_size = sum(f.stat().st_size for f in backup_folder.rglob("*") if f.is_file())
            folder_size_mb = folder_size / (1024 * 1024)
            
            # Delete folder and contents
            import shutil
            shutil.rmtree(backup_folder)
            
            self._log_progress(f"[CLEANUP] ✓ Complete! Deleted backup folder, freed {folder_size_mb:.2f} MB", "success")
            self._update_status("Ready", self.SUCCESS_COLOR)
            
            msg = f"Deleted backup folder\nFreed {folder_size_mb:.2f} MB"
            messagebox.showinfo("Cleanup Complete", msg)
        
        except Exception as e:
            self._log_progress(f"[CLEANUP] ✗ Error: {e}", "error")
            self._update_status("Cleanup failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Cleanup failed: {e}")
        
        finally:
            self.delete_backups_btn.config(state="normal")

    def _backup_selected(self) -> None:
        """Backup selected mods to the backup folder inside mods folder."""
        if not self.selected_mods:
            messagebox.showwarning("Warning", "Please select at least one mod to backup")
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
            
            msg = f"Backed up {len(backed_up)} mod(s) to:\n{backup_folder}"
            if failed:
                msg += f"\n\nFailed ({len(failed)}):\n" + "\n".join([f"  • {m}" for m in failed])
            
            messagebox.showinfo("Backup Complete", msg)
        
        except Exception as e:
            self._log_progress(f"[BACKUP] ✗ Error: {e}", "error")
            self._update_status("Backup failed", self.ERROR_COLOR)
            messagebox.showerror("Error", f"Backup failed: {e}")
        
        finally:
            self.backup_btn.config(state="normal")