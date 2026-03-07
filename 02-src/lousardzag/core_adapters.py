"""Adapter for using armenian-corpus-core central package in lousardzag.

This module provides compatibility wrappers that:
1. Try to import from the central package (armenian_corpus_core)
2. Fall back to local lousardzag modules if central package is not available
3. Route through environment-controlled feature flags

This enables gradual migration to the central package without breaking existing code.

Environment Variables:
- LOUSARDZAG_USE_CENTRAL_PACKAGE: Enable/disable central package usage (default: 1)
- LOUSARDZAG_DEBUG_IMPORTS: Show import diagnostics (default: 0)
"""

from __future__ import annotations

import os
import sys
from typing import Optional, Any

# Debug mode for import tracing
_DEBUG_IMPORTS = os.environ.get("LOUSARDZAG_DEBUG_IMPORTS", "0").lower() in ("1", "true", "yes")


def _debug_print(message: str) -> None:
    """Print debug message if debug mode enabled."""
    if _DEBUG_IMPORTS:
        print(f"[lousardzag.core_adapters] {message}", file=sys.stderr)


def _is_central_enabled() -> bool:
    """Check if central package usage is enabled via environment variable."""
    env_value = os.environ.get("LOUSARDZAG_USE_CENTRAL_PACKAGE", "1")
    enabled = env_value.lower() in ("1", "true", "yes")
    _debug_print(f"Central package enabled: {enabled} (env: {env_value})")
    return enabled


def get_extraction_registry():
    """Get extraction tool registry from central package or local fallback.
    
    Returns:
        ExtractionRegistry: The central package registry if available, else None
        
    Behavior:
        - Returns None if central package usage is explicitly disabled
        - Returns None if central package is not installed
        - Returns registry instance if central package is available and enabled
    
    Example:
        >>> import os
        >>> os.environ["LOUSARDZAG_USE_CENTRAL_PACKAGE"] = "1"
        >>> registry = get_extraction_registry()
        >>> if registry:
        ...     tools = registry.list_available_tools()
        ...     for tool in tools:
        ...         print(f"{tool.batch}: {tool.name}")
    """
    if not _is_central_enabled():
        _debug_print("Central package usage is disabled (LOUSARDZAG_USE_CENTRAL_PACKAGE not set or 0)")
        return None
    
    try:
        _debug_print("Attempting to import central package registry...")
        from armenian_corpus_core.extraction.registry import get_registry
        registry = get_registry()
        _debug_print(f"Successfully loaded registry with {len(registry.list_tools())} tools")
        return registry
    except ImportError as e:
        _debug_print(f"Failed to import central package: {e}")
        _debug_print("Falling back to local tool descriptions")
        return None
    except Exception as e:
        _debug_print(f"Unexpected error loading central package: {e}")
        return None


def get_extraction_tools_metadata() -> dict[str, Any]:
    """Get metadata about available extraction tools.
    
    Returns dictionary with tool information from central registry if available,
    else a local fallback description.
    
    Returns:
        dict: Tool metadata with keys: name, description, inputs, outputs, status
    """
    registry = get_extraction_registry()
    
    if registry:
        return registry.to_dict()
    
    # Fallback: local tools description
    return {
        "tools": {
            "export_core_contracts_jsonl": {
                "name": "export_core_contracts_jsonl",
                "description": "Export lousardzag DB rows to core contract JSONL",
                "status": "available",
                "location": "local:07-tools/extraction/",
            },
            "merge_document_records": {
                "name": "merge_document_records",
                "description": "Merge and deduplicate DocumentRecord JSONL files",
                "status": "available",
                "location": "local:07-tools/extraction/",
            },
        },
        "location": "local",
        "note": "Use LOUSARDZAG_USE_CENTRAL_PACKAGE=1 to enable central package",
    }


def load_document_records_from_jsonl(jsonl_path: str, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """Load DocumentRecord JSONL file.
    
    Provides unified interface for loading extraction pipeline output.
    
    Args:
        jsonl_path: Path to JSONL file
        limit: Optional row limit (0 = all)
    
    Returns:
        List of document records as dictionaries
    """
    import json
    from pathlib import Path
    
    records = []
    path = Path(jsonl_path)
    
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")
    
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    
    return records


def get_pipeline_stats(unified_jsonl_path: str) -> dict[str, Any]:
    """Get statistics about unified document records.
    
    Args:
        unified_jsonl_path: Path to unified_document_records.jsonl
    
    Returns:
        Dictionary with statistics:
        - total_records
        - content_bearing
        - fingerprint_only
        - by_dialect
        - by_source_family
    """
    records = load_document_records_from_jsonl(unified_jsonl_path)
    
    stats = {
        "total_records": len(records),
        "content_bearing": 0,
        "fingerprint_only": 0,
        "by_dialect": {},
        "by_source_family": {},
    }
    
    for record in records:
        # Count content bearing vs. fingerprint only
        text = record.get("text", "").strip()
        if text:
            stats["content_bearing"] += 1
        else:
            stats["fingerprint_only"] += 1
        
        # Count by dialect
        dialect = record.get("dialect_tag", "unknown")
        stats["by_dialect"][dialect] = stats["by_dialect"].get(dialect, 0) + 1
        
        # Count by source family
        source = record.get("source_family", "unknown")
        stats["by_source_family"][source] = stats["by_source_family"].get(source, 0) + 1
    
    return stats


__all__ = [
    "get_extraction_registry",
    "get_extraction_tools_metadata",
    "load_document_records_from_jsonl",
    "get_pipeline_stats",
    "diagnose_central_package",
]


def diagnose_central_package() -> dict[str, Any]:
    """Run diagnostic checks on central package availability and health.
    
    Returns a dictionary with diagnostic information for troubleshooting.
    
    Returns:
        dict with keys:
        - central_package_enabled: Whether usage is enabled via env var
        - central_package_installed: Whether package can be imported
        - registry_available: Whether registry is accessible
        - tools_count: Number of tools registered (if registry available)
        - error_message: Error details if something failed
        - recommendations: List of suggested actions if issues found
    
    Example:
        >>> diagnostics = diagnose_central_package()
        >>> if not diagnostics["central_package_installed"]:
        ...     print("To fix: pip install -e /path/to/armenian-corpus-core")
    """
    diagnostics = {
        "central_package_enabled": _is_central_enabled(),
        "central_package_installed": False,
        "registry_available": False,
        "tools_count": 0,
        "error_message": None,
        "recommendations": [],
    }
    
    # Check if package can be imported
    try:
        import armenian_corpus_core
        diagnostics["central_package_installed"] = True
        _debug_print(f"Central package found at: {armenian_corpus_core.__file__}")
    except ImportError as e:
        diagnostics["central_package_installed"] = False
        diagnostics["error_message"] = str(e)
        if not diagnostics["central_package_enabled"]:
            diagnostics["recommendations"].append(
                "1. Enable central package: set LOUSARDZAG_USE_CENTRAL_PACKAGE=1"
            )
        diagnostics["recommendations"].append(
            "2. Install central package: pip install -e /path/to/armenian-corpus-core"
        )
        return diagnostics
    
    # Check if registry is accessible
    registry = get_extraction_registry()
    if registry:
        diagnostics["registry_available"] = True
        diagnostics["tools_count"] = len(registry.list_tools())
        _debug_print(f"Registry loaded successfully with {diagnostics['tools_count']} tools")
    else:
        if not diagnostics["central_package_enabled"]:
            diagnostics["recommendations"].append(
                "To use central package: set LOUSARDZAG_USE_CENTRAL_PACKAGE=1"
            )
        else:
            diagnostics["recommendations"].append(
                "Registry is not available. Check installation with: pip show armenian-corpus-core"
            )
    
    return diagnostics
