"""Tests for clipboard module."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cpy_download.clipboard import (
    ClipboardBackend,
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
