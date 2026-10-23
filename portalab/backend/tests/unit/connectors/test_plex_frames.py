"""Issue 230: still images of a film's own Plex file — which file, how long, HDR or not, and the command."""

from portalab.connectors.plex.frames import command, part_of


def test_a_films_file_its_length_and_hdr() -> None:
    item = {
        "duration": 10_140_000,
        "Media": [
            {
                "Part": [
                    {
                        "key": "/library/parts/42/1700000000/file.mkv",
                        "Stream": [{"streamType": 1, "colorTrc": "smpte2084"}, {"streamType": 2}],
                    }
                ]
            }
        ],
    }
    assert part_of(item) == ("/library/parts/42/1700000000/file.mkv", 10140.0, True)
    item["Media"][0]["Part"][0]["Stream"] = [{"streamType": 1, "colorTrc": "bt709"}]
    assert part_of(item)[2] is False  # type: ignore[index]
    assert part_of({"duration": 1000, "Media": [{"Part": [{"key": "https://elsewhere/file.mkv"}]}]}) is None
    assert part_of({"Media": [{"Part": [{"key": "/library/parts/1/2/f.mkv"}]}]}) is None  # no length


def test_one_image_taken_where_asked() -> None:
    argv = command("http://plex:32400/library/parts/42/1/file.mkv", "secret", 3600.04, hdr=False)
    assert argv[argv.index("-ss") + 1] == "3600.0"
    assert argv.index("-ss") < argv.index("-i")  # seek first: only the image's bytes are read
    assert argv[argv.index("-headers") + 1] == "X-Plex-Token: secret\r\n"
    assert argv[argv.index("-frames:v") + 1] == "1" and argv[-1] == "pipe:1"
    assert "tonemap" not in argv[argv.index("-vf") + 1]
    hdr = command("http://plex/x", "t", 10, hdr=True)
    assert "tonemap" in hdr[hdr.index("-vf") + 1]
