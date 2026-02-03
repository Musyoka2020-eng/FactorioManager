"""Custom UI widgets."""
import tkinter as tk
from typing import Optional, Callable


class Notification(tk.Frame):
    """Toast-style notification widget with auto-dismiss and optional action buttons."""
    
    # Color scheme for notification types
    NOTIFICATION_COLORS = {
        "success": {"bg": "#2d5016", "fg": "#4ec952", "icon": "✓"},
        "error": {"bg": "#3a0f0f", "fg": "#d13438", "icon": "✗"},
        "warning": {"bg": "#3a2f1a", "fg": "#ffad00", "icon": "⚠"},
        "info": {"bg": "#1a2a3a", "fg": "#0078d4", "icon": "ℹ"},
    }
    
    def __init__(
        self,
        master,
        message: str,
        notification_type: str = "info",
        duration_ms: int = 4000,
        on_dismiss: Optional[Callable] = None,
        actions: Optional[list] = None,
        **kwargs
    ):
        """
        Initialize notification widget.
        
        Args:
            master: Parent widget
            message: Notification message
            notification_type: Type - "success", "error", "warning", or "info"
            duration_ms: Duration to show notification before auto-dismiss
            on_dismiss: Callback function when notification is dismissed
            actions: List of tuples (label, callback) for action buttons
        """
        super().__init__(master, **kwargs)
        
        self.message = message
        self.notification_type = notification_type
        self.duration_ms = duration_ms
        self.on_dismiss = on_dismiss
        self.dismiss_timer = None
        self.actions = actions or []
        
        # Get colors for notification type
        colors = self.NOTIFICATION_COLORS.get(notification_type, self.NOTIFICATION_COLORS["info"])
        self.config(bg=colors["bg"], relief="flat", bd=1, highlightthickness=1, highlightbackground=colors["fg"])
        
        # Create content frame
        content_frame = tk.Frame(self, bg=colors["bg"])
        content_frame.pack(fill="both", expand=True, padx=12, pady=10)
        
        # Main horizontal layout: icon+message on left, buttons on right
        left_frame = tk.Frame(content_frame, bg=colors["bg"])
        left_frame.pack(side="left", fill="both", expand=True)
        
        # Icon
        icon_label = tk.Label(
            left_frame,
            text=colors["icon"],
            font=("Segoe UI", 14, "bold"),
            bg=colors["bg"],
            fg=colors["fg"]
        )
        icon_label.pack(side="left", padx=(0, 10))
        
        # Message text
        text_label = tk.Label(
            left_frame,
            text=message,
            font=("Segoe UI", 10),
            bg=colors["bg"],
            fg="#e0e0e0",
            wraplength=350,
            justify="left"
        )
        text_label.pack(side="left", fill="both", expand=True)
        
        # Right frame for buttons
        buttons_frame = tk.Frame(content_frame, bg=colors["bg"])
        buttons_frame.pack(side="right", padx=(12, 0), fill="y")
        
        # Add action buttons if provided
        if self.actions:
            for label, callback in self.actions:
                btn = tk.Button(
                    buttons_frame,
                    text=label,
                    command=lambda cb=callback: self._action_click(cb),
                    bg="#0078d4",
                    fg="#ffffff",
                    activebackground="#1084d7",
                    activeforeground="#ffffff",
                    relief="flat",
                    padx=14,
                    pady=5,
                    font=("Segoe UI", 10, "bold"),
                    cursor="hand2",
                    bd=0,
                    highlightthickness=0,
                    width=10,
                    anchor="center"
                )
                btn.pack(side="left", padx=3)
        
        # Close button (X)
        close_btn = tk.Label(
            buttons_frame,
            text="✕",
            font=("Segoe UI", 12, "bold"),
            bg=colors["bg"],
            fg=colors["fg"],
            cursor="hand2",
            padx=6,
            pady=2
        )
        close_btn.pack(side="left", padx=(6, 0))
        close_btn.bind("<Button-1>", lambda e: self.dismiss())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ffffff"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=colors["fg"]))
        
        # Schedule auto-dismiss only if no actions (persistent if has actions)
        if duration_ms > 0 and not self.actions:
            self.dismiss_timer = self.after(duration_ms, self.dismiss)
    
    def _action_click(self, callback: Callable) -> None:
        """Handle action button click."""
        # Call the action callback
        callback()
        # Auto-dismiss after action
        self.dismiss()
    
    def dismiss(self) -> None:
        """Dismiss the notification."""
        if self.dismiss_timer:
            self.after_cancel(self.dismiss_timer)
        
        if self.on_dismiss:
            self.on_dismiss()
        
        self.destroy()


class NotificationManager:
    """Manages notifications in a container."""
    
    def __init__(self, root_window, max_notifications: int = 5):
        """
        Initialize notification manager.
        
        Args:
            root_window: Root Tkinter window
            max_notifications: Maximum notifications to show at once
        """
        self.root = root_window
        self.max_notifications = max_notifications
        self.notifications = []
        self.container = None
    
    def _ensure_container(self) -> None:
        """Create notification container if it doesn't exist."""
        if self.container is None:
            self.container = tk.Frame(self.root, bg="#0e0e0e")
            # Center horizontally, positioned below header with wider width for buttons
            self.container.place(relx=0.5, y=70, anchor="n", width=700)
            self.container.lift()  # Bring to front
            self.root.update_idletasks()
    
    def _cleanup_container(self) -> None:
        """Remove container if no notifications left."""
        if self.container and len(self.notifications) == 0 and self.container.winfo_exists():
            self.container.place_forget()
            self.container = None
    
    def show(
        self,
        message: str,
        notification_type: str = "info",
        duration_ms: int = 4000,
        actions: Optional[list] = None
    ) -> Notification:
        """
        Show a notification.
        
        Args:
            message: Notification message
            notification_type: Type - "success", "error", "warning", or "info"
            duration_ms: Duration to show (0 = persistent)
            actions: List of tuples (label, callback) for action buttons
            
        Returns:
            Notification widget instance
        """
        self._ensure_container()
        
        # Remove old notifications if at max
        if len(self.notifications) >= self.max_notifications:
            old_notif = self.notifications.pop(0)
            if old_notif.winfo_exists():
                old_notif.destroy()
        
        def on_dismiss():
            if notification in self.notifications:
                self.notifications.remove(notification)
            # Cleanup container if empty
            self._cleanup_container()
        
        notification = Notification(
            self.container,
            message,
            notification_type=notification_type,
            duration_ms=duration_ms,
            on_dismiss=on_dismiss,
            actions=actions
        )
        notification.pack(fill="x", pady=4)
        self.notifications.append(notification)
        
        # Update display
        self.root.update_idletasks()
        
        return notification


class PlaceholderEntry(tk.Entry):
    """Entry widget with placeholder text support."""
    
    def __init__(self, master, placeholder="", placeholder_color="#888888", *args, **kwargs):
        """Initialize with placeholder support.
        
        Args:
            master: Parent widget
            placeholder: Placeholder text to display
            placeholder_color: Color for placeholder text
        """
        super().__init__(master, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = placeholder_color
        self.default_color = self["fg"]
        
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        
        # Show placeholder on init
        self._show_placeholder()
    
    def _show_placeholder(self):
        """Show placeholder text."""
        if not self.get():
            self.insert(0, self.placeholder)
            self.config(fg=self.placeholder_color)
    
    def _on_focus_in(self, event):
        """Remove placeholder on focus."""
        if self.get() == self.placeholder:
            self.delete(0, "end")
            self.config(fg=self.default_color)
    
    def _on_focus_out(self, event):
        """Show placeholder if empty on focus out."""
        if not self.get():
            self._show_placeholder()
    
    def get_text(self):
        """Get actual text without placeholder."""
        text = self.get()
        return "" if text == self.placeholder else text
