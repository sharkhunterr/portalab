"""#368 — IGDB, the game database: its Twitch application's token asked once and sent with every query; a
franchise found by its name (the one holding the library's games, else the fullest of that name), its games
the oldest first (a version of another or a DLC left out); a game's sheet; images from IGDB's host only."""

import httpx

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import GAME_DATABASE
from portalab.connectors.igdb import IgdbConnector, image_ref, quoted
from tests.contract.connectors.builtin_fixtures import handle_for


class FakeTwitch(IgdbConnector):
    """Twitch's token endpoint answered by the same fake server as IGDB's API."""

    def token_client(self, service: ServiceHandle) -> ConnectorHttpClient:
        return ConnectorHttpClient("https://id.twitch.tv", retries=0, transport=service.http.transport)


async def test_a_franchise_and_its_games() -> None:
    seen: list[httpx.Request] = []
    handle = handle_for("igdb", seen=seen)
    provider = FakeTwitch().provider(GAME_DATABASE, handle)
    franchise = await provider.franchise("the legend of zelda", ["7346"])
    assert franchise is not None and franchise.name == "The Legend of Zelda"
    assert franchise.ids == {"igdb": "franchises:596"}  # it holds the library's game, the series does not
    assert [(g.tmdb_id, g.title, g.year) for g in franchise.games] == [
        ("1022", "The Legend of Zelda", 1986),
        ("1025", "Zelda II", 1987),
        ("7346", "Breath of the Wild", 2017),
    ]
    assert franchise.games[0].poster == "co1uii" and franchise.games[0].vote_average == 8.5
    # the token asked once, with the application's id and secret; every query carries both
    tokens = [r for r in seen if r.url.path == "/oauth2/token"]
    assert len(tokens) == 1 and tokens[0].url.params["client_id"] == "abcdef0123456789"
    queries = [r for r in seen if r.url.path.startswith("/v4/")]
    assert all(r.headers["authorization"] == "Bearer igdb-app-token" for r in queries)
    assert all(r.headers["client-id"] == "abcdef0123456789" for r in queries)
    assert await provider.franchise("Nothing Like It", []) is None


async def test_a_game_s_sheet() -> None:
    provider = FakeTwitch().provider(GAME_DATABASE, handle_for("igdb"))
    game = await provider.game("7346")
    assert game is not None and game.title == "The Legend of Zelda: Breath of the Wild"
    assert (game.year, game.release_date, game.rating, game.votes) == (2017, "2017-03-03", 9.7, 4000)
    assert game.platforms == ["Nintendo Switch", "Wii U"]
    assert game.developers == ["Nintendo EPD"] and game.publishers == ["Nintendo"]
    assert game.genres == ["Adventure", "Role-playing (RPG)"] and game.themes == ["Open world"]
    assert game.images == ["ar5s3", "sc6lvu"]  # a reference that is not an image id left out
    assert game.trailer == "zw47_q9wbBE" and game.franchises == ["The Legend of Zelda"]
    assert game.names == {"ja-JP": "ゼルダの伝説", "Acronym": "Zelda BOTW"}
    assert await provider.game("1") is None and await provider.game("../x") is None


def test_queries_and_images_stay_ours() -> None:
    assert quoted('Zelda"; fields *') == '"Zelda fields *"' and quoted('a\\b') == '"a b"'
    assert image_ref({"image_id": "co1uii"}) == "co1uii" and image_ref("../x") is None
