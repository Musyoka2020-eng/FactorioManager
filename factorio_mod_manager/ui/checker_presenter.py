"""Data presentation and filtering for checker tab - separated from UI logic."""
from typing import Dict, List
from ..core import Mod, ModStatus


class CheckerPresenter:
    """Handles data filtering, sorting, and formatting for display."""
    
    # Status colors mapping
    STATUS_COLORS = {
        ModStatus.UP_TO_DATE: ("✓ Up to date", "#4ec952"),
        ModStatus.OUTDATED: ("⬆️ Outdated", "#ffad00"),
        ModStatus.UNKNOWN: ("❓ Unknown", "#b0b0b0"),
        ModStatus.ERROR: ("✗ Error", "#d13438"),
    }
    
    @staticmethod
    def get_status_text_and_color(status: ModStatus) -> tuple[str, str]:
        """Get display text and color for a mod status."""
        return CheckerPresenter.STATUS_COLORS.get(status, ("❓ Unknown", "#b0b0b0"))
    
    @staticmethod
    def filter_mods(
        mods: Dict[str, Mod],
        search_query: str,
        filter_mode: str,
        selected_mods: set,
        sort_by: str
    ) -> List[tuple[str, Mod]]:
        """
        Filter and sort mods based on criteria.
        
        Args:
            mods: Dictionary of all mods
            search_query: Text search (mod name, title, author)
            filter_mode: "all", "outdated", "up_to_date", or "selected"
            selected_mods: Set of selected mod names
            sort_by: "name", "version", "downloads", or "date"
        
        Returns:
            List of (mod_name, mod) tuples, filtered and sorted
        """
        query = search_query.lower()
        filtered = []
        
        for mod_name, mod in mods.items():
            # Text search filter
            if query and not (
                query in mod.name.lower() 
                or query in (mod.title or "").lower() 
                or query in mod.author.lower()
            ):
                continue
            
            # Status filter
            if filter_mode == "outdated" and mod.status != ModStatus.OUTDATED:
                continue
            elif filter_mode == "up_to_date" and mod.status != ModStatus.UP_TO_DATE:
                continue
            elif filter_mode == "selected" and mod_name not in selected_mods:
                continue
            
            filtered.append((mod_name, mod))
        
        # Sort mods
        if sort_by == "name":
            filtered.sort(key=lambda x: x[0].lower())
        elif sort_by == "version":
            filtered.sort(key=lambda x: x[1].version, reverse=True)
        elif sort_by == "downloads":
            filtered.sort(key=lambda x: x[1].downloads or 0, reverse=True)
        elif sort_by == "date":
            from datetime import datetime
            filtered.sort(key=lambda x: x[1].release_date or datetime.min, reverse=True)
        
        return filtered
    
    @staticmethod
    def get_statistics(mods: Dict[str, Mod]) -> Dict[str, int]:
        """Get statistics about installed mods."""
        return {
            "total": len(mods),
            "up_to_date": sum(1 for m in mods.values() if m.status == ModStatus.UP_TO_DATE),
            "outdated": sum(1 for m in mods.values() if m.status == ModStatus.OUTDATED),
            "unknown": sum(1 for m in mods.values() if m.status == ModStatus.UNKNOWN),
            "errors": sum(1 for m in mods.values() if m.status == ModStatus.ERROR),
        }
    
    @staticmethod
    def format_statistics(stats: Dict[str, int]) -> str:
        """Format statistics dictionary into display string (single line)."""
        return (
            f"Total: {stats['total']} mods  •  "
            f"✓ Up to date: {stats['up_to_date']}  •  "
            f"⬆️ Outdated: {stats['outdated']}  •  "
            f"❓ Unknown: {stats['unknown']}  •  "
            f"✗ Errors: {stats['errors']}"
        )
    
    @staticmethod
    def format_statistics_multiline(stats: Dict[str, int]) -> List[tuple[str, str]]:
        """Format statistics for display with each stat on its own line.
        
        Returns:
            List of (label, value) tuples for better layout
        """
        return [
            ("Total", f"{stats['total']} mods"),
            ("✓ Up to date", f"{stats['up_to_date']}"),
            ("⬆️ Outdated", f"{stats['outdated']}"),
            ("❓ Unknown", f"{stats['unknown']}"),
            ("✗ Errors", f"{stats['errors']}"),
        ]
