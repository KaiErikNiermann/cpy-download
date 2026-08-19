"""CLI for cpy-download."""

from __future__ import annotations

# Typer resolves these annotations at runtime, so Path must be a real import
# rather than a TYPE_CHECKING-only one.
from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from .clipboard import ClipboardBackend, CopyMethod, copy_to_clipboard
from .downloader import download_video

app = typer.Typer(
    name="cpydl",
    help="Download a video from a URL and copy it to your Linux clipboard.",
    no_args_is_help=True,
)


@app.command()
def grab(
    url: Annotated[
        str, typer.Argument(help="URL of the video to download (Twitter, YouTube, etc.)")
    ],
    clipboard: Annotated[
        ClipboardBackend,
        typer.Option("--clipboard", "-c", help="Clipboard backend to use."),
    ] = ClipboardBackend.AUTO,
    method: Annotated[
        CopyMethod,
        typer.Option("--method", "-m", help="How to place the file on the clipboard."),
    ] = CopyMethod.URI,
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="yt-dlp format spec."),
    ] = "best[ext=mp4]/best",
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir", "-o", help="Directory to save the video. Defaults to a temp dir."
        ),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option("--keep/--no-keep", help="Keep the downloaded file after copying."),
    ] = True,
) -> None:
    """Download a video and copy it to your clipboard."""
    typer.echo(f"Downloading: {url}")

    try:
        video_path = download_video(url, output_dir=output_dir, format_spec=format)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.echo(f"Download failed: {exc}", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"Downloaded: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

    try:
        used = copy_to_clipboard(video_path, backend=clipboard, method=method)
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"Clipboard error: {exc}", err=True)
        typer.echo(f"Video is still available at: {video_path}")
        raise typer.Exit(1) from None

    typer.echo(f"Copied to clipboard via {used.value} (method: {method.value})")

    if not keep and output_dir is None:
        video_path.unlink(missing_ok=True)
        typer.echo("Temp file cleaned up.")
    else:
        typer.echo(f"File saved at: {video_path}")


@app.command()
def copy(
    file: Annotated[Path, typer.Argument(help="Path to a local video file to copy to clipboard.")],
    clipboard: Annotated[
        ClipboardBackend,
        typer.Option("--clipboard", "-c", help="Clipboard backend to use."),
    ] = ClipboardBackend.AUTO,
    method: Annotated[
        CopyMethod,
        typer.Option("--method", "-m", help="How to place the file on the clipboard."),
    ] = CopyMethod.URI,
) -> None:
    """Copy a local video file to the clipboard (no download)."""
    if not file.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(1)

    try:
        used = copy_to_clipboard(file, backend=clipboard, method=method)
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"Clipboard error: {exc}", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"Copied {file.name} to clipboard via {used.value} (method: {method.value})")


@app.command()
def version() -> None:
    """Show the version."""
    from . import __version__

    typer.echo(f"cpydl {__version__}")


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
