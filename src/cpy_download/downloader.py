"""Video downloader using yt-dlp."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _check_ytdlp() -> str:
    path = shutil.which("yt-dlp")
    if path is None:
        raise FileNotFoundError(
            "yt-dlp not found. Install it: 'pip install yt-dlp' or "
            "'sudo pacman -S yt-dlp' / 'sudo apt install yt-dlp'."
        )
    return path


def download_video(
    url: str,
    output_dir: Path | None = None,
    format_spec: str = "best[ext=mp4]/best",
) -> Path:
    """Download a video from a URL using yt-dlp.

    Returns the path to the downloaded file.
    """
    ytdlp = _check_ytdlp()

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="cpydl_"))

    output_template = str(output_dir / "%(title).80s.%(ext)s")

    result = subprocess.run(
        [
            ytdlp,
            "--no-playlist",
            "-f",
            format_spec,
            "-o",
            output_template,
            "--print",
            "after_move:filepath",
            "--no-simulate",
            url,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

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
