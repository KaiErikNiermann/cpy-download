# cpy-download

Download videos from URLs and copy them to your Linux clipboard.

## Installation

```bash
./install.sh
```

### Requirements

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for downloading videos
- `ffmpeg` for Reddit videos, whose audio and video arrive as separate streams
- `xclip` (X11) or `wl-copy` (Wayland) for clipboard access

## Usage

```bash
# Download a video and copy to clipboard
cpydl grab https://example.com/video

# Reddit posts work too, including crossposts and share links
cpydl grab https://www.reddit.com/r/aviation/comments/1w9bl1g/

# Copy a local video file to clipboard
cpydl copy ./video.mp4

# Show version
cpydl version
```

### Reddit

Reddit closed its unauthenticated surfaces, so yt-dlp's own Reddit extractor now
fails with `Account authentication is required`. `cpydl` routes around this
without needing an account or browser cookies: it takes an anonymous OAuth token
via the mobile app's `installed_client` grant, reads the post from
`oauth.reddit.com`, and hands the resulting `v.redd.it` DASH manifest to yt-dlp.
The token is cached under `$XDG_CACHE_HOME/cpy-download/`.

Reddit's DASH streams are video-only plus audio-only, never muxed, so a
muxed-only format spec fails outright rather than merely dropping audio. `cpydl`
selects `bv*+ba/b` for these automatically; `--format` still overrides it.

## Project Structure

```
cpy-download/
├── src/
│   └── cpy_download/
│       ├── __init__.py
│       ├── cli.py
│       ├── clipboard.py
│       ├── downloader.py
│       └── reddit.py
├── tests/
│   ├── test_basic.py
│   ├── test_clipboard.py
│   ├── test_cli.py
│   └── test_reddit.py
├── pyproject.toml
└── README.md
```

## Development

```bash
poetry install

poetry run pytest                                          # tests
poetry run ruff check src tests                            # lint
poetry run ruff format --check src tests                   # formatting
poetry run mypy src                                        # types
poetry run radon cc src --average --show-complexity        # complexity report
poetry run xenon --max-absolute B --max-modules B --max-average A src   # complexity gate
```

CI runs all of the above on Python 3.11-3.14.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT - see the [LICENSE](LICENSE) file for details.
