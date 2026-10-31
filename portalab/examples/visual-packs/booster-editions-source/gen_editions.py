"""Writes the fourteen edition scene packs (one per media card edition, in its frame's era) but for their videos
(build.sh): their emblems, stylesheets — the sealed pack, the back, the opening, each rarity's reveal over the
whole screen and the look of the rarity's name Portalab writes there — and every manifest. No card faces: a card
drawn from an edition's booster keeps its edition's frame (portalab-editions). Fonts (from Google Fonts: SIL OFL,
or Apache 2.0 for Special Elite and Permanent Marker) are copied from fonts/."""

import json
import math
import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DURATION = {"rare": 3.2, "epic": 3.8, "legendary": 4.6}
FONTS = {
    "Limelight.woff2": ("Limelight by Nicole Fally", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "SpecialElite.woff2": ("Special Elite by Astigmatic", "Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)"),
    "Lobster.woff2": ("Lobster by Pablo Impallari", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Shrikhand.woff2": ("Shrikhand by Jonny Pinhorn", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "AlfaSlabOne.woff2": ("Alfa Slab One by JM Solé", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Bungee.woff2": ("Bungee by David Jonathan Ross", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "PressStart2P.woff2": ("Press Start 2P by CodeMan38", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "PermanentMarker.woff2": ("Permanent Marker by Font Diner", "Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)"),
    "Fredoka.woff2": ("Fredoka by Milena Brandão", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "UncialAntiqua.woff2": ("Uncial Antiqua by Astigmatic", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Rye.woff2": ("Rye by Nicole Fally", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Raleway.woff2": ("Raleway by Matt McInerney, Pablo Impallari and Rodrigo Fuenzalida", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Audiowide.woff2": ("Audiowide by Astigmatic", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
    "Unbounded.woff2": ("Unbounded by NaN", "SIL Open Font License 1.1 (https://openfontlicense.org)"),
}


def comment(text):
    lines = textwrap.wrap(text, 110)
    return "/* " + "\n".join(("   " if i else "") + line for i, line in enumerate(lines)) + " */\n"


def svg(body, w=100, h=100):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>\n'


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def polar(cx, cy, r, a):
    return cx + math.cos(a) * r, cy + math.sin(a) * r


# --- emblems ------------------------------------------------------------------------------------------------
def emblem_nitrate():
    rays = "".join(f'<path d="{path([(50, 78), polar(50, 78, 64, math.pi + i * math.pi / 12), polar(50, 78, 64, math.pi + (i + 1) * math.pi / 12)])}" fill="{"#a8814f" if i % 2 else "#5c4026"}"/>' for i in range(12))
    return svg(f'<rect x="4" y="4" width="92" height="92" fill="#0d0b09"/>{rays}<rect x="8" y="8" width="84" height="84" fill="none" stroke="#dcd6cc" stroke-width="2"/>'
               '<rect x="13" y="13" width="74" height="74" fill="none" stroke="#dcd6cc" stroke-width="1"/><path d="M50,4 L56,10 L50,16 L44,10 Z" fill="#dcd6cc"/>')


def emblem_noir():
    return svg('<circle cx="50" cy="50" r="46" fill="#c9a26b"/><circle cx="50" cy="50" r="46" fill="none" stroke="#b81212" stroke-width="4" stroke-dasharray="6 3"/>'
               '<path d="M18,88 L24,70 L38,64 L62,64 L76,70 L82,88 Z" fill="#0a0a0c"/><ellipse cx="50" cy="52" rx="11" ry="13" fill="#0a0a0c"/>'
               '<path d="M26,42 L74,42 L66,46 L34,46 Z" fill="#0a0a0c"/><path d="M37,42 L38,28 L50,25 L62,28 L63,42 Z" fill="#0a0a0c"/>')


def emblem_drivein():
    star = "".join(f'{"M" if i == 0 else "L"}{polar(50, 50, (44 if i % 4 == 0 else 24) if i % 2 == 0 else 5, -math.pi / 2 + i * math.pi / 8)[0]:.1f},{polar(50, 50, (44 if i % 4 == 0 else 24) if i % 2 == 0 else 5, -math.pi / 2 + i * math.pi / 8)[1]:.1f} ' for i in range(16)) + "Z"
    orbits = "".join(f'<ellipse cx="50" cy="50" rx="34" ry="11" fill="none" stroke="#3fd6cc" stroke-width="3" transform="rotate({a} 50 50)"/>' for a in (0, 60, 120))
    return svg(f'<path d="{star}" fill="#fff2d6"/>{orbits}<circle cx="50" cy="50" r="7" fill="#e51a38"/>')


def emblem_super8():
    petals = "".join(f'<ellipse cx="50" cy="26" rx="11" ry="20" fill="#ff4599" transform="rotate({i * 45} 50 50)"/>' for i in range(8))
    return svg(f'<circle cx="50" cy="50" r="48" fill="#3a0a5c"/><circle cx="50" cy="50" r="40" fill="none" stroke="#ff7614" stroke-width="5"/>{petals}<circle cx="50" cy="50" r="13" fill="#ffdb33"/>')


def emblem_film():
    holes = "".join(f'<circle cx="{polar(50, 50, 26, i * math.tau / 5 - math.pi / 2)[0]:.1f}" cy="{polar(50, 50, 26, i * math.tau / 5 - math.pi / 2)[1]:.1f}" r="10" fill="#eedbb8"/>' for i in range(5))
    return svg(f'<circle cx="50" cy="50" r="46" fill="#241a14"/><circle cx="50" cy="50" r="40" fill="none" stroke="#ff9430" stroke-width="3"/>{holes}<circle cx="50" cy="50" r="6" fill="#eedbb8"/>'
               '<path d="M50,96 L100,96 L100,86 L60,86 Z" fill="#241a14"/>')


def emblem_laserdisc():
    rings = "".join(f'<circle cx="46" cy="46" r="{r}" fill="{c}"/>' for r, c in ((40, "#ff9ab8"), (32, "#ffd633"), (24, "#8cead0"), (16, "#4073ff")))
    return svg(f'<circle cx="52" cy="52" r="42" fill="#0f0f14"/>{rings}<circle cx="46" cy="46" r="40" fill="none" stroke="#0f0f14" stroke-width="3"/><circle cx="46" cy="46" r="5" fill="#0f0f14"/>'
               '<path d="M70,72 L94,94 L64,96 Z" fill="#9e7af5" stroke="#0f0f14" stroke-width="3"/>')


def emblem_vhs():
    rows = "".join(f'<rect x="{50 - w}" y="{y}" width="{2 * w}" height="6" fill="#ffd16b"/>' for y, w in ((14, 12), (20, 24), (26, 30), (32, 34), (38, 36), (46, 36), (54, 34), (62, 30), (70, 24)))
    return svg(f'<rect x="2" y="2" width="96" height="96" fill="#1a1445"/><rect x="2" y="56" width="96" height="42" fill="#a1347c"/>{rows}'
               '<rect x="2" y="78" width="20" height="20" fill="#0a0917"/><rect x="22" y="70" width="14" height="28" fill="#0a0917"/><rect x="62" y="74" width="16" height="24" fill="#0a0917"/><rect x="78" y="66" width="20" height="32" fill="#0a0917"/>')


def emblem_zine():
    star = path([polar(50, 50, 42 if i % 2 == 0 else 18, -math.pi / 2 + i * math.pi / 5) for i in range(10)])
    return svg(f'<path d="M8,12 L90,6 L94,88 L12,94 Z" fill="#f2f0e6"/><path d="{star}" fill="none" stroke="#ff3388" stroke-width="5" stroke-linejoin="round"/>'
               '<path d="M2,20 L34,6 L38,14 L6,28 Z" fill="#ebe0b8" opacity="0.9"/><rect x="30" y="76" width="40" height="8" fill="#fff226" opacity="0.8"/>')


def emblem_bubble():
    return svg('<circle cx="50" cy="50" r="44" fill="#80dbff" fill-opacity="0.35" stroke="#80dbff" stroke-width="4"/><ellipse cx="34" cy="30" rx="12" ry="7" fill="#ffffff" transform="rotate(-35 34 30)"/>'
               '<path d="M70,66 A26,26 0 0 1 56,78" fill="none" stroke="#ffffff" stroke-width="3" stroke-linecap="round"/><circle cx="80" cy="18" r="8" fill="#80dbff" fill-opacity="0.4" stroke="#80dbff" stroke-width="2"/>')


def emblem_disc():
    cols = ("#d91a2e", "#264dd9", "#1a9e59", "#ff9e1f", "#8033bf")
    panes = "".join(f'<path d="M50,50 L{polar(50, 50, 40, i * math.tau / 10)[0]:.1f},{polar(50, 50, 40, i * math.tau / 10)[1]:.1f} A40,40 0 0 1 {polar(50, 50, 40, (i + 1) * math.tau / 10)[0]:.1f},{polar(50, 50, 40, (i + 1) * math.tau / 10)[1]:.1f} Z" fill="{cols[i % 5]}" stroke="#e0ad47" stroke-width="2"/>' for i in range(10))
    return svg(f'<circle cx="50" cy="50" r="47" fill="#e0ad47"/>{panes}<circle cx="50" cy="50" r="22" fill="none" stroke="#e0ad47" stroke-width="3"/><circle cx="50" cy="50" r="9" fill="#d91a2e" stroke="#e0ad47" stroke-width="3"/>')


def emblem_leather():
    return svg('<circle cx="50" cy="50" r="48" fill="#8fc2ed"/><circle cx="50" cy="50" r="44" fill="none" stroke="#f5dc9e" stroke-width="2" stroke-dasharray="5 4"/>'
               '<path d="M50,12 C72,12 78,32 70,48 L58,64 L42,64 L30,48 C22,32 28,12 50,12 Z" fill="#eb4d47"/><path d="M50,12 C56,24 56,48 54,64 L46,64 C44,48 44,24 50,12 Z" fill="#faca40"/>'
               '<path d="M42,64 L44,74 M58,64 L56,74" stroke="#7a4f28" stroke-width="2"/><rect x="43" y="74" width="14" height="10" fill="#7a4f28"/>')


def emblem_tiles():
    return svg('<rect x="4" y="4" width="44" height="44" fill="#00aba8"/><rect x="52" y="4" width="44" height="44" fill="#f7941a"/><rect x="4" y="52" width="44" height="44" fill="#e04d3d"/><rect x="52" y="52" width="44" height="20" fill="#2180c7"/><rect x="52" y="76" width="44" height="20" fill="#8cc233"/>')


def emblem_stream():
    hexa = path([polar(50, 50, 44, math.pi / 6 + i * math.pi / 3) for i in range(6)])
    return svg(f'<path d="{hexa}" fill="#05051a" stroke="#33f2ff" stroke-width="4"/><path d="M40,32 L70,50 L40,68 Z" fill="#ff2699"/><path d="M40,32 L70,50 L40,68 Z" fill="none" stroke="#ffffff" stroke-width="2"/>'
               '<path d="M14,22 L14,14 L22,14 M86,78 L86,86 L78,86" fill="none" stroke="#33f2ff" stroke-width="3"/>')


def emblem_glass():
    return svg('<defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#40ffa6"/><stop offset="0.5" stop-color="#26bff2"/><stop offset="1" stop-color="#9966ff"/></linearGradient></defs>'
               '<path d="M50,6 C70,34 82,50 82,64 A32,32 0 0 1 18,64 C18,50 30,34 50,6 Z" fill="url(#a)" fill-opacity="0.75" stroke="#ffffff" stroke-width="3"/>'
               '<path d="M32,62 A18,18 0 0 0 44,80" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>')


# --- the editions -----------------------------------------------------------------------------------------
def texts(fr_name, en_name, fr_desc, en_desc):
    return (fr_name, en_name, fr_desc, en_desc)


EDITIONS = {
    "nitrate": dict(
        font=("Limelight.woff2", "Edition Limelight", "400"), ink="#0d0b09", main="#dcd6cc", light="#c79a5c", emblem=emblem_nitrate,
        names={"fr": "Intertitre — édition Nitrate", "en": "Intertitle — Nitrate edition"},
        description={"fr": "Le booster de l'édition Nitrate (le muet) : chaque rareté prend tout l'écran — un soleil Art déco sépia sous des filets d'argent, le scintillement du projecteur et les rayures de la copie, l'iris se ferme et se rouvre, la carte arrive de dos dans un cercle de lumière, et au retournement le faisceau éclate en rayons d'argent. Un paquet de laque noire filetée d'argent qui prend feu comme une pellicule nitrate.",
                     "en": "The Nitrate edition's booster (the silent era): every rarity takes the whole screen — a sepia Art Deco sun under silver hairlines, the projector's flicker and the print's scratches, the iris closes and opens again, the card comes face down in a circle of light, and as it turns the beam bursts into silver rays. A black lacquer pack ruled in silver that catches fire like a nitrate print."},
        pack_bg="repeating-conic-gradient(from 270deg at 50% 100%, #5c4026 0 7.5deg, #a8814f 7.5deg 15deg), linear-gradient(#0d0b09, #0d0b09)",
        pack_band="linear-gradient(180deg, #dcd6cc, #8a857c)",
        word="color: #f2ece0;\n  -webkit-text-stroke: 0.1rem #0d0b09;\n  paint-order: stroke fill;\n  text-shadow: 0 0 0.2rem #0d0b09, 0.4rem 0.4rem 0 #5c4026, 0 0 2rem rgba(242, 236, 224, 0.5);",
        fate="""@keyframes edition-fate {
  0% { filter: none; opacity: 1; }
  20% { filter: sepia(1) brightness(1.1); }
  34% { filter: sepia(1) brightness(0.8); opacity: 1; }
  46%, 100% { filter: sepia(1) brightness(0.2); opacity: 0; }
}""",
        parts={"backdrop": texts("Salle du muet", "Silent picture house", "Un soleil Art déco sépia sous des filets d'argent à angles coupés, le faisceau du projecteur où passe la poussière, le scintillement et les rayures de la copie (vidéo en boucle).", "A sepia Art Deco sun under silver hairlines with cut corners, the projector's beam with dust drifting in it, the print's flicker and scratches (a looping video)."),
               "look": texts("Laque et argent", "Lacquer and silver", "Un paquet de laque noire, un soleil Art déco sépia, des filets d'argent, l'image de l'œuvre dans un cadre d'argent, son nom en capitales Art déco.", "A black lacquer pack, a sepia Art Deco sun, silver hairlines, the work's art in a silver frame, its name in Art Deco capitals."),
               "opening": texts("Pellicule qui brûle", "Burning print", "Le projecteur scintille ; la copie nitrate prend feu, un trou brûle le paquet de part en part, des braises s'envolent.", "The projector flickers; the nitrate print catches fire, a hole burns through the pack, embers flying."),
               "back": texts("Dos Art déco", "Art Deco back", "Laque noire, soleil sépia, filets d'argent.", "Black lacquer, a sepia sun, silver hairlines.")}),
    "noir": dict(
        font=("SpecialElite.woff2", "Edition Special Elite", "400"), ink="#0a0a0c", main="#c9a26b", light="#b81212", emblem=emblem_noir,
        names={"fr": "Dossier noir — édition Noir", "en": "Case file — Noir edition"},
        description={"fr": "Le booster de l'édition Noir (le film noir) : chaque rareté prend tout l'écran — la lumière des stores sur le mur, la pluie, un détective en chapeau mou de dos, le dossier glisse sur l'écran, la carte arrive au milieu du tableau des indices reliés par un fil rouge, et au retournement un flash de magnésium, un tampon rouge et des photos jetées. Un dossier kraft tamponné qui part à la déchiqueteuse.",
                     "en": "The Noir edition's booster (film noir): every rarity takes the whole screen — the blinds' light on the wall, the rain, a detective in a fedora from behind, the case file slides across the screen, the card comes amid the board of clues tied by a red string, and as it turns a flashbulb, a red stamp and prints thrown down. A stamped kraft case file that goes through the shredder."},
        pack_bg="repeating-linear-gradient(-20deg, rgba(0, 0, 0, 0.22) 0 14px, transparent 14px 30px), linear-gradient(170deg, #d9b47c, #9c7a4a)",
        pack_band="linear-gradient(180deg, #b81212, #6e0909)",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; clip-path: inset(0 0 0 0); opacity: 1; }
  10% { transform: none; }
  13% { transform: scale(0.97); filter: grayscale(1); }
  18% { transform: none; filter: grayscale(1); }
  36% { transform: translateY(0); filter: grayscale(1); clip-path: inset(0 0 0 0); opacity: 1; }
  54%, 100% { transform: translateY(100%); filter: grayscale(1); clip-path: inset(0 0 100% 0); opacity: 1; }
}""",
        parts={"backdrop": texts("Bureau de nuit", "Office at night", "Un bureau de détective la nuit, la lumière d'une enseigne à travers les stores qui glisse sur le mur, la pluie sur la vitre, la lampe de bureau, un fil rouge entre les indices, un éclair de temps en temps (vidéo en boucle).", "A detective's office at night, a sign's light through the blinds sliding on the wall, rain on the glass, the desk lamp, a red string between clues, lightning now and then (a looping video)."),
               "look": texts("Dossier kraft", "Kraft case file", "Un dossier kraft barré de l'ombre des stores, l'image de l'œuvre en photo tirée, son nom tapé à la machine, un tampon rouge.", "A kraft case file crossed by the blinds' shadow, the work's art as a print, its name typed, a red stamp."),
               "opening": texts("Classé", "Case closed", "Un tampon rouge s'abat sur le paquet ; il passe à la déchiqueteuse et retombe en lanières.", "A red stamp slams onto the pack; it goes through the shredder and falls in strips."),
               "back": texts("Dos kraft", "Kraft back", "Kraft rayé par les stores, un détective en silhouette.", "Kraft striped by the blinds, a detective in silhouette.")}),
    "drivein": dict(
        font=("Lobster.woff2", "Edition Lobster", "400"), ink="#081430", main="#3fd6cc", light="#e51a38", emblem=emblem_drivein,
        names={"fr": "Drive-in atomique — édition Drive-in", "en": "Atomic drive-in — Drive-in edition"},
        description={"fr": "Le booster de l'édition Drive-in (les années 1950) : chaque rareté prend tout l'écran — une nuit atomique, un grand atome turquoise, des étoiles Googie qui scintillent, une flèche d'ampoules qui clignotent, le faisceau du projecteur s'ouvre, la carte arrive sur le grand écran devant les voitures à ailerons, et au retournement une explosion d'étoiles et de boomerangs, du pop-corn qui saute. Un paquet crème et turquoise qui éclate en pop-corn.",
                     "en": "The Drive-in edition's booster (the 1950s): every rarity takes the whole screen — an atomic night, a great turquoise atom, Googie stars twinkling, an arrow of blinking bulbs, the projector's beam opens, the card comes onto the big screen before finned cars, and as it turns a burst of stars and boomerangs, popcorn popping. A cream and turquoise pack that bursts into popcorn."},
        pack_bg="linear-gradient(160deg, transparent 0 58%, #3fd6cc 58% 70%, transparent 70%), linear-gradient(180deg, #fff2d6, #f2dcae)",
        pack_band="linear-gradient(180deg, #e51a38, #9c0f24)",
        word="color: #e51a38;\n  -webkit-text-stroke: 0.12rem #fff2d6;\n  paint-order: stroke fill;\n  text-shadow: 0.3rem 0.3rem 0 #3fd6cc, 0 0 2rem rgba(255, 210, 120, 0.8);",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  10% { filter: brightness(1.15); }
  16% { filter: none; }
  22% { filter: brightness(1.15); }
  28% { filter: none; }
  34% { transform: scale(1.02); filter: brightness(1.2); }
  37% { transform: scale(1.08); filter: brightness(1.8); opacity: 1; }
  42%, 100% { transform: scale(0.2); filter: brightness(2); opacity: 0; }
}""",
        parts={"backdrop": texts("Séance en plein air", "Open-air show", "Une nuit étoilée de l'ère atomique, le grand écran du drive-in éclairé par le faisceau, les voitures à ailerons et leurs feux rouges, une flèche d'ampoules qui clignotent (vidéo en boucle).", "A starry atomic-age night, the drive-in's big screen lit by the beam, finned cars and their red taillights, an arrow of chasing bulbs (a looping video)."),
               "look": texts("Chrome et crème", "Chrome and cream", "Un paquet crème barré d'une aile turquoise, une bande cerise, l'image de l'œuvre dans un écran de télévision arrondi, son nom en script, une étoile Googie et un atome en emblème.", "A cream pack crossed by a turquoise fin, a cherry band, the work's art in a rounded television screen, its name in script, a Googie star and an atom as emblem."),
               "opening": texts("Pop-corn", "Popcorn", "Les ampoules font le tour du paquet comme une enseigne ; il éclate en pop-corn et en étoiles.", "Bulbs chase round the pack like a marquee; it bursts into popcorn and stars."),
               "back": texts("Dos atomique", "Atomic back", "Crème et turquoise, une étoile Googie et un atome.", "Cream and turquoise, a Googie star and an atom.")}),
    "super8": dict(
        font=("Shrikhand.woff2", "Edition Shrikhand", "400"), ink="#2a0645", main="#ff7614", light="#ff4599", emblem=emblem_super8,
        names={"fr": "Psychédélique — édition Super 8", "en": "Psychedelic — Super 8 edition"},
        description={"fr": "Le booster de l'édition Super 8 (les années 1960) : chaque rareté prend tout l'écran — des anneaux op-art qui ondulent autour d'un soleil rayonnant, les couleurs qui fondent en haut et en bas, une goutte de lampe à lave envahit l'écran, la carte arrive parmi des fleurs qui tournent, et au retournement une gerbe de fleurs et les anneaux qui vibrent. Un paquet violet qui fond en coulures de couleur.",
                     "en": "The Super 8 edition's booster (the 1960s): every rarity takes the whole screen — op-art rings rippling round a radiating sun, the colours melting top and bottom, a lava-lamp blob swallows the screen, the card comes among turning flowers, and as it turns a spray of flowers and the rings shaking. A purple pack that melts in runs of colour."},
        pack_bg="repeating-radial-gradient(circle at 50% 45%, #ff7614 0 8px, #3a0a5c 8px 16px, #ff4599 16px 24px, #6b1a8f 24px 32px)",
        pack_band="linear-gradient(180deg, #ffdb33, #ff7614)",
        word="color: #ffdb33;\n  font-style: italic;\n  -webkit-text-stroke: 0.12rem #2a0645;\n  paint-order: stroke fill;\n  text-shadow: 0.25rem 0.25rem 0 #ff4599, 0.5rem 0.5rem 0 #ff7614, 0.75rem 0.75rem 0 #2a0645;",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  20% { filter: hue-rotate(60deg); }
  30% { transform: skewX(4deg); filter: hue-rotate(160deg); }
  38% { transform: translateY(4%) scale(1.02, 1.1) skewX(-6deg); filter: hue-rotate(260deg); opacity: 1; }
  48%, 100% { transform: translateY(40%) scale(0.9, 1.6); filter: hue-rotate(360deg); opacity: 0; }
}""",
        parts={"backdrop": texts("Op-art", "Op-art", "Des anneaux op-art qui ondulent en violet, orange et rose autour d'un soleil aux rayons qui tournent, des bandes qui fondent en haut et en bas (vidéo en boucle).", "Op-art rings rippling in purple, orange and pink round a sun with turning rays, bands melting top and bottom (a looping video)."),
               "look": texts("Affiche de concert", "Concert poster", "Un paquet d'anneaux psychédéliques, l'image de l'œuvre dans une fenêtre arrondie, son nom en lettres grasses penchées aux contours décalés, une fleur en emblème.", "A pack of psychedelic rings, the work's art in a rounded window, its name in fat slanted letters with offset outlines, a flower as emblem."),
               "opening": texts("Ça fond", "Meltdown", "Les couleurs du paquet tournent, des anneaux ondulent ; il fond en coulures roses, orange et violettes.", "The pack's colours turn, rings ripple out; it melts in pink, orange and purple runs."),
               "back": texts("Dos op-art", "Op-art back", "Anneaux psychédéliques et une fleur.", "Psychedelic rings and a flower.")}),
    "film": dict(
        font=("AlfaSlabOne.woff2", "Edition Alfa Slab", "400"), ink="#241a14", main="#ff9430", light="#e65430", emblem=emblem_film,
        names={"fr": "Affiche 70s — édition Pellicule", "en": "70s poster — Film reel edition"},
        description={"fr": "Le booster de l'édition Pellicule (les années 1970) : chaque rareté prend tout l'écran — l'amorce du compte à rebours sur du papier vieilli, son balayage qui tourne, la carte arrive devant un soleil couchant en bandes sous un ciel de trame, des bandes de pellicule qui défilent, et au retournement des rayons de soleil et des bouts d'affiche. Une affiche de papier arrachée en lambeaux.",
                     "en": "The Film reel edition's booster (the 1970s): every rarity takes the whole screen — the countdown leader on aged paper, its sweep going round, the card comes before a banded sunset under a halftone sky, strips of film running, and as it turns sun rays and scraps of poster. A paper poster torn to shreds."},
        pack_bg="linear-gradient(180deg, transparent 0 52%, #e65430 52% 58%, transparent 58% 62%, #9c2a3e 62% 68%, transparent 68%), radial-gradient(circle at 50% 52%, #ffcc4d 0 30%, transparent 30.5%), linear-gradient(180deg, #eedbb8, #d9c08f)",
        pack_band="linear-gradient(180deg, #241a14, #3d2b20)",
        word="color: #ffcc4d;\n  -webkit-text-stroke: 0.12rem #241a14;\n  paint-order: stroke fill;\n  text-shadow: 0.35rem 0.35rem 0 #e65430, 0.7rem 0.7rem 0 #241a14;",
        fate="""@keyframes edition-fate {
  0% { transform: none; clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); opacity: 1; }
  30% { transform: none; }
  34% { transform: rotate(-3deg); clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); }
  40% { transform: translate(-10%, -20%) rotate(-12deg); clip-path: polygon(0 0, 100% 0, 100% 40%, 0 70%); opacity: 1; }
  50%, 100% { transform: translate(-30%, -60%) rotate(-25deg); clip-path: polygon(0 0, 100% 0, 100% 40%, 0 70%); opacity: 0; }
}""",
        parts={"backdrop": texts("Coucher de soleil 70s", "70s sunset", "Le coucher de soleil d'une affiche des années 1970 : un soleil en bandes, un ciel de trame, le sol rayé, le grain du papier, des bandes de pellicule qui défilent en haut et en bas (vidéo en boucle).", "A 1970s poster's sunset: a banded sun, a halftone sky, striped ground, the paper's grain, strips of film running along top and foot (a looping video)."),
               "look": texts("Affiche d'époque", "Period poster", "Un paquet de papier vieilli, un soleil couchant en bandes, l'image de l'œuvre, son nom en lettres d'affiche, une bobine en emblème.", "An aged paper pack, a banded setting sun, the work's art, its name in poster letters, a reel as emblem."),
               "opening": texts("Affiche arrachée", "Torn poster", "Une déchirure traverse l'affiche ; elle est arrachée, des lambeaux de papier volent.", "A tear runs across the poster; it is ripped off, scraps of paper flying."),
               "back": texts("Dos d'affiche", "Poster back", "Papier vieilli, soleil couchant, une bobine.", "Aged paper, a setting sun, a reel.")}),
    "laserdisc": dict(
        font=("Bungee.woff2", "Edition Bungee", "400"), ink="#0f0f14", main="#ff9ab8", light="#ffd633", emblem=emblem_laserdisc,
        names={"fr": "Memphis — édition LaserDisc", "en": "Memphis — LaserDisc edition"},
        description={"fr": "Le booster de l'édition LaserDisc (le début des années 1980) : chaque rareté prend tout l'écran — des formes Memphis pastel cerclées de noir sur du papier millimétré, des gribouillis, un grand disque coloré roule sur l'écran, la carte arrive devant un disque irisé qui tourne parmi des confettis en orbite, et au retournement une explosion de confettis. Un paquet découpé en formes qui s'éparpillent.",
                     "en": "The LaserDisc edition's booster (the early 1980s): every rarity takes the whole screen — pastel Memphis shapes ringed in black on graph paper, squiggles, a giant coloured disc rolls across, the card comes before a spinning iridescent disc among orbiting confetti, and as it turns a burst of confetti. A pack cut into shapes that scatter."},
        pack_bg="radial-gradient(circle at 25% 25%, #ffd633 0 14%, transparent 14.5%), linear-gradient(135deg, transparent 0 62%, #8cead0 62% 80%, transparent 80%), repeating-linear-gradient(0deg, rgba(64, 115, 255, 0.2) 0 1px, transparent 1px 12px), repeating-linear-gradient(90deg, rgba(64, 115, 255, 0.2) 0 1px, transparent 1px 12px), #fff8e6",
        pack_band="repeating-linear-gradient(45deg, #0f0f14 0 6px, #ff9ab8 6px 12px)",
        word="color: #ffd633;\n  -webkit-text-stroke: 0.12rem #0f0f14;\n  paint-order: stroke fill;\n  text-shadow: 0.4rem 0.4rem 0 #0f0f14, 0 0 0 #ff9ab8;",
        fate="""@keyframes edition-fate {
  0% { transform: none; opacity: 1; }
  25% { transform: rotate(-3deg); }
  30% { transform: rotate(3deg); }
  35% { transform: rotate(-2deg) scale(1.05); }
  38% { transform: scale(1.08); opacity: 1; }
  40%, 100% { transform: scale(0) rotate(90deg); opacity: 0; }
}""",
        parts={"backdrop": texts("Memphis", "Memphis", "Une grille pastel qui file vers un soleil jaune, des confettis Memphis cerclés de noir qui dérivent et tournent, un disque irisé qui tourne dans un coin (vidéo en boucle).", "A pastel grid running off to a yellow sun, Memphis confetti ringed in black drifting and turning, an iridescent disc spinning in a corner (a looping video)."),
               "look": texts("Papier Memphis", "Memphis paper", "Un paquet de papier millimétré, un soleil jaune, une bande pastel, l'image de l'œuvre à ombre portée, son nom en capitales géométriques, un disque irisé en emblème.", "A graph paper pack, a yellow sun, a pastel band, the work's art with a solid shadow, its name in geometric capitals, an iridescent disc as emblem."),
               "opening": texts("Éclaté en formes", "Shape burst", "Un gribouillis traverse le paquet ; il éclate en triangles, ronds et barres pastel.", "A squiggle runs across the pack; it bursts into pastel triangles, circles and bars."),
               "back": texts("Dos Memphis", "Memphis back", "Papier millimétré, formes pastel, un disque irisé.", "Graph paper, pastel shapes, an iridescent disc.")}),
    "vhs": dict(
        font=("PressStart2P.woff2", "Edition Press Start", "400"), ink="#0a0917", main="#33fff2", light="#ff40cc", emblem=emblem_vhs,
        names={"fr": "Arcade — édition VHS", "en": "Arcade — VHS edition"},
        description={"fr": "Le booster de l'édition VHS (la fin des années 1980) : chaque rareté prend tout l'écran — un crépuscule en bandes de pixels sur une ville de pixels, un soleil rayé, les lignes de balayage et la bande de tracking de la cassette, l'écran se dissout en gros pixels, la carte arrive parmi des pièces qui tournent, et au retournement une explosion 8 bits. Un paquet de borne d'arcade qui se brouille et explose en pixels.",
                     "en": "The VHS edition's booster (the late 1980s): every rarity takes the whole screen — a dusk in pixel bands over a pixel city, a striped sun, scanlines and the tape's tracking band, the screen dissolves into big pixels, the card comes among spinning coins, and as it turns an 8-bit explosion. An arcade cabinet pack that glitches and bursts into pixels."},
        pack_bg="linear-gradient(180deg, #1a1445 0 30%, #2e1c63 30% 45%, #5a2378 45% 58%, #a1347c 58% 70%, #e0507a 70% 80%, #ff8c66 80%)",
        pack_band="repeating-linear-gradient(90deg, #33fff2 0 8px, #0a0917 8px 16px)",
        word="color: #ffffff;\n  -webkit-text-stroke: 0;\n  text-shadow: 0.3rem 0 0 #ff40cc, -0.3rem 0 0 #33fff2, 0 0.3rem 0 #0a0917;",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  16% { transform: none; }
  18% { transform: translate(-6px, 0); filter: hue-rotate(60deg); }
  20% { transform: translate(4px, 0); filter: none; }
  26% { transform: none; filter: contrast(1.4); }
  30% { transform: translate(-8px, 2px); filter: hue-rotate(-60deg); }
  34% { transform: none; filter: none; }
  37% { transform: scale(1.04); filter: brightness(2); opacity: 1; }
  40%, 100% { transform: scale(1.15); filter: brightness(2); opacity: 0; }
}""",
        parts={"backdrop": texts("Crépuscule 8 bits", "8-bit dusk", "Un crépuscule en bandes de pixels sur une ville de pixels aux fenêtres allumées, un soleil rayé, des étoiles qui clignotent, des lignes de balayage, la bande de tracking qui passe (vidéo en boucle).", "A dusk in pixel bands over a pixel city with lit windows, a striped sun, blinking stars, scanlines, the tracking band passing (a looping video)."),
               "look": texts("Borne d'arcade", "Arcade cabinet", "Un paquet de crépuscule en bandes de pixels, une bande néon, l'image de l'œuvre sur un écran, son nom en lettres de jeu vidéo, un soleil de pixels en emblème.", "A pack of dusk in pixel bands, a neon band, the work's art on a screen, its name in video game letters, a pixel sun as emblem."),
               "opening": texts("Game over", "Game over", "Le paquet se brouille comme une cassette usée ; il explose en pixels de couleur.", "The pack glitches like a worn tape; it bursts into coloured pixels."),
               "back": texts("Dos 8 bits", "8-bit back", "Crépuscule en pixels, un soleil rayé.", "A pixel dusk, a striped sun.")}),
    "zine": dict(
        font=("PermanentMarker.woff2", "Edition Marker", "400"), ink="#121212", main="#f2f0e6", light="#ff3388", emblem=emblem_zine,
        names={"fr": "Photocopie — édition Fanzine", "en": "Photocopy — Zine edition"},
        description={"fr": "Le booster de l'édition Fanzine (le milieu des années 1990) : chaque rareté prend tout l'écran — un collage de bouts de pages photocopiés sur le noir du toner, du scotch, du surligneur, un cercle au feutre rose, la lumière du photocopieur passe, la carte arrive et le feutre l'entoure, et au retournement du scotch claqué sur ses coins et des étoiles griffonnées. Un paquet barré au feutre et déchiré en morceaux.",
                     "en": "The Zine edition's booster (the mid-1990s): every rarity takes the whole screen — a collage of photocopied scraps on black toner, tape, a highlighter, a pink marker loop, the copier's light passes, the card comes and the marker rings it, and as it turns tape slapped on its corners and scribbled stars. A pack crossed out in marker and torn to pieces."},
        pack_bg="linear-gradient(170deg, transparent 0 70%, rgba(255, 242, 38, 0.6) 70% 76%, transparent 76%), repeating-radial-gradient(circle at 30% 30%, rgba(0, 0, 0, 0.15) 0 1px, transparent 1px 4px), linear-gradient(#f2f0e6, #dcdad0)",
        pack_band="linear-gradient(180deg, #121212, #2a2a2a)",
        word="color: #ff3388;\n  -webkit-text-stroke: 0.1rem #121212;\n  paint-order: stroke fill;\n  text-shadow: 0.25rem 0.25rem 0 #fff226, 0 0 1.2rem rgba(0, 0, 0, 0.8);",
        fate="""@keyframes edition-fate {
  0% { transform: none; opacity: 1; }
  12% { transform: none; }
  30% { transform: rotate(-1deg); }
  38% { transform: rotate(2deg) scale(1.02); opacity: 1; }
  40%, 100% { transform: rotate(6deg) scale(0.9); opacity: 0; }
}""",
        parts={"backdrop": texts("Collage photocopié", "Photocopied collage", "Un collage de bouts de pages photocopiés qui bougent un peu à chaque copie, du surligneur, un cercle au feutre rose, le grain du toner, la lumière du photocopieur qui passe (vidéo en boucle).", "A collage of photocopied scraps shifting a little at each copy, a highlighter, a pink marker loop, the toner's grain, the copier's light passing (a looping video)."),
               "look": texts("Fanzine", "Zine", "Un paquet photocopié, du surligneur, l'image de l'œuvre tramée, son nom au feutre, une étoile griffonnée et du scotch en emblème.", "A photocopied pack, a highlighter, the work's art in halftone, its name in marker, a scribbled star and tape as emblem."),
               "opening": texts("Barré, déchiré", "Crossed out, torn", "Le paquet est barré d'une croix au feutre rose ; il est déchiré en morceaux qui volent.", "The pack is crossed out in pink marker; it is torn into flying pieces."),
               "back": texts("Dos photocopié", "Photocopied back", "Papier photocopié, une étoile au feutre.", "Photocopied paper, a marker star.")}),
    "bubble": dict(
        font=("Fredoka.woff2", "Edition Fredoka", "700"), ink="#05224d", main="#80dbff", light="#4dff8c", emblem=emblem_bubble,
        names={"fr": "Bulle Y2K — édition Bulle", "en": "Y2K bubble — Bubble edition"},
        description={"fr": "Le booster de l'édition Bulle (autour de l'an 2000) : chaque rareté prend tout l'écran — des bulles translucides qui montent devant une pluie de code vert, une bulle géante gonfle et éclate, la carte arrive devant un grand orbe bleu bonbon, et au retournement des bulles qui jaillissent et éclatent en gouttelettes. Un paquet de plastique translucide emporté dans une bulle qui éclate.",
                     "en": "The Bubble edition's booster (around 2000): every rarity takes the whole screen — translucent bubbles rising before a rain of green code, a giant bubble swells and pops, the card comes before a great candy-blue orb, and as it turns bubbles bursting out and popping into droplets. A translucent plastic pack carried off in a bubble that pops."},
        pack_bg="repeating-linear-gradient(180deg, rgba(255, 255, 255, 0.12) 0 2px, transparent 2px 5px), radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.7), transparent 30%), linear-gradient(170deg, #80dbff, #1a8ae6 60%, #0a4ca8)",
        pack_band="linear-gradient(180deg, #c8f5ff, #4dc2f5)",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  14% { transform: translateY(0); }
  40% { transform: translateY(-8%) scale(1.03); filter: none; opacity: 1; }
  44% { transform: translateY(-8%) scale(1.12); filter: brightness(1.4); opacity: 1; }
  48%, 100% { transform: translateY(-8%) scale(1.3); filter: brightness(1.4); opacity: 0; }
}""",
        parts={"backdrop": texts("Pluie de code", "Code rain", "Un bleu bonbon profond sous de fines rayures, une pluie de code vert, des bulles brillantes qui montent en se balançant (vidéo en boucle).", "A deep candy blue under fine stripes, a rain of green code, glossy bubbles rising and swaying (a looping video)."),
               "look": texts("Plastique translucide", "Translucent plastic", "Un paquet de plastique bleu bonbon rayé, un reflet brillant, l'image de l'œuvre sur un écran arrondi, son nom en lettres rondes, une bulle en emblème.", "A striped candy-blue plastic pack, a glossy highlight, the work's art on a rounded screen, its name in round letters, a bubble as emblem."),
               "opening": texts("Bulle", "Bubble", "Une bulle se referme sur le paquet et l'emporte un peu vers le haut ; elle éclate en gouttelettes.", "A bubble closes round the pack and carries it up a little; it pops into droplets."),
               "back": texts("Dos translucide", "Translucent back", "Plastique bleu bonbon, une bulle.", "Candy-blue plastic, a bubble.")}),
    "disc": dict(
        font=("UncialAntiqua.woff2", "Edition Uncial", "400"), ink="#1a0510", main="#e0ad47", light="#d91a2e", emblem=emblem_disc,
        names={"fr": "Vitrail — édition DVD", "en": "Stained glass — DVD edition"},
        description={"fr": "Le booster de l'édition DVD (le milieu des années 2000) : chaque rareté prend tout l'écran — une rosace de vitrail qui tourne sur un damas lie-de-vin, des volutes dorées, des braises qui montent, la rosace s'embrase de lumière, la carte arrive devant elle dans ses rayons, et au retournement le vitrail éclate en éclats de couleur. Un paquet de vitrail qui se brise.",
                     "en": "The DVD edition's booster (the mid-2000s): every rarity takes the whole screen — a stained-glass rose window turning on a wine damask, gold scrolls, embers rising, the window flares with light, the card comes before it in its rays, and as it turns the glass bursts into coloured shards. A stained-glass pack that shatters."},
        pack_bg="radial-gradient(circle at 50% 42%, transparent 0 28%, #e0ad47 28% 30%, transparent 30%), repeating-conic-gradient(from 0deg at 50% 42%, #d91a2e 0 18deg, #264dd9 18deg 36deg, #1a9e59 36deg 54deg, #ff9e1f 54deg 72deg, #8033bf 72deg 90deg), #3d0a1a",
        pack_band="linear-gradient(180deg, #ffe699, #b8862a)",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  25% { filter: brightness(1.2) saturate(1.3); }
  36% { filter: brightness(1.8) saturate(1.5); }
  38% { filter: brightness(2.4); opacity: 1; }
  40%, 100% { transform: scale(1.05); filter: brightness(2.4); opacity: 0; }
}""",
        parts={"backdrop": texts("Rosace", "Rose window", "Un damas lie-de-vin, une rosace de vitrail qui luit dans l'ombre, sa lumière qui tombe en rayons, des braises qui montent, des volutes dorées dans les coins (vidéo en boucle).", "A wine damask, a stained-glass rose window glowing in the dark, its light falling in rays, embers rising, gold scrolls in the corners (a looping video)."),
               "look": texts("Vitrail", "Stained glass", "Un paquet lie-de-vin, une rosace de vitrail cerclée d'or, l'image de l'œuvre au centre, son nom en onciales, une rosace en emblème.", "A wine pack, a stained-glass rose window ringed in gold, the work's art in the middle, its name in uncials, a rose window as emblem."),
               "opening": texts("Vitrail brisé", "Shattered glass", "La lumière inonde le paquet comme un vitrail ; il se brise en éclats de couleur sertis d'or.", "Light floods the pack like a window; it shatters into coloured shards set in gold."),
               "back": texts("Dos de vitrail", "Stained-glass back", "Damas lie-de-vin, une rosace.", "Wine damask, a rose window.")}),
    "leather": dict(
        font=("Rye.woff2", "Edition Rye", "400"), ink="#2e1608", main="#d9a54a", light="#8fc2ed", emblem=emblem_leather,
        names={"fr": "Cuir & lin — édition Cuir & lin", "en": "Leather & linen — Leather & linen edition"},
        description={"fr": "Le booster de l'édition Cuir & lin (le skeuomorphisme) : chaque rareté prend tout l'écran — un ciel d'aquarelle, des nuages qui passent, des montgolfières qui montent, dans un cadre de cuir cousu aux rivets de laiton, la couverture de cuir se referme et se rouvre, la carte arrive parmi les montgolfières, et au retournement un lâcher de ballons et un ruban de satin. Un paquet de cuir emporté par des ballons.",
                     "en": "The Leather & linen edition's booster (skeuomorphism): every rarity takes the whole screen — a watercolour sky, clouds drifting, hot-air balloons rising, in a stitched leather rim with brass rivets, the leather cover closes and opens again, the card comes among the balloons, and as it turns a release of balloons and a satin ribbon. A leather pack carried off by balloons."},
        pack_bg="radial-gradient(circle at 50% 42%, #8fc2ed 0 32%, transparent 32.5%), repeating-linear-gradient(45deg, rgba(0, 0, 0, 0.06) 0 2px, transparent 2px 4px), linear-gradient(170deg, #7a4520, #4a2810)",
        pack_band="repeating-linear-gradient(90deg, #f5dc9e 0 6px, transparent 6px 10px), linear-gradient(180deg, #e0ad47, #9c7020)",
        fate="""@keyframes edition-fate {
  0% { transform: none; opacity: 1; }
  37% { transform: translateY(0) rotate(0); opacity: 1; }
  45% { transform: translateY(-40%) rotate(-2deg); }
  58% { transform: translateY(-134%) rotate(2deg); opacity: 1; }
  70%, 100% { transform: translateY(-175%) rotate(3deg); opacity: 0; }
}""",
        parts={"backdrop": texts("Ciel d'aquarelle", "Watercolour sky", "Un ciel d'aquarelle, des nuages doux qui passent, des montgolfières qui montent lentement, dans un cadre de cuir cousu aux rivets de laiton (vidéo en boucle).", "A watercolour sky, soft clouds drifting, hot-air balloons rising slowly, in a stitched leather rim with brass rivets (a looping video)."),
               "look": texts("Cuir cousu", "Stitched leather", "Un paquet de cuir cousu, un hublot de ciel bleu, l'image de l'œuvre, son nom gravé, une montgolfière en emblème.", "A stitched leather pack, a porthole of blue sky, the work's art, its name pressed in, a hot-air balloon as emblem."),
               "opening": texts("Lâcher de ballons", "Balloon lift", "Des ballons attachés au paquet se gonflent ; ils l'emportent dans le ciel.", "Balloons tied to the pack fill up; they carry it away into the sky."),
               "back": texts("Dos de cuir", "Leather back", "Cuir cousu, une montgolfière.", "Stitched leather, a hot-air balloon.")}),
    "tiles": dict(
        font=("Raleway.woff2", "Edition Raleway", "200"), ink="#1a1a1f", main="#00aba8", light="#f7941a", emblem=emblem_tiles,
        names={"fr": "Aplats — édition Tuiles", "en": "Flat — Tiles edition"},
        description={"fr": "Le booster de l'édition Tuiles (le design plat) : chaque rareté prend tout l'écran — une mosaïque de tuiles plates qui se retournent en vague, un soleil plat qui bat avec sa longue ombre, les tuiles recouvrent l'écran et le découvrent, la carte arrive avec sa longue ombre, et au retournement des carrés de couleur projetés et des bandes plates qui balaient. Un paquet qui se défait en tuiles qui se retournent.",
                     "en": "The Tiles edition's booster (flat design): every rarity takes the whole screen — a mosaic of flat tiles turning over in a wave, a flat sun pulsing with its long shadow, the tiles cover the screen and uncover it, the card comes with its long shadow, and as it turns squares of colour flung out and flat stripes sweeping. A pack that comes apart in tiles turning over."},
        pack_bg="linear-gradient(90deg, #00aba8 0 48%, transparent 48% 52%, #f7941a 52%) 0 0 / 100% 33% no-repeat, linear-gradient(90deg, #e04d3d 0 48%, transparent 48% 52%, #2180c7 52%) 0 50% / 100% 30% no-repeat, linear-gradient(90deg, #8cc233 0 48%, transparent 48% 52%, #9954b8 52%) 0 100% / 100% 32% no-repeat, #1a1a1f",
        pack_band="linear-gradient(#00aba8, #00aba8)",
        word="color: #ffffff;\n  letter-spacing: 0.02em;\n  text-transform: lowercase;\n  text-shadow: none;",
        fate="""@keyframes edition-fate {
  0% { opacity: 1; }
  27% { opacity: 1; }
  29%, 100% { opacity: 0; }
}""",
        parts={"backdrop": texts("Mosaïque plate", "Flat mosaic", "Une mosaïque de tuiles plates en huit couleurs qui se retournent en vague, un soleil plat qui bat avec sa longue ombre (vidéo en boucle).", "A mosaic of flat tiles in eight colours turning over in a wave, a flat sun pulsing with its long shadow (a looping video)."),
               "look": texts("Tuiles", "Tiles", "Un paquet de tuiles plates en couleurs vives sur fond sombre, sans ombre ni dégradé, l'image de l'œuvre en tuile, son nom en lettres fines, quatre tuiles en emblème.", "A pack of flat tiles in bright colours on a dark ground, no shadow nor gradient, the work's art as a tile, its name in thin letters, four tiles as emblem."),
               "opening": texts("Retournement", "Flip away", "Le paquet se défait en une grille de tuiles qui se retournent et s'en vont, en vague.", "The pack comes apart in a grid of tiles turning over and away, in a wave."),
               "back": texts("Dos en tuiles", "Tiles back", "Tuiles plates de couleur, sans ombre.", "Flat coloured tiles, no shadow.")}),
    "stream": dict(
        font=("Audiowide.woff2", "Edition Audiowide", "400"), ink="#05051a", main="#33f2ff", light="#ff2699", emblem=emblem_stream,
        names={"fr": "Holo — édition Streaming", "en": "Holo — Streaming edition"},
        description={"fr": "Le booster de l'édition Streaming (la fin des années 2010) : chaque rareté prend tout l'écran — un sol de grille néon qui file vers une brume magenta, l'anneau de chargement qui tourne, des crochets d'interface, des parasites de temps en temps, une ligne de balayage descend, la carte arrive sur une plateforme holographique, et au retournement des anneaux d'hologramme qui montent. Un paquet qui se brouille et s'envole en voxels.",
                     "en": "The Streaming edition's booster (the late 2010s): every rarity takes the whole screen — a neon grid floor running to a magenta haze, the loading ring spinning, interface brackets, a glitch now and then, a scan line falls, the card comes onto a holographic platform, and as it turns hologram rings rising. A pack that glitches and is uploaded in voxels."},
        pack_bg="linear-gradient(180deg, transparent 0 60%, rgba(255, 38, 153, 0.5) 60% 62%, transparent 62%), repeating-linear-gradient(90deg, rgba(51, 242, 255, 0.25) 0 1px, transparent 1px 14px), repeating-linear-gradient(0deg, rgba(51, 242, 255, 0.25) 0 1px, transparent 1px 14px), linear-gradient(180deg, #120a33, #05051a)",
        pack_band="linear-gradient(90deg, #33f2ff, #ff2699)",
        word="color: #ffffff;\n  -webkit-text-stroke: 0.06rem #33f2ff;\n  text-shadow: 0 0 1.4rem #33f2ff, 0.2rem 0 0 #ff2699, -0.2rem 0 0 #33f2ff;",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; clip-path: inset(0 0 0 0); opacity: 1; }
  20% { transform: none; clip-path: inset(0 0 0 0); }
  22% { transform: translate(-6px, 0); clip-path: inset(10% 0 60% 0); }
  24% { transform: translate(5px, 0); clip-path: inset(40% 0 20% 0); }
  26% { transform: none; clip-path: inset(0 0 0 0); }
  30% { transform: translate(-3px, 0); }
  34% { transform: none; filter: hue-rotate(90deg); clip-path: inset(0 0 0 0); opacity: 1; }
  38% { clip-path: inset(48% 0 48% 0); filter: brightness(2); }
  42%, 100% { clip-path: inset(50% 0 50% 0); filter: brightness(2); opacity: 0; }
}""",
        parts={"backdrop": texts("Grille néon", "Neon grid", "Un sol de grille néon qui file vers une brume magenta à l'horizon, un soleil violet de lignes, des particules qui montent, un faisceau de balayage, des parasites de temps en temps (vidéo en boucle).", "A neon grid floor running to a magenta haze on the horizon, a violet sun of lines, particles rising, a scan beam, a glitch now and then (a looping video)."),
               "look": texts("Coque holo", "Holo hull", "Un paquet sombre quadrillé de néon, une bande cyan et magenta, l'image de l'œuvre derrière des crochets, son nom en lettres techniques, un bouton lecture en emblème.", "A dark pack gridded in neon, a cyan and magenta band, the work's art behind brackets, its name in technical letters, a play button as emblem."),
               "opening": texts("Téléversé", "Uploaded", "Le paquet se brouille en bandes, l'image se replie en une ligne ; il s'envole en voxels de lumière.", "The pack glitches in bars, its picture collapses into a line; it is uploaded in voxels of light."),
               "back": texts("Dos holo", "Holo back", "Grille néon, un bouton lecture.", "A neon grid, a play button.")}),
    "glass": dict(
        font=("Unbounded.woff2", "Edition Unbounded", "800"), ink="#040a1f", main="#26bff2", light="#40ffa6", emblem=emblem_glass,
        names={"fr": "Verre liquide — édition Verre", "en": "Liquid glass — Glass edition"},
        description={"fr": "Le booster de l'édition Verre liquide (aujourd'hui) : chaque rareté prend tout l'écran — les voiles d'une aurore sous des plaques de verre dépoli qui flottent, des gouttes de verre, une goutte liquide s'étale sur l'écran, la carte arrive derrière une grande lentille parmi des plaques en orbite, et au retournement des ondes qui courent sur le verre et un reflet qui le traverse. Un paquet qui fond en verre liquide.",
                     "en": "The Liquid glass edition's booster (today): every rarity takes the whole screen — an aurora's veils under floating plates of frosted glass, drops of glass, a liquid drop spreads over the screen, the card comes behind a great lens among orbiting plates, and as it turns ripples running over the glass and a glint crossing it. A pack that melts into liquid glass."},
        pack_bg="linear-gradient(160deg, rgba(255, 255, 255, 0.35), rgba(255, 255, 255, 0.05) 40%, rgba(255, 255, 255, 0.2)), radial-gradient(ellipse at 30% 30%, #40ffa6, transparent 50%), radial-gradient(ellipse at 70% 60%, #9966ff, transparent 55%), linear-gradient(170deg, #26bff2, #0a1a4a)",
        pack_band="linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(200, 230, 255, 0.5))",
        fate="""@keyframes edition-fate {
  0% { transform: none; filter: none; opacity: 1; }
  25% { transform: none; filter: blur(0); }
  34% { transform: scale(1.02, 0.98); filter: blur(2px); }
  40% { transform: translateY(6%) scale(1.1, 0.9); filter: blur(6px); opacity: 1; }
  46%, 100% { transform: translateY(20%) scale(1.3, 0.6); filter: blur(14px); opacity: 0; }
}""",
        parts={"backdrop": texts("Aurore sous verre", "Aurora under glass", "Les voiles d'une aurore qui bougent sous des plaques de verre dépoli, chacune avec sa lumière en haut et son bord clair, un reflet qui les traverse (vidéo en boucle).", "An aurora's veils moving under plates of frosted glass, each with its light on top and its bright edge, a glint crossing them (a looping video)."),
               "look": texts("Verre dépoli", "Frosted glass", "Un paquet de verre dépoli sur une aurore, un bord clair, l'image de l'œuvre vue à travers une lentille, son nom en lettres larges, une goutte de verre en emblème.", "A frosted glass pack over an aurora, a bright edge, the work's art seen through a lens, its name in wide letters, a drop of glass as emblem."),
               "opening": texts("Fonte", "Melt", "Le paquet se trouble et fond en verre liquide ; des ondes courent, des gouttes tombent.", "The pack blurs and melts into liquid glass; ripples run, drops fall."),
               "back": texts("Dos de verre", "Glass back", "Verre dépoli sur une aurore, une goutte.", "Frosted glass over an aurora, a drop.")}),
}
# --- each edition's reveal: how the card comes, and whether Portalab's word for the rarity shows, and how ---------
# word: ("slam", scale, upright) — Portalab's own: huge, on a slant, cut as the card comes; a stylesheet — the word
# set otherwise; None — no word, the card alone. card: its keyframes and how they play (from --card-at).
CONCEPTS = {
    "nitrate": dict(
        text=("Un intertitre de film muet : la rareté, droite, sous les filets d'argent, qui scintille comme la copie ; puis la carte projetée, sépia, tremblant dans le couloir du projecteur, se retourne.",
              "A silent film's intertitle: the rarity, upright, under the silver hairlines, flickering like the print; then the card projected, sepia, weaving in the projector's gate, turns over."),
        word="""  --word-turn: 0deg;
  font-size: min(9vw, 13vh);
  letter-spacing: 0.08em;
  animation: ed-nitrate-title var(--card-at) linear both;
}
/* the intertitle, flickering on the screen */
@keyframes ed-nitrate-title {
  0% { opacity: 0; translate: 0 0.4%; }
  8% { opacity: 0.7; }
  12% { opacity: 1; translate: 0 -0.3%; }
  30% { opacity: 0.8; }
  34% { opacity: 1; translate: 0 0.2%; }
  62% { opacity: 0.88; }
  66%, 86% { opacity: 1; translate: 0 0; }
  100% { opacity: 0; }""",
        card=("""  0% { opacity: 0; filter: sepia(1) brightness(2.2); transform: translateY(1.5%); }
  15% { opacity: 1; }
  22% { opacity: 0.35; transform: translateY(-1%); }
  30% { opacity: 1; transform: translateY(0.8%); }
  45% { opacity: 0.6; }
  55% { opacity: 1; filter: sepia(0.8) brightness(1.4); transform: translateY(-0.4%); }
  100% { opacity: 1; filter: none; transform: none; }""", "0.55s linear")),
    "noir": dict(
        text=("Pas de mot : le dossier est jeté sur le bureau — la carte glisse de côté, tournoie et s'arrête sous la lampe, au milieu des indices, puis se retourne.",
              "No word: the case file is tossed on the desk — the card slides in from the side, spins and stops under the lamp, amid the clues, then turns over."),
        word=None,
        card=("""  0% { transform: translate(-120vw, 8vh) rotate(-38deg); }
  70% { transform: translate(2vw, 0) rotate(5deg); }
  85% { transform: translate(-0.6vw, 0) rotate(-1.5deg); }
  100% { transform: none; }""", "0.55s cubic-bezier(0.2, 0.7, 0.3, 1)")),
    "drivein": dict(
        text=("La rareté s'allume en haut de l'écran comme l'enseigne au néon du drive-in, et y reste ; la carte, projetée de loin sur le grand écran, grandit dans le faisceau et se retourne.",
              "The rarity lights up at the top of the screen like the drive-in's neon sign, and stays; the card, projected from afar on the big screen, grows in the beam and turns over."),
        word="""  --word-turn: 0deg;
  top: 4%;
  font-size: min(10vw, 11vh);
  animation: ed-drivein-sign var(--takeover-s) linear both;
}
/* the neon sign sputters on, and stays lit */
@keyframes ed-drivein-sign {
  0% { opacity: 0; }
  4% { opacity: 1; }
  6% { opacity: 0.2; }
  9% { opacity: 1; }
  11% { opacity: 0.4; }
  14%, 92% { opacity: 1; }
  100% { opacity: 0; }""",
        card=("""  0% { opacity: 0; transform: translateY(-22vh) scale(0.08); filter: brightness(4) blur(4px); }
  60% { opacity: 1; transform: translateY(1vh) scale(1.04); filter: brightness(1.6) blur(0); }
  100% { transform: none; filter: none; }""", "0.55s cubic-bezier(0.3, 0.9, 0.4, 1)")),
    "super8": dict(
        text=("La rareté en lettres géantes sur l'affiche psychédélique ; puis la carte jaillit en spirale du tunnel de couleurs, ses teintes tournant, et se retourne.",
              "The rarity in huge letters over the psychedelic poster; then the card spirals out of the tunnel of colours, its hues turning, and turns over."),
        word=("slam", "0.75", "0.62"),
        card=("""  0% { opacity: 0; transform: rotate(-720deg) scale(0); filter: hue-rotate(0deg) saturate(2); }
  70% { opacity: 1; transform: rotate(12deg) scale(1.08); filter: hue-rotate(300deg) saturate(1.5); }
  100% { transform: none; filter: none; }""", "0.55s cubic-bezier(0.25, 0.8, 0.35, 1)")),
    "film": dict(
        text=("Le compte à rebours de l'amorce, puis la rareté en titre d'affiche des années 70 ; la carte se lève de l'horizon comme le soleil et se retourne.",
              "The leader's countdown, then the rarity as a seventies poster's title; the card rises from the horizon like the sun and turns over."),
        word=("slam", "0.7", "0.56"),
        card=("""  0% { transform: translateY(80vh); filter: saturate(1.6) brightness(1.3) hue-rotate(-15deg); }
  80% { transform: translateY(-2vh); }
  100% { transform: none; filter: none; }""", "0.55s cubic-bezier(0.2, 0.8, 0.3, 1)")),
    "laserdisc": dict(
        text=("La rareté en lettres géantes parmi les formes Memphis ; puis la carte surgit d'un bond, s'écrase et s'étire comme un dessin animé, et se retourne.",
              "The rarity in huge letters among the Memphis shapes; then the card pops out with a bounce, squashing and stretching like a cartoon, and turns over."),
        word=("slam", "0.7", "0.5"),
        card=("""  0% { transform: scale(0) rotate(-30deg); }
  45% { transform: scale(1.22, 0.78) rotate(4deg); }
  62% { transform: scale(0.86, 1.14) rotate(-2deg); }
  78% { transform: scale(1.06, 0.95); }
  100% { transform: none; }""", "0.55s ease-out")),
    "vhs": dict(
        text=("La rareté clignote en haut de l'écran comme le texte d'une borne d'arcade ; la carte s'allume comme un vieux téléviseur — une ligne blanche qui s'ouvre, par paliers — et se retourne.",
              "The rarity blinks at the top of the screen like an arcade cabinet's text; the card switches on like an old TV set — a white line opening up, in steps — and turns over."),
        word="""  --word-turn: 0deg;
  top: 6%;
  font-size: min(5.4vw, 6vh);
  letter-spacing: 0.06em;
  animation: ed-vhs-blink var(--takeover-s) steps(1) both;
}
/* blinking, as on an arcade cabinet, then steady */
@keyframes ed-vhs-blink {
  0% { opacity: 0; }
  4% { opacity: 1; }
  10% { opacity: 0; }
  16% { opacity: 1; }
  22% { opacity: 0; }
  28%, 92% { opacity: 1; }
  100% { opacity: 0; }""",
        card=("""  0% { opacity: 0; transform: scale(1.4, 0.01); filter: brightness(5); }
  25% { opacity: 1; transform: scale(1.2, 0.02); filter: brightness(5); }
  60% { transform: scale(0.95, 1.05); filter: brightness(2) contrast(1.4); }
  100% { transform: none; filter: none; }""", "0.5s steps(6)")),
    "zine": dict(
        text=("La rareté griffonnée en grand au marqueur ; puis la carte est plaquée sur la page comme un autocollant et y reste de travers, puis se retourne.",
              "The rarity scrawled big in marker; then the card is slapped on the page like a sticker and stays askew, then turns over."),
        word=("slam", "0.72", "0.52"),
        card=("""  0% { opacity: 0; transform: scale(2.6) rotate(-16deg); }
  55% { opacity: 1; transform: scale(0.94) rotate(-2deg); }
  75% { transform: scale(1.02) rotate(-4.5deg); }
  100% { transform: rotate(-3.5deg); }""", "0.45s linear")),
    "bubble": dict(
        text=("Pas de mot : la carte monte du fond de l'écran dans les bulles, en se balançant, et se retourne une fois arrivée.",
              "No word: the card rises from the foot of the screen among the bubbles, swaying, and turns over once there."),
        word=None,
        card=("""  0% { opacity: 0; transform: translate(0, 70vh) scale(0.6); }
  20% { opacity: 1; }
  40% { transform: translate(-4vw, 35vh) scale(0.75) rotate(-6deg); }
  70% { transform: translate(3vw, 6vh) scale(0.95) rotate(4deg); }
  88% { transform: translate(-1vw, -1vh) scale(1.03) rotate(-1deg); }
  100% { transform: none; }""", "0.55s ease-out")),
    "disc": dict(
        text=("Pas de mot : la carte descend lentement d'en haut, dans une lumière de vitrail qui s'apaise, et se retourne.",
              "No word: the card comes down slowly from above, in a stained-glass light that settles, and turns over."),
        word=None,
        card=("""  0% { opacity: 0; transform: translateY(-45vh) scale(0.85); filter: brightness(3) blur(8px); }
  70% { opacity: 1; transform: translateY(1vh) scale(1.01); filter: brightness(1.4) blur(0); }
  100% { transform: none; filter: none; }""", "0.55s cubic-bezier(0.25, 0.7, 0.35, 1)")),
    "leather": dict(
        text=("Pas de mot : la carte arrive suspendue de très haut, comme sous une montgolfière, se balance, et se retourne en se balançant encore.",
              "No word: the card comes hanging from high above, as under a hot-air balloon, swings, and turns over still swinging."),
        word=None,
        extra="  transform-origin: 50% -60vh;\n",
        card=("""  0% { opacity: 0; transform: rotate(-38deg); }
  10% { opacity: 1; }
  35% { transform: rotate(16deg); }
  58% { transform: rotate(-7deg); }
  78% { transform: rotate(3deg); }
  100% { transform: none; }""", "0.9s ease-in-out")),
    "tiles": dict(
        text=("La rareté en très grand titre fin, en minuscules, qui défile lentement derrière la carte comme un panorama ; la carte se rabat comme une tuile et se retourne.",
              "The rarity as a huge thin lower-case title, gliding slowly behind the card like a panorama; the card flips down like a tile and turns over."),
        word="""  --word-turn: 0deg;
  inset-inline: 4% auto;
  top: 3%;
  z-index: 1;
  font-size: min(26vw, 30vh);
  text-align: start;
  animation: ed-tiles-pan var(--takeover-s) linear both;
}
/* a panorama's title, gliding slowly across */
@keyframes ed-tiles-pan {
  0% { opacity: 0; translate: 30% 0; }
  8%, 92% { opacity: 1; }
  100% { opacity: 0; translate: -20% 0; }""",
        extra="  transform-origin: 50% 0;\n",
        card=("""  0% { opacity: 0; transform: perspective(1200px) rotateX(-95deg); }
  60% { opacity: 1; transform: perspective(1200px) rotateX(8deg); }
  100% { transform: none; }""", "0.5s cubic-bezier(0.1, 0.9, 0.2, 1)")),
    "stream": dict(
        text=("La rareté s'affiche en bas comme une légende de HUD, ses lettres se resserrant ; la carte se matérialise en hologramme, balayée de bas en haut, et se retourne.",
              "The rarity shows at the foot like a HUD caption, its letters closing in; the card materialises as a hologram, scanned from the foot up, and turns over."),
        word="""  --word-turn: 0deg;
  top: auto;
  bottom: 6%;
  font-size: min(4.5vw, 5vh);
  animation: ed-stream-hud var(--takeover-s) linear both;
}
/* a HUD's caption locking on */
@keyframes ed-stream-hud {
  0% { opacity: 0; letter-spacing: 1.6em; }
  10% { opacity: 1; letter-spacing: 0.5em; }
  12% { opacity: 0.3; }
  14%, 92% { opacity: 1; letter-spacing: 0.5em; }
  100% { opacity: 0; letter-spacing: 0.5em; }""",
        card=("""  0% { opacity: 0; clip-path: inset(100% -50% 0 -50%); filter: brightness(2.5) drop-shadow(0 0 1rem #33f2ff); transform: skewX(-8deg); }
  50% { opacity: 1; clip-path: inset(40% -50% 0 -50%); transform: skewX(4deg); }
  70% { clip-path: inset(0 -50% 0 -50%); filter: brightness(1.5) drop-shadow(0 0 0.6rem #33f2ff); transform: skewX(-2deg); }
  76% { opacity: 0.5; }
  80% { opacity: 1; }
  100% { clip-path: inset(-50% -50% -50% -50%); filter: none; transform: none; }""", "0.55s linear")),
    "glass": dict(
        text=("Pas de mot : la carte prend forme dans une goutte de verre liquide — floue, trop grande, elle se resserre et devient nette — puis se retourne.",
              "No word: the card takes shape in a drop of liquid glass — blurred, too big, it draws in and sharpens — then turns over."),
        word=None,
        card=("""  0% { opacity: 0; transform: scale(1.5); filter: blur(28px) saturate(2); }
  60% { opacity: 1; transform: scale(0.97); filter: blur(2px) saturate(1.3); }
  100% { transform: none; filter: none; }""", "0.55s cubic-bezier(0.2, 0.8, 0.3, 1)")),
}


def font_face(e):
    file, family, weight = e["font"]
    return f'@font-face {{\n  font-family: "{family}";\n  src: url("{file}") format("woff2");\n  font-weight: {weight};\n  font-display: swap;\n}}\n'


def look_css(key, e):
    h = f'[data-booster-look="{key}"]'
    fam, weight = e["font"][1], e["font"][2]
    return comment(f"The sealed pack (its hook: data-booster-look): {e['parts']['look'][3]}") + font_face(e) + f"""{h} .booster-pack {{
  border-radius: 0.5rem;
  background: {e['pack_bg']};
  box-shadow: inset 0 0 0 3px {e['ink']}, inset 0 0 0 6px {e['main']}, inset 0 0 0 8px {e['ink']}, 0 1rem 2rem rgba(0, 0, 0, 0.55), 0 0 1.4rem color-mix(in srgb, {e['main']} 40%, transparent);
}}
{h} .booster-pack__art {{
  inset: 13% 10% 33%;
  inline-size: 80%;
  block-size: 54%;
  border: 3px solid {e['ink']};
  border-radius: 0.3rem;
  box-shadow: 0 0 0 3px {e['light']}, 0 0 0 6px {e['ink']}, 0 0.5rem 1rem rgba(0, 0, 0, 0.5);
  mask: none;
}}
{h} .booster-pack__foil {{
  opacity: 1;
  background: linear-gradient(105deg, transparent 40%, rgba(255, 255, 255, 0.45) 48%, transparent 56%) -160% 0 / 200% 100% no-repeat;
  animation: edition-sweep 4s ease-in-out infinite;
}}
@keyframes edition-sweep {{
  0%, 55% {{ background-position: -160% 0; }}
  85%, 100% {{ background-position: 260% 0; }}
}}
{h} .booster-pack__stars {{
  opacity: 0;
}}
{h} .booster-pack__flap {{
  border: 0;
  background: {e['pack_band']};
  box-shadow: inset 0 -3px 0 {e['ink']};
}}
{h} .booster-pack__emblem {{
  inline-size: 62%;
  aspect-ratio: 1;
  background: url("emblem.svg") center / contain no-repeat;
  border-radius: 0;
  box-shadow: none;
}}
{h} .booster-pack__emblem svg {{
  opacity: 0;
}}
{h} .booster-pack__name {{
  inset: auto 3% 11%;
  font-family: "{fam}", sans-serif;
  font-weight: {weight};
  font-size: clamp(0.95rem, 2.2vw, 1.35rem);
  line-height: 1.1;
  color: #ffffff;
  -webkit-text-stroke: 4px {e['ink']};
  paint-order: stroke fill;
  text-shadow: 0 0 1rem color-mix(in srgb, {e['main']} 70%, transparent);
}}
{h} .booster-pack__count {{
  inset: 0.5rem 0.5rem auto auto;
  display: grid;
  place-items: center;
  inline-size: 2.6rem;
  block-size: 2.6rem;
  padding: 0;
  border-radius: 0;
  background: url("emblem.svg") center / contain no-repeat;
  color: #ffffff;
  font-family: "{fam}", sans-serif;
  font-weight: {weight};
  font-size: 0.8rem;
  text-shadow: 0 1px 3px #000000;
  box-shadow: none;
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-pack__foil {{
    animation: none;
  }}
}}
"""


def back_css(key, e):
    h = f'[data-card-back="{key}"]'
    return comment(f"Face down (its hook: the card, data-card-back), every card alike — a back never tells the rarity: {e['parts']['back'][3]}") + f"""{h} .booster-card__back {{
  border: 0;
  border-radius: 0.55rem;
  background: {e['pack_bg']};
  box-shadow: inset 0 0 0 3px {e['ink']}, inset 0 0 0 6px {e['main']}, inset 0 0 0 8px {e['ink']}, 0 0.5rem 1rem rgba(0, 0, 0, 0.5);
}}
{h} .booster-card__back-pattern {{
  opacity: 0;
}}
{h} .booster-card__back-sigil {{
  inline-size: 60%;
  aspect-ratio: 1;
  border: 0;
  border-radius: 0;
  background: url("emblem.svg") center / contain no-repeat;
  box-shadow: none;
  filter: drop-shadow(0 0 0.7rem color-mix(in srgb, {e['main']} 70%, transparent));
}}
{h} .booster-card__back-sigil svg {{
  opacity: 0;
}}
"""


def opening_css(key, e):
    h = f'[data-opening="{key}"]'
    return comment(f"The opening (its hook: the scene's pack while it opens, data-opening), 2.6 s, drawn in EffectCraft and played as a video: {e['parts']['opening'][3]}") + f"""{h} .booster-stage__tear .booster-pack {{
  animation: edition-fate 2.6s linear both;
}}
{e['fate']}
/* room for the video: the pack at its size in the middle of a layer 4.8 pack-widths wide and 2.7 high, fading
   out towards its edges */
{h} .booster-stage__opening {{
  inset: -85% -190%;
  mask-image: radial-gradient(closest-side, #000 70%, transparent 100%);
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-stage__tear .booster-pack {{
    animation: none;
  }}
}}
"""


def reveal_css(key, e, rarity):
    """A rarity over the whole screen, between its two videos: the card's way in, and Portalab's word for the
    rarity — slammed on a slant (Portalab's own), set otherwise, or left out."""
    h = f'.booster-takeover[data-reveal="{key}-{rarity}"]'
    c = CONCEPTS[key[3:]]
    fam, weight = e["font"][1], e["font"][2]
    css = comment(f"{'An' if rarity == 'epic' else 'A'} {rarity} card turned (its hook: data-reveal), staged over the whole screen (place: screen) between this reveal's two videos (behind the card and over it): {c['text'][1]}")
    if c["word"] is None:
        css += f"{h} .booster-takeover__word {{\n  display: none;\n}}\n"
    else:
        css += font_face(e) + f"""{h} .booster-takeover__word {{
  font-family: "{fam}", sans-serif;
  font-weight: {weight};
  font-style: normal;
  {e['word']}
"""
        if c["word"][0] == "slam":
            css += f"""  scale: {c['word'][1]};
}}
/* held upright, the name runs along the screen's height: smaller, so it fits */
@media (max-aspect-ratio: 4 / 5) {{
  {h} .booster-takeover__word {{
    scale: {c['word'][2]};
  }}
}}
"""
        else:
            css += c["word"] + "\n}\n"
    keyframes, play = c["card"]
    css += f"""/* the card's way in */
{h} .booster-takeover__card {{
{c.get('extra', '')}  animation: ed-{key[3:]}-card {play} var(--card-at) both;
}}
@keyframes ed-{key[3:]}-card {{
{keyframes}
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-takeover__card,
  {h} .booster-takeover__word {{
    animation: none;
  }}
}}
"""
    return css


def element(folder, typ, look, names, descriptions, render):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "element.json").write_text(json.dumps({"type": typ, "look": look, "names": names, "descriptions": descriptions, "render": render}, ensure_ascii=False, indent=2) + "\n")


def write(edition, e):
    key = f"ed-{edition}"
    pack = ROOT / f"booster-{key}"
    E = pack / "elements"
    p = e["parts"]
    parts = lambda part: ({"fr": p[part][0], "en": p[part][1]}, {"fr": p[part][2], "en": p[part][3]})
    for folder in (f"look-{key}", f"back-{key}"):
        (E / folder).mkdir(parents=True, exist_ok=True)
        (E / folder / "emblem.svg").write_text(e["emblem"]())
    reveals = ("reveal-rare", "reveal-epic", "reveal-legendary")
    for folder in (f"look-{key}", *reveals):
        (E / folder).mkdir(parents=True, exist_ok=True)
        (E / folder / e["font"][0]).unlink(missing_ok=True)
        if folder == f"look-{key}" or CONCEPTS[edition]["word"] is not None:   # a reveal without the word needs no font
            shutil.copy(HERE / "fonts" / e["font"][0], E / folder / e["font"][0])
    (E / f"look-{key}" / "pack.css").write_text(look_css(key, e))
    element(E / f"look-{key}", "booster_look", key, *parts("look"), {"kind": "css", "css": ["pack.css"]})
    (E / f"back-{key}" / "back.css").write_text(back_css(key, e))
    element(E / f"back-{key}", "card_back", key, *parts("back"), {"kind": "css", "css": ["back.css"], "rarity": "common"})
    (E / f"opening-{key}").mkdir(parents=True, exist_ok=True)
    (E / f"opening-{key}" / "opening.css").write_text(opening_css(key, e))
    element(E / f"opening-{key}", "booster_opening", key, *parts("opening"), {"kind": "video", "file": "opening.mp4", "alpha": "side", "css": ["opening.css"], "stage": True, "duration": 2.6})
    element(E / f"backdrop-{key}", "booster_backdrop", key, *parts("backdrop"), {"kind": "video", "file": "stage.mp4"})
    word = {"rare": ("Rare", "Rare"), "epic": ("Épique", "Epic"), "legendary": ("Légendaire", "Legendary")}
    for r in ("rare", "epic", "legendary"):
        (E / f"reveal-{r}" / "reveal.css").write_text(reveal_css(key, e, r))
        element(E / f"reveal-{r}", "card_reveal", f"{key}-{r}", {"fr": f"Révélation {word[r][0].lower()}", "en": f"{word[r][1]} reveal"}, {"fr": CONCEPTS[edition]["text"][0], "en": CONCEPTS[edition]["text"][1]},
                {"kind": "video", "file": "reveal.mp4", "over": "over.mp4", "alpha": "side", "place": "screen", "css": ["reveal.css"], "duration": DURATION[r], "rarity": r})
    short = e["names"]["fr"].split(" — ")[0], e["names"]["en"].split(" — ")[0]
    (E / f"scene-{key}").mkdir(parents=True, exist_ok=True)
    (E / f"scene-{key}" / "element.json").write_text(json.dumps({
        "type": "booster_scene", "look": key, "names": {"fr": f"Scène {short[0]}", "en": f"{short[1]} scene"},
        "descriptions": {"fr": "Toute l'ouverture, chaque rareté en plein écran. Les cartes tirées gardent le cadre de leur édition ; leurs raretés et leurs noms restent ceux de Portalab.",
                         "en": "The whole opening, every rarity over the whole screen. The cards drawn keep their edition's frame; their rarities and names stay Portalab's."},
        "render": {"kind": "data"},
        "payload": {"parts": {"booster_look": f"look-{key}", "backdrop": f"backdrop-{key}", "opening": f"opening-{key}", "back": {"common": f"back-{key}"},
                              "reveal": {r: f"reveal-{r}" for r in ("rare", "epic", "legendary")}}}}, ensure_ascii=False, indent=2) + "\n")
    (pack / "pack.json").write_text(json.dumps({"format": 1, "id": key, "version": "1.0.0", "names": e["names"], "descriptions": e["description"],
                                                "author": "Portalab (example)", "license": "CC0-1.0"}, ensure_ascii=False, indent=2) + "\n")
    who, licence = FONTS[e["font"][0]]
    (pack / "CREDITS.txt").write_text(f"""{e['names']['en']} — an example booster scene for Portalab (CC0-1.0), one of the edition scenes, every shader,
stylesheet and drawing original.

Font: {who} — {licence}, from Google Fonts (latin subset); embedded unmodified as {e['font'][0]}.

Animations (*.mp4): drawn and rendered with EffectCraft (Apache-2.0, https://github.com/storytold/effectcraft) on the
manga toolkit (../booster-manga-source/effectcraft/core.jsx), made into videos with ffmpeg (../tools/alpha_video.py,
../tools/stage_video.mjs); sources and build in ../booster-editions-source.
""")


if __name__ == "__main__":
    for edition, e in EDITIONS.items():
        write(edition, e)
    print("edition packs written")
