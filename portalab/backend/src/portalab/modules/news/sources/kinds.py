"""#299: what kind of source a feed is, told by its address — a YouTube channel, another video site, a
podcast, a forum (Reddit) or a plain site's RSS/Atom feed — so each shows its own icon beside its name."""

from typing import Literal
from urllib.parse import urlsplit

SourceKind = Literal["youtube", "video", "podcast", "reddit", "rss"]

_VIDEO = ("vimeo.com", "dailymotion.com", "peertube", "odysee.com", "rumble.com")
_PODCAST = (
    "anchor.fm",
    "acast.com",
    "ausha.co",
    "audioboom.com",
    "megaphone.fm",
    "simplecast.com",
    "art19.com",
    "podbean.com",
    "spreaker.com",
    "libsyn.com",
    "buzzsprout.com",
    "transistor.fm",
    "podcasts.apple.com",
    "radiofrance-podcast.net",
)


def source_kind(url: str) -> SourceKind:
    host = (urlsplit(url).hostname or "").lower()

    def on(*sites: str) -> bool:
        return any(host == site or host.endswith(f".{site}") or site in host for site in sites)

    if on("youtube.com", "youtu.be"):
        return "youtube"
    if on(*_VIDEO):
        return "video"
    if on(*_PODCAST) or "podcast" in host:
        return "podcast"
    if on("reddit.com"):
        return "reddit"
    return "rss"
