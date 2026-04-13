"""Factorio Mod Portal API integration."""
import re
from typing import Dict, List, Optional, Any, Tuple
import requests # type: ignore
from bs4 import BeautifulSoup # type: ignore
from .mod import Mod, FACTORIO_EXPANSIONS


class PortalAPIError(Exception):
    """Custom exception for portal API errors."""
    
    def __init__(self, message: str, error_type: str = "unknown", status_code: Optional[int] = None):
        """
        Initialize API error.
        
        Args:
            message: Error message for user
            error_type: Type of error - "offline", "not_found", "server_error", "timeout", "unknown"
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code


class FactorioPortalAPI:
    """Interface to Factorio Mod Portal API."""

    BASE_URL = "https://mods.factorio.com"
    API_URL = "https://mods.factorio.com/api/mods"

    def __init__(self):
        """Initialize portal API client."""
        self.session = requests.Session()

    def get_mod(self, mod_name: str) -> Optional[Dict[str, Any]]:
        """
        Get mod information from the portal.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Dictionary with mod info or None if not found
            
        Raises:
            PortalAPIError: With specific error type (offline, not_found, server_error, timeout)
        """
        try:
            # Use /full endpoint to get complete info including full info_json with dependencies
            response = self.session.get(
                f"{self.API_URL}/{mod_name}/full",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise PortalAPIError(
                    f"Mod '{mod_name}' not found on the portal",
                    error_type="not_found",
                    status_code=404
                )
            elif response.status_code in [500, 502, 503, 504]:
                raise PortalAPIError(
                    f"Factorio portal server error ({response.status_code}). Please try again later.",
                    error_type="server_error",
                    status_code=response.status_code
                )
            else:
                raise PortalAPIError(
                    f"API returned status {response.status_code}",
                    error_type="server_error",
                    status_code=response.status_code
                )
        except requests.exceptions.ConnectionError:
            raise PortalAPIError(
                "Cannot connect to Factorio portal. Check your internet connection.",
                error_type="offline"
            )
        except requests.exceptions.Timeout:
            raise PortalAPIError(
                "Connection to Factorio portal timed out. Please try again.",
                error_type="timeout"
            )
        except PortalAPIError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            raise PortalAPIError(
                f"Error fetching mod '{mod_name}': {str(e)}",
                error_type="unknown"
            )

    def get_mod_download_url(self, mod_name: str, version: str) -> Optional[str]:
        """
        Get download URL for a specific mod version.
        
        Args:
            mod_name: Name of the mod
            version: Version string
            
        Returns:
            Download URL or None
            
        Raises:
            PortalAPIError: With specific error type
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
        except PortalAPIError:
            raise
        except Exception as e:
            raise PortalAPIError(
                f"Error getting download URL for {mod_name}@{version}: {str(e)}",
                error_type="unknown"
            )

    def get_mod_dependencies(self, mod_name: str) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Get dependencies for a mod.
        
        Args:
            mod_name: Name of the mod
            
        Returns:
            Tuple of (required_dependencies, optional_dependencies, incompatible_dependencies, expansion_dependencies)
            
        Raises:
            PortalAPIError: With specific error type
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
        except PortalAPIError:
            raise
        except Exception as e:
            raise PortalAPIError(
                f"Error getting dependencies for {mod_name}: {str(e)}",
                error_type="unknown"
            )

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

    def search_mods(
        self,
        query: str,
        limit: int = 20,
        category: str = "",
        version: str = "",
        page: int = 1,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Search for mods on the portal.

        The portal's q= and tag= URL parameters are non-functional (they return
        all mods sorted by name regardless of value).

        Fast path (no query, no category): uses server-side pagination so every
        page of "recently updated" mods can be browsed cheaply.

        Client-side path (text query OR category filter): fetches up to 200
        recently-updated mods, applies category filter + text ranking, and
        slices the requested page from the ranked pool.  An extra namelist=
        lookup supplements exact name matches that might not appear in the
        recent-200 window.

        Args:
            query:    Search query (empty string for browse mode).
            limit:    Results per page (default 20).
            category: Portal category value (e.g. "content", "overhaul").
                      Empty string means no filter.
            version:  Factorio version filter ("2.0", "1.1", or "" for all).
            page:     1-based page number.

        Returns:
            Tuple of (results, current_page, total_pages).
        """
        page = max(1, page)
        try:
            # ------------------------------------------------------------------
            # Fast path: pure browse (no text query, no category filter)
            # ------------------------------------------------------------------
            if not query and not category:
                params: Dict[str, Any] = {
                    "sort": "updated_at",
                    "sort_order": "desc",
                    "hide_deprecated": "true",
                    "page_size": limit,
                    "page": page,
                }
                if version:
                    params["version"] = version
                resp = self.session.get(self.API_URL, params=params, timeout=15)
                if resp.status_code != 200:
                    return [], 1, 1
                body = resp.json()
                results: List[Dict[str, Any]] = body.get("results", [])
                pag = body.get("pagination", {})
                current_page = pag.get("page", page)
                total_pages  = pag.get("page_count", 1)
                return results, current_page, max(1, total_pages)

            # ------------------------------------------------------------------
            # Client-side path: fetch pool, filter, rank, paginate
            # ------------------------------------------------------------------
            # "No category" mods are old/unmaintained — they sit at the tail of
            # the updated_at-desc list.  Flip to asc so we actually find them.
            sort_order = "asc" if category == "__no_category__" else "desc"
            pool_params: Dict[str, Any] = {
                "sort": "updated_at",
                "sort_order": sort_order,
                "hide_deprecated": "true",
                "page_size": 200,
            }
            if version:
                pool_params["version"] = version
            resp = self.session.get(self.API_URL, params=pool_params, timeout=15)
            if resp.status_code != 200:
                return [], 1, 1
            pool: List[Dict[str, Any]] = resp.json().get("results", [])

            # Category filter
            if category == "__no_category__":
                pool = [r for r in pool if not r.get("category")]
            elif category:
                pool = [r for r in pool if r.get("category", "") == category]

            # Text ranking
            if query:
                q = query.lower()

                def _rank(entry: Dict[str, Any]) -> tuple:
                    name  = (entry.get("name")    or "").lower()
                    title = (entry.get("title")   or "").lower()
                    summ  = (entry.get("summary") or "").lower()
                    score = -(entry.get("score") or 0)
                    if name == q:
                        return (0, score)
                    if title == q:
                        return (1, score)
                    if name.startswith(q):
                        return (2, score)
                    if title.startswith(q):
                        return (3, score)
                    if q in name:
                        return (4, score)
                    if q in title:
                        return (5, score)
                    if q in summ:
                        return (6, score)
                    return (99, 0)

                ranked  = [(r, _rank(r)) for r in pool]
                matched = [(r, k) for r, k in ranked if k[0] < 99]
                matched.sort(key=lambda x: x[1])
                pool = [r for r, _ in matched]

                # Supplement with exact name match (catches mods outside recent-200)
                try:
                    nr = self.session.get(
                        self.API_URL, params={"namelist": query}, timeout=8
                    )
                    if nr.status_code == 200:
                        existing = {r["name"] for r in pool}
                        new_exact = [
                            r for r in nr.json().get("results", [])
                            if r["name"] not in existing
                        ]
                        pool = new_exact + pool
                except Exception:
                    pass
            else:
                # Browse+category mode: rank by community score
                pool.sort(key=lambda x: -(x.get("score") or 0))

            # Paginate the ranked pool
            total_pages = max(1, (len(pool) + limit - 1) // limit)
            page        = min(page, total_pages)
            start       = (page - 1) * limit
            return pool[start : start + limit], page, total_pages

        except Exception as e:
            print(f"Error searching for mods: {e}")
        return [], 1, 1

    def get_mod_changelog(self, mod_name: str) -> Dict[str, Any]:
        """
        Fetch mod changelog from the mod portal HTML page.

        Args:
            mod_name: Name of the mod

        Returns:
            Dictionary with parsed changelog data {version: changelog_text}

        Raises:
            PortalAPIError: On network or parsing failures
        """
        try:
            changelog_url = f"{self.BASE_URL}/mod/{mod_name}/changelog"
            response = self.session.get(changelog_url, timeout=10)

            if response.status_code != 200:
                raise PortalAPIError(
                    f"Failed to fetch changelog for {mod_name}: HTTP {response.status_code}"
                )

            soup = BeautifulSoup(response.text, 'html.parser')
            changelog_data = {}

            # Find all pre tags with class 'panel-hole-combined'
            # Each version has its own pre tag
            pre_tags = soup.find_all('pre', class_='panel-hole-combined')

            for pre_tag in pre_tags:
                changelog_text = pre_tag.get_text()

                # Extract version number from first line
                # Format: "Version: X.Y.Z"
                first_line = changelog_text.split('\n')[0]
                version_match = re.match(r'^\s*Version:\s*(\d+\.\d+\.\d+)', first_line)

                if version_match:
                    version = version_match.group(1)
                    # Content is everything in the pre tag
                    content = changelog_text.strip()
                    if content:
                        changelog_data[version] = content

            return changelog_data

        except PortalAPIError:
            raise
        except Exception as e:
            raise PortalAPIError(f"Error fetching changelog for {mod_name}: {e}") from e