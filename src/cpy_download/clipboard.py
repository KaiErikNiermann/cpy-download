"""Clipboard backends for Linux (X11 and Wayland)."""

from __future__ import annotations

import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path


class ClipboardBackend(str, Enum):
    """Supported clipboard backends."""

    XCLIP = "xclip"
    WL_COPY = "wl-copy"
    AUTO = "auto"


class CopyMethod(str, Enum):
    """How to represent the file on the clipboard."""

    URI = "uri"  # text/uri-list (standard freedesktop, most compatible)
    GNOME = "gnome"  # x-special/gnome-copied-files (GNOME/GTK apps only)
    RAW = "raw"  # raw video bytes with video/* MIME (least compatible)


MIME_BY_SUFFIX: dict[str, str] = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".flv": "video/x-flv",
    ".ts": "video/mp2t",
    ".m4v": "video/mp4",
}


def detect_backend() -> ClipboardBackend:
    """Detect the appropriate clipboard backend from the display server.

    Checks $XDG_SESSION_TYPE first (most reliable), then falls back to
    checking $WAYLAND_DISPLAY and $DISPLAY environment variables.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "wayland":
        return ClipboardBackend.WL_COPY
    if session_type == "x11":
        return ClipboardBackend.XCLIP

    # Fallback heuristics
    if os.environ.get("WAYLAND_DISPLAY"):
        return ClipboardBackend.WL_COPY
    if os.environ.get("DISPLAY"):
        return ClipboardBackend.XCLIP

    raise RuntimeError(
        "Cannot detect display server. Set --clipboard explicitly or ensure "
        "$XDG_SESSION_TYPE / $WAYLAND_DISPLAY / $DISPLAY is set."
    )


def _check_tool(name: str) -> str:
    """Return the full path to a clipboard tool, or raise if missing."""
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(
            f"'{name}' not found. Install it with your package manager "
            f"(e.g. 'sudo pacman -S {name}' or 'sudo apt install {name}')."
        )
    return path


def _resolve_backend(backend: ClipboardBackend) -> ClipboardBackend:
    if backend is ClipboardBackend.AUTO:
        return detect_backend()
    return backend


def _video_mime(path: Path) -> str:
    return MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _copy_xclip(file_path: Path, method: CopyMethod) -> None:
    tool = _check_tool("xclip")
    abs_path = file_path.resolve()

    if method is CopyMethod.GNOME:
        payload = f"copy\nfile://{abs_path}".encode()
        mime = "x-special/gnome-copied-files"
    elif method is CopyMethod.URI:
        payload = f"file://{abs_path}\n".encode()
        mime = "text/uri-list"
    else:  # RAW
        payload = abs_path.read_bytes()
        mime = _video_mime(abs_path)

    subprocess.run(
        [tool, "-selection", "clipboard", "-t", mime, "-i"],
        input=payload,
        check=True,
    )


def _copy_wl(file_path: Path, method: CopyMethod) -> None:
    tool = _check_tool("wl-copy")
    abs_path = file_path.resolve()

    if method is CopyMethod.GNOME:
        payload = f"copy\nfile://{abs_path}".encode()
        mime = "x-special/gnome-copied-files"
    elif method is CopyMethod.URI:
        payload = f"file://{abs_path}\n".encode()
        mime = "text/uri-list"
    else:  # RAW
        payload = abs_path.read_bytes()
        mime = _video_mime(abs_path)

    subprocess.run(
        [tool, "--type", mime],
        input=payload,
        check=True,
    )


def copy_to_clipboard(
    file_path: Path,
    backend: ClipboardBackend = ClipboardBackend.AUTO,
    method: CopyMethod = CopyMethod.URI,
) -> ClipboardBackend:
    """Copy a file to the system clipboard.

    Returns the backend that was actually used.
    """
    resolved = _resolve_backend(backend)

    if resolved is ClipboardBackend.XCLIP:
        _copy_xclip(file_path, method)
    elif resolved is ClipboardBackend.WL_COPY:
        _copy_wl(file_path, method)
    else:
        raise ValueError(f"Unknown backend: {resolved}")

    return resolved
