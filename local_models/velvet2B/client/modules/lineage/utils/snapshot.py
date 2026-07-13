"""Lightweight codebase snapshot capture for the client SDK.

Mirrors the scan logic from the server-side graph_lineage.diff.snapshot module
but is fully self-contained — no dependency on the server package.

Scan rules:
- Root level: *.py, *.txt, *.yml, *.yaml
- modules/ folder: recursive *.py, *.yml, *.yaml
- .lineage/ folder: included (experiment.yml, server.yml, etc.)
- All other dot-files/dot-folders: EXCLUDED
- Max 10MB per file: blocking error
"""

from __future__ import annotations

import hashlib
import json 
from pathlib import Path

# Extensions tracked at root level
_ROOT_EXTENSIONS: set[str] = {".py", ".txt", ".yml", ".yaml"}

# Extensions tracked inside modules/
_MODULE_EXTENSIONS: set[str] = {".py", ".yml", ".yaml"}

MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB


class FileTooLargeError(Exception):
    """Raised when a tracked file exceeds MAX_FILE_SIZE."""

    def __init__(self, filepath: Path, size: int):
        self.filepath = filepath
        self.size = size
        super().__init__(
            f"File '{filepath}' is {size / (1024*1024):.1f}MB which exceeds the "
            f"maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.0f}MB. "
            f"Move large files outside the project root or add them to a dot-folder."
        )


def _is_dot_path(path: Path, root: Path) -> bool:
    """Check if any part of the relative path starts with '.' (except .lineage)."""
    rel = path.relative_to(root)
    for part in rel.parts:
        if part.startswith(".") and part != ".lineage":
            return True
    return False


def _read_file_safe(filepath: Path) -> str:
    """Read file with size check and encoding safety."""
    if filepath.is_symlink():
        return ""

    size = filepath.stat().st_size
    if size > MAX_FILE_SIZE:
        raise FileTooLargeError(filepath, size)

    return filepath.read_text(encoding="utf-8", errors="replace")


def capture_codebase(project_root: Path) -> str:
    """Scan project and capture all tracked files into a dict.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Dict of {relative_path: file_content} for all tracked files.

    Raises:
        FileTooLargeError: If any tracked file exceeds MAX_FILE_SIZE.
    """
    resolved_root = project_root.resolve()
    files: dict[str, str] = {}

    # 1. Root-level files (non-recursive, matching extensions)
    for item in sorted(resolved_root.iterdir()):
        if item.is_file() and not item.name.startswith("."):
            if item.suffix in _ROOT_EXTENSIONS:
                try:
                    item.resolve().relative_to(resolved_root)
                except ValueError:
                    continue
                files[item.name] = _read_file_safe(item)

    # 2. modules/ folder (recursive)
    modules_dir = resolved_root / "modules"
    if modules_dir.is_dir():
        for item in sorted(modules_dir.rglob("*")):
            if item.is_file() and not _is_dot_path(item, resolved_root):
                if item.suffix in _MODULE_EXTENSIONS:
                    try:
                        item.resolve().relative_to(resolved_root)
                    except ValueError:
                        continue
                    rel_key = str(item.relative_to(resolved_root))
                    files[rel_key] = _read_file_safe(item)

    # 3. .lineage/ folder (all files)
    lineage_dir = resolved_root / ".lineage"
    if lineage_dir.is_dir():
        for item in sorted(lineage_dir.rglob("*")):
            if item.is_file():
                try:
                    item.resolve().relative_to(resolved_root)
                except ValueError:
                    continue
                rel_key = str(item.relative_to(resolved_root))
                files[rel_key] = _read_file_safe(item)

    return json.dumps(files, sort_keys=True)


def content_hash(files: dict[str, str]) -> str:
    """Compute a single SHA-256 hash of the entire codebase dict.

    Useful for quick equality checks before sending full content.
    """
    combined = "".join(
        f"{k}:{hashlib.sha256(v.replace(chr(13)+chr(10), chr(10)).encode()).hexdigest()}"
        for k, v in sorted(files.items())
    )
    return hashlib.sha256(combined.encode()).hexdigest()
