"""Mod downloader with dependency resolution."""
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from .mod import Mod
from .portal import FactorioPortalAPI
from ..utils import format_file_size


class ModDownloader:
    """Download mods with automatic dependency resolution."""

    def __init__(
        self,
        mods_folder: str,
        username: Optional[str] = None,
        token: Optional[str] = None,
        max_workers: int = 4,
    ):
        """
        Initialize mod downloader.
        
        Args:
            mods_folder: Path to Factorio mods folder
            username: Factorio username
            token: Factorio API token
            max_workers: Maximum concurrent downloads
        """
        self.mods_folder = Path(mods_folder)
        self.mods_folder.mkdir(parents=True, exist_ok=True)
        self.portal = FactorioPortalAPI(username, token)
        self.max_workers = max_workers
        self.session = requests.Session()
        if username and token:
            self.session.auth = (username, token)
        
        # Callback for progress updates
        self.progress_callback: Optional[Callable] = None
        # Callback for per-mod status updates: (mod_name, status, progress_pct)
        self.mod_progress_callback: Optional[Callable] = None
        # Callback for overall download progress: (completed, total)
        self.overall_progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    def set_mod_progress_callback(self, callback: Callable) -> None:
        """Set callback for per-mod progress updates."""
        self.mod_progress_callback = callback
    
    def set_overall_progress_callback(self, callback: Callable) -> None:
        """Set callback for overall download progress."""
        self.overall_progress_callback = callback

    def _log_progress(self, message: str) -> None:
        """Log progress message."""
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

    def get_installed_mods(self) -> Dict[str, Mod]:
        """
        Get all installed mods from the mods folder.
        
        Returns:
            Dictionary mapping mod names to Mod objects
        """
        installed = {}
        
        if not self.mods_folder.exists():
            return installed
        
        for mod_file in self.mods_folder.glob("*.zip"):
            try:
                # Parse filename: modname_version.zip
                filename = mod_file.stem
                if '_' in filename:
                    name, version = filename.rsplit('_', 1)
                else:
                    name = filename
                    version = "0.0.0"
                
                mod = Mod(
                    name=name,
                    title=name,
                    version=version,
                    author="Unknown",
                    file_path=str(mod_file),
                )
                installed[name] = mod
            except Exception as e:
                self._log_progress(f"Error parsing mod {mod_file.name}: {e}")
        
        return installed

    def resolve_dependencies(
        self,
        mod_name: str,
        include_optional: bool = False,
        visited: Optional[Set[str]] = None,
    ) -> tuple[Dict[str, Mod], List[str], List[str]]:
        """
        Recursively resolve all dependencies for a mod.
        
        Args:
            mod_name: Name of the mod
            include_optional: Include optional dependencies
            visited: Set of already visited mods (to avoid circular deps)
            
        Returns:
            Tuple of (dependencies_dict, incompatibilities_list, expansion_requirements_list)
        """
        if visited is None:
            visited = set()
        
        if mod_name in visited:
            return {}, [], []
        
        visited.add(mod_name)
        dependencies = {}
        incompatibilities = []
        expansions = []
        
        self._log_progress(f"Resolving dependencies for {mod_name}...")
        
        try:
            mod = self.portal.parse_mod_from_portal(mod_name)
            if not mod:
                self._log_progress(f"Error: Could not find mod {mod_name}")
                return {}, [], []
            
            dependencies[mod_name] = mod
            
            # Add incompatible mods to warning list
            if mod.incompatible_dependencies:
                incompatibilities.extend(mod.incompatible_dependencies)
            
            # Add expansion requirements
            if mod.expansion_dependencies:
                expansions.extend(mod.expansion_dependencies)
            
            # Get dependencies to resolve
            all_deps = mod.dependencies.copy()
            if include_optional:
                all_deps.extend(mod.optional_dependencies)
            
            # Recursively resolve each dependency
            for dep_name in all_deps:
                dep_mods, dep_incompats, dep_expansions = self.resolve_dependencies(
                    dep_name,
                    include_optional=include_optional,
                    visited=visited,
                )
                dependencies.update(dep_mods)
                incompatibilities.extend(dep_incompats)
                expansions.extend(dep_expansions)
        
        except Exception as e:
            self._log_progress(f"Error resolving dependencies for {mod_name}: {e}")
        
        return dependencies, incompatibilities, expansions

    def download_mod(self, mod: Mod, force: bool = False) -> bool:
        """
        Download a single mod using re146.dev.
        
        Args:
            mod: Mod object to download
            force: Force download even if already exists
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already installed
            mod_file = self.mods_folder / f"{mod.name}_{mod.version}.zip"
            
            if mod_file.exists() and not force:
                self._log_progress(f"✓ {mod.name}@{mod.version} already installed")
                return True
            
            # Check if older version exists
            if not mod_file.exists():
                for existing_file in self.mods_folder.glob(f"{mod.name}_*.zip"):
                    existing_version = existing_file.stem.split('_', 1)[1]
                    if existing_version != mod.version:
                        self._log_progress(f"⚠️  {mod.name}: Found older version {existing_version}, upgrading to {mod.version}")
                        break
            
            self._log_progress(f"⬇ Downloading {mod.name}@{mod.version}...")
            
            # Try browser-based download via re146.dev
            if self._download_with_re146(mod, mod_file):
                self._log_progress(f"✓ Downloaded {mod.name}@{mod.version}")
                return True
            
            return False
        
        except Exception as e:
            self._log_progress(f"✗ Error downloading {mod.name}: {e}")
            return False

    def _download_with_re146(self, mod: Mod, output_path: Path) -> bool:
        """
        Download mod from re146.dev mirror using HTTP.
        
        Args:
            mod: Mod object
            output_path: Where to save the file
            
        Returns:
            True if successful
        """
        try:
            # Use re146.dev mirror
            mirror_url = f"https://mods-storage.re146.dev/{mod.name}/{mod.version}.zip"
            self._log_progress(f"  Downloading from mirror: {mirror_url}")
            
            # Download with streaming to handle large files
            response = requests.get(mirror_url, timeout=60, stream=True)
            
            if response.status_code == 404:
                self._log_progress(f"  ✗ Mod not found on mirror (404)")
                return False
            
            if response.status_code != 200:
                self._log_progress(f"  ✗ Download failed with status {response.status_code}")
                return False
            
            # Get total file size if available
            total_size = int(response.headers.get('content-length', 0))
            if total_size > 0:
                self._log_progress(f"  Downloading {format_file_size(total_size)}...")
            
            # Download to output path
            downloaded_size = 0
            chunk_size = 8192
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Log progress for large files
                        if total_size > 0 and downloaded_size % (chunk_size * 100) == 0:
                            progress_pct = (downloaded_size / total_size) * 100
                            self._log_progress(f"    Progress: {progress_pct:.1f}%")
            
            # Verify file was downloaded
            if not output_path.exists():
                self._log_progress(f"  ✗ Downloaded file not found")
                return False
            
            file_size = output_path.stat().st_size
            self._log_progress(f"  ✓ Downloaded {format_file_size(file_size)}")
            
            # Verify it's a valid ZIP file
            try:
                with zipfile.ZipFile(output_path, 'r') as z:
                    result = z.testzip()
                    if result is not None:
                        self._log_progress(f"  ✗ ZIP file corrupted: {result}")
                        output_path.unlink()
                        return False
                    self._log_progress(f"  ✓ ZIP file is valid")
            except Exception as z_err:
                self._log_progress(f"  ✗ Invalid ZIP file: {z_err}")
                output_path.unlink()
                return False
            
            return True
        
        except Exception as e:
            self._log_progress(f"  ✗ Download error: {e}")
            if output_path.exists():
                try:
                    output_path.unlink()
                except:
                    pass
            return False


    def download_mods(
        self,
        mod_names: List[str],
        include_optional: bool = False,
    ) -> tuple[List[Mod], List[str]]:
        """
        Download multiple mods with all dependencies.
        
        Args:
            mod_names: List of mod names to download
            include_optional: Include optional dependencies
            
        Returns:
            Tuple of (downloaded_mods, failed_mods)
        """
        # Resolve all dependencies
        all_mods = {}
        all_incompatibilities = set()
        all_expansions = set()
        failed = []
        
        for mod_name in mod_names:
            try:
                deps, incompats, expansions = self.resolve_dependencies(
                    mod_name,
                    include_optional=include_optional,
                )
                all_mods.update(deps)
                all_incompatibilities.update(incompats)
                all_expansions.update(expansions)
            except Exception as e:
                self._log_progress(f"Error resolving {mod_name}: {e}")
                failed.append(mod_name)
        
        # Remove duplicates
        all_mods = dict(sorted(all_mods.items()))
        
        # Check for incompatibility warnings
        if all_incompatibilities:
            self._log_progress(f"\n⚠️  Incompatible mods detected (cannot coexist):")
            for incompat in sorted(all_incompatibilities):
                self._log_progress(f"  - {incompat}")
            self._log_progress(f"  These mods conflict with selected mods.")
        
        # Check conflicts with already installed mods
        installed_mods = self.get_installed_mods()
        conflicts_with_installed = []
        
        for mod_name in all_incompatibilities:
            if mod_name in installed_mods:
                conflicts_with_installed.append(f"{mod_name} (installed)")
        
        if conflicts_with_installed:
            self._log_progress(f"\n⚠️  WARNING: Conflicts with installed mods:")
            for conflict in conflicts_with_installed:
                self._log_progress(f"  ⚠️  {conflict}")
            self._log_progress(f"  Installing may cause issues. Proceed with caution!")
        
        # Check for expansion requirements
        if all_expansions:
            self._log_progress(f"\n💿 Required DLC Expansions:")
            for expansion in sorted(all_expansions):
                self._log_progress(f"  - {expansion}")
            self._log_progress(f"  Note: These must be purchased and installed manually")
        
        self._log_progress(f"\n📦 To download: {len(all_mods)} mods")
        for mod_name in all_mods:
            mod = all_mods[mod_name]
            # Show dependency count
            total_deps = len(mod.dependencies) + len(mod.optional_dependencies)
            dep_info = f" ({total_deps} deps)" if total_deps > 0 else ""
            self._log_progress(f"  - {mod_name}{dep_info}")
            # Notify UI to add progress item for each mod
            if self.mod_progress_callback:
                self.mod_progress_callback(mod_name, "⏳ Starting...", 0)
        
        # Download all mods
        downloaded = []
        completed = 0
        total = len(all_mods)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.download_mod, mod): mod
                for mod in all_mods.values()
            }
            
            for future in as_completed(futures):
                mod = futures[future]
                try:
                    if future.result():
                        downloaded.append(mod)
                        if self.mod_progress_callback:
                            self.mod_progress_callback(mod.name, "✓ Downloaded", 100)
                    else:
                        failed.append(mod.name)
                        if self.mod_progress_callback:
                            self.mod_progress_callback(mod.name, "✗ Failed", 0)
                except Exception as e:
                    self._log_progress(f"Error downloading {mod.name}: {e}")
                    failed.append(mod.name)
                    if self.mod_progress_callback:
                        self.mod_progress_callback(mod.name, f"✗ Error: {e}", 0)
                finally:
                    completed += 1
                    if self.overall_progress_callback:
                        self.overall_progress_callback(completed, total)
        
        return downloaded, failed
