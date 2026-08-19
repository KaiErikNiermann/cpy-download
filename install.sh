#!/bin/env zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"

echo "Installing cpydl..."

# Install the package with pipx (isolated global install)
if command -v pipx &>/dev/null; then
    pipx install "$SCRIPT_DIR" --force
elif command -v pip &>/dev/null; then
    echo "pipx not found, falling back to pip install --user"
    pip install --user "$SCRIPT_DIR"
else
    echo "Error: neither pipx nor pip found. Install one first." >&2
    exit 1
fi

# Check for yt-dlp
if ! command -v yt-dlp &>/dev/null; then
    echo "Warning: yt-dlp not found. Install it for download support:"
    echo "  pipx install yt-dlp  OR  sudo pacman -S yt-dlp  OR  sudo apt install yt-dlp"
fi

# Check for clipboard tool
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    if ! command -v wl-copy &>/dev/null; then
        echo "Warning: wl-copy not found. Install wl-clipboard:"
        echo "  sudo pacman -S wl-clipboard  OR  sudo apt install wl-clipboard"
    fi
else
    if ! command -v xclip &>/dev/null; then
        echo "Warning: xclip not found. Install it:"
        echo "  sudo pacman -S xclip  OR  sudo apt install xclip"
    fi
fi

echo "Done. Run 'cpydl --help' to get started."
