"""Downloader tab UI."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from typing import Optional, Dict, Any
from threading import Thread
import time
from ..core import ModDownloader
from ..core.portal import FactorioPortalAPI
from ..utils import config, validate_mod_url, format_file_size


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

    def __init__(self, parent: ttk.Notebook):
        """
        Initialize downloader tab.
        
        Args:
            parent: Parent notebook widget
        """
        self.frame = ttk.Frame(parent, style="Dark.TFrame")
        self.parent = parent
        self.downloader: Optional[ModDownloader] = None
        self.portal = FactorioPortalAPI()
        self.is_downloading = False
        self.last_search_time = 0
        self.search_timer = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the UI components."""
        # Create main scrollable area
        main_scroll = ttk.Scrollbar(self.frame)
        main_scroll.pack(side="right", fill="y")
        
        canvas = tk.Canvas(
            self.frame,
            bg=self.BG_COLOR,
            highlightthickness=0,
            yscrollcommand=main_scroll.set
        )
        canvas.pack(side="left", fill="both", expand=True)
        main_scroll.config(command=canvas.yview)
        
        # Create frame inside canvas
        content_frame = tk.Frame(canvas, bg=self.BG_COLOR)
        canvas.create_window((0, 0), window=content_frame, anchor="nw", tags="content_frame")
        
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make canvas window width match canvas width
            canvas.itemconfig("content_frame", width=event.width)
        
        canvas.bind("<Configure>", on_configure)
        
        # Store canvas and content_frame for later binding
        self._scroll_canvas = canvas
        self._scroll_content_frame = content_frame
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            try:
                # Check if canvas still exists
                if self._scroll_canvas.winfo_exists():
                    self._scroll_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass  # Widget was destroyed, ignore
            return "break"
        
        def _on_mousewheel_linux(event):
            try:
                if self._scroll_canvas.winfo_exists():
                    if event.num == 4:
                        self._scroll_canvas.yview_scroll(-3, "units")
                    elif event.num == 5:
                        self._scroll_canvas.yview_scroll(3, "units")
            except:
                pass  # Widget was destroyed, ignore
            return "break"
        
        self._mousewheel_handler = _on_mousewheel
        self._mousewheel_handler_linux = _on_mousewheel_linux
        
        # Bind to canvas
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", _on_mousewheel_linux)
        canvas.bind("<Button-5>", _on_mousewheel_linux)
        
        # === INPUT SECTION ===
        input_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        input_frame.pack(fill="x", padx=10, pady=10)
        
        # Header
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        header = tk.Label(
            input_frame,
            text="📥 Download Mod",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Mod URL with icon
        url_label_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        url_label_frame.pack(anchor="w", padx=15, pady=(5, 0))
        
        url_label = tk.Label(
            url_label_frame,
            text="🔗 Mod URL:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10)
        )
        url_label.pack(anchor="w")
        
        self.url_entry = tk.Entry(
            input_frame,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            insertbackground=self.FG_COLOR,
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10)
        )
        self.url_entry.pack(fill="x", padx=15, pady=(5, 10))
        self.url_entry.insert(0, "https://mods.factorio.com/mod/")
        
        # Bind URL changes to trigger search
        self.url_entry.bind("<KeyRelease>", lambda e: self._schedule_search())
        
        # Mods folder
        folder_label_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        folder_label_frame.pack(anchor="w", padx=15, pady=(5, 0))
        
        folder_label = tk.Label(
            folder_label_frame,
            text="📁 Mods Folder:",
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            font=("Segoe UI", 10)
        )
        folder_label.pack(anchor="w")
        
        folder_frame = tk.Frame(input_frame, bg=self.DARK_BG)
        folder_frame.pack(fill="x", padx=15, pady=(5, 0))
        
        self.folder_var = tk.StringVar(value=config.get("mods_folder", ""))
        self.folder_label = tk.Label(
            folder_frame,
            textvariable=self.folder_var,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            font=("Segoe UI", 9),
            wraplength=400,
            justify="left"
        )
        self.folder_label.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        
        browse_btn = tk.Button(
            folder_frame,
            text="Browse",
            command=self._browse_folder,
            bg=self.ACCENT_COLOR,
            fg="#ffffff",
            activebackground="#1084d7",
            activeforeground="#ffffff",
            relief="flat",
            padx=15,
            font=("Segoe UI", 9, "bold")
        )
        browse_btn.pack(side="right", padx=5)
        
        # === MOD INFO SECTION ===
        info_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        info_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        info_header = tk.Label(
            info_frame,
            text="ℹ️  Mod Information",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        info_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Info display area with scrollbar
        info_scroll_frame = tk.Frame(info_frame, bg=self.DARK_BG)
        info_scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        info_scrollbar = tk.Scrollbar(info_scroll_frame)
        info_scrollbar.pack(side="right", fill="y")
        
        self.mod_info_text = tk.Text(
            info_scroll_frame,
            height=8,
            bg=self.BG_COLOR,
            fg=self.SECONDARY_FG,
            yscrollcommand=info_scrollbar.set,
            font=("Segoe UI", 9),
            relief="flat",
            state="disabled",
            wrap="word"
        )
        info_scrollbar.config(command=self.mod_info_text.yview)
        self.mod_info_text.pack(fill="both", expand=True)
        
        # Configure text tags for colors
        self.mod_info_text.tag_configure("title", font=("Segoe UI", 11, "bold"), foreground=self.ACCENT_COLOR)
        self.mod_info_text.tag_configure("label", font=("Segoe UI", 9, "bold"), foreground=self.FG_COLOR)
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
        
        options_header = tk.Label(
            options_frame,
            text="⚙️  Options",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        options_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.include_optional_var = tk.BooleanVar(
            value=config.get("download_optional", False)
        )
        
        checkbox = tk.Checkbutton(
            options_frame,
            text="Include optional dependencies (⚠️  may increase download size)",
            variable=self.include_optional_var,
            bg=self.DARK_BG,
            fg=self.FG_COLOR,
            activebackground=self.DARK_BG,
            activeforeground=self.ACCENT_COLOR,
            selectcolor=self.DARK_BG,
            font=("Segoe UI", 9)
        )
        checkbox.pack(anchor="w", padx=15, pady=(5, 10))
        
        # === ACTION BUTTONS ===
        button_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.download_btn = tk.Button(
            button_frame,
            text="⬇️  Download",
            command=self._start_download,
            bg=self.SUCCESS_COLOR,
            fg="#000000",
            activebackground="#5cd65f",
            activeforeground="#000000",
            relief="flat",
            padx=20,
            pady=10,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2"
        )
        self.download_btn.pack(side="left", padx=5)
        
        # === PROGRESS SECTION ===
        progress_frame = tk.Frame(content_frame, bg=self.DARK_BG, relief="flat", bd=1)
        progress_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        progress_header = tk.Label(
            progress_frame,
            text="📊 Download Progress",
            font=header_font,
            bg=self.DARK_BG,
            fg=self.FG_COLOR
        )
        progress_header.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=15, pady=(5, 0))
        
        # Progress text area with scrollbar
        scroll_frame = tk.Frame(progress_frame, bg=self.DARK_BG)
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        
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
            font=("Consolas", 9)
        )
        self.progress_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.progress_text.yview)
        
        # Configure text tags for colors
        self.progress_text.tag_config("success", foreground=self.SUCCESS_COLOR)
        self.progress_text.tag_config("error", foreground=self.ERROR_COLOR)
        self.progress_text.tag_config("info", foreground=self.ACCENT_COLOR)
        self.progress_text.tag_config("warning", foreground="#ffad00")
        
        # Bind mouse wheel to all child widgets
        self._bind_mousewheel_to_children(self._scroll_content_frame)
    def _bind_mousewheel_to_children(self, widget):
        """Recursively bind mouse wheel events to all child widgets (except scrollable ones)."""
        try:
            # Don't bind to Text widgets - they have their own scrolling
            if isinstance(widget, tk.Text):
                return
            
            # Bind to current widget
            widget.bind("<MouseWheel>", self._mousewheel_handler)
            widget.bind("<Button-4>", self._mousewheel_handler_linux)
            widget.bind("<Button-5>", self._mousewheel_handler_linux)
            
            # Recursively bind to all children
            for child in widget.winfo_children():
                self._bind_mousewheel_to_children(child)
        except:
            # Widget was destroyed or no longer valid, silently ignore
            pass

    def _browse_folder(self) -> None:
        """Browse for mods folder."""
        folder = filedialog.askdirectory(
            title="Select Factorio Mods Folder",
            initialdir=self.folder_var.get() or config.get("mods_folder", "")
        )
        if folder:
            self.folder_var.set(folder)
            config.set("mods_folder", folder)
    
    def _log_progress(self, message: str, tag: str = "") -> None:
        """Log progress message to text widget."""
        self.progress_text.insert("end", message + "\n", tag)
        self.progress_text.see("end")
        self.progress_text.update_idletasks()
    
    def _start_download(self) -> None:
        """Start downloading mods in background thread."""
        url = self.url_entry.get().strip()
        mods_folder = self.folder_var.get()
        
        # Validate input
        if not url or url == "https://mods.factorio.com/mod/":
            messagebox.showerror("Error", "Please enter a mod URL")
            return
        
        if not validate_mod_url(url):
            messagebox.showerror(
                "Error",
                "Invalid URL. Please use: https://mods.factorio.com/mod/ModName"
            )
            return
        
        if not mods_folder:
            messagebox.showerror("Error", "Please select a mods folder")
            return
        
        # Extract mod name from URL (remove query parameters)
        mod_name = url.split("/mod/")[-1].strip("/")
        mod_name = mod_name.split("?")[0]  # Remove query parameters like ?from=search
        
        # Disable button and start download
        self.download_btn.config(state="disabled")
        self.is_downloading = True
        
        # Clear progress
        self.progress_text.delete("1.0", "end")
        self.progress_var.set(0)
        self._log_progress(f"Starting download for {mod_name}...\n", "info")
        
        # Start download in background thread
        thread = Thread(
            target=self._download_thread,
            args=(mod_name, mods_folder),
            daemon=True
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
            self.downloader.set_progress_callback(lambda msg: self._log_progress(msg, "info"))
            
            self._log_progress("Resolving dependencies...", "info")
            
            # Download mod
            include_optional = self.include_optional_var.get()
            downloaded, failed = self.downloader.download_mods(
                [mod_name],
                include_optional=include_optional
            )
            
            # Show results
            if downloaded:
                msg = f"\n✓ Successfully downloaded {len(downloaded)} mod(s)"
                self._log_progress(msg, "success")
                messagebox.showinfo("Download Complete", msg.strip())
            
            if failed:
                msg = f"\n✗ Failed to download: {', '.join(failed)}"
                self._log_progress(msg, "error")
        
        except Exception as e:
            msg = f"\n✗ Error: {e}"
            self._log_progress(msg, "error")
            messagebox.showerror("Error", f"Download failed: {e}")
        
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
            mod_name = mod_name.split("?")[0]  # Remove query parameters like ?from=search
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
            # Fetch mod info from portal
            mod_data = self.portal.get_mod(mod_name)
            self._display_mod_info(mod_data, mod_name)
        except Exception as e:
            self._display_mod_info(None, f"Error searching for mod: {e}")
    
    def _display_mod_info(self, mod_data: Optional[Dict[str, Any]], mod_name: str) -> None:
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
                self.mod_info_text.insert("end", f"{version} (Released: {released})\n", "value")
            
            # Homepage
            homepage = mod_data.get("homepage", None)
            if homepage:
                self.mod_info_text.insert("end", "Homepage: ", "label")
                self.mod_info_text.insert("end", f"{homepage}\n", "value")
            
            # GitHub
            github = mod_data.get("github_path", None)
            if github:
                self.mod_info_text.insert("end", "GitHub: ", "label")
                self.mod_info_text.insert("end", f"https://github.com/{github}\n", "value")
            
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
                        elif dep.startswith("(?)")  or dep.startswith("?"):
                            # Optional
                            dep_name = dep.replace("(?)", "").replace("?", "").strip()
                            # Extract just mod name (before constraints)
                            dep_name = dep_name.split()[0] if " " in dep_name else dep_name.split(">")[0].split("=")[0].split("<")[0].split("!")[0].strip()
                            if dep_name:
                                optional.append(dep_name)
                        else:
                            # Required
                            dep_name = dep.split()[0] if " " in dep else dep.split(">")[0].split("=")[0].split("<")[0].strip()
                            if dep_name and dep_name != "base":
                                # Check if it's an expansion
                                if dep_name in EXPANSIONS:
                                    expansions.append(dep_name)
                                else:
                                    required.append(dep_name)
                    
                    if required:
                        self.mod_info_text.insert("end", "  🔗 Required: ", "label")
                        self.mod_info_text.insert("end", ", ".join(required) + "\n", "value")
                    
                    if optional:
                        self.mod_info_text.insert("end", "  ❓ Optional: ", "label")
                        self.mod_info_text.insert("end", ", ".join(optional) + "\n", "warning")
                    
                    if incompatible:
                        self.mod_info_text.insert("end", "  ❌ Incompatible: ", "label")
                        self.mod_info_text.insert("end", ", ".join(incompatible) + "\n", "error")
                    
                    if expansions:
                        self.mod_info_text.insert("end", "  💿 Requires DLC: ", "label")
                        self.mod_info_text.insert("end", ", ".join(expansions) + "\n", "error")
                else:
                    self.mod_info_text.insert("end", "✓ No dependencies\n", "success")
            
        except Exception as e:
            self.mod_info_text.insert("end", f"Error displaying mod info: {e}", "error")
        
        finally:
            self.mod_info_text.config(state="disabled")