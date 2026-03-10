from typing import List, Dict, Optional
import json
import os
import re
from pathlib import Path

html_re = re.compile(r"<.*?>")

_CONFIG_PATH = Path.home() / ".config" / "zotero-mcp" / "config.json"


def get_zotero_db_path() -> Optional[str]:
    """
    Get Zotero database path from environment or config file.

    Priority:
    1. ZOTERO_DB_PATH environment variable
    2. semantic_search.zotero_db_path in ~/.config/zotero-mcp/config.json
    3. None (caller will use LocalZoteroReader auto-detect)

    Returns:
        Database path string, or None for auto-detect.
    """
    env_path = os.getenv("ZOTERO_DB_PATH", "").strip()
    if env_path:
        return env_path

    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
            db_path = cfg.get("semantic_search", {}).get("zotero_db_path")
            if db_path and str(db_path).strip():
                return str(db_path).strip()
    except Exception:
        pass

    return None

def format_creators(creators: list[dict[str, str]]) -> str:
    """
    Format creator names into a string.

    Args:
        creators: List of creator objects from Zotero.

    Returns:
        Formatted string with creator names.
    """
    names = []
    for creator in creators:
        if "firstName" in creator and "lastName" in creator:
            names.append(f"{creator['lastName']}, {creator['firstName']}")
        elif "name" in creator:
            names.append(creator["name"])
    return "; ".join(names) if names else "No authors listed"


def is_local_mode() -> bool:
    """Return True if running in local mode.

    Local mode is enabled when environment variable `ZOTERO_LOCAL` is set to a
    truthy value ("true", "yes", or "1", case-insensitive).
    """
    value = os.getenv("ZOTERO_LOCAL", "")
    return value.lower() in {"true", "yes", "1"}

def clean_html(raw_html: str) -> str:
    """
    Remove HTML tags from a string.

    Args:
        raw_html: String containing HTML content.
    Returns:
        Cleaned string without HTML tags.
    """
    clean_text = re.sub(html_re, "", raw_html)
    return clean_text