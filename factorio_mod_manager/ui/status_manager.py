"""Thread-safe status manager for concurrent tab operations."""
from queue import Queue, Empty
from typing import Callable, Optional
import threading


class StatusManager:
    """Manages status updates from multiple tabs via a queue."""
    
    def __init__(self, update_callback: Callable[[str, str], None]):
        """
        Initialize status manager.
        
        Args:
            update_callback: Callback function(message, status_type) called to update status
        """
        self.status_queue: Queue = Queue()
        self.update_callback = update_callback
        self.running = False
        self.processor_thread = None
    
    def push_status(self, message: str, status_type: str = "info") -> None:
        """
        Push a status update to the queue (thread-safe).
        
        Args:
            message: Status message
            status_type: Type (info, success, error, working)
        """
        self.status_queue.put((message, status_type))
    
    def start(self, root) -> None:
        """Start processing status queue updates."""
        if self.running:
            return
        
        self.running = True
        
        def process_queue():
            while self.running:
                try:
                    message, status_type = self.status_queue.get(timeout=0.1)
                    # Use after_idle to ensure update on main thread
                    root.after_idle(lambda m=message, s=status_type: self.update_callback(m, s))
                except Empty:
                    continue
                except:
                    pass
        
        self.processor_thread = threading.Thread(target=process_queue, daemon=True)
        self.processor_thread.start()
    
    def stop(self) -> None:
        """Stop processing status queue."""
        self.running = False
