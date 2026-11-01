"""#299: a source's kind (its icon) told by its address."""

import pytest

from portalab.modules.news.sources.kinds import source_kind


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://www.youtube.com/feeds/videos.xml?channel_id=UC_x", "youtube"),
        ("https://vimeo.com/channels/staffpicks/videos/rss", "video"),
        ("https://feeds.acast.com/public/shows/abc", "podcast"),
        ("https://radiofrance-podcast.net/podcast09/rss_1.xml", "podcast"),
        ("https://www.reddit.com/r/movies/.rss", "reddit"),
        ("https://www.allocine.fr/rss/news.xml", "rss"),
        ("not an address", "rss"),
    ],
)
def test_a_source_s_kind_comes_from_its_address(url: str, kind: str) -> None:
    assert source_kind(url) == kind
