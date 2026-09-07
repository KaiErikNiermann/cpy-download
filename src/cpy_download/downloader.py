"""Video downloader using yt-dlp."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .reddit import RedditError, RedditMediaKind, is_reddit_url
from .reddit import resolve as resolve_reddit

logger = logging.getLogger(__name__)

# Muxed-stream sources (YouTube, Twitter, ...) where a single file is available.
DEFAULT_FORMAT: Final = "best[ext=mp4]/best"
# Reddit's DASH manifests carry *only* video-only and audio-only streams, so a
# muxed-only spec like DEFAULT_FORMAT fails outright with "Requested format is
# not available". Pick the best of each and let ffmpeg merge them.
DASH_FORMAT: Final = "bv*+ba/b"


@dataclass(frozen=True, slots=True)
class DownloadTarget:
    """A URL resolved to something yt-dlp can fetch, plus how to fetch it."""

    url: str
    format_spec: str
    title: str | None = None


def _check_ytdlp() -> str:
    path = shutil.which("yt-dlp")
    if path is None:
        raise FileNotFoundError(
            "yt-dlp not found. Install it: 'pip install yt-dlp' or "
            "'sudo pacman -S yt-dlp' / 'sudo apt install yt-dlp'."
        )
    return path


def _check_ffmpeg() -> None:
    """Merging separate audio/video streams needs ffmpeg on PATH."""
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError(
            "ffmpeg not found, but this download needs it to merge separate "
            "audio and video streams. Install it: 'sudo pacman -S ffmpeg' / "
            "'sudo apt install ffmpeg'."
        )


def resolve_target(url: str, format_spec: str | None = None) -> DownloadTarget:
    """Resolve a URL to a fetchable target, choosing a format spec if none given.

    Reddit posts are resolved through the anonymous OAuth API because yt-dlp's
    own Reddit extractor now requires account credentials.
    """
    if not is_reddit_url(url):
        return DownloadTarget(url=url, format_spec=format_spec or DEFAULT_FORMAT)

    media = resolve_reddit(url)
    logger.debug("Resolved Reddit URL to %s: %s", media.kind, media.url)

    if media.kind is RedditMediaKind.HOSTED_VIDEO:
        return DownloadTarget(
            url=media.url,
            format_spec=format_spec or DASH_FORMAT,
            title=media.title,
        )
    # An off-site link post: hand the destination to yt-dlp's own extractor.
    return DownloadTarget(
        url=media.url,
        format_spec=format_spec or DEFAULT_FORMAT,
        title=media.title,
    )


def _sanitize_title(title: str) -> str:
    """Make a title safe for use as a literal in a yt-dlp output template."""
    cleaned = title.replace("%", "%%").replace("/", "-")
    cleaned = "".join(ch for ch in cleaned if ch.isprintable()).strip()
    return cleaned[:80] or "video"


def _output_template(output_dir: Path, title: str | None) -> str:
    """Build the -o template, substituting a known title when we have one.

    Reddit DASH manifests go through yt-dlp's generic extractor, whose idea of
    the title is the literal string "DASHPlaylist" -- so when the Reddit API
    already gave us the real post title, bake it in instead.
    """
    if title is None:
        return str(output_dir / "%(title).80s.%(ext)s")
    return str(output_dir / f"{_sanitize_title(title)}.%(ext)s")


def _ytdlp_error(stderr: str) -> str:
    """Extract the meaningful ERROR lines from yt-dlp's stderr."""
    errors = [line.strip() for line in stderr.splitlines() if line.strip().startswith("ERROR:")]
    return "\n".join(errors) if errors else stderr.strip()


def download_video(
    url: str,
    output_dir: Path | None = None,
    format_spec: str | None = None,
) -> Path:
    """Download a video from a URL using yt-dlp.

    Returns the path to the downloaded file.
    """
    ytdlp = _check_ytdlp()
    target = resolve_target(url, format_spec)

    # "+" in a format spec means two streams that ffmpeg has to mux together.
    needs_merge = "+" in target.format_spec
    if needs_merge:
        _check_ffmpeg()

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="cpydl_"))

    command = [
        ytdlp,
        "--no-playlist",
        "-f",
        target.format_spec,
        "-o",
        _output_template(output_dir, target.title),
        "--print",
        "after_move:filepath",
        "--no-simulate",
    ]
    if needs_merge:
        command += ["--merge-output-format", "mp4"]
    command.append(target.url)

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # check=True would hide yt-dlp's stderr behind an opaque exit-status
        # message, which is exactly what made Reddit's auth wall hard to read.
        raise RuntimeError(f"yt-dlp failed:\n{_ytdlp_error(result.stderr)}")

    # yt-dlp --print filepath outputs the final path on the last non-empty line
    lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"yt-dlp did not output a file path.\nstderr: {result.stderr}")

    downloaded = Path(lines[-1])
    if not downloaded.exists():
        raise FileNotFoundError(
            f"yt-dlp reported path does not exist: {downloaded}\nstderr: {result.stderr}"
        )

    return downloaded


__all__ = [
    "DASH_FORMAT",
    "DEFAULT_FORMAT",
    "DownloadTarget",
    "RedditError",
    "download_video",
    "resolve_target",
]
