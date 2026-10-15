"""``ui.theme_catalog`` (spec 022, consumed by Campaigns 014): the theme keys that exist and the Admin
policy currently allows — campaigns may only name such a theme as an overlay."""

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "ui.theme_catalog"
ENTITLEMENTS = "marketplace.theme_entitlements"


@runtime_checkable
class ThemeCatalog(Protocol):
    async def allowed_keys(self) -> frozenset[str]: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=ThemeCatalog,
    multi_provider=False,
    description="Theme keys enabled and allowed by policy (022)",
)


@runtime_checkable
class ThemeEntitlements(Protocol):
    """027 US11 (provided by Marketplace 015): a theme sold as a product is chosen by its owners only."""

    async def sold(self) -> frozenset[str]:
        """Theme keys offered by an available ``theme`` product."""
        ...

    async def owned(self, user_id: UUID) -> frozenset[str]:
        """Theme keys of the ``theme`` products the user owns (live ownerships)."""
        ...


ENTITLEMENTS_SPEC = CapabilitySpec(
    name=ENTITLEMENTS,
    version="1.0",
    protocol=ThemeEntitlements,
    multi_provider=False,
    description="Themes sold in the Marketplace and the ones a user owns (027 US11)",
)


COSMETICS = "marketplace.cosmetics"

# 027: profile and colour cosmetics — designs drawn by the interface (no image file), keys shared by the
# Marketplace (what is sold) and the UI (what is shown). A design no product sells is free for everyone.
PROFILE_BANNERS: tuple[str, ...] = (
    "aurora", "ocean", "dusk", "forest", "sunset", "synthwave", "starfield", "sakura", "circuit", "halloween",
    # 027 universes
    "castle", "hyperspace", "code", "dunes", "bloodmoon", "snowfall", "pow", "speedlines", "toon", "cabin",
    "neon-grid", "mono", "nebula", "skyline", "mirrorball", "night-city",
    "upsidedown", "hawkins", "shire", "mordor", "pixelshire",
    "vhs", "mesh",
    "vhs", "nostromo",
    # #79: animated banners — an ambience playing inside the banner
    "live-starfield", "live-code-rain", "live-snow", "live-embers", "live-petals", "live-aurora",
    "live-disco", "live-bats", "live-fireflies", "live-rain", "live-spores", "live-hearts",
    "live-upsidedown", "live-veins", "live-meadow", "live-ash", "live-vhs", "live-bokeh", "live-nostromo",
    "live-inferno", "live-thunderstorm", "live-reef", "live-volcano", "live-whiteout", "live-blackhole",
    "live-liquidmetal", "live-neoncity", "live-matrix", "live-goldenhour", "live-darkness", "live-lavalamp",
    "live-polar", "live-plasma",
    # #81: the seasons
    "graveyard", "wrapping", "sweetheart", "garden", "seaside", "live-cobwebs", "live-ornaments",
    "live-loveletters", "live-butterflies", "live-seagulls",
    # #89: the universes
    "greathall", "jollyship", "assemblyline", "live-floatingcandles", "live-cannonsmoke", "live-gears",
    # #89: the desktop, the fruit company, the social network
    "greenhill", "coastline", "friendswall", "live-skyclouds", "live-silkwaves", "live-reactions",
    # #89: music streaming, series streaming, the newspaper
    "soundwave", "postergrid", "frontpage", "live-equalizer", "live-cinemaglow", "live-pages",
    # #89: the retro games
    "lcdscreen", "linestack", "bunkers", "live-lcdstars", "live-fallingblocks", "live-fleet",
    "mazewalls", "brickworld", "live-ghosts", "live-spincoins",
    # #89: funk, the beach, spring
    "sunset70s", "lifeguard", "tulipfield", "live-groovywaves", "live-beachballs", "live-dandelion",
    # #130: the cosmos
    "starchart", "orbits", "live-orion", "live-crab", "live-helix", "live-pillars", "live-cliffs",
    "live-solarsystem", "live-saturnrise", "live-perseids", "live-constellations", "live-milkyway",
    "live-greatcomet",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "lunarsurface", "earthrise", "asteroidfield", "launchpad", "live-solarflare", "live-moonrise",
    "live-asteroids",
)  # fmt: skip
AVATAR_FRAMES: tuple[str, ...] = (
    "none", "simple", "gold", "neon", "flames", "frost", "rainbow", "pixel",
    "runes", "orbit", "code", "sand", "blood", "pumpkin", "holly", "pow", "chrome", "hologram", "cyber",
    "hero", "disco", "toxic", "sakura",
    "veins", "lights", "onering", "elven",
    "vhs", "rings",
    "vhs", "tracker",
    # #78: drawn by the GPU, in shapes of their own
    "pyre", "tesla", "abyssal", "obsidian", "frostcrown", "starlit", "regalia", "biohazard", "prism",
    "sigil", "mainframe", "hanami", "wraith", "sweetie", "borealis", "corona",
    "chronogate",  # #78: the time portal
    # #81: the seasons
    "cauldron", "candycane", "heartbeat", "daisy", "lifebuoy", "spectre", "tinsel", "amour", "verdant",
    "sunburst",
    # #89: the universes
    "housecrest", "shipwheel", "visor",
    # #89: the desktop, the fruit company, the social network
    "window", "appicon", "storyring",
    # #89: music streaming, series streaming, the newspaper
    "vinyl", "profiletile", "postage",
    # #89: the retro games
    "cartridge", "blockframe", "crab", "corridor", "warppipe",
    # #89: funk, the beach, spring
    "retroarc", "parasol", "flowerwreath",
    # #130: the cosmos
    "nebulaveil", "orrery", "starchart", "cometring", "ringedworld", "pulsar", "eclipse", "meteorite",
    "polaris",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "crescent", "sunrays", "asteroidring", "saturnring", "heliosphere", "lunarhalo",
)  # fmt: skip
PALETTES: tuple[str, ...] = (
    "theme", "ocean", "forest", "sunset", "candy", "royal", "ember", "matrix",
    "aurora", "lagoon", "lava", "mint", "gold", "ice", "rose", "toxic", "midnight", "coffee", "lavender",
    "bubblegum", "polar", "copper", "solar", "berry", "slate", "peach", "crimson",
    "hawkins", "gondor",
    "vhs", "nova",
    "vhs", "nostromo",
    # #81: the seasons
    "pumpkinspice", "evergreen", "cherry", "pastel", "tropical",
    # #89: the universes
    "scarletgold", "rum", "gunmetal",
    # #89: the desktop, the fruit company, the social network
    "luna", "graphite", "chatgradient",
    # #89: music streaming, series streaming, the newspaper
    "groove", "redcarpet", "newsprint",
    # #89: the retro games
    "dotmatrix", "blockcolors", "arcadegreen", "mazeblue", "brickred",
    # #89: funk, the beach, spring
    "seventies", "sandbar", "lilac",
    # #130: the cosmos
    "orionpink", "deepspace",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "solarflare", "lunar", "nebulateal",
)  # fmt: skip
# animated layers: behind the whole portal (ambient preference, theme default) or a profile (background)
AMBIENTS: tuple[str, ...] = (
    "none", "snow", "embers", "code-rain", "fireflies", "starfield", "warp", "petals", "bats", "bubbles",
    "rain", "sparkles", "disco", "fog", "sand", "leaves", "hearts", "glitch", "lights", "spores", "aurora",
    # 027: VHS tracking, wind, tide, sky lanterns, 8-bit sky
    "vhs", "wind", "tide", "lanterns", "pixelsky",
    "upsidedown", "veins", "meadow", "ash",
    "bokeh",
    "nostromo",
    # #68: premium ambiences, drawn on a canvas (WebGL shaders, particles)
    "inferno", "thunderstorm", "sandstorm", "polar", "cosmos", "abyss", "blizzard", "fireworks", "downpour",
    "matrix", "mesh", "meshwave",
    "volcano", "blackhole", "reef", "firestorm", "whiteout", "liquidmetal", "plasma", "forest", "neoncity",
    "weather",
    "haunted", "darkness", "lostsignal", "garland", "christmasnight", "hearth",
    "goldenhour", "windowrain", "summerfield", "soapbubbles", "skylanterns", "autumnlane",
    "pixelcamp", "pixelbeach", "pixelballoons",
    "amberglow", "candlelight", "steam", "fairybokeh", "warmsilk", "honey", "knit",
    "paintmix", "acrylicpour", "watercolor", "marbling",
    "poppaint", "poppour", "popwatercolor", "popmarbling", "lavalamp",
    "impasto", "paintribbon",
    # #81: the seasons
    "cobwebs", "ornaments", "loveletters", "butterflies", "seagulls",
    # #89: the universes
    "floatingcandles", "cannonsmoke", "gears",
    # #89: the desktop, the fruit company, the social network
    "skyclouds", "silkwaves", "reactions",
    # #89: music streaming, series streaming, the newspaper
    "equalizer", "cinemaglow", "pages",
    # #89: the retro games
    "lcdstars", "fallingblocks", "fleet", "ghosts", "spincoins",
    # #89: funk, the beach, spring
    "groovywaves", "beachballs", "dandelion",
    # #130: the cosmos
    "orion", "crab", "helix", "pillars", "cliffs", "solarsystem", "saturnrise", "perseids",
    "constellations", "milkyway", "greatcomet",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "solarflare", "moonrise", "asteroids",
)  # fmt: skip
CELEBRATIONS: tuple[str, ...] = (
    "none", "sparkle", "confetti", "glow", "snow", "bats", "pixels", "hearts", "stars", "coins", "lightning",
    "petals", "bubbles", "assemble", "burn", "shatter", "freeze", "glitch", "portal",
    "flicker", "fireworks",
    "rewind", "bloom",
    "rewind", "tracker",
    # #78: drawn by the GPU
    "nova", "goldshower", "petalstorm", "rebirth", "stormstrike", "skyveil", "arcana", "timerift",
    # #81: the seasons
    "candy", "gifts", "cupid", "eggs", "splash",
    # #89: the universes
    "wandsparks", "cannonball", "bolts",
    # #89: the desktop, the fruit company, the social network
    "cardcascade", "balloons", "likes",
    # #89: music streaming, series streaming, the newspaper
    "musicnotes", "ribbons", "inkstamp",
    # #89: the retro games
    "pixelhearts", "lineclear", "lasers", "pellets", "coinpop",
    # #89: funk, the beach, spring
    "flowerpower", "seashells", "songbirds",
    # #130: the cosmos
    "starshower", "bigbang",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "comets", "planets",
)  # fmt: skip
NOTIFICATION_STYLES: tuple[str, ...] = (
    "toast", "banner", "pill", "minimal", "glass", "neon", "comic", "terminal", "parchment", "hologram",
    "pixel", "paper", "square", "circle", "cloud", "ticket", "tag", "split",
    # 027 universes: space saga, pirates, manga, film noir, VHS tape
    "saga", "pirate", "manga", "noir", "vhs",
    "upsidedown", "elven", "onering",
    "island",
    "nostromo",
    # #78: drawn by the GPU
    "blaze", "voltage", "aqua", "magma", "glacier", "galaxy", "aurum", "toxic", "holo", "runes", "matrix",
    "sakura", "shadow", "candy", "aurora", "plasma",
    "chrono",  # #78: the time portal
    # #81: the seasons
    "tombstone", "giftwrap", "loveletter", "bloom", "postcard",
    # #89: the universes
    "scroll", "bottle", "chamfer",
    # #89: the desktop, the fruit company, the social network
    "balloon", "trafficlights", "chathead",
    # #89: music streaming, series streaming, the newspaper
    "nowplaying", "nextepisode", "telegram",
    # #89: the retro games
    "rpgbox", "blockrow", "invasion", "ghostly", "bricks",
    # #89: funk, the beach, spring
    "jukebox", "beachtowel", "seedpacket",
    # #130: the cosmos
    "stellar", "orrery", "starmap", "comet", "ringworld", "pulsar", "totality", "meteor",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "solar", "lunar", "transmission", "missioncontrol",
)  # fmt: skip
NOTIFICATION_ANIMATIONS: tuple[str, ...] = (
    "slide", "fade", "pop", "zoom", "bounce", "flip", "swing", "glitch", "drop", "spiral", "slam",
    "rise", "wipe", "focus", "jelly", "shake",
    # 027: film transitions (a hard wipe right to left, an iris) and the four elements
    "filmwipe", "iris", "air", "water", "earth", "fire",
    # 027: sucked into a black hole, melting, a comic « KAPOW! », a dimensional portal
    "blackhole", "melt", "kapow", "portal",
    "flipup", "balrog", "eye",
    "tracking", "morph",
    "tracking", "uplink",
    # #78: drawn by the GPU
    "ignite", "surge", "splash", "frostbite", "stardust", "hex", "decrypt", "petalfall", "eclipse", "warp",
    # #89: the universes
    "swoop", "anchor", "transform",
    # #89: the desktop, the fruit company, the social network
    "trayrise", "genie", "chatpop",
    # #89: music streaming, series streaming, the newspaper
    "beatdrop", "curtainwipe", "spinpaper",
    # #89: the retro games
    "pixelreveal", "harddrop", "march", "chomp", "jumpin",
    # #89: funk, the beach, spring
    "funkwalk", "surfin", "sprout",
    # #130: the cosmos
    "shootingstar", "nebulabloom", "eclipsed",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "liftoff", "orbitin",
)  # fmt: skip
# the name shown big on a profile: a font and an effect (Steam-like « titles »)
NAME_STYLES: tuple[str, ...] = (
    "none", "wizard", "galaxy", "matrix", "desert", "horror", "halloween", "christmas", "comic", "manga",
    "cartoon", "cozy", "futuristic", "minimal", "alien", "hero", "neowave", "disco", "cyberpunk", "pixel",
    "handwritten", "fire", "ice", "rainbow", "royal",
    "upsidedown", "elvish", "mordor",
    "vhs", "nova",
    "vhs", "nostromo",
    # #78: drawn by the GPU
    "nameblaze", "namevolt", "namefrost", "namegalaxy", "namegold", "nameshadow", "namesakura",
    "nameplasma", "nameaurora", "namechrono",
    # #81: the seasons
    "slime", "gingerbread", "lovestruck", "springtime", "tropical", "namespectre", "nametinsel",
    "nameamour", "namesunburst",
    # #89: the universes
    "spellbound", "pirata", "steelplate",
    # #89: the desktop, the fruit company, the social network
    "titlebar", "aluminium", "verified",
    # #89: music streaming, series streaming, the newspaper
    "recap", "marathon", "typewriter",
    # #89: the retro games
    "lcdtext", "bevelblocks", "hiscore", "neonmaze", "gametitle",
    # #89: funk, the beach, spring
    "funkadelic", "surfwave", "watercolour",
    # #130: the cosmos
    "spaceage", "starlines", "staratlas",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "lunarsilver", "solarfire", "bigbang",
)  # fmt: skip
# animated badges and titles (payload ``style`` of ``badge``/``title`` products)
BADGE_STYLES: tuple[str, ...] = (
    "none", "shimmer", "pulse", "flame", "glitch", "rainbow", "float", "spin", "frost", "neon", "gold",
    "vhs", "pixel", "terminal", "water", "wind", "saber",
    "veins", "mirror", "ring", "elven",
    "glass",
    "hazard",
    # #78: drawn by the GPU
    "blaze", "voltage", "aqua", "magma", "glacier", "galaxy", "aurum", "toxic", "holo", "runes", "matrix",
    "sakura", "shadow", "candy", "aurora", "plasma",
    "chrono",  # #78: the time portal
    # #130: the cosmos
    "stellar", "orrery", "starmap", "comet", "ringworld", "pulsar", "totality", "meteor",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "solar", "lunar",
)  # fmt: skip
# 027: the look of the level badge (the « XP badge » in the header, the navigation and on the profile, seen
# by everyone): ``classic`` is free and changes with the level (a new rank every ten levels)
LEVEL_BADGES: tuple[str, ...] = (
    "classic", "pixel", "neon", "crest", "gem", "hologram", "vhs", "saber", "elements",
    "blackhole", "melt", "kapow", "portal", "crown", "inferno",
    "upsidedown", "veins", "lights", "onering", "eye", "mithril", "balrog", "frost", "nebula", "circuit",
    "cassette", "squircle",
    "cassette", "tracker",
    "blaze", "voltage", "aqua", "magma",  # #73: drawn by the GPU
    # #77
    "glacier", "galaxy", "aurum", "toxic", "holo", "runes", "matrix", "sakura", "shadow", "candy", "aurora",
    "plasma",
    "chrono",  # #78: the time portal
    # #81: the seasons
    "jackolantern", "bauble", "heart", "easteregg", "sunset", "spectre", "tinsel", "verdant",
    # #89: the universes
    "snitch", "doubloon", "chevron",
    # #89: the desktop, the fruit company, the social network
    "startbutton", "aquagel", "speechbubble",
    # #89: music streaming, series streaming, the newspaper
    "eqbars", "toprank", "presscard",
    # #89: the retro games
    "batteryled", "tpiece", "saucer", "chomper", "qblock",
    # #89: funk, the beach, spring
    "eighttrack", "flipflop", "ladybug",
    # #130: the cosmos
    "stellar", "orrery", "starmap", "comet", "ringworld", "pulsar", "totality", "meteor",
    # #130: the second wave — the sun, the moon, asteroids, rockets
    "moonphase", "sunbadge", "rocketbadge", "solar", "lunar",
)  # fmt: skip
# 027: how a level-up is shown (the full-screen moment with what was won and unlocked); ``classic`` is free
LEVEL_UPS: tuple[str, ...] = (
    "classic", "arcade", "cosmic", "comic", "elements", "cinema",
    # 027: one per universe — each theme celebrates its levels its own way (``motion.levelUp``)
    "crawl", "spell", "decode", "sandstorm", "bloodmoon", "pumpkin", "gift", "manga", "boing", "hearth",
    "hud", "minimal", "abduction", "hero", "synthwave", "disco", "glitch", "noir", "spotlight", "upsidedown",
    "onering",
    "vhs", "nova",
    "vhs", "nostromo",
    # #78: full-stage, drawn by the GPU
    "phoenix", "thunderstrike", "tidalwave", "supernova", "goldrush", "arcanum", "sakurastorm", "aurorasky",
    "timeportal",  # #78: the time portal
    # #89: the universes
    "owlpost", "plunder", "rollout",
    # #89: the desktop, the fruit company, the social network
    "setupwizard", "unboxing", "viral",
    # #89: music streaming, series streaming, the newspaper
    "encore", "finale", "extraedition",
    # #89: the retro games
    "statsup", "fourlines", "wavecleared", "powerup", "flagpole",
    # #89: funk, the beach, spring
    "jukeboxdrop", "sandcastle", "fullbloom",
    # #130: the cosmos
    "hyperjump", "constellate",
    # #133: the Upside Down's gate
    "rift",
)  # fmt: skip
UNIVERSE_THEMES: tuple[str, ...] = (
    "wizard", "galaxy", "matrix", "desert", "horror", "halloween", "christmas", "comic", "manga", "cartoon",
    "cozy", "futuristic", "minimal", "alien", "heroes", "neowave", "disco", "cyberpunk", "sincity", "plex",
    "upsidedown", "middleearth",
    "vhs", "nova",
    "vhs", "nostromo",
    # #89: the universes
    "academy", "caribbean", "mecha",
    # #89: the desktop, the fruit company, the social network
    "classicdesk", "cupertino", "social",
    # #89: music streaming, series streaming, the newspaper
    "groove", "binge", "gazette",
    # #89: the retro games
    "pocket", "blockfall", "invaders", "mazechase", "platformer",
    # #89: funk, the beach, spring
    "funky", "beach", "blossom",
    # #130: the cosmos
    "observatory", "spacestation", "starship",
)  # fmt: skip
PROFILE_SLOTS = {
    "banner": ("profile_banner", "banner"),
    "frame": ("avatar_frame", "frame"),
    "background": ("profile_background", "background"),
    "name": ("name_style", "style"),
    "level": ("level_badge", "style"),  # 027: the level badge's look, worn on the profile
}


@runtime_checkable
class CosmeticEntitlements(Protocol):
    """027 (provided by Marketplace 015): cosmetic choices sold as products — notification styles and
    animations… — are chosen by their owners only. ``kind`` is the product type, ``field`` the payload key
    naming the choice (e.g. ``notification_style`` / ``style``)."""

    async def sold(self, kind: str, field: str) -> frozenset[str]: ...

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]: ...

    async def equipped(self, user_id: UUID) -> dict[str, Any]:
        """The profile cosmetics a member wears: ``banner``, ``frame``, ``backdrop`` ({object_id, ref})."""
        ...


COSMETICS_SPEC = CapabilitySpec(
    name=COSMETICS,
    version="1.0",
    protocol=CosmeticEntitlements,
    multi_provider=False,
    description="Cosmetic choices sold in the Marketplace and the ones a user owns (027)",
)

# some keys were listed twice over the specs' merges: each list keeps one of each, in order
PROFILE_BANNERS = tuple(dict.fromkeys(PROFILE_BANNERS))
AVATAR_FRAMES = tuple(dict.fromkeys(AVATAR_FRAMES))
PALETTES = tuple(dict.fromkeys(PALETTES))
AMBIENTS = tuple(dict.fromkeys(AMBIENTS))
CELEBRATIONS = tuple(dict.fromkeys(CELEBRATIONS))
NOTIFICATION_STYLES = tuple(dict.fromkeys(NOTIFICATION_STYLES))
NOTIFICATION_ANIMATIONS = tuple(dict.fromkeys(NOTIFICATION_ANIMATIONS))
NAME_STYLES = tuple(dict.fromkeys(NAME_STYLES))
BADGE_STYLES = tuple(dict.fromkeys(BADGE_STYLES))
LEVEL_BADGES = tuple(dict.fromkeys(LEVEL_BADGES))
LEVEL_UPS = tuple(dict.fromkeys(LEVEL_UPS))
UNIVERSE_THEMES = tuple(dict.fromkeys(UNIVERSE_THEMES))
