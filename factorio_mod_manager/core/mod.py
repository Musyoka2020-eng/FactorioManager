"""Mod data model."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class ModStatus(Enum):
    """Mod status enumeration."""
    UP_TO_DATE = "up_to_date"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"
    ERROR = "error"


# Factorio expansions that are paid DLC or official features, not downloadable mods
# These are features/content that must be installed separately and cannot be auto-downloaded
# - space-age: Official paid DLC expansion
# - elevated-rails: Official feature (not available on mod portal, requires base game 2.0+)
FACTORIO_EXPANSIONS = {
    "space-age",
    "elevated-rails",
}


@dataclass
class Mod:
    """Represents a Factorio mod."""
    
    name: str
    title: str
    version: str
    author: str
    description: str = ""
    factorio_version: str = ""
    dependencies: List[str] = field(default_factory=list)  # mod_name >= version
    optional_dependencies: List[str] = field(default_factory=list)  # (?) mod_name
    incompatible_dependencies: List[str] = field(default_factory=list)  # ! mod_name
    expansion_dependencies: List[str] = field(default_factory=list)  # Paid DLC expansions
    url: str = ""
    file_path: Optional[str] = None
    latest_version: Optional[str] = None
    release_date: Optional[datetime] = None
    downloads: int = 0
    file_size: int = 0
    homepage: str = ""
    status: ModStatus = ModStatus.UNKNOWN
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post initialization."""
        if not self.url and self.name:
            self.url = f"https://mods.factorio.com/mod/{self.name}"

    @property
    def is_outdated(self) -> bool:
        """Check if mod is outdated."""
        return self.status == ModStatus.OUTDATED

    @property
    def needs_update(self) -> bool:
        """Check if mod needs update."""
        if not self.latest_version or not self.version:
            return False
        return self._compare_versions(self.version, self.latest_version) < 0

    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if v1 < v2
            0 if v1 == v2
            1 if v1 > v2
        """
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            for i in range(max(len(v1_parts), len(v2_parts))):
                p1 = v1_parts[i] if i < len(v1_parts) else 0
                p2 = v2_parts[i] if i < len(v2_parts) else 0
                
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            return 0
        except (ValueError, AttributeError):
            return 0

    def update_status(self) -> None:
        """Update mod status based on version comparison."""
        if self.needs_update:
            self.status = ModStatus.OUTDATED
        else:
            self.status = ModStatus.UP_TO_DATE

    def __repr__(self) -> str:
        """String representation."""
        return f"Mod({self.name}@{self.version})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "factorio_version": self.factorio_version,
            "dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "url": self.url,
            "latest_version": self.latest_version,
            "status": self.status.value,
            "downloads": self.downloads,
            "file_size": self.file_size,
        }
