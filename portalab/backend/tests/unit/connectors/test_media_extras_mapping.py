"""Issue 465 — each service's videos and extra pictures, as the portal tells them: YouTube ids checked, kinds
named, pictures only from the services' own image hosts, the RomM screenshots kept local."""

from portalab.capabilities.media import Artwork, ExtraVideo, MediaExtras
from portalab.connectors.fanart import extra_images
from portalab.connectors.igdb import map_details, map_videos, video_kind
from portalab.connectors.plex import map_extras as plex_extras
from portalab.connectors.romm import game_extras
from portalab.connectors.thetvdb import map_trailers
from portalab.connectors.tmdb import map_extras as tmdb_extras
from portalab.modules.media.extras import arrange


def test_tmdb_youtube_videos_and_backdrops() -> None:
    told = tmdb_extras(
        {
            "videos": {
                "results": [
                    {
                        "site": "YouTube",
                        "key": "abcdefghijk",
                        "type": "Trailer",
                        "name": "T",
                        "iso_639_1": "fr",
                    },
                    {"site": "YouTube", "key": "bcdefghijkl", "type": "Behind the Scenes", "official": True},
                    {"site": "Vimeo", "key": "123", "type": "Trailer"},
                    {"site": "YouTube", "key": "short", "type": "Trailer"},
                    {"site": "YouTube", "key": "cdefghijklm", "type": "Opening Credits"},
                ]
            },
            "images": {
                "backdrops": [
                    {"file_path": "/text.jpg", "iso_639_1": "en", "vote_average": 9},
                    {"file_path": "/bare.jpg", "iso_639_1": None, "vote_average": 5},
                    {"file_path": "../etc/passwd"},
                ]
            },
        }
    )
    assert [(v.key, v.kind, v.language) for v in told.videos] == [
        ("abcdefghijk", "trailer", "fr"),
        ("bcdefghijkl", "behind_the_scenes", None),
        ("cdefghijklm", "other", None),
    ]
    assert told.videos[1].official
    assert [(i.ref, i.lang) for i in told.images] == [("/bare.jpg", None), ("/text.jpg", "en")]


def test_fanart_backgrounds_and_thumbs_only() -> None:
    images = extra_images(
        [
            Artwork("logo", "/fanart/logo.png", None, 50),
            Artwork("thumb", "/fanart/thumb.jpg", "en", 3),
            Artwork("background", "/fanart/b1.jpg", "fr", 9),
            Artwork("background", "/fanart/b2.jpg", None, 1),
        ]
    )
    assert [(i.kind, i.ref) for i in images] == [
        ("fanart", "/fanart/b2.jpg"),
        ("fanart", "/fanart/b1.jpg"),
        ("still", "/fanart/thumb.jpg"),
    ]


def test_tvdb_trailers_on_youtube() -> None:
    trailers = map_trailers(
        {
            "trailers": [
                {
                    "url": "https://www.youtube.com/watch?v=abcdefghijk&t=3",
                    "name": "Bande",
                    "language": "fra",
                },
                {"url": "https://youtu.be/bcdefghijkl", "language": "xyz", "runtime": 95},
                {"url": "https://vimeo.com/1"},
                {"url": "https://www.youtube.com/watch?v=abcdefghijk<script>"},
            ]
        }
    )
    assert [(t.key, t.language, t.duration_s) for t in trailers] == [
        ("abcdefghijk", "fr", None),
        ("bcdefghijkl", None, 95.0),
    ]
    assert map_trailers(None) == [] and map_trailers({"trailers": "nope"}) == []


def test_plex_extras_named_and_kinded() -> None:
    videos = plex_extras(
        {
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "51",
                        "title": "Trailer",
                        "subtype": "trailer",
                        "duration": 120000,
                        "thumb": "/t",
                    },
                    {"ratingKey": "52", "title": "Making of", "extraType": 5},
                    {"ratingKey": "53", "title": "Odd", "extraType": "x"},
                    {"ratingKey": "../54", "title": "Bad"},
                    {"title": "No key"},
                ]
            }
        }
    )
    assert [(v.site, v.key, v.kind, v.duration_s, v.picture) for v in videos] == [
        ("service", "51", "trailer", 120.0, "51"),
        ("service", "52", "behind_the_scenes", None, None),
        ("service", "53", "other", None, None),
    ]


def test_igdb_every_video_named_and_its_pictures_apart() -> None:
    assert video_kind("Official Gameplay Reveal") == "gameplay"
    assert video_kind("Teaser trailer") == "teaser"
    assert video_kind("Launch Trailer") == "trailer"
    assert video_kind("Soundtrack") == "other"
    videos = map_videos([{"video_id": "abcdefghijk", "name": "Gameplay"}, {"video_id": "bad"}, "nope"])
    assert videos == [ExtraVideo(site="youtube", key="abcdefghijk", name="Gameplay", kind="gameplay")]
    game = map_details(
        {
            "id": 7,
            "name": "Game",
            "screenshots": [{"image_id": "sc1"}, {"image_id": "BAD!"}],
            "artworks": [{"image_id": "ar1"}],
            "videos": [{"video_id": "abcdefghijk", "name": "Trailer"}],
        }
    )
    assert game is not None
    assert list(game.screenshots) == ["sc1"] and list(game.artworks) == ["ar1"]
    assert game.trailer == "abcdefghijk" and game.videos[0].kind == "trailer"


def test_romm_video_and_local_screenshots() -> None:
    told = game_extras(
        {
            "youtube_video_id": "abcdefghijk",
            "path_screenshots": ["roms/1/2/screenshots/0.jpg", "../../etc/passwd"],
            "merged_screenshots": [
                "/assets/romm/resources/roms/1/2/screenshots/0.jpg?ts=1",  # the same one, spelt otherwise
                "https://images.igdb.com/igdb/image/upload/t_original/x.jpg",  # remote: left out
            ],
        }
    )
    assert [(v.key, v.kind) for v in told.videos] == [("abcdefghijk", "other")]  # RomM tells no kind
    assert [i.ref for i in told.images] == ["/assets/romm/resources/roms/1/2/screenshots/0.jpg"]
    assert game_extras({"youtube_video_id": "<b>x</b>"}).videos == []


def test_arranged_once_each_trailers_first_the_members_language_first() -> None:
    found = [
        (
            "a",
            MediaExtras(
                videos=[
                    ExtraVideo(site="youtube", key="abcdefghijk", kind="featurette"),
                    ExtraVideo(site="youtube", key="bcdefghijkl", kind="trailer", language="en"),
                    ExtraVideo(site="youtube", key="cdefghijklm", kind="trailer", language="fr"),
                ]
            ),
        ),
        (
            "b",
            MediaExtras(
                videos=[
                    ExtraVideo(site="youtube", key="cdefghijklm", name="Bande-annonce", kind="trailer"),
                    ExtraVideo(site="service", key="9", kind="trailer"),
                ]
            ),
        ),
    ]
    arranged = arrange(found, "fr-FR")
    assert [v.video.key for v in arranged.videos] == ["cdefghijklm", "9", "bcdefghijkl", "abcdefghijk"]
    first = arranged.videos[0].video
    assert (first.name, first.language) == ("Bande-annonce", "fr")  # what both tellings know, together
    # a video told without its kind (RomM's) takes the kind another service tells (IGDB's)
    games = arrange(
        [
            ("romm", MediaExtras(videos=[ExtraVideo(site="youtube", key="abcdefghijk")])),
            ("igdb", MediaExtras(videos=[ExtraVideo(site="youtube", key="abcdefghijk", kind="gameplay")])),
        ],
        "en",
    )
    assert games.videos[0].video.kind == "gameplay"
