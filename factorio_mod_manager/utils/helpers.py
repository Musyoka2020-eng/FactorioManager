"""Helper utilities for Factorio Mod Manager."""
import json
import zipfile
import socket
from pathlib import Path
from typing import Dict, Optional, Any
import requests # type: ignore


def parse_mod_info(mod_zip_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse mod information from info.json in a mod zip file.
    
    Args:
        mod_zip_path: Path to the mod zip file
        
    Returns:
        Dictionary with mod info or None if parsing fails
    """
    try:
        with zipfile.ZipFile(mod_zip_path, 'r') as zip_file:
            # Find info.json in the zip
            info_files = [f for f in zip_file.namelist() if f.endswith('info.json')]
            if not info_files:
                return None
            
            info_file = info_files[0]
            with zip_file.open(info_file) as f:
                info = json.load(f)
                return info
    except Exception as e:
        print(f"Error parsing mod info from {mod_zip_path}: {e}")
        return None


def extract_version_from_filename(filename: str) -> Optional[str]:
    """
    Extract version from mod filename (e.g., 'modname_1.2.3.zip').
    
    Args:
        filename: The mod filename
        
    Returns:
        Version string or None if not found
    """
    # Pattern: modname_version.zip
    if '_' in filename and filename.endswith('.zip'):
        parts = filename[:-4].rsplit('_', 1)  # Remove .zip and split on last _
        if len(parts) == 2 and parts[1]:
            return parts[1]
    return None


def format_file_size(bytes_size: float) -> str:
    """
    Format bytes to human-readable size.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted string (e.g., '1.5 MB')
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def validate_mod_url(url: str) -> bool:
    """
    Validate if URL is a valid Factorio Mod Portal URL.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    return url.startswith("https://mods.factorio.com/mod/")


def is_online() -> tuple[bool, Optional[str]]:
    """
    Check if device has internet connectivity.
    
    Args:
        None
        
    Returns:
        Tuple of (is_online: bool, error_message: str or None)
    """
    try:
        # Try to resolve DNS
        socket.gethostbyname("mods.factorio.com")
        return True, None
    except socket.gaierror:
        return False, "DNS resolution failed - unable to reach mods.factorio.com"
    except socket.error as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        return False, f"Connection check failed: {str(e)}"


def check_factorio_portal_status() -> tuple[bool, str]:
    """
    Check if Factorio portal is accessible and responding.
    
    Args:
        None
        
    Returns:
        Tuple of (is_accessible: bool, status_message: str)
    """
    try:
        response = requests.head("https://mods.factorio.com", timeout=5)
        if response.status_code == 200:
            return True, "Portal is online"
        else:
            return False, f"Portal returned status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Factorio portal - network error"
    except requests.exceptions.Timeout:
        return False, "Connection to Factorio portal timed out"
    except Exception as e:
        return False, f"Portal check failed: {str(e)}"

