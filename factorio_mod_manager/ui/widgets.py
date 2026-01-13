"""Custom UI widgets."""
import tkinter as tk


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
