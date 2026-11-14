"""Which emulator core plays a platform (issue 419) — RomM's own table for EmulatorJS, so a game plays here
as it does in RomM. The cores that need threads (``SharedArrayBuffer``) run only in a page isolated from
other origins; the play page is."""

CORES: dict[str, str] = {
    "3do": "opera",
    "acpc": "cap32",
    "amiga": "puae",
    "arcade": "mame2003_plus",
    "neogeoaes": "fbneo",
    "neogeomvs": "fbneo",
    "atari2600": "stella2014",
    "atari5200": "a5200",
    "atari7800": "prosystem",
    "c64": "vice_x64sc",
    "colecovision": "gearcoleco",
    "doom": "prboom",
    "dos": "dosbox_pure",
    "jaguar": "virtualjaguar",
    "lynx": "handy",
    "neo-geo-pocket": "mednafen_ngp",
    "neo-geo-pocket-color": "mednafen_ngp",
    "nes": "fceumm",
    "famicom": "fceumm",
    "fds": "fceumm",
    "n64": "mupen64plus_next",
    "nds": "melonds",
    "gb": "gambatte",
    "gbc": "gambatte",
    "gba": "mgba",
    "pc-fx": "mednafen_pcfx",
    "psx": "pcsx_rearmed",
    "philips-cd-i": "same_cdi",
    "psp": "ppsspp",
    "segacd": "genesis_plus_gx",
    "sega32": "picodrive",
    "gamegear": "genesis_plus_gx",
    "sms": "genesis_plus_gx",
    "genesis": "genesis_plus_gx",
    "saturn": "yabause",
    "snes": "snes9x",
    "tg16": "mednafen_pce",
    "turbografx-cd": "mednafen_pce",
    "supergrafx": "mednafen_pce",
    "vic-20": "vice_xvic",
    "virtualboy": "beetle_vb",
    "wonderswan": "mednafen_wswan",
    "wonderswan-color": "mednafen_wswan",
    "zxs": "fuse",
    "3ds": "azahar",
}
THREADED: frozenset[str] = frozenset({"dosbox_pure", "ppsspp", "azahar"})


def core_for(platform: str) -> str | None:
    return CORES.get(platform.strip().lower())
