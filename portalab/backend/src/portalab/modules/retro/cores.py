"""Which engine plays a platform (issues 419, 421) — RomM's own tables, so a game plays here as it does in
RomM: an EmulatorJS core (the first RomM offers), or Ruffle for Flash; the Sega consoles' virtual gamepad
layout. The cores that need threads (``SharedArrayBuffer``) run only in a page isolated from other origins;
the play page is."""

CORES: dict[str, str] = {
    "3do": "opera",
    "acpc": "cap32",
    "amiga": "puae",
    "amiga-cd32": "puae",
    "arcade": "mame2003_plus",
    "neogeoaes": "fbneo",
    "neogeomvs": "fbneo",
    "atari2600": "stella2014",
    "atari-2600-plus": "stella2014",
    "atari5200": "a5200",
    "atari7800": "prosystem",
    "c-plus-4": "vice_xplus4",
    "c64": "vice_x64sc",
    "cpet": "vice_xpet",
    "commodore-64c": "vice_x64sc",
    "c128": "vice_x128",
    "commmodore-128": "vice_x128",
    "colecovision": "gearcoleco",
    "doom": "prboom",
    "dos": "dosbox_pure",
    "jaguar": "virtualjaguar",
    "lynx": "handy",
    "atari-lynx-mkii": "handy",
    "neo-geo-pocket": "mednafen_ngp",
    "neo-geo-pocket-color": "mednafen_ngp",
    "nes": "fceumm",
    "famicom": "fceumm",
    "fds": "fceumm",
    "game-televisison": "fceumm",
    "new-style-nes": "fceumm",
    "n64": "mupen64plus_next",
    "ique-player": "mupen64plus_next",
    "nds": "melonds",
    "nintendo-ds-lite": "melonds",
    "nintendo-dsi": "melonds",
    "nintendo-dsi-xl": "melonds",
    "gb": "gambatte",
    "game-boy-pocket": "gambatte",
    "game-boy-light": "gambatte",
    "gba": "mgba",
    "game-boy-adavance-sp": "mgba",
    "game-boy-micro": "mgba",
    "gbc": "gambatte",
    "pc-fx": "mednafen_pcfx",
    "psx": "pcsx_rearmed",
    "philips-cd-i": "same_cdi",
    "psp": "ppsspp",
    "segacd": "genesis_plus_gx",
    "sega32": "picodrive",
    "gamegear": "genesis_plus_gx",
    "sms": "genesis_plus_gx",
    "sega-mark-iii": "genesis_plus_gx",
    "sega-game-box-9": "genesis_plus_gx",
    "sega-master-system-ii": "genesis_plus_gx",
    "master-system-super-compact": "genesis_plus_gx",
    "master-system-girl": "genesis_plus_gx",
    "genesis": "genesis_plus_gx",
    "sega-mega-drive-2-slash-genesis": "genesis_plus_gx",
    "sega-mega-jet": "genesis_plus_gx",
    "mega-pc": "genesis_plus_gx",
    "tera-drive": "genesis_plus_gx",
    "sega-nomad": "genesis_plus_gx",
    "saturn": "yabause",
    "snes": "snes9x",
    "sfam": "snes9x",
    "super-nintendo-original-european-version": "snes9x",
    "super-famicom-shvc-001": "snes9x",
    "super-famicom-jr-model-shvc-101": "snes9x",
    "new-style-super-nes-model-sns-101": "snes9x",
    "tg16": "mednafen_pce",
    "turbografx-cd": "mednafen_pce",
    "supergrafx": "mednafen_pce",
    "vic-20": "vice_xvic",
    "virtualboy": "beetle_vb",
    "wonderswan": "mednafen_wswan",
    "swancrystal": "mednafen_wswan",
    "wonderswan-color": "mednafen_wswan",
    "zxs": "fuse",
}
THREADED: frozenset[str] = frozenset({"dosbox_pure", "ppsspp", "azahar"})
RUFFLE = "ruffle"
FLASH: frozenset[str] = frozenset({"flash", "browser"})  # 421: played by Ruffle, as RomM serves it
# 421: the virtual gamepad of the Sega consoles (EmulatorJS's ``EJS_controlScheme``), RomM's table
CONTROL_SCHEMES: dict[str, str] = {
    "segacd": "segaCD",
    "sega32": "sega32x",
    "gamegear": "segaGG",
    "sms": "segaMS",
    "sega-mark-iii": "segaMS",
    "sega-master-system-ii": "segaMS",
    "master-system-super-compact": "segaMS",
    "master-system-girl": "segaMS",
    "genesis": "segaMD",
    "sega-mega-drive-2-slash-genesis": "segaMD",
    "sega-mega-jet": "segaMD",
    "mega-pc": "segaMD",
    "tera-drive": "segaMD",
    "sega-nomad": "segaMD",
    "saturn": "segaSaturn",
}


def core_for(platform: str) -> str | None:
    """The core of a platform: an EmulatorJS core's name, or ``ruffle`` (Flash)."""
    slug = platform.strip().lower()
    return RUFFLE if slug in FLASH else CORES.get(slug)


def control_scheme(platform: str) -> str | None:
    return CONTROL_SCHEMES.get(platform.strip().lower())
