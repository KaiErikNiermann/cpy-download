# cpy-download

Download videos from URLs and copy them to your Linux clipboard.

## Installation

```bash
./install.sh
```

### Requirements

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for downloading videos
- `xclip` (X11) or `wl-copy` (Wayland) for clipboard access

## Usage

```bash
# Download a video and copy to clipboard
cpydl grab https://example.com/video

# Copy a local video file to clipboard
cpydl copy ./video.mp4

# Show version
cpydl version
```

## Project Structure

```
cpy-download/
├── src/
│   └── cpy_download/
│       ├── __init__.py
│       ├── cli.py
│       ├── clipboard.py
│       └── downloader.py
├── tests/
│   ├── test_basic.py
│   └── test_clipboard.py
├── pyproject.toml
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

See the [LICENSE](LICENSE) file for details.
