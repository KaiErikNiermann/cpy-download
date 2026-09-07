"""Tests for Reddit URL resolution and the DASH-aware download path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cpy_download import downloader, reddit
from cpy_download.downloader import DASH_FORMAT, DEFAULT_FORMAT, resolve_target
from cpy_download.reddit import (
    RedditError,
    RedditMedia,
    RedditMediaKind,
    extract_post_id,
    is_reddit_url,
)

DASH_URL = "https://v.redd.it/s88vuiumhznh1/DASHPlaylist.mpd?a=1&v=1&f=sd"


def _video_post(**overrides: Any) -> dict[str, Any]:
    post: dict[str, Any] = {
        "title": "A plane doing something regrettable",
        "is_video": True,
        "secure_media": {"reddit_video": {"dash_url": DASH_URL, "has_audio": True}},
    }
    return post | overrides


@pytest.mark.parametrize(
    "url",
    [
        "https://www.reddit.com/r/aviation/comments/1w9bl1g/title/",
        "https://old.reddit.com/r/aviation/comments/1w9bl1g/title/",
        "https://reddit.com/comments/1w9bl1g",
        "https://redd.it/1w9bl1g",
        "https://v.redd.it/s88vuiumhznh1",
    ],
)
def test_is_reddit_url_accepts_reddit_shapes(url: str) -> None:
    assert is_reddit_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://x.com/user/status/1",
        "https://notreddit.com/r/x/comments/abc/t/",
    ],
)
def test_is_reddit_url_rejects_others(url: str) -> None:
    assert not is_reddit_url(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.reddit.com/r/aviation/comments/1w9bl1g/title/", "1w9bl1g"),
        ("https://old.reddit.com/r/aviation/comments/1w9bl1g/title/", "1w9bl1g"),
        ("https://reddit.com/comments/1w9bl1g", "1w9bl1g"),
        ("https://redd.it/1w9bl1g", "1w9bl1g"),
        ("https://www.youtube.com/watch?v=abc", None),
    ],
)
def test_extract_post_id(url: str, expected: str | None) -> None:
    assert extract_post_id(url) == expected


def test_hosted_video_is_resolved_to_its_dash_manifest() -> None:
    media = reddit._media_from_post(_video_post())
    assert media.kind is RedditMediaKind.HOSTED_VIDEO
    assert media.url == DASH_URL
    assert media.has_audio


def test_video_is_found_through_a_crosspost() -> None:
    post = {
        "title": "crossposted",
        "secure_media": None,
        "media": None,
        "crosspost_parent_list": [_video_post()],
    }
    assert reddit._media_from_post(post).url == DASH_URL


def test_link_post_falls_back_to_the_external_url() -> None:
    post = {"title": "look", "is_self": False, "url": "https://www.youtube.com/watch?v=abc"}
    media = reddit._media_from_post(post)
    assert media.kind is RedditMediaKind.EXTERNAL
    assert media.url == "https://www.youtube.com/watch?v=abc"


@pytest.mark.parametrize(
    "post",
    [
        {"title": "just text", "is_self": True},
        {"title": "an image", "is_self": False, "url": "https://i.redd.it/abc.jpg"},
    ],
)
def test_posts_without_video_raise(post: dict[str, Any]) -> None:
    with pytest.raises(RedditError):
        reddit._media_from_post(post)


def test_direct_media_url_skips_the_api() -> None:
    media = reddit.resolve("https://v.redd.it/s88vuiumhznh1")
    assert media.url == "https://v.redd.it/s88vuiumhznh1/DASHPlaylist.mpd"


def test_reddit_target_uses_a_dash_aware_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reddit DASH has no muxed stream, so the muxed-only default must not be used."""
    monkeypatch.setattr(
        downloader,
        "resolve_reddit",
        lambda _url: RedditMedia(RedditMediaKind.HOSTED_VIDEO, DASH_URL, "Title", True),
    )
    target = resolve_target("https://www.reddit.com/r/a/comments/1w9bl1g/t/")
    assert target.format_spec == DASH_FORMAT
    assert target.url == DASH_URL
    assert target.title == "Title"


def test_explicit_format_overrides_the_per_source_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        downloader,
        "resolve_reddit",
        lambda _url: RedditMedia(RedditMediaKind.HOSTED_VIDEO, DASH_URL, None, True),
    )
    target = resolve_target("https://www.reddit.com/r/a/comments/1w9bl1g/t/", "worst")
    assert target.format_spec == "worst"


def test_non_reddit_urls_pass_through_untouched() -> None:
    target = resolve_target("https://www.youtube.com/watch?v=abc")
    assert target.url == "https://www.youtube.com/watch?v=abc"
    assert target.format_spec == DEFAULT_FORMAT
    assert target.title is None


def test_known_title_is_baked_into_the_output_template() -> None:
    """The generic extractor would otherwise name every Reddit file DASHPlaylist."""
    template = downloader._output_template(Path("/tmp/x"), "100% real / footage")
    assert template == "/tmp/x/100%% real - footage.%(ext)s"


def test_output_template_falls_back_to_ytdlp_title() -> None:
    assert downloader._output_template(Path("/tmp/x"), None) == "/tmp/x/%(title).80s.%(ext)s"


def test_ytdlp_error_surfaces_the_error_lines() -> None:
    stderr = (
        "WARNING: Your yt-dlp version is old\n"
        "ERROR: [Reddit] 1w9bl1g: Account authentication is required.\n"
    )
    assert downloader._ytdlp_error(stderr) == (
        "ERROR: [Reddit] 1w9bl1g: Account authentication is required."
    )
