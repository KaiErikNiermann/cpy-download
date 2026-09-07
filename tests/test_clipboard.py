"""Tests for clipboard module."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from cpy_download.clipboard import (
    ClipboardBackend,
    CopyMethod,
    _copy_wl,
    _copy_xclip,
    _video_mime,
    detect_backend,
)


class TestDetectBackend:
    def test_wayland_via_session_type(self) -> None:
        env = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_backend() == ClipboardBackend.WL_COPY

    def test_x11_via_session_type(self) -> None:
        env = {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_backend() == ClipboardBackend.XCLIP

    def test_wayland_fallback(self) -> None:
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_backend() == ClipboardBackend.WL_COPY

    def test_x11_fallback(self) -> None:
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ":0"}
        with patch.dict(os.environ, env, clear=False):
            assert detect_backend() == ClipboardBackend.XCLIP

    def test_no_display_raises(self) -> None:
        env = {"XDG_SESSION_TYPE": "", "WAYLAND_DISPLAY": "", "DISPLAY": ""}
        with (
            patch.dict(os.environ, env, clear=False),
            pytest.raises(RuntimeError, match="Cannot detect display server"),
        ):
            detect_backend()


class TestVideoMime:
    def test_mp4(self) -> None:
        assert _video_mime(Path("test.mp4")) == "video/mp4"

    def test_webm(self) -> None:
        assert _video_mime(Path("test.webm")) == "video/webm"

    def test_unknown(self) -> None:
        assert _video_mime(Path("test.xyz")) == "application/octet-stream"

    def test_case_insensitive(self) -> None:
        assert _video_mime(Path("test.MP4")) == "video/mp4"


class TestDetachedStdio:
    """The resident clipboard daemon must not inherit our stdout/stderr.

    xclip and wl-copy both stay alive after we return, to serve the selection
    they own. If they inherit a pipe -- as they do under `cpydl ... 2>&1 | x`
    -- they hold its write end open and the reader never sees EOF, so the whole
    pipeline hangs long after cpydl has finished its work.
    """

    @pytest.mark.parametrize(
        ("copy_fn", "tool"),
        [(_copy_xclip, "xclip"), (_copy_wl, "wl-copy")],
    )
    def test_daemon_stdio_is_detached(self, copy_fn: object, tool: str, tmp_path: Path) -> None:
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"data")

        with (
            patch("cpy_download.clipboard.shutil.which", return_value=f"/usr/bin/{tool}"),
            patch("cpy_download.clipboard.subprocess.run") as run,
        ):
            copy_fn(video, CopyMethod.URI)  # type: ignore[operator]

        kwargs = run.call_args.kwargs
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
