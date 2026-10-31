"""Writes the five genre scene packs (Blockbuster, Ténèbres, Rideau, Arcanes, Hyperespace) but for their videos
(build.sh): their emblems, stylesheets — the sealed pack, the back, the four faces, the opening, each rarity's
reveal over the whole screen and the look of the rarity's name Portalab writes there — and every manifest.
Fonts (SIL OFL, from Google Fonts) are copied from fonts/."""

import json
import math
import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DURATION = {"rare": 3.2, "epic": 3.8, "legendary": 4.6}
RARITIES = ("common", "rare", "epic", "legendary")


def comment(text):
    lines = textwrap.wrap(text, 110)
    return "/* " + "\n".join(("   " if i else "") + line for i, line in enumerate(lines)) + " */\n"


def svg(body, w=100, h=100):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>\n'


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def star(cx, cy, n, ro, ri, turn=0.0):
    return [(cx + math.cos(turn + i * math.pi / n) * (ro if i % 2 == 0 else ri), cy + math.sin(turn + i * math.pi / n) * (ro if i % 2 == 0 else ri)) for i in range(n * 2)]


def emblem_blockbuster():
    return svg(f'<path d="{path(star(50, 50, 12, 48, 30, 0.1))}" fill="#ff6a00" stroke="#1a1d24" stroke-width="3"/>'
               f'<path d="{path(star(50, 50, 10, 32, 20, 0.3))}" fill="#ffb31a"/><path d="{path(star(50, 50, 8, 17, 10))}" fill="#fff4cc"/>')


def emblem_tenebres():
    crow = "M22,58 L40,50 L52,36 L58,44 L66,40 L70,46 L64,50 L74,62 L60,58 L52,66 L44,60 L30,64 Z"
    return svg('<circle cx="50" cy="44" r="34" fill="#b8080f"/><circle cx="58" cy="38" r="30" fill="#7a0409" opacity="0.35"/>'
               f'<path d="{crow}" fill="#060304"/><path d="M8,92 Q30,70 50,88 Q70,72 92,92 Z" fill="#060304"/>')


def emblem_rideau():
    petals = "".join(f'<ellipse cx="50" cy="{50 - r * 0.45:.1f}" rx="{r * 0.55:.1f}" ry="{r * 0.42:.1f}" fill="{c}" transform="rotate({a} 50 50)"/>'
                     for r, c, a in ((44, "#7a0312", 0), (44, "#8e0716", 72), (44, "#7a0312", 144), (44, "#8e0716", 216), (44, "#7a0312", 288),
                                     (30, "#b50d22", 36), (30, "#c41a2e", 108), (30, "#b50d22", 180), (30, "#c41a2e", 252), (30, "#b50d22", 324)))
    return svg(f'{petals}<circle cx="50" cy="50" r="12" fill="#d9263b"/><path d="M50,50 m-6,0 a6,6 0 1,0 12,0" fill="none" stroke="#7a0312" stroke-width="2"/>'
               '<circle cx="50" cy="50" r="47" fill="none" stroke="#f2c14e" stroke-width="2.5"/>')


def emblem_arcanes():
    ticks = "".join(f'<line x1="{50 + math.cos(a) * 40:.1f}" y1="{50 + math.sin(a) * 40:.1f}" x2="{50 + math.cos(a) * 45:.1f}" y2="{50 + math.sin(a) * 45:.1f}" stroke="#ffd96a" stroke-width="1.5"/>'
                    for a in (i / 36 * math.tau for i in range(36)))
    tri = lambda t: path([(50 + math.cos(t + k * math.tau / 3) * 34, 50 + math.sin(t + k * math.tau / 3) * 34) for k in range(3)])
    return svg(f'<circle cx="50" cy="50" r="46" fill="#140c3a"/>{ticks}<circle cx="50" cy="50" r="46" fill="none" stroke="#ffd96a" stroke-width="2.5"/>'
               f'<circle cx="50" cy="50" r="38" fill="none" stroke="#ffd96a" stroke-width="1.5"/><path d="{tri(-math.pi / 2)}" fill="none" stroke="#3ee8d8" stroke-width="2.5"/>'
               f'<path d="{tri(math.pi / 2)}" fill="none" stroke="#3ee8d8" stroke-width="2.5"/><circle cx="50" cy="50" r="7" fill="#ffd96a"/>')


def emblem_hyperespace():
    return svg('<ellipse cx="50" cy="54" rx="47" ry="13" fill="none" stroke="#4de8ff" stroke-width="4" transform="rotate(-14 50 54)"/>'
               '<circle cx="50" cy="50" r="26" fill="#2c3f8c"/><path d="M28,38 Q50,26 72,40 L70,46 Q50,34 30,44 Z" fill="#6f8cf0" opacity="0.8"/>'
               '<path d="M3,66 A47,13 -14 0 0 97,42" fill="none" stroke="#4de8ff" stroke-width="4" transform="rotate(0)"/>'
               '<circle cx="84" cy="18" r="2.5" fill="#ffffff"/><circle cx="14" cy="24" r="2" fill="#ffffff"/>')


GENRES = {
    "blockbuster": dict(
        version="1.1.0",
        # issue 296: each rarity its own moment
        moments={
            "rare": ("La poursuite : une route de nuit qui fonce vers l'écran, des phares, des traces de pneus ; la carte arrive dans les lignes de vitesse et se retourne dans une onde de choc.",
                     "The chase: a night road rushing at the screen, headlights, skid marks; the card comes in the speed lines and turns over in a shockwave."),
            "epic": ("L'explosion : l'écran coupé entre l'acier et le feu, puis une boule de feu, des débris et une onde de choc autour de la carte qui se retourne.",
                     "The explosion: the screen cut between steel and fire, then a fireball, debris and a shockwave round the card as it turns over."),
            "legendary": ("Le final : une ville en feu à l'horizon, deux chasseurs qui passent, puis des explosions en chaîne autour de la carte, des projecteurs dans un ciel rouge et deux entailles qui se croisent.",
                          "The finale: a city burning on the horizon, two fighters screaming past, then explosions going off round the card, searchlights in a red sky and two crossing slashes."),
        },
        family="action", font=("Anton.woff2", "Genre Anton", "400"), ink="#0d0f14", main="#ff6a00", light="#ffb31a", dark="#1a1d24", emblem=emblem_blockbuster,
        names={"fr": "Blockbuster — action", "en": "Blockbuster — action"},
        description={"fr": "Le booster Action en grand spectacle, chaque rareté son moment en plein écran : une poursuite de nuit pour une rare, une explosion pour une épique, le final pour une légendaire — une ville en feu, des chasseurs, des explosions en chaîne. Un paquet d'acier brossé à bande de danger qui explose après un compte à rebours ; une ville de nuit sous les projecteurs.",
                     "en": "The Action booster as a blockbuster, every rarity its own moment over the whole screen: a night chase for a rare, an explosion for an epic, the finale for a legendary — a city on fire, fighter jets, explosions going off one after another. A brushed-steel pack with a hazard band that blows up after a countdown; a city at night under searchlights."},
        pack_bg="repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.05) 0 2px, transparent 2px 5px), linear-gradient(165deg, #5b6474, #2a2f3a 55%, #12151c)",
        pack_band="repeating-linear-gradient(135deg, #ff6a00 0 10px, #0d0f14 10px 20px)", face_bg="linear-gradient(170deg, #20242d, #0d0f14)",
        word="color: #ffffff;\n  -webkit-text-stroke: 0.3rem #0d0f14;\n  paint-order: stroke fill;\n  text-shadow: 0.5rem 0.5rem 0 #ff6a00;",
        fate="""@keyframes genre-fate {
  0% { transform: none; filter: none; opacity: 1; }
  30% { transform: scale(1.02); }
  34% { transform: translate(-2px, 1px) scale(1.04); }
  37% { transform: translate(3px, -1px) scale(1.06); filter: brightness(1.4); opacity: 1; }
  40% { transform: scale(1.35); filter: brightness(3.5); opacity: 0.8; }
  44%, 100% { transform: scale(1.7); filter: brightness(5); opacity: 0; }
}""",
        parts={"backdrop": ("Ville sous les projecteurs", "City under searchlights", "Une ville de nuit en silhouettes, des projecteurs qui balaient le ciel, une lueur orange à l'horizon, des braises qui montent (vidéo en boucle).", "A city at night in silhouettes, searchlights sweeping the sky, an orange glow on the horizon, embers rising (a looping video)."),
               "look": ("Paquet d'acier", "Steel pack", "Un paquet d'acier brossé, une bande de danger orange et noire, l'image de l'œuvre dans un cadre riveté, son nom en lettres massives, une explosion en emblème.", "A brushed steel pack, an orange and black hazard band, the work's art in a riveted frame, its name in massive letters, an explosion as emblem."),
               "opening": ("Compte à rebours", "Countdown", "Trois anneaux se referment sur le paquet comme un compte à rebours ; il explose en boule de feu, des débris projetés.", "Three rings close on the pack like a countdown; it blows up in a fireball, debris flying."),
               "back": ("Dos d'acier", "Steel back", "Acier brossé, bande de danger, une explosion au centre.", "Brushed steel, a hazard band, an explosion in the middle.")}),
    "tenebres": dict(
        version="1.1.0",
        # issue 296: each rarity its own moment
        moments={
            "rare": ("L'ampoule : une ampoule nue qui grésille dans le noir ; à chaque coupure, quelqu'un s'est approché. La carte arrive sous l'ampoule, des yeux rouges l'observent au bord de la lumière.",
                     "The bulb: a bare bulb flickering in the dark; each time it dies, someone has come closer. The card comes under the bulb, red eyes watching from the edge of its light."),
            "epic": ("Les griffes : trois griffes déchirent l'écran, le sang coule, des stores se ferment ; des corbeaux s'envolent, la foudre frappe et l'écran se fend autour de la carte.",
                     "The claws: three claws rip the screen, blood runs, blinds close; crows burst away, lightning strikes and the screen cracks round the card."),
            "legendary": ("La lune de sang : une lune rouge entre des branches mortes, une nuée de corbeaux qui envahit l'écran, puis tourne autour de la carte sous la foudre et les griffes.",
                          "The blood moon: a red moon between dead branches, a swarm of crows filling the screen, then wheeling round the card under lightning and claws."),
        },
        family="dark", font=("Creepster.woff2", "Genre Creepster", "400"), ink="#060304", main="#c4101c", light="#ff4040", dark="#140508", emblem=emblem_tenebres,
        names={"fr": "Ténèbres — sombre", "en": "Ténèbres — darkness"},
        description={"fr": "Le booster Sombre (horreur, crime, thrillers) : chaque rareté prend tout l'écran — trois griffures rouges déchirent un écran noir où coule le sang, des stores se ferment comme dans un polar, puis la carte arrive de dos parmi des corbeaux qui s'envolent, et au retournement un éclair, l'écran fêlé comme du verre. Un paquet de cuir noir lacéré ; une forêt brumeuse sous une lune de sang.",
                     "en": "The Dark booster (horror, crime, thrillers): every rarity takes the whole screen — three red claw marks tear a black screen running with blood, blinds close as in a thriller, then the card comes face down among crows bursting away, and as it turns a lightning strike, the screen cracked like glass. A clawed black leather pack; a misty forest under a blood moon."},
        pack_bg="linear-gradient(115deg, transparent 0 40%, #7a0409 40% 42%, transparent 42% 46%, #7a0409 46% 48%, transparent 48% 52%, #7a0409 52% 54%, transparent 54%), radial-gradient(circle at 70% 25%, rgba(196, 16, 28, 0.35), transparent 50%), linear-gradient(170deg, #241014, #0a0405)",
        pack_band="linear-gradient(180deg, #c4101c, #5e0207)", face_bg="linear-gradient(170deg, #1e0b0e, #060304)",
        word="color: #c4101c;\n  -webkit-text-stroke: 0.2rem #060304;\n  paint-order: stroke fill;\n  text-shadow: 0 0.4rem 0 #060304, 0 0 2rem rgba(196, 16, 28, 0.8);",
        fate="""@keyframes genre-fate {
  0% { transform: none; filter: none; clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); opacity: 1; }
  20% { transform: translate(-2px, 0); }
  26% { transform: translate(2px, 1px) rotate(1deg); clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); }
  32% { transform: translate(0, 6px) rotate(-2deg); clip-path: polygon(0 0, 46% 0, 60% 30%, 40% 55%, 58% 100%, 0 100%); filter: brightness(0.8) sepia(0.4); opacity: 1; }
  44% { transform: translate(-30px, 60px) rotate(-8deg); clip-path: polygon(0 0, 30% 0, 40% 30%, 25% 55%, 35% 100%, 0 100%); opacity: 0.6; }
  52%, 100% { transform: translate(-60px, 160px) rotate(-14deg); clip-path: polygon(0 0, 30% 0, 40% 30%, 25% 55%, 35% 100%, 0 100%); opacity: 0; }
}""",
        parts={"backdrop": ("Lune de sang", "Blood moon", "Une forêt brumeuse d'arbres nus sous une lune de sang voilée, la brume qui rampe, des éclairs au loin, des corbeaux qui passent (vidéo en boucle).", "A misty forest of bare trees under a veiled blood moon, mist creeping, lightning far off, crows passing (a looping video)."),
               "look": ("Cuir lacéré", "Clawed leather", "Un paquet de cuir noir lacéré de griffures rouges, l'image de l'œuvre sous un cadre de fer, son nom en lettres dégoulinantes, une lune de sang et un corbeau en emblème.", "A black leather pack clawed red, the work's art under an iron frame, its name in dripping letters, a blood moon and a crow as emblem."),
               "opening": ("Griffures", "Claws", "Des griffes lacèrent le paquet par deux fois ; il se déchire et tombe, le sang éclabousse, des corbeaux s'envolent.", "Claws rip the pack twice; it tears and falls, blood spatters, crows burst away."),
               "back": ("Dos de cuir", "Leather back", "Cuir noir griffé de rouge, une lune de sang et un corbeau.", "Black leather clawed red, a blood moon and a crow.")}),
    "rideau": dict(
        version="1.1.0",
        # issue 296: each rarity its own moment
        moments={
            "rare": ("La poursuite : une scène dans le noir, un projecteur qui cherche quelqu'un ; la lumière se ferme puis s'ouvre sur la carte, dans la poussière dorée.",
                     "The spotlight: a dark stage, a spotlight looking for someone; the light closes, then opens on the card, in golden dust."),
            "epic": ("Le lever de rideau : le rideau s'ouvre, des roses et des confettis dorés sont lancés vers la carte sous la poursuite.",
                     "The curtain rises: the curtain parts, roses and gold confetti are thrown towards the card under the spotlight."),
            "legendary": ("L'ovation : le théâtre, ses balcons dorés et son lustre ; le grand rideau tombe, puis se relève sur une salle debout, des poursuites qui se croisent et une pluie de roses.",
                          "The ovation: the theatre, its gilded balconies and chandelier; the great curtain falls, then rises on a standing house, crossing spotlights and a rain of roses."),
        },
        family="drama", font=("PlayfairDisplay.woff2", "Genre Playfair", "900"), ink="#1a0508", main="#b50d22", light="#f2c14e", dark="#3a060c", emblem=emblem_rideau,
        names={"fr": "Rideau — drame", "en": "Rideau — drama"},
        description={"fr": "Le booster Drame, comme un soir de première : chaque rareté prend tout l'écran — un rideau de velours rouge, de la poussière d'or dans la lumière, le rideau s'ouvre, la carte arrive de dos sous un projecteur parmi des pétales, et au retournement des confettis d'or et des roses lancées. Un paquet de velours bordé d'or que le rideau emporte ; une salle de théâtre aux feux de la rampe.",
                     "en": "The Drama booster, like an opening night: every rarity takes the whole screen — a red velvet curtain, gold dust in the light, the curtain parts, the card comes face down under a spotlight among petals, and as it turns gold confetti and thrown roses. A velvet pack trimmed with gold that the curtain sweeps away; a theatre in the footlights."},
        pack_bg="repeating-linear-gradient(90deg, #8e0716 0 10%, #5a0310 10% 20%), linear-gradient(180deg, transparent 80%, rgba(0, 0, 0, 0.4))",
        pack_band="linear-gradient(180deg, #f2c14e, #a8781a)", face_bg="linear-gradient(170deg, #4a0710, #1a0508)",
        upright="0.6",
        word="scale: 0.8;\n  color: #f2c14e;\n  font-style: italic;\n  -webkit-text-stroke: 0.12rem #1a0508;\n  paint-order: stroke fill;\n  text-shadow: 0 0 2.4rem rgba(255, 230, 170, 0.6), 0.3rem 0.3rem 0 #1a0508;",
        fate="""@keyframes genre-fate {
  0% { transform: none; filter: none; clip-path: inset(0 0 0 0); opacity: 1; }
  30% { transform: scale(1.03); filter: brightness(1.25); clip-path: inset(0 0 0 0); }
  55% { transform: scale(1.03); clip-path: inset(0 50% 0 50%); filter: brightness(1.25); opacity: 1; }
  56%, 100% { clip-path: inset(0 50% 0 50%); opacity: 0; }
}""",
        parts={"backdrop": ("Feux de la rampe", "Footlights", "Une salle de théâtre dans l'ombre, des rideaux de velours rouge sur les côtés, les feux de la rampe, un faisceau de lumière où danse la poussière (vidéo en boucle).", "A theatre in the dark, red velvet curtains at the sides, the footlights, a beam of light where dust dances (a looping video)."),
               "look": ("Paquet de velours", "Velvet pack", "Un paquet de velours rouge plissé bordé d'or, l'image de l'œuvre comme une affiche encadrée, son nom en italiques dorées, une rose en emblème.", "A pleated red velvet pack trimmed with gold, the work's art like a framed poster, its name in gold italics, a rose as emblem."),
               "opening": ("Le rideau tombe", "Curtain", "Un projecteur trouve le paquet, des pétales tombent ; le rideau se referme sur lui, des confettis d'or éclatent.", "A spotlight finds the pack, petals fall; the curtain closes on it, gold confetti bursts."),
               "back": ("Dos de velours", "Velvet back", "Velours rouge plissé, un liseré d'or, une rose au centre.", "Pleated red velvet, a gold line, a rose in the middle.")}),
    "arcanes": dict(
        version="1.1.0",
        # issue 296: each rarity its own moment
        moments={
            "rare": ("Les runes : un cercle de runes qui se trace dans la nuit et s'embrase ; la carte se pose au centre d'un anneau turquoise.",
                     "The runes: a rune circle drawing itself in the night and flaring; the card lands in a turquoise ring."),
            "epic": ("Le portail : des cercles de runes, un portail qui avale l'écran, puis des ailes de lumière qui se déploient derrière la carte.",
                     "The portal: rune circles, a portal swallowing the screen, then wings of light unfolding behind the card."),
            "legendary": ("Le dragon : un dragon traverse la lune au-dessus des montagnes, son souffle d'or balaie l'écran, puis un dragon de lumière s'enroule autour de la carte, ailes déployées.",
                          "The dragon: a dragon crosses the moon above the mountains, its golden breath sweeps the screen, then a dragon of light coils round the card, its wings spread."),
        },
        family="fantasy", font=("CinzelDecorative.woff2", "Genre Cinzel", "900"), ink="#0a0720", main="#3ee8d8", light="#ffd96a", dark="#140c3a", emblem=emblem_arcanes,
        names={"fr": "Arcanes — fantastique", "en": "Arcanes — fantasy"},
        description={"fr": "Le booster Fantastique : chaque rareté prend tout l'écran — un grand cercle de runes dorées qui tourne dans l'indigo, il s'embrase en portail, la carte arrive de dos dans un vortex violet et turquoise parmi des pierres runiques en orbite, et au retournement de grandes ailes de lumière se déploient derrière elle. Un grimoire scellé de runes qui se dissout en poussière d'étoiles ; un ciel d'aurores et d'îles flottantes.",
                     "en": "The Fantasy booster: every rarity takes the whole screen — a great circle of gold runes turning in indigo, flaring into a portal, the card comes face down in a violet and teal vortex among orbiting rune stones, and as it turns great wings of light unfold behind it. A grimoire sealed with runes that dissolves into stardust; a sky of auroras and floating islands."},
        pack_bg="radial-gradient(circle at 50% 42%, rgba(62, 232, 216, 0.25), transparent 45%), linear-gradient(170deg, #2a1c66, #140c3a 55%, #0a0720)",
        pack_band="linear-gradient(180deg, #ffd96a, #b8862a)", face_bg="linear-gradient(170deg, #1e1452, #0a0720)",
        upright="0.5",
        word="scale: 0.66;\n  color: #ffd96a;\n  -webkit-text-stroke: 0.1rem #0a0720;\n  paint-order: stroke fill;\n  text-shadow: 0 0 2rem rgba(62, 232, 216, 0.9), 0 0 0.6rem rgba(255, 217, 106, 0.9);",
        fate="""@keyframes genre-fate {
  0% { transform: none; filter: none; opacity: 1; }
  35% { transform: scale(0.97); filter: brightness(1.3) saturate(1.4); }
  45% { transform: scale(1.02); filter: brightness(2) blur(1px); opacity: 1; }
  60%, 100% { transform: scale(1.12) translateY(-20px); filter: brightness(3) blur(6px); opacity: 0; }
}""",
        parts={"backdrop": ("Aurores", "Auroras", "Un ciel de nuit traversé d'aurores turquoise et violettes, des îles flottantes en silhouette, une lune, des étoiles et de la poussière dorée qui monte (vidéo en boucle).", "A night sky crossed by teal and violet auroras, floating islands in silhouette, a moon, stars and gold dust rising (a looping video)."),
               "look": ("Grimoire", "Grimoire", "Un grimoire indigo, un cercle de runes dorées et turquoise, l'image de l'œuvre dans un médaillon, son nom en capitales ornées.", "An indigo grimoire, a circle of gold and teal runes, the work's art in a medallion, its name in ornate capitals."),
               "opening": ("Sceau de runes", "Rune seal", "Un cercle de runes se trace et se referme sur le paquet ; il se dissout en poussière d'étoiles qui s'envole.", "A circle of runes draws itself and closes on the pack; it dissolves into stardust drifting away."),
               "back": ("Dos runique", "Rune back", "Indigo profond, un cercle de runes dorées et turquoise au centre.", "Deep indigo, a circle of gold and teal runes in the middle.")}),
    "hyperespace": dict(
        version="1.1.0",
        # issue 296: each rarity its own moment
        moments={
            "rare": ("Le scanner : un radar qui balaie l'espace à la recherche d'un signal ; la carte apparaît sur une grille holographique.",
                     "The scanner: a radar sweeping space for a signal; the card appears over a holographic grid."),
            "epic": ("Le saut : l'hyperespace, un éclair blanc, puis une planète à anneaux derrière la carte et une onde de choc.",
                     "The jump: hyperspace, a white flash, then a ringed planet behind the card and a shockwave."),
            "legendary": ("La flotte : un vaisseau géant surgit de l'hyperespace, puis une flotte entière sort autour de la carte, ses lasers croisés devant la planète.",
                          "The fleet: a huge ship tears out of hyperspace, then a whole fleet drops out round the card, its lasers crossing before the planet."),
        },
        family="sf", font=("Orbitron.woff2", "Genre Orbitron", "800"), ink="#020617", main="#4de8ff", light="#ff4dc4", dark="#0a1636", emblem=emblem_hyperespace,
        names={"fr": "Hyperespace — science-fiction", "en": "Hyperespace — science fiction"},
        description={"fr": "Le booster Science-fiction : chaque rareté prend tout l'écran — un saut en hyperespace, les étoiles étirées en traits, un éclair de saut, la carte arrive de dos devant une planète à anneau dans les nébuleuses, et au retournement l'onde du saut et un balayage d'hologramme. Une capsule blanche aux lueurs cyan téléportée dans un faisceau ; un ciel d'étoiles et de nébuleuses.",
                     "en": "The Science fiction booster: every rarity takes the whole screen — a jump to hyperspace, stars stretched into streaks, the jump's flash, the card comes face down before a ringed planet amid nebulas, and as it turns the jump's shockwave and a hologram's scan. A white capsule glowing cyan beamed away in a beam; a sky of stars and nebulas."},
        pack_bg="linear-gradient(90deg, transparent 0 46%, rgba(77, 232, 255, 0.7) 46% 47%, transparent 47% 53%, rgba(77, 232, 255, 0.7) 53% 54%, transparent 54%), linear-gradient(170deg, #eef3fb, #b9c6dc 60%, #8a98b2)",
        pack_band="linear-gradient(180deg, #4de8ff, #1a7f9e)", face_bg="linear-gradient(170deg, #0f1f48, #020617)",
        upright="0.46",
        word="scale: 0.6;\n  color: #ffffff;\n  letter-spacing: 0.02em;\n  -webkit-text-stroke: 0.08rem #4de8ff;\n  text-shadow: 0 0 1.6rem #4de8ff, 0 0 0.4rem #4de8ff;",
        fate="""@keyframes genre-fate {
  0% { transform: none; filter: none; opacity: 1; }
  30% { transform: scale(1, 1); filter: brightness(1.3) hue-rotate(10deg); }
  50% { transform: scale(0.5, 1.4); filter: brightness(2.5); opacity: 1; }
  60% { transform: scale(0.04, 1.8); filter: brightness(4); opacity: 0.9; }
  66%, 100% { transform: scale(0, 2); opacity: 0; }
}""",
        parts={"backdrop": ("Nébuleuses", "Nebulas", "Un ciel d'étoiles qui scintillent, des nébuleuses magenta et bleues qui dérivent, une planète à anneau qui tourne lentement, une étoile filante de temps en temps (vidéo en boucle).", "A sky of twinkling stars, magenta and blue nebulas drifting, a ringed planet turning slowly, now and then a shooting star (a looping video)."),
               "look": ("Capsule", "Capsule", "Une capsule de panneaux blancs aux lueurs cyan, l'image de l'œuvre sur un écran, son nom en lettres techniques, une planète à anneau en emblème.", "A capsule of white panels glowing cyan, the work's art on a screen, its name in technical letters, a ringed planet as emblem."),
               "opening": ("Téléportation", "Beam-up", "Un faisceau de téléportation verrouille le paquet, des anneaux montent ; il est aspiré dans le faisceau, des fragments de lumière s'élèvent.", "A teleport beam locks on the pack, rings rising; it is drawn into the beam, fragments of light rising."),
               "back": ("Dos de capsule", "Capsule back", "Panneaux sombres, lueurs cyan, une planète à anneau au centre.", "Dark panels, cyan glows, a ringed planet in the middle.")}),
}
REVEAL = {
    "rare": ("Plein écran, joué en vidéo : d'abord la rareté en lettres géantes (écrite par Portalab) sur l'écran de l'univers, puis la carte arrive de dos et se retourne dans un éclair.",
             "Full screen, played as video: first the rarity in huge letters (written by Portalab) over the scene's screen, then the card comes face down and turns over in a flash."),
}


def font_face(g):
    file, family, weight = g["font"]
    return f'@font-face {{\n  font-family: "{family}";\n  src: url("{file}") format("woff2");\n  font-weight: {weight};\n  font-display: swap;\n}}\n'


def look_css(key, g):
    h = f'[data-booster-look="{key}"]'
    fam, weight = g["font"][1], g["font"][2]
    return comment(f"The sealed pack (its hook: data-booster-look): {g['parts']['look'][3]}") + font_face(g) + f"""{h} .booster-pack {{
  border-radius: 0.5rem;
  background: {g['pack_bg']};
  box-shadow: inset 0 0 0 3px {g['ink']}, inset 0 0 0 6px {g['main']}, inset 0 0 0 8px {g['ink']}, 0 1rem 2rem rgba(0, 0, 0, 0.55), 0 0 1.4rem color-mix(in srgb, {g['main']} 40%, transparent);
}}
{h} .booster-pack__art {{
  inset: 13% 10% 33%;
  inline-size: 80%;
  block-size: 54%;
  border: 3px solid {g['ink']};
  border-radius: 0.3rem;
  box-shadow: 0 0 0 3px {g['light']}, 0 0 0 6px {g['ink']}, 0 0.5rem 1rem rgba(0, 0, 0, 0.5);
  mask: none;
}}
{h} .booster-pack__foil {{
  opacity: 1;
  background: linear-gradient(105deg, transparent 40%, rgba(255, 255, 255, 0.45) 48%, transparent 56%) -160% 0 / 200% 100% no-repeat;
  animation: genre-sweep 4s ease-in-out infinite;
}}
@keyframes genre-sweep {{
  0%, 55% {{ background-position: -160% 0; }}
  85%, 100% {{ background-position: 260% 0; }}
}}
{h} .booster-pack__stars {{
  opacity: 0;
}}
{h} .booster-pack__flap {{
  border: 0;
  background: {g['pack_band']};
  box-shadow: inset 0 -3px 0 {g['ink']};
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
  font-size: clamp(1.05rem, 2.4vw, 1.5rem);
  line-height: 1.05;
  color: #ffffff;
  -webkit-text-stroke: 4px {g['ink']};
  paint-order: stroke fill;
  text-shadow: 0 0 1rem color-mix(in srgb, {g['main']} 70%, transparent);
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
  font-size: 0.85rem;
  text-shadow: 0 1px 3px #000000;
  box-shadow: none;
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-pack__foil {{
    animation: none;
  }}
}}
"""


def back_css(key, g):
    h = f'[data-card-back="{key}"]'
    return comment(f"Face down (its hook: the card, data-card-back), every card alike — a back never tells the rarity: {g['parts']['back'][3]}") + f"""{h} .booster-card__back {{
  border: 0;
  border-radius: 0.55rem;
  background: {g['pack_bg']};
  box-shadow: inset 0 0 0 3px {g['ink']}, inset 0 0 0 6px {g['main']}, inset 0 0 0 8px {g['ink']}, 0 0.5rem 1rem rgba(0, 0, 0, 0.5);
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
  filter: drop-shadow(0 0 0.7rem color-mix(in srgb, {g['main']} 70%, transparent));
}}
{h} .booster-card__back-sigil svg {{
  opacity: 0;
}}
"""


RIM = {"common": ("#8f8a99", "#4c4856"), "rare": ("#4da8ff", "#1a4c9e"), "epic": ("#c06aff", "#5a1a9e"), "legendary": ("#ffc83e", "#a86a00")}


def face_css(key, g, rarity):
    h = f'[data-card-face="{key}-{rarity}"]'
    light, dark = RIM[rarity]
    fam, weight = g["font"][1], g["font"][2]
    css = comment(f"A {rarity} card of {g['names']['en']} (its hook: the card once turned, data-card-face): a frame in the rarity's metal round the scene's colours, its lettering the scene's. The face turns in 3D: never its transform; a turned media card is never redrawn.") + font_face(g) + f"""{h} .mcard__card {{
  padding: 3cqi;
  border-radius: 2.4cqi;
  background: linear-gradient(160deg, {light}, {dark});
  box-shadow: inset 0 0 0 0.4cqi rgba(255, 255, 255, 0.25), 0 0 0 0.5cqi {g['ink']}, 0 0 2.4cqi color-mix(in srgb, {light} 50%, transparent);
}}
{h} .mcard__body {{
  border-radius: 1.6cqi;
  background: {g['face_bg']};
  box-shadow: inset 0 0 0 0.5cqi {g['main']}, inset 0 0 0 0.9cqi {g['ink']};
  color: #f4f0f8;
}}
{h} .mcard[data-rarity] .mcard__name {{
  font-family: "{fam}", var(--mcard-title);
  font-weight: {weight};
  line-height: 1.15;
  color: #ffffff;
  text-shadow: 0 0 1.2cqi color-mix(in srgb, {g['main']} 80%, transparent), 0.25cqi 0.25cqi 0 {g['ink']};
}}
{h} .mcard__genre,
{h} .mcard__rarity,
{h} .mcard__cost {{
  background: {g['main']};
  color: {g['ink']};
  box-shadow: 0 0 0 0.3cqi {g['ink']};
  font-family: "{fam}", var(--mcard-title);
  font-weight: {weight};
}}
{h} .mcard__emblem {{
  background: {g['ink']};
  color: {g['main']};
}}
{h} .mcard__art {{
  border-radius: 1cqi;
  box-shadow: 0 0 0 0.4cqi {light}, 0 0 0 0.8cqi {g['ink']};
}}
{h} .mcard__strip {{
  background: {g['main']};
  color: {g['ink']};
}}
{h} .mcard__figures strong {{
  font-family: "{fam}", var(--mcard-title);
  font-weight: {weight};
}}
"""
    if rarity != "common":
        css += f"""/* a sweep of light over it, once, as it lands */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 36%, {light} 47%, rgba(255, 255, 255, 0.95) 50%, {g['main']} 53%, transparent 64%) 0 0 / 300% 300%;
  mix-blend-mode: overlay;
  opacity: 0.55;
  animation: genre-sweep-{rarity} 1.4s ease-in-out 0.4s both;
}}
@keyframes genre-sweep-{rarity} {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 80% 80%; }}
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-card__face::after {{
    animation: none;
  }}
}}
"""
    return css


def opening_css(key, g):
    h = f'[data-opening="{key}"]'
    return comment(f"The opening (its hook: the scene's pack while it opens, data-opening), 2.6 s, drawn in EffectCraft and played as a video: {g['parts']['opening'][3]}") + f"""{h} .booster-stage__tear .booster-pack {{
  animation: genre-fate 2.6s linear both;
}}
{g['fate']}
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


def reveal_css(key, g, rarity):
    h = f'[data-reveal="{key}-{rarity}"]'
    fam, weight = g["font"][1], g["font"][2]
    return comment(f"A {rarity} card turned (its hook: data-reveal), staged over the whole screen (place: screen): the rarity's name first, over the scene's screen, then the card face down, turning over — between this reveal's two videos (behind it and over it). This stylesheet dresses the rarity's name Portalab writes.") + font_face(g) + f"""{h} .booster-takeover__word {{
  font-family: "{fam}", sans-serif;
  font-weight: {weight};
  font-style: normal;
  {g['word']}
}}
""" + (f"""/* held upright, the name runs along the screen's height: smaller, so it fits */
@media (max-aspect-ratio: 4 / 5) {{
  {h} .booster-takeover__word {{
    scale: {g['upright']};
  }}
}}
""" if g.get("upright") else "")


def element(folder, typ, look, names, descriptions, render):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "element.json").write_text(json.dumps({"type": typ, "look": look, "names": names, "descriptions": descriptions, "render": render}, ensure_ascii=False, indent=2) + "\n")


def write(key, g):
    pack = ROOT / f"booster-{key}"
    E = pack / "elements"
    p = g["parts"]
    texts = lambda part: ({"fr": p[part][0], "en": p[part][1]}, {"fr": p[part][2], "en": p[part][3]})
    for folder in (f"look-{key}", f"back-{key}"):
        (E / folder).mkdir(parents=True, exist_ok=True)
        (E / folder / "emblem.svg").write_text(g["emblem"]())
    for folder in (f"look-{key}", *(f"face-{r}" for r in RARITIES), "reveal-rare", "reveal-epic", "reveal-legendary"):
        (E / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / "fonts" / g["font"][0], E / folder / g["font"][0])
    (E / f"look-{key}" / "pack.css").write_text(look_css(key, g))
    element(E / f"look-{key}", "booster_look", key, *texts("look"), {"kind": "css", "css": ["pack.css"]})
    (E / f"back-{key}" / "back.css").write_text(back_css(key, g))
    element(E / f"back-{key}", "card_back", key, *texts("back"), {"kind": "css", "css": ["back.css"], "rarity": "common"})
    (E / f"opening-{key}").mkdir(parents=True, exist_ok=True)
    (E / f"opening-{key}" / "opening.css").write_text(opening_css(key, g))
    element(E / f"opening-{key}", "booster_opening", key, *texts("opening"), {"kind": "video", "file": "opening.mp4", "alpha": "side", "css": ["opening.css"], "stage": True, "duration": 2.6})
    element(E / f"backdrop-{key}", "booster_backdrop", key, *texts("backdrop"), {"kind": "video", "file": "stage.mp4"})
    face_names = {"common": ("Face commune", "Common face"), "rare": ("Face rare", "Rare face"), "epic": ("Face épique", "Epic face"), "legendary": ("Face légendaire", "Legendary face")}
    for r in RARITIES:
        (E / f"face-{r}" / "face.css").write_text(face_css(key, g, r))
        element(E / f"face-{r}", "card_face", f"{key}-{r}", {"fr": face_names[r][0], "en": face_names[r][1]},
                {"fr": "Un cadre au métal de sa rareté autour des couleurs de la scène, son lettrage celui de la scène.", "en": "A frame in its rarity's metal round the scene's colours, its lettering the scene's."},
                {"kind": "css", "css": ["face.css"], "rarity": r})
    word = {"rare": ("Rare", "Rare"), "epic": ("Épique", "Epic"), "legendary": ("Légendaire", "Legendary")}
    for r in ("rare", "epic", "legendary"):
        (E / f"reveal-{r}" / "reveal.css").write_text(reveal_css(key, g, r))
        fr_d, en_d = g.get("moments", {}).get(r) or REVEAL["rare"]
        element(E / f"reveal-{r}", "card_reveal", f"{key}-{r}", {"fr": f"Révélation {word[r][0].lower()}", "en": f"{word[r][1]} reveal"}, {"fr": fr_d, "en": en_d},
                {"kind": "video", "file": "reveal.mp4", "over": "over.mp4", "alpha": "side", "place": "screen", "css": ["reveal.css"], "duration": DURATION[r], "rarity": r})
    (E / f"scene-{key}").mkdir(parents=True, exist_ok=True)
    (E / f"scene-{key}" / "element.json").write_text(json.dumps({
        "type": "booster_scene", "look": key, "names": {"fr": f"Scène {g['names']['fr'].split(' — ')[0]}", "en": f"{g['names']['en'].split(' — ')[0]} scene"},
        "descriptions": {"fr": "Toute l'ouverture, chaque rareté en plein écran. Les cartes tirées, leurs raretés et leurs noms restent ceux de Portalab.",
                         "en": "The whole opening, every rarity over the whole screen. The cards drawn, their rarities and names stay Portalab's."},
        "render": {"kind": "data"},
        "payload": {"parts": {"booster_look": f"look-{key}", "backdrop": f"backdrop-{key}", "opening": f"opening-{key}", "back": {"common": f"back-{key}"},
                              "face": {r: f"face-{r}" for r in RARITIES}, "reveal": {r: f"reveal-{r}" for r in ("rare", "epic", "legendary")}}}}, ensure_ascii=False, indent=2) + "\n")
    (pack / "pack.json").write_text(json.dumps({"format": 1, "id": key, "version": g.get("version", "1.0.0"), "names": g["names"], "descriptions": g["description"],
                                                "author": "Portalab (example)", "license": "CC0-1.0"}, ensure_ascii=False, indent=2) + "\n")
    fonts = {"Anton.woff2": "Anton by Vernon Adams", "Creepster.woff2": "Creepster by Sideshow", "PlayfairDisplay.woff2": "Playfair Display by Claus Eggers Sørensen",
             "CinzelDecorative.woff2": "Cinzel Decorative by Natanael Gama", "Orbitron.woff2": "Orbitron by Matt McInerney"}
    (pack / "CREDITS.txt").write_text(f"""{g['names']['en']} — an example booster scene for Portalab (CC0-1.0), one of the genre scenes, every shader,
stylesheet and drawing original.

Font: {fonts[g['font'][0]]} — SIL Open Font License 1.1 (https://openfontlicense.org), from Google Fonts (latin
subset); embedded unmodified as {g['font'][0]}.

Animations (*.mp4): drawn and rendered with EffectCraft (Apache-2.0, https://github.com/storytold/effectcraft) on the
manga toolkit (../booster-manga-source/effectcraft/core.jsx), made into videos with ffmpeg (../tools/alpha_video.py,
../tools/stage_video.mjs); sources and build in ../booster-genres-source.
""")


if __name__ == "__main__":
    for key, genre in GENRES.items():
        write(key, genre)
    print("genre packs written")
