"""Factorio Mod Portal API integration."""
import re
from typing import Dict, List, Optional, Any
import requests
from bs4 import BeautifulSoup
from .mod import Mod, FACTORIO_EXPANSIONS


class FactorioPortalAPI:
    """Interface to Factorio Mod Portal API."""

    BASE_URL = "https://mods.factorio.com"
    API_URL = "https://mods.factorio.com/api/mods"

    def __init__(self, username: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize portal API client.
        
        Args:
            username: Factorio username (for downloading mods)
            token: Factorio API token (for downloading mods)
        """
        self.username = username
        self.token = token
        self.session = requests.Session()
        if username and token:
            self.session.auth = (username, token)

    def get_mod(self, mod_name: str) -> Optional[Dict[str, Any]]:
        """
        Get mod information from the portal.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Dictionary with mod info or None if not found
        """
        try:
            # Use /full endpoint to get complete info including full info_json with dependencies
            response = self.session.get(
                f"{self.API_URL}/{mod_name}/full",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching mod {mod_name} from API: {e}")
        
        return None

    def get_mod_download_url(self, mod_name: str, version: str) -> Optional[str]:
        """
        Get download URL for a specific mod version.
        
        Args:
            mod_name: Name of the mod
            version: Version string
            
        Returns:
            Download URL or None
        """
        try:
            mod_data = self.get_mod(mod_name)
            if not mod_data:
                return None
            
            # Find the release with matching version
            for release in mod_data.get("releases", []):
                if release.get("version") == version:
                    filename = release.get("filename")
                    if filename:
                        return f"{self.BASE_URL}/download/{filename}"
            
            return None
        except Exception as e:
            print(f"Error getting download URL for {mod_name}@{version}: {e}")
            return None

    def get_mod_dependencies(self, mod_name: str) -> tuple[List[str], List[str], List[str], List[str]]:
        """
        Get dependencies for a mod.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Tuple of (required_dependencies, optional_dependencies, incompatible_dependencies, expansion_dependencies)
        """
        try:
            mod_data = self.get_mod(mod_name)
            if not mod_data:
                return [], [], [], []
            
            dependencies = []
            optional_dependencies = []
            incompatible_dependencies = []
            expansion_dependencies = []
            
            # Get latest release dependencies from info_json
            releases = mod_data.get("releases", [])
            if releases:
                latest = releases[-1]  # Latest release
                info_json = latest.get("info_json", {})
                
                # Dependencies are in info_json.dependencies as strings
                for dep in info_json.get("dependencies", []):
                    dep = dep.strip()
                    
                    if not dep or dep == "base" or dep.startswith("base "):
                        continue
                    
                    # Parse dependency format
                    if dep.startswith("!"):
                        # Incompatible dependency
                        dep_name = dep[1:].strip()
                        incompatible_dependencies.append(dep_name)
                    elif dep.startswith("(?)") or dep.startswith("?"):
                        # Optional dependency - remove prefix and constraints
                        dep_name = dep.replace("(?)", "").replace("?", "").strip()
                        # Extract just the mod name (before version constraint)
                        dep_name = dep_name.split()[0] if " " in dep_name else dep_name.split(">")[0].split("=")[0].split("<")[0].split("!")[0].strip()
                        # Check if it's an expansion
                        if dep_name in FACTORIO_EXPANSIONS:
                            expansion_dependencies.append(dep_name)
                        elif dep_name:
                            optional_dependencies.append(dep_name)
                    else:
                        # Required dependency - extract mod name
                        dep_name = dep.split()[0] if " " in dep else dep.split(">")[0].split("=")[0].split("<")[0].strip()
                        if dep_name and dep_name != "base":
                            # Check if it's an expansion
                            if dep_name in FACTORIO_EXPANSIONS:
                                expansion_dependencies.append(dep_name)
                            else:
                                dependencies.append(dep_name)
            
            return dependencies, optional_dependencies, incompatible_dependencies, expansion_dependencies
        except Exception as e:
            print(f"Error getting dependencies for {mod_name}: {e}")
            return [], [], [], []

    def parse_mod_from_portal(self, mod_name: str) -> Optional[Mod]:
        """
        Parse mod data from portal and create Mod object.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Mod object or None
        """
        try:
            mod_data = self.get_mod(mod_name)
            if not mod_data:
                return None
            
            # Get latest release
            releases = mod_data.get("releases", [])
            if not releases:
                return None
            
            latest_release = releases[-1]
            version = latest_release.get("version", "0.0.0")
            dependencies, optional_deps, incompatible_deps, expansion_deps = self.get_mod_dependencies(mod_name)
            
            mod = Mod(
                name=mod_name,
                title=mod_data.get("title", mod_name),
                version=version,
                author=mod_data.get("author", "Unknown"),
                description=mod_data.get("description", ""),
                factorio_version=latest_release.get("factorio_version", ""),
                dependencies=dependencies,
                optional_dependencies=optional_deps,
                incompatible_dependencies=incompatible_deps,
                expansion_dependencies=expansion_deps,
                downloads=mod_data.get("downloads_count", 0),
                homepage=mod_data.get("homepage", ""),
                raw_data=mod_data,
            )
            
            return mod
        except Exception as e:
            print(f"Error parsing mod {mod_name}: {e}")
            return None

    def search_mods(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for mods on the portal.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of mod dictionaries
        """
        try:
            response = self.session.get(
                f"{self.API_URL}",
                params={"q": query},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])[:limit]
        except Exception as e:
            print(f"Error searching for mods: {e}")
        
        return []
