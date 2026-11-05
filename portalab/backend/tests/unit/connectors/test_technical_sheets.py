"""#354: a title's technical sheet read from Plex and Jellyfin — its files and streams (video, audio tracks,
subtitles) and when it was added — and Radarr's grab: the release, its indexer, the client, the torrent."""

from datetime import UTC, datetime

from portalab.connectors.arr import acquisition_events
from portalab.connectors.jellyfin.technical import sheet_of as jellyfin_sheet
from portalab.connectors.plex.technical import sheet_of as plex_sheet

PLEX = {
    "addedAt": 1759712337,
    "Media": [
        {
            "bitrate": 18500,
            "container": "mkv",
            "duration": 9000000,
            "Part": [
                {
                    "file": "/movies/Spider-Man (2026)/Spider-Man.mkv",
                    "size": 20812345678,
                    "container": "mkv",
                    "Stream": [
                        {"streamType": 1, "codec": "hevc", "height": 2160, "DOVIPresent": True,
                         "displayTitle": "4K DoVi/HDR10 (HEVC Main 10)", "bitrate": 16000},
                        {"streamType": 2, "codec": "eac3", "language": "Français",
                         "audioChannelLayout": "5.1(side)", "extendedDisplayTitle": "Français (EAC3 5.1)",
                         "default": True},
                        {"streamType": 2, "codec": "truehd", "language": "English", "channels": 8},
                        {"streamType": 3, "codec": "srt", "language": "Français", "forced": True},
                        {"streamType": 4, "codec": "mjpeg"},
                    ],
                }
            ],
        }
    ],
}  # fmt: skip


def test_plex_technical_sheet() -> None:
    sheet = plex_sheet(PLEX)
    assert sheet.added_at == datetime.fromtimestamp(1759712337, UTC)
    [file] = sheet.files
    assert file.path == "/movies/Spider-Man (2026)/Spider-Man.mkv" and file.size == 20812345678
    assert file.duration_s == 9000.0 and file.container == "mkv" and file.bitrate == 18500
    video, french, english, subtitles = file.streams  # no image stream
    assert (video.kind, video.resolution, video.dynamic_range) == ("video", "2160p", "Dolby Vision")
    assert (french.kind, french.language, french.channels, french.default) == (
        "audio",
        "Français",
        "5.1(side)",
        True,
    )
    assert french.title == "Français (EAC3 5.1)" and english.channels == "8"
    assert (subtitles.kind, subtitles.codec, subtitles.forced) == ("subtitle", "srt", True)


def test_jellyfin_technical_sheet() -> None:
    sheet = jellyfin_sheet(
        {
            "DateCreated": "2026-10-06T01:38:57.0000000Z",
            "MediaSources": [
                {
                    "Path": "/media/films/Alien.mkv",
                    "Size": 4_000_000_000,
                    "Container": "mkv",
                    "RunTimeTicks": 70_000_000_000,
                    "Bitrate": 9_000_000,
                    "MediaStreams": [
                        {
                            "Type": "Video",
                            "Codec": "h264",
                            "Height": 1080,
                            "VideoRangeType": "SDR",
                            "BitRate": 8_000_000,
                        },
                        {
                            "Type": "Audio",
                            "Codec": "ac3",
                            "Language": "fre",
                            "ChannelLayout": "5.1",
                            "IsDefault": True,
                        },
                        {"Type": "Subtitle", "Codec": "subrip", "Language": "eng", "IsForced": False},
                    ],
                }
            ],
        }
    )
    assert sheet.added_at == datetime(2026, 10, 6, 1, 38, 57, tzinfo=UTC)
    [file] = sheet.files
    assert file.duration_s == 7000.0 and file.bitrate == 9000
    video, audio, subtitles = file.streams
    assert (video.resolution, video.dynamic_range, video.bitrate) == ("1080p", "SDR", 8000)
    assert (audio.language, audio.channels, audio.default) == ("fre", "5.1", True)
    assert subtitles.kind == "subtitle" and subtitles.language == "eng"


def test_radarr_grab_tells_its_indexer_and_torrent() -> None:
    [grabbed] = acquisition_events(
        [
            {
                "eventType": "grabbed",
                "date": "2026-10-05T05:20:00Z",
                "sourceTitle": "Spider-Man.Brand.New.Day.2026.MULTi.1080p.WEB.x264-GRP",
                "downloadId": "ABCDEF0123456789",
                "data": {"indexer": "YggTorrent (Prowlarr)", "downloadClient": "Deluge"},
            }
        ]
    )
    assert grabbed.release == "Spider-Man.Brand.New.Day.2026.MULTi.1080p.WEB.x264-GRP"
    assert (grabbed.indexer, grabbed.client, grabbed.download_id) == (
        "YggTorrent (Prowlarr)",
        "Deluge",
        "ABCDEF0123456789",
    )
