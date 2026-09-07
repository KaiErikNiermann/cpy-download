"""Resolve Reddit post URLs to directly downloadable media URLs.

Reddit's unauthenticated surfaces are all closed as of 2026 -- ``/.json``,
``api.reddit.com`` and the post HTML each answer 403 or a JS stub -- which is
why yt-dlp's Reddit extractor fails with "Account authentication is required".

Two things still work without an account, and this module is built on them:

* the mobile app's *installed client* OAuth grant issues anonymous bearer
  tokens with no user attached, and ``oauth.reddit.com`` serves full post JSON
  to those tokens;
* the media CDN (``v.redd.it``) serves its DASH/HLS manifests with no auth and
  no signature -- the ``?a=`` token on the URLs Reddit hands back is not
  load-bearing.

So the account-free path is: anonymous token -> post JSON ->
``reddit_video.dash_url`` -> yt-dlp.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

# The Reddit for Android client id. The installed_client grant it enables is
# anonymous -- no account, no cookies -- but it is the one value here that
# could rot if Reddit ever rotates it.
_CLIENT_ID: Final = "ohXpoqrZYub1kg"
_DEVICE_ID: Final = "DO_NOT_TRACK_THIS_DEVICE"
_GRANT_TYPE: Final = "https://oauth.reddit.com/grants/installed_client"
_TOKEN_URL: Final = "https://www.reddit.com/api/v1/access_token"
_OAUTH_BASE: Final = "https://oauth.reddit.com"
_USER_AGENT: Final = "android:cpy-download:0.1.0 (+https://github.com/KaiErikNiermann/cpy-download)"
_TIMEOUT: Final = 20.0

# Tokens live 24h; expire ours early so a long download never straddles the edge.
_EXPIRY_MARGIN_S: Final = 300.0

_POST_HOSTS: Final = frozenset(
    {
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "new.reddit.com",
        "np.reddit.com",
        "m.reddit.com",
        "sh.reddit.com",
        "redd.it",
    }
)
_MEDIA_HOST: Final = "v.redd.it"

_COMMENTS_RE: Final = re.compile(r"^/(?:r/[^/]+/)?comments/(?P<id>[a-z0-9]+)", re.IGNORECASE)
_SHORTLINK_RE: Final = re.compile(r"^/(?P<id>[a-z0-9]+)/?$", re.IGNORECASE)
# /r/<sub>/s/<slug> share links redirect to the real permalink.
_SHARE_RE: Final = re.compile(r"^/r/[^/]+/s/[a-z0-9]+/?$", re.IGNORECASE)


class RedditMediaKind(StrEnum):
    """What kind of media a resolved Reddit post points at."""

    HOSTED_VIDEO = "hosted_video"  # v.redd.it, needs a DASH-aware format spec
    EXTERNAL = "external"  # links out (YouTube, Streamable, ...); yt-dlp knows these


@dataclass(frozen=True, slots=True)
class RedditMedia:
    """A Reddit post resolved down to something yt-dlp can fetch."""

    kind: RedditMediaKind
    url: str
    title: str | None = None
    has_audio: bool = True


class RedditError(RuntimeError):
    """Raised when a Reddit post cannot be resolved to a downloadable URL."""


@dataclass(frozen=True, slots=True)
class _Token:
    access_token: str
    expires_at: float

    @property
    def valid(self) -> bool:
        return time.time() < self.expires_at - _EXPIRY_MARGIN_S


def _cache_path() -> Path:
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base / "cpy-download" / "reddit-token.json"


def _http_json(request: urllib.request.Request) -> Any:
    """Perform a request and decode the JSON body."""
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RedditError(f"Reddit returned HTTP {exc.code} for {request.full_url}") from exc
    except urllib.error.URLError as exc:
        raise RedditError(f"Could not reach Reddit: {exc.reason}") from exc


def _load_cached_token() -> _Token | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        token = _Token(str(raw["access_token"]), float(raw["expires_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        # A corrupt cache is never worth failing over; just re-authenticate.
        logger.debug("Discarding unreadable token cache at %s", path)
        return None
    return token if token.valid else None


def _store_token(token: _Token) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"access_token": token.access_token, "expires_at": token.expires_at})
        )
        path.chmod(0o600)
    except OSError:
        logger.debug("Could not persist token cache to %s", path, exc_info=True)


def _fetch_token() -> _Token:
    """Request a fresh anonymous bearer token via the installed_client grant."""
    body = urllib.parse.urlencode({"grant_type": _GRANT_TYPE, "device_id": _DEVICE_ID}).encode()
    basic = base64.b64encode(f"{_CLIENT_ID}:".encode()).decode()
    payload = _http_json(
        urllib.request.Request(  # noqa: S310
            _TOKEN_URL,
            data=body,
            headers={"Authorization": f"Basic {basic}", "User-Agent": _USER_AGENT},
        )
    )
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RedditError("Reddit did not return an access token.")
    expires_in = float(payload.get("expires_in", 3600))
    return _Token(str(payload["access_token"]), time.time() + expires_in)


def _get_token() -> _Token:
    cached = _load_cached_token()
    if cached is not None:
        return cached
    token = _fetch_token()
    _store_token(token)
    return token


def _follow_share_link(url: str) -> str:
    """Resolve a /r/<sub>/s/<slug> share link to its canonical permalink."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
            return str(response.geturl())
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RedditError(f"Could not resolve Reddit share link: {exc}") from exc


def is_reddit_url(url: str) -> bool:
    """Whether this URL is a Reddit post or a Reddit-hosted media URL."""
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    return host in _POST_HOSTS or host == _MEDIA_HOST or f"www.{host}" in _POST_HOSTS


def extract_post_id(url: str) -> str | None:
    """Pull the base36 post id out of any Reddit post URL shape."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path

    if _SHARE_RE.match(path):
        path = urllib.parse.urlparse(_follow_share_link(url)).path

    if match := _COMMENTS_RE.match(path):
        return match.group("id")
    # Bare /<id> is only a post id on the redd.it shortener.
    if host.removeprefix("www.") == "redd.it" and (match := _SHORTLINK_RE.match(path)):
        return match.group("id")
    return None


def _fetch_post(post_id: str) -> dict[str, Any]:
    """Fetch a post's JSON from the OAuth API using an anonymous token."""
    token = _get_token()
    request = urllib.request.Request(  # noqa: S310
        f"{_OAUTH_BASE}/comments/{post_id}?raw_json=1",
        headers={"Authorization": f"Bearer {token.access_token}", "User-Agent": _USER_AGENT},
    )
    payload = _http_json(request)
    try:
        post = payload[0]["data"]["children"][0]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RedditError(f"Unexpected post JSON shape for {post_id}.") from exc
    if not isinstance(post, dict):
        raise RedditError(f"Unexpected post JSON shape for {post_id}.")
    return post


def _reddit_video(post: dict[str, Any]) -> dict[str, Any] | None:
    """Return the reddit_video block, looking through a crosspost if needed."""
    for source in (post.get("secure_media"), post.get("media")):
        if isinstance(source, dict) and isinstance(video := source.get("reddit_video"), dict):
            return video
    parents = post.get("crosspost_parent_list")
    if isinstance(parents, list) and parents and isinstance(parents[0], dict):
        return _reddit_video(parents[0])
    return None


def _external_url(post: dict[str, Any]) -> str | None:
    """The off-site URL a link post points at, if it is one."""
    if post.get("is_self"):
        return None
    candidate = post.get("url_overridden_by_dest") or post.get("url")
    if not isinstance(candidate, str):
        return None
    host = urllib.parse.urlparse(candidate).netloc.lower()
    # i.redd.it/preview links are images, not something yt-dlp should chase.
    if not host or host.endswith("redd.it") or "reddit.com" in host:
        return None
    return candidate


def _media_from_post(post: dict[str, Any]) -> RedditMedia:
    title = post.get("title") if isinstance(post.get("title"), str) else None

    if (video := _reddit_video(post)) is not None:
        dash = video.get("dash_url") or video.get("fallback_url")
        if not isinstance(dash, str):
            raise RedditError("Reddit video has no playable manifest URL.")
        return RedditMedia(
            kind=RedditMediaKind.HOSTED_VIDEO,
            url=dash,
            title=title,
            has_audio=bool(video.get("has_audio", True)),
        )

    if (external := _external_url(post)) is not None:
        return RedditMedia(kind=RedditMediaKind.EXTERNAL, url=external, title=title)

    raise RedditError(
        "This Reddit post has no video (it looks like a text, image or gallery post)."
    )


def resolve(url: str) -> RedditMedia:
    """Resolve a Reddit URL to a directly downloadable media URL.

    Raises ``RedditError`` if the post carries no downloadable video.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() == _MEDIA_HOST:
        # Already a v.redd.it URL -- go straight to its manifest.
        if video_id := parsed.path.strip("/").split("/")[0]:
            return RedditMedia(
                kind=RedditMediaKind.HOSTED_VIDEO,
                url=f"https://{_MEDIA_HOST}/{video_id}/DASHPlaylist.mpd",
            )
        raise RedditError(f"Could not read a video id from {url}")

    post_id = extract_post_id(url)
    if post_id is None:
        raise RedditError(f"Not a recognisable Reddit post URL: {url}")
    return _media_from_post(_fetch_post(post_id))
