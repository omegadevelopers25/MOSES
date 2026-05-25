"""MOSES package shim.

This file avoids importing application entry points at package-import time
to prevent circular imports when a top-level ``moses.py`` module also
exists in the project. It re-exports key symbols from the root module
if available.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

# Attempt to locate the sibling top-level 'moses.py' and load it as a
# private module so that importing the package still provides the
# expected symbols without causing the package to import the GUI entry
# points.
_root = Path(__file__).parent.parent / "moses.py"
if _root.exists():
    spec = importlib.util.spec_from_file_location("_moses_root", str(_root))
    if spec and spec.loader:
        _mod = importlib.util.module_from_spec(spec)
        sys.modules["_moses_root"] = _mod
        spec.loader.exec_module(_mod)
        for _name in ("DEFAULT_MODEL", "DEFAULT_TIMEZONE", "SYSTEM_INSTRUCTION", "AssistantStore", "MosesAgent", "WorkspaceAccess"):
            if hasattr(_mod, _name):
                globals()[_name] = getattr(_mod, _name)

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TIMEZONE",
    "SYSTEM_INSTRUCTION",
    "AssistantStore",
    "MosesAgent",
    "WorkspaceAccess",
]
