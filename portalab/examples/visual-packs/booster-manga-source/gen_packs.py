"""Writes the manga universe's four scene packs (booster-shonen, -magical, -ninja, -mecha) but for their
animations and their stages' videos (build.sh; the stages written by hand in stages/*.glsl): their still shapes (SVG),
the sealed pack's look, the back, the four faces, the opening's and the reveals' stylesheets, every element's
manifest and the pack's own. Fonts are copied from FONTS (SIL OFL, from Google Fonts)."""

import json
import math
import os
import random
import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONTS = Path(os.environ.get("MANGA_FONTS", HERE / "fonts"))


def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{"<defs>" + defs + "</defs>" if defs else ""}{body}</svg>\n')


def path(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def wrap(text, first=""):
    lines = textwrap.wrap(first + text, 110)
    return "/* " + "\n".join(("   " if i else "") + line for i, line in enumerate(lines)) + " */\n"


# --- still shapes ------------------------------------------------------------------------------------------
def flames(color, dark):
    """Shōnen: flat flames licking upwards in rows, inked — a print for packs and rims."""
    rng = random.Random(3)
    body = []
    for row in range(5):
        y0 = 120 + row * 100
        for k in range(7):
            x0 = k * 60 + (30 if row % 2 else 0) - 20
            h = rng.uniform(60, 110)
            pts = [(x0, y0), (x0 + 10, y0 - h * 0.5), (x0 + 22, y0 - h * 0.35), (x0 + 30, y0 - h), (x0 + 40, y0 - h * 0.4),
                   (x0 + 50, y0 - h * 0.6), (x0 + 58, y0)]
            body.append(f'<path d="{path(pts)}" fill="{color}" stroke="{dark}" stroke-width="3" stroke-linejoin="round"/>')
    return svg(400, 560, "".join(body))


def impact(fill="#ffffff", rim="#ff8a1e"):
    """An impact star, inked, its rim in the scene's colour (the card count sits on it)."""
    rng = random.Random(5)
    pts = []
    for i in range(28):
        a = i / 28 * math.tau
        r = (46 if i % 2 == 0 else 30) * rng.uniform(0.85, 1.05)
        pts.append((50 + math.cos(a) * r, 50 + math.sin(a) * r))
    return svg(100, 100, f'<path d="{path(pts)}" fill="{fill}" stroke="#14101a" stroke-width="5" stroke-linejoin="round"/>'
                         f'<path d="{path([(50 + (x - 50) * 0.78, 50 + (y - 50) * 0.78) for x, y in pts])}" fill="none" stroke="{rim}" stroke-width="4"/>')


def lace(color="#ffffff"):
    """Magical girl: a strip of lace — scallops, eyelets and a fine edge — repeating sideways."""
    body = []
    for i in range(4):
        x = i * 30 + 15
        body.append(f'<path d="M{x - 15},0 A15,15 0 0 0 {x + 15},0 Z" fill="{color}"/>')
        body.append(f'<circle cx="{x}" cy="6" r="3.2" fill="none" stroke="#f3a6cf" stroke-width="1.4"/>')
    body.append('<path d="M0,1 L120,1" stroke="#f3a6cf" stroke-width="2"/>')
    return svg(120, 18, "".join(body))


def bow():
    """A ribbon bow: two loops, two tails, a knot, two pinks."""
    return svg(200, 120, (
        '<path d="M100,60 C60,10 10,10 18,52 C24,86 70,76 100,60 Z" fill="#ff7fc0" stroke="#c2407f" stroke-width="4"/>'
        '<path d="M100,60 C140,10 190,10 182,52 C176,86 130,76 100,60 Z" fill="#ff7fc0" stroke="#c2407f" stroke-width="4"/>'
        '<path d="M92,66 L64,116 L84,108 L96,118 Z" fill="#ff9fd0" stroke="#c2407f" stroke-width="4"/>'
        '<path d="M108,66 L136,116 L116,108 L104,118 Z" fill="#ff9fd0" stroke="#c2407f" stroke-width="4"/>'
        '<path d="M36,40 C50,30 70,36 86,52" fill="none" stroke="#ffd2ea" stroke-width="5" stroke-linecap="round"/>'
        '<rect x="86" y="46" width="28" height="28" rx="8" fill="#ff5fae" stroke="#c2407f" stroke-width="4"/>'))


def heart_gem():
    """A heart cut like a gem, its facets in pinks, a sparkle."""
    def heart(r, dx=0, dy=0):
        pts = []
        for i in range(48):
            t = i / 48 * math.tau
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append((50 + dx + x / 17 * r, 52 + dy + y / 17 * r))
        return path(pts)
    return svg(100, 100, f'<path d="{heart(44)}" fill="#e94a9b" stroke="#7a1a50" stroke-width="3"/>'
                         f'<path d="{heart(30, -3, -3)}" fill="#ff8cc6"/><path d="{heart(14, -8, -9)}" fill="#ffd6ec"/>'
                         '<path d="M74,22 L77,30 L85,33 L77,36 L74,44 L71,36 L63,33 L71,30 Z" fill="#ffffff"/>')


def wood():
    """Ninja: dark wood, its grain running down."""
    defs = ('<filter id="w" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.006 0.12" numOctaves="3" seed="2"/>'
            '<feColorMatrix values="0.5 0 0 0 0.05  0.32 0 0 0 0.02  0.18 0 0 0 0.01  0 0 0 0 1"/></filter>')
    return svg(400, 560, '<rect width="400" height="560" filter="url(#w)"/>', defs)


def ofuda():
    """A paper seal tag (ofuda): cream paper, a red border, a tomoe circle and brushed bars (no writing)."""
    body = ['<rect x="4" y="4" width="92" height="232" rx="3" fill="#f4ead2" stroke="#2a1a14" stroke-width="3"/>',
            '<rect x="12" y="12" width="76" height="216" fill="none" stroke="#c4271c" stroke-width="3"/>',
            '<circle cx="50" cy="60" r="26" fill="none" stroke="#c4271c" stroke-width="5"/>']
    for k in range(3):
        a = k * math.tau / 3
        x, y = 50 + math.cos(a) * 11, 60 + math.sin(a) * 11
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#c4271c"/>')
    for i, (w, y) in enumerate(((44, 108), (30, 132), (50, 156), (36, 180), (24, 204))):
        body.append(f'<rect x="{50 - w / 2:.0f}" y="{y}" width="{w}" height="{9 if i % 2 else 12}" rx="4" fill="#2a1a14"/>')
    return svg(100, 240, "".join(body))


def shuriken_svg():
    pts = []
    for i in range(4):
        a = i * math.pi / 2 - math.pi / 4
        pts += [(50 + math.cos(a - 0.62) * 15, 50 + math.sin(a - 0.62) * 15), (50 + math.cos(a) * 47, 50 + math.sin(a) * 47),
                (50 + math.cos(a + 0.35) * 17, 50 + math.sin(a + 0.35) * 17)]
    return svg(100, 100, f'<path d="{path(pts)}" fill="#8a929e" stroke="#1a1c22" stroke-width="3" stroke-linejoin="round"/>'
                         '<circle cx="50" cy="50" r="7" fill="#1a1c22"/><path d="M50,50 L83,17" stroke="#d8dee8" stroke-width="3"/>')


def moon():
    """A huge red moon, a few clouds drifting over it."""
    return svg(200, 200, '<defs><radialGradient id="m"><stop offset="0" stop-color="#ff6a3a"/><stop offset="1" stop-color="#9c1810"/></radialGradient></defs>'
                         '<circle cx="100" cy="100" r="92" fill="url(#m)"/>'
                         '<path d="M20,120 Q60,100 100,118 T190,112 L190,126 Q140,138 100,128 T20,134 Z" fill="#1d1420" fill-opacity="0.75"/>'
                         '<path d="M40,70 Q80,56 120,70 L120,78 Q80,68 40,80 Z" fill="#1d1420" fill-opacity="0.6"/>')


def panel():
    """Mecha: armour plates — panel lines, rivets, a hazard stripe at the foot."""
    rng = random.Random(8)
    body = ['<rect width="400" height="560" fill="none"/>']
    for x in (0, 140, 260, 400):
        body.append(f'<path d="M{x},0 L{x},560" stroke="#0e1218" stroke-width="3"/>')
    for y in (0, 120, 300, 430, 560):
        body.append(f'<path d="M0,{y} L400,{y}" stroke="#0e1218" stroke-width="3"/>')
    for x in (0, 140, 260):
        for y in (0, 120, 300, 430):
            for dx, dy in ((10, 10), (rng.choice((110, 100)), 10), (10, 100)):
                body.append(f'<circle cx="{x + dx}" cy="{y + dy}" r="3.5" fill="#cfd6e0" stroke="#0e1218" stroke-width="1"/>')
    body.append('<path d="M0,1 L400,1 M0,121 L400,121 M0,301 L400,301" stroke="#ffffff" stroke-opacity="0.25" stroke-width="2"/>')
    return svg(400, 560, "".join(body))


def core_svg():
    """A reactor core glowing cyan behind a ring of vents."""
    vents = "".join(f'<rect x="47" y="6" width="6" height="16" rx="2" fill="#0e1218" transform="rotate({k * 30} 50 50)"/>' for k in range(12))
    return svg(100, 100, '<defs><radialGradient id="c"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="#7ff6ff"/>'
                         '<stop offset="0.75" stop-color="#1aa8c8"/><stop offset="1" stop-color="#0a3040"/></radialGradient></defs>'
                         f'<circle cx="50" cy="50" r="46" fill="#3a4250" stroke="#0e1218" stroke-width="3"/>{vents}'
                         '<circle cx="50" cy="50" r="28" fill="url(#c)" stroke="#0e1218" stroke-width="3"/>')


def hexes(color="#3ee8ff"):
    """A tile of hexagons in thin lines."""
    pts = lambda cx, cy: [(cx + 15 * math.cos(math.pi / 3 * k), cy + 15 * math.sin(math.pi / 3 * k)) for k in range(6)]
    body = "".join(f'<path d="{path(pts(cx, cy))}" fill="none" stroke="{color}" stroke-opacity="0.35" stroke-width="1.2"/>'
                   for cx, cy in ((0, 0), (45, 0), (22.5, 13), (0, 26), (45, 26)))
    return svg(45, 26, body)


# --- the styles ----------------------------------------------------------------------------------------------
RARE = ("common", "rare", "epic", "legendary")
STYLES = {
    "shonen": dict(
        font=("DelaGothicOne.woff2", "Manga Dela", 400), names={"fr": "Shōnen — aura de combat", "en": "Shōnen — a fighting aura"},
        descriptions={"fr": "Une ouverture de booster façon manga de combat, ses animations dessinées image par image dans EffectCraft et jouées en vidéo haute qualité : un plateau rocheux sous l'orage ; un paquet noir imprimé de flammes, qui se charge d'une aura orange, soulève les rochers et crépite d'éclairs avant qu'un pilier de lumière ne jaillisse ; des cartes au lettrage épais, révélées par une aura bleue, une aura violette et ses rochers en lévitation ou — légendaire — une aura dorée qui explose sous un pilier de lumière.",
                      "en": "A booster opening like a fighting manga's, its animations drawn frame by frame in EffectCraft and played as high-quality video: a rocky plateau under a storm; a black pack printed with flames that charges with an orange aura, lifts the rocks and crackles with lightning before a pillar of light shoots up; cards in heavy lettering, revealed by a blue aura, a violet aura and its levitating rocks or — legendary — a golden aura exploding under a pillar of light."},
        svgs={"flames-orange.svg": (lambda: flames("#ff8a1e", "#14101a"), ("look-shonen", "back-shonen", "face-common")),
              "flames-blue.svg": (lambda: flames("#3a8cff", "#0a1430"), ("face-rare",)),
              "flames-violet.svg": (lambda: flames("#9a4dff", "#1a0a30"), ("face-epic",)),
              "flames-gold.svg": (lambda: flames("#ffc21e", "#2a1a04"), ("face-legendary",)),
              "impact.svg": (impact, ("look-shonen", "back-shonen"))},
        faces={"common": ("#3a3540", "#1a161e", "flames-orange.svg", "#9a909e", "Common face", "Face commune"),
               "rare": ("#1a3a8a", "#0a1638", "flames-blue.svg", "#4aa0ff", "Rare face", "Face rare"),
               "epic": ("#4a1a8a", "#1a0838", "flames-violet.svg", "#b06aff", "Epic face", "Face épique"),
               "legendary": ("#8a5a08", "#2a1804", "flames-gold.svg", "#ffc21e", "Legendary face", "Face légendaire")},
        body=("#fffaf0", "#14101a"), title_stroke=True,
        opening_pack="""@keyframes manga-charge {
  0% { transform: none; filter: none; opacity: 1; }
  12% { transform: translate(-1px, 0) scale(1.01); }
  18% { transform: translate(2px, -1px) scale(1.025); }
  24% { transform: translate(-2px, 1px) scale(1.04); filter: brightness(1.15); }
  30% { transform: translate(3px, -1px) scale(1.06) skewX(-1deg); filter: brightness(1.3) saturate(1.4); }
  35% { transform: translate(-4px, 1px) scale(1.09) skewX(1deg); filter: brightness(1.6) saturate(1.6); }
  39% { transform: translate(4px, 0) scale(1.13, 1.1); filter: brightness(2.4) saturate(0.6); opacity: 1; }
  41% { transform: scale(1.3, 1.24); filter: brightness(4); opacity: 0.9; }
  43% { transform: scale(1.55); filter: brightness(5); opacity: 0; }
  100% { transform: scale(1.55); opacity: 0; }
}""",
        parts={"backdrop": ("Plateau sous l'orage", "Stormy plateau", "Un plateau rocheux sous un ciel d'orage : nuages qui roulent, éclairs au loin, rochers qui flottent et oscillent, poussière soulevée par le vent (HD).", "A rocky plateau under a stormy sky: clouds rolling, distant lightning, rocks floating and bobbing, dust lifted by the wind (HD)."),
               "look": ("Paquet de combat", "Fighting pack", "Un paquet noir imprimé de flammes orange cernées d'encre, sous une trame ; l'image de l'œuvre dans une case encrée ; son nom en lettres épaisses cernées ; le nombre de cartes sur une étoile d'impact.", "A black pack printed with inked orange flames under halftone; the work's art in an inked panel; its name in heavy outlined letters; the card count on an impact star."),
               "opening": ("Transformation", "Power up", "Une aura orange flambe de plus en plus haut autour du paquet, des rochers s'arrachent du sol, des éclairs de ki crépitent, des lignes de concentration se resserrent ; puis un pilier de lumière jaillit, une onde de choc fend le sol dans la poussière, rochers et braises volent.", "An orange aura flares higher and higher round the pack, rocks tear off the ground, ki lightning crackles, concentration lines close in; then a pillar of light shoots up, a shockwave cracks the ground in dust, rocks and embers fly."),
               "back": ("Dos de combat", "Fighting back", "Noir, des flammes orange imprimées, une étoile d'impact au centre.", "Black, printed with orange flames, an impact star in the middle."),
               "rare": ("Aura bleue", "Blue aura", "Une aura bleue flambe autour de la carte, des éclairs crépitent, une onde de choc, des braises bleues montent.", "A blue aura flares round the card, lightning crackles, a shockwave, blue embers rise."),
               "epic": ("Aura violette", "Violet aura", "Une aura violette, des rochers arrachés qui lévitent autour de la carte, des éclairs, des lignes de concentration, un impact.", "A violet aura, rocks torn off and levitating round the card, lightning, concentration lines, an impact."),
               "legendary": ("Aura dorée", "Golden aura", "Une aura dorée explose autour de la carte sous un pilier de lumière, ondes de choc, rochers et braises ; devant elle, des éclairs la traversent et de grands éclats.", "A golden aura explodes round the card under a pillar of light, shockwaves, rocks and embers; in front of it, lightning crosses it and great glints.")}),
    "magical": dict(
        font=("MochiyPopOne.woff2", "Manga Mochiy", 400), names={"fr": "Magical girl — transformation", "en": "Magical girl — a transformation"},
        descriptions={"fr": "Une ouverture de booster façon magical girl, ses animations dessinées image par image dans EffectCraft et jouées en vidéo haute qualité : un ciel pastel semé d'étoiles et de bulles ; un paquet rose bordé de dentelle et noué d'un nœud, un cœur-gemme ; un cercle magique, des rubans qui s'enroulent, un éclat d'étoile et une pluie de cœurs, d'étoiles et de pétales ; des cartes en dentelle révélées par des bulles irisées, des rubans et des cœurs ou — légendaire — un cercle magique géant et une pluie d'étoiles.",
                      "en": "A booster opening like a magical girl's transformation, its animations drawn frame by frame in EffectCraft and played as high-quality video: a pastel sky strewn with stars and bubbles; a pink pack trimmed with lace and tied with a bow, a heart gem; a magic circle, ribbons spiralling, a star flash and a shower of hearts, stars and petals; lace cards revealed by iridescent bubbles, ribbons and hearts or — legendary — a giant magic circle and a rain of stars."},
        svgs={"lace.svg": (lace, ("look-magical", "back-magical", "face-common", "face-rare", "face-epic", "face-legendary")),
              "bow.svg": (bow, ("look-magical", "back-magical")), "heart.svg": (heart_gem, ("look-magical", "back-magical"))},
        faces={"common": ("#e8dcf4", "#c9b4e6", None, "#b08ad8", "Common face", "Face commune"),
               "rare": ("#bfeeff", "#7cc8f4", None, "#3aa8e0", "Rare face", "Face rare"),
               "epic": ("#ffc4e4", "#ff7fc0", None, "#e94a9b", "Epic face", "Face épique"),
               "legendary": ("#ffe6f4", "#d4c4ff", None, "#c08a1a", "Legendary face", "Face légendaire")},
        body=("#fff7fc", "#5a2a4a"), title_stroke=False,
        opening_pack="""@keyframes manga-charge {
  0% { transform: none; filter: none; opacity: 1; }
  14% { transform: translateY(-8px) rotate(-2deg); }
  24% { transform: translateY(-12px) rotate(3deg) scale(1.03); filter: brightness(1.15); }
  29% { transform: translateY(-14px) rotate(40deg) scale(0.9); filter: brightness(1.4) blur(0); }
  33% { transform: translateY(-16px) rotate(220deg) scale(0.55); filter: brightness(1.9) blur(1px); }
  36% { transform: translateY(-18px) rotate(480deg) scale(0.2); filter: brightness(2.6) blur(2px); opacity: 1; }
  38% { transform: translateY(-18px) rotate(620deg) scale(0.02); filter: brightness(4) blur(3px); opacity: 0; }
  100% { transform: translateY(-18px) scale(0.02); opacity: 0; }
}""",
        parts={"backdrop": ("Ciel pastel", "Pastel sky", "Un ciel pastel du lilas au rose et au cyan, des étoiles qui scintillent, des bulles irisées qui montent, un croissant de lune et des halos de lumière (HD).", "A pastel sky from lilac to pink and cyan, stars twinkling, iridescent bubbles rising, a crescent moon and soft halos of light (HD)."),
               "look": ("Paquet en dentelle", "Lace pack", "Un paquet rose nacré bordé de dentelle, noué d'un nœud de ruban, un cœur taillé comme une gemme ; l'image de l'œuvre dans un médaillon ; son nom en lettres rondes ; des étincelles.", "A pearly pink pack trimmed with lace, tied with a ribbon bow, a heart cut like a gem; the work's art in a locket; its name in round letters; sparkles."),
               "opening": ("Transformation", "Transformation", "Un cercle magique se trace, des rubans s'enroulent autour du paquet, des cœurs et des étincelles montent ; un éclat d'étoile, un anneau de lumière, les rubans se déroulent et une pluie de cœurs, d'étoiles, de pétales et de bulles retombe.", "A magic circle draws itself, ribbons spiral round the pack, hearts and sparkles rise; a star flash, a ring of light, the ribbons unwind and a shower of hearts, stars, petals and bubbles falls."),
               "back": ("Dos en dentelle", "Lace back", "Lilas nacré, une bordure de dentelle, un nœud et un cœur-gemme au centre.", "Pearly lilac, a lace border, a bow and a heart gem in the middle."),
               "rare": ("Bulles", "Bubbles", "Un anneau de lumière, des bulles irisées qui montent autour de la carte, des étincelles.", "A ring of light, iridescent bubbles rising round the card, sparkles."),
               "epic": ("Rubans", "Ribbons", "Deux rubans tourbillonnent autour de la carte, une gerbe de cœurs, d'étoiles et de pétales, des étincelles.", "Two ribbons whirl round the card, a burst of hearts, stars and petals, sparkles."),
               "legendary": ("Cercle magique", "Magic circle", "Un cercle magique géant qui tourne derrière la carte, des rayons pastel, des rubans qui l'enlacent devant et derrière, une pluie d'étoiles, des cœurs et de grands éclats.", "A giant magic circle turning behind the card, pastel rays, ribbons wrapping it in front and behind, a rain of stars, hearts and great glints.")}),
    "ninja": dict(
        font=("YujiBoku.woff2", "Manga Boku", 400), names={"fr": "Ninja — techniques de l'ombre", "en": "Ninja — shadow techniques"},
        descriptions={"fr": "Une ouverture de booster façon manga de ninjas, ses animations dessinées image par image dans EffectCraft et jouées en vidéo haute qualité : une nuit sous une lune rouge géante, des toits de tuiles et la brume ; un paquet de bois sombre scellé d'une étiquette de papier ; un sceau qui s'embrase, une bombe fumigène, un éclair de lame et une volée de shuriken ; des cartes de bois et de papier révélées par un tourbillon de shuriken, des kunai et des éclairs bleus ou — légendaire — l'invocation d'un dragon de feu.",
                      "en": "A booster opening like a ninja manga's, its animations drawn frame by frame in EffectCraft and played as high-quality video: night under a huge red moon, tiled roofs and mist; a dark wooden pack sealed with a paper tag; a seal catching fire, a smoke bomb, a blade's flash and a volley of shuriken; cards of wood and paper revealed by a whirlwind of shuriken, kunai and blue lightning or — legendary — the summoning of a dragon of fire."},
        svgs={"wood.svg": (wood, ("look-ninja", "back-ninja", "face-common", "face-rare", "face-epic", "face-legendary")),
              "ofuda.svg": (ofuda, ("look-ninja",)), "shuriken.svg": (shuriken_svg, ("look-ninja", "back-ninja")), "moon.svg": (moon, ("back-ninja",))},
        faces={"common": ("#3a2a22", "#1a120e", None, "#8a929e", "Common face", "Face commune"),
               "rare": ("#2a2e40", "#10121e", None, "#4a8cff", "Rare face", "Face rare"),
               "epic": ("#40201c", "#1e0c0a", None, "#e0301e", "Epic face", "Face épique"),
               "legendary": ("#4a3010", "#1e1206", None, "#ff9a1e", "Legendary face", "Face légendaire")},
        body=("#f2e6cc", "#1e1410"), title_stroke=False,
        opening_pack="""@keyframes manga-charge {
  0% { transform: none; filter: none; opacity: 1; }
  8% { transform: translate(-1px, 0); filter: sepia(0.3); }
  15% { transform: translate(1px, 0) scale(1.02); filter: sepia(0.5) brightness(1.2); opacity: 1; }
  19% { transform: translateY(6px) scale(1.08, 0.9); filter: brightness(1.5) blur(1px); opacity: 0.8; }
  24% { transform: translateY(14px) scale(0.85, 0.6); filter: brightness(1.8) blur(4px); opacity: 0; }
  100% { opacity: 0; }
}""",
        parts={"backdrop": ("Nuit sous la lune rouge", "Night under the red moon", "Une nuit bleu sombre sous une lune rouge géante voilée de nuages, des silhouettes de toits de tuiles, la brume qui passe, des feuilles d'érable qui tombent et, de temps en temps, l'ombre d'un ninja qui bondit devant la lune (HD).", "A dark blue night under a huge red moon veiled with clouds, silhouettes of tiled roofs, mist drifting, maple leaves falling and, now and then, the shadow of a ninja leaping across the moon (HD)."),
               "look": ("Coffret scellé", "Sealed box", "Un coffret de bois sombre ceint d'une corde, scellé d'une étiquette de papier au cercle vermillon ; l'image de l'œuvre comme un panneau peint ; son nom tracé au pinceau ; un shuriken.", "A dark wooden box tied with a cord, sealed with a paper tag bearing a vermillion circle; the work's art like a painted panel; its name brushed; a shuriken."),
               "opening": ("Bombe fumigène", "Smoke bomb", "Le sceau du paquet s'embrase, une bombe fumigène éclate et l'engloutit, un éclair de lame la traverse, des shuriken jaillissent du nuage dans toutes les directions et des feuilles d'érable tourbillonnent.", "The pack's seal catches fire, a smoke bomb bursts and swallows it, a blade's flash crosses it, shuriken shoot out of the cloud every way and maple leaves swirl."),
               "back": ("Dos de bois", "Wooden back", "Bois sombre, une lune rouge et un shuriken au centre.", "Dark wood, a red moon and a shuriken in the middle."),
               "rare": ("Tourbillon de shuriken", "Shuriken whirlwind", "Un nuage de fumée, puis un tourbillon de shuriken autour de la carte, en traînées, projetés au loin.", "A puff of smoke, then a whirlwind of shuriken round the card, streaking, flung away."),
               "epic": ("Kunai et éclairs", "Kunai and lightning", "Des kunai fusent et se plantent autour de la carte, des éclairs bleus crépitent entre eux, la fumée, des feuilles.", "Kunai fly in and strike round the card, blue lightning crackles between them, smoke, leaves."),
               "legendary": ("Invocation", "Summoning", "Un cercle de sceaux s'allume sous la carte, la fumée éclate et un dragon de feu en surgit, s'enroule autour d'elle devant et derrière, des braises montent.", "A circle of seals glows under the card, smoke bursts and a dragon of fire rises out of it, coiling round it in front and behind, embers rising.")}),
    "mecha": dict(
        font=("ChakraPetch.woff2", "Manga Petch", 700), names={"fr": "Mecha — robots géants", "en": "Mecha — giant robots"},
        descriptions={"fr": "Une ouverture de booster façon anime de robots géants, ses animations dessinées image par image dans EffectCraft et jouées en vidéo haute qualité : un hangar aux néons, une grille au sol et des projecteurs ; une capsule blindée aux plaques rivetées, son réacteur qui luit ; un HUD qui verrouille la cible, des verrous qui sautent, de la vapeur, le blindage qui s'arrache dans l'éclair du réacteur ; des cartes blindées à l'écran de pilotage, révélées par un scan, une salve de missiles ou — légendaire — des ailes d'énergie qui se déploient.",
                      "en": "A booster opening like a giant-robot anime's, its animations drawn frame by frame in EffectCraft and played as high-quality video: a neon hangar, a grid floor and searchlights; an armoured capsule of riveted plates, its reactor glowing; a HUD locking on, bolts releasing, steam, the armour torn off in the reactor's flash; armoured cards with a cockpit screen, revealed by a scan, a missile salvo or — legendary — wings of energy unfolding."},
        svgs={"panel.svg": (panel, ("look-mecha", "back-mecha", "face-common", "face-rare", "face-epic", "face-legendary")),
              "core.svg": (core_svg, ("look-mecha", "back-mecha")), "hexes.svg": (hexes, ("face-common", "face-rare", "face-epic", "face-legendary", "back-mecha"))},
        faces={"common": ("#7a8290", "#3a404c", None, "#9aa4b4", "Common face", "Face commune"),
               "rare": ("#5a7080", "#22303c", None, "#3ee8ff", "Rare face", "Face rare"),
               "epic": ("#705a80", "#2c2236", None, "#ff4aa8", "Epic face", "Face épique"),
               "legendary": ("#8a7a50", "#3a3018", None, "#ffc83e", "Legendary face", "Face légendaire")},
        body=("#0c1420", "#d6f6ff"), title_stroke=False,
        opening_pack="""@keyframes manga-charge {
  0% { transform: none; filter: none; clip-path: inset(0 0 0 0); opacity: 1; }
  16% { transform: none; clip-path: inset(0 0 0 0); }
  20% { transform: translateX(6px); filter: hue-rotate(40deg) brightness(1.2); clip-path: inset(12% 0 58% 0); }
  21% { transform: translateX(-8px); clip-path: inset(46% 0 22% 0); }
  22% { transform: translateX(4px); filter: hue-rotate(-30deg); clip-path: inset(0 0 0 0); }
  24% { transform: translateX(-5px); clip-path: inset(70% 0 4% 0); }
  25% { transform: none; filter: brightness(1.4); clip-path: inset(0 0 0 0); }
  29% { transform: scale(1.04, 0.03); filter: brightness(3); opacity: 1; }
  33% { transform: scale(0.02, 0.02); filter: brightness(4); opacity: 1; }
  35% { transform: scale(0, 0); opacity: 0; }
  100% { transform: scale(0, 0); opacity: 0; }
}""",
        parts={"backdrop": ("Hangar aux néons", "Neon hangar", "Un hangar sombre : une grille de néons cyan qui file vers l'horizon, des projecteurs qui balaient, des hexagones d'interface, des étincelles et des voyants qui clignotent (HD).", "A dark hangar: a grid of cyan neon running to the horizon, searchlights sweeping, interface hexagons, sparks and blinking lights (HD)."),
               "look": ("Capsule blindée", "Armoured capsule", "Une capsule de plaques blindées rivetées, une bande de danger, son réacteur cyan qui luit ; l'image de l'œuvre sur un écran ; son nom en lettres techniques ; le nombre de cartes sur un voyant.", "A capsule of riveted armour plates, a hazard stripe, its cyan reactor glowing; the work's art on a screen; its name in technical letters; the card count on an indicator."),
               "opening": ("Déverrouillage", "Release", "Un HUD verrouille le paquet, ses quatre verrous sautent, des jets de vapeur fusent, ses plaques s'arrachent dans l'éclair cyan du réacteur, des arcs électriques, une onde de choc hexagonale et des étincelles.", "A HUD locks on the pack, its four bolts release, steam jets burst, its plates fly off in the reactor's cyan flash, electric arcs, a hexagonal shockwave and sparks."),
               "back": ("Dos blindé", "Armoured back", "Plaques blindées rivetées, une trame hexagonale, un réacteur cyan au centre.", "Riveted armour plates, a hexagonal grid, a cyan reactor in the middle."),
               "rare": ("Scan", "Scan", "Un HUD verrouille la carte, une ligne de scan la balaie, des barres de données, des étincelles.", "A HUD locks on the card, a scan line sweeps it, data bars, sparks."),
               "epic": ("Salve de missiles", "Missile salvo", "Une salve de missiles lancée de derrière la carte, en éventail sur des traînées de fumée, qui explosent haut et loin, des étincelles.", "A missile salvo launched from behind the card, fanning out on trails of smoke, blasting high and wide, sparks."),
               "legendary": ("Ailes d'énergie", "Wings of energy", "Des ailes d'énergie cyan et blanches se déploient derrière la carte, ses propulseurs flambent sous elle, un réticule ; devant elle, le cadre du HUD, une ligne de scan, des étincelles et de grands éclats.", "Wings of cyan and white energy unfold behind the card, its thrusters flare under it, a reticle; in front of it, the HUD's frame, a scan line, sparks and great glints.")}),
}
DURATIONS = {"rare": 1.8, "epic": 2.4, "legendary": 3.0}


def room(sel):
    return f"""/* room for the effect: a layer 2.6 times the card, fading out towards its edges — never the outline of its box */
{sel} {{
  inset: -80%;
  width: 260%;
  height: 260%;
  mask-image: radial-gradient(closest-side, #000 72%, transparent 100%);
}}
/* on a phone, the cards' row scrolls sideways and cuts what overflows it 5rem above and below a card: the
   effect has faded out before it */
@media (max-width: 40rem) {{
  {sel} {{
    mask-image: radial-gradient(closest-side, #000 72%, transparent 100%), linear-gradient(to bottom, transparent calc(30.77% - 4.5rem), #000 calc(30.77% - 1.5rem), #000 calc(69.23% + 1.5rem), transparent calc(69.23% + 4.5rem));
    mask-composite: intersect;
  }}
}}
"""


def font_face(style):
    file, family, weight = STYLES[style]["font"]
    return f'@font-face {{\n  font-family: "{family}";\n  src: url("{file}") format("woff2");\n  font-weight: {weight};\n  font-display: swap;\n}}\n'


def face_css(style, rarity):
    s = STYLES[style]
    top, bottom, print_file, accent, _, _ = s["faces"][rarity]
    paper, ink = s["body"]
    family, weight = s["font"][1], s["font"][2]
    h = f'[data-card-face="{style}-{rarity}"]'
    rim = {
        "shonen": f'url("{print_file}") 0 0 / 160% auto, radial-gradient(circle, rgba(0, 0, 0, 0.35) 0 1px, transparent 1.5px) 0 0 / 1.4cqi 1.4cqi, linear-gradient(160deg, {top}, {bottom})',
        "magical": f'url("lace.svg") 0 0 / 30% auto repeat-x, url("lace.svg") 0 100% / 30% auto repeat-x, linear-gradient(160deg, {top}, {bottom})',
        "ninja": f'url("wood.svg") 0 0 / 100% 100%, linear-gradient(160deg, {top}, {bottom})',
        "mecha": f'url("panel.svg") 0 0 / 100% 100%, linear-gradient(160deg, {top}, {bottom})',
    }[style]
    if style == "magical" and rarity == "legendary":
        rim = 'url("lace.svg") 0 0 / 30% auto repeat-x, url("lace.svg") 0 100% / 30% auto repeat-x, conic-gradient(from 200deg at 40% 45%, #ffd6e8, #ffe9b0, #c8ffd9, #b8e4ff, #d9c4ff, #ffd6e8)'
    body = {
        "shonen": f"radial-gradient(circle, rgba(20, 16, 26, 0.08) 0 0.35cqi, transparent 0.5cqi) 0 0 / 2.2cqi 2.2cqi, {paper}",
        "magical": f"radial-gradient(circle at 20% 15%, rgba(255, 190, 228, 0.5), transparent 40%), radial-gradient(circle at 85% 90%, rgba(190, 230, 255, 0.5), transparent 45%), {paper}",
        "ninja": f"linear-gradient(180deg, rgba(120, 90, 50, 0.08), transparent 30%, rgba(120, 90, 50, 0.1)), {paper}",
        "mecha": f'url("hexes.svg") 0 0 / 9cqi auto, linear-gradient(180deg, #102030, {paper})',
    }[style]
    edge = {"shonen": f"0 0 0 0.75cqi {ink}", "magical": f"0 0 0 0.5cqi #ffffff, 0 0 0 0.8cqi {accent}",
            "ninja": f"0 0 0 0.45cqi {accent}, 0 0 0 0.8cqi #0c0806", "mecha": f"0 0 0 0.35cqi {accent}, 0 0 1.4cqi {accent}, inset 0 0 1.2cqi rgba(62, 232, 255, 0.25)"}[style]
    title = {"shonen": f"color: #ffd21f;\n  -webkit-text-stroke: 1.1cqi {ink};\n  paint-order: stroke fill;\n  text-shadow: 0.9cqi 1cqi 0 {accent};",
             "magical": f"color: {accent};\n  text-shadow: 0 0.3cqi 0 #ffffff, 0 0 1.2cqi rgba(255, 140, 200, 0.6);",
             "ninja": f"color: {ink};\n  text-shadow: 0.2cqi 0.2cqi 0 rgba(196, 39, 28, 0.35);",
             "mecha": f"color: {accent};\n  letter-spacing: 0.08em;\n  text-transform: uppercase;\n  text-shadow: 0 0 1cqi {accent};"}[style]
    intro = wrap(f"A {rarity} card of the {style} scene: its frame, its body and its lettering in the scene's style. (Its hook: the card once turned, data-card-face.) The face turns in 3D: never its transform; a turned media card is never redrawn — what moves, moves once, as it is revealed.")
    css = intro + font_face(style) + f"""{h} .mcard__card {{
  padding: 3cqi;
  border-radius: {"3.4cqi" if style == "magical" else "1.6cqi" if style == "mecha" else "2.4cqi"};
  background: {rim};
  box-shadow: inset 0 0 0 0.35cqi rgba(255, 255, 255, 0.18), 0 0 0 0.45cqi #0c0a10, 0 1.4cqi 3cqi rgba(0, 0, 0, 0.5);
}}
{h} .mcard__body {{
  border-radius: {"2.6cqi" if style == "magical" else "0.8cqi" if style == "mecha" else "1.6cqi"};
  background: {body};
  box-shadow: {edge};
  color: {ink};
}}
{h} .mcard[data-rarity] .mcard__name {{
  font-family: "{family}", var(--mcard-title);
  font-weight: {weight};
  line-height: 1.15;
  {title}
}}
{h} .mcard__genre,
{h} .mcard__rarity,
{h} .mcard__cost {{
  background: {accent};
  color: {"#14101a" if style in ("mecha", "shonen") and rarity == "legendary" else "#ffffff"};
  box-shadow: 0 0 0 0.3cqi {ink if style != "mecha" else accent};
  font-family: "{family}", var(--mcard-title);
  font-weight: {weight};
}}
{h} .mcard__emblem {{
  background: {ink if style != "mecha" else "#0c1420"};
  color: {accent};
}}
{h} .mcard__art {{
  border-radius: {"2cqi" if style == "magical" else "0.6cqi"};
  box-shadow: {edge};
}}
{h} .mcard__strip {{
  background: {ink if style != "mecha" else accent};
  color: {"#0c1420" if style == "mecha" else "#ffffff"};
}}
{h} .mcard__figures strong {{
  font-family: "{family}", var(--mcard-title);
  font-weight: {weight};
}}
"""
    if rarity in ("rare", "epic"):
        css += f"""/* a gleam gliding over the card once */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 32%, rgba(255, 255, 255, 0.75) 46%, {accent} 50%, rgba(255, 255, 255, 0.75) 54%, transparent 68%) 0 0 / 300% 300%;
  mix-blend-mode: soft-light;
  opacity: 0.6;
  animation: manga-gleam-{rarity} 1.6s ease-out both;
}}
@keyframes manga-gleam-{rarity} {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 72% 72%; }}
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-card__face::after {{
    animation: none;
  }}
}}
"""
    if rarity == "legendary":
        css += f"""/* a blaze of the scene's colour sweeping over it once as it lands, a glint crossing its art */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 38%, {accent} 47%, rgba(255, 255, 255, 0.95) 50%, {accent} 53%, transparent 62%) 0 0 / 300% 300%;
  mix-blend-mode: overlay;
  opacity: 0.65;
  animation: manga-blaze 1.6s ease-in-out 1s both;
}}
@keyframes manga-blaze {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 80% 80%; }}
}}
{h} .mcard__art::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 44%, rgba(255, 255, 255, 0.95) 46%, transparent 49%) -150% 0 / 250% 100% no-repeat;
  animation: manga-glint 1.4s ease-in-out 1.7s both;
}}
@keyframes manga-glint {{
  0% {{ background-position: -150% 0; }}
  100% {{ background-position: 250% 0; }}
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-card__face::after {{
    animation: none;
  }}
  {h} .mcard__art::after {{
    animation: none;
    opacity: 0;
  }}
}}
"""
    return css


def look_css(style):
    s = STYLES[style]
    h = f'[data-booster-look="{style}"]'
    family, weight = s["font"][1], s["font"][2]
    dress = {
        "shonen": ('url("flames-orange.svg") 50% 108% / 130% auto no-repeat, radial-gradient(circle, rgba(255, 138, 30, 0.35) 0 1.2px, transparent 1.8px) 0 0 / 8px 8px, linear-gradient(170deg, #2a2430, #0e0a12)',
                   "inset 0 0 0 3px #14101a, inset 0 0 0 7px #ff8a1e, inset 0 0 0 10px #14101a, 0.5rem 0.6rem 0 #14101a",
                   "border: 4px solid #14101a; border-radius: 0.3rem; box-shadow: 5px 6px 0 #ff8a1e, 5px 6px 0 3px #14101a;",
                   'color: #ffd21f; -webkit-text-stroke: 5px #14101a; paint-order: stroke fill; text-shadow: 3px 4px 0 #ff5a1e, 5px 6px 0 #14101a;',
                   'background: url("impact.svg") center / contain no-repeat; color: #14101a;'),
        "magical": ('url("lace.svg") 0 0 / 34% auto repeat-x, url("lace.svg") 0 100% / 34% auto repeat-x, radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.8), transparent 40%), linear-gradient(160deg, #ffd6ec, #ff9fd0 55%, #d4b4ff)',
                    "inset 0 0 0 3px #ffffff, inset 0 0 0 6px #f3a6cf, 0 0 1.4rem rgba(255, 160, 210, 0.6)",
                    "border: 4px solid #ffffff; border-radius: 1.4rem; box-shadow: 0 0 0 3px #f3a6cf, 0 0.4rem 1rem rgba(200, 80, 150, 0.35);",
                    'color: #ffffff; text-shadow: 0 2px 0 #e94a9b, 0 0 0.8rem rgba(255, 120, 190, 0.8);',
                    'background: url("heart.svg") center / contain no-repeat; color: #ffffff; text-shadow: 0 1px 2px #7a1a50;'),
        "ninja": ('url("wood.svg") 0 0 / 100% 100%, linear-gradient(170deg, #3a2a22, #140c0a)',
                  "inset 0 0 0 3px #0c0806, inset 0 0 0 6px #6a4a2a, inset 0 0 0 8px #0c0806, 0 1rem 1.6rem rgba(0, 0, 0, 0.6)",
                  "border: 3px solid #0c0806; border-radius: 0.2rem; box-shadow: 0 0 0 3px #c4271c, 0 0 0 6px #0c0806;",
                  'color: #f2e6cc; text-shadow: 2px 2px 0 #c4271c, 0 0 0.6rem rgba(0, 0, 0, 0.8);',
                  'background: url("shuriken.svg") center / contain no-repeat; color: #ffffff; text-shadow: 0 1px 2px #000000;'),
        "mecha": ('url("panel.svg") 0 0 / 100% 100%, repeating-linear-gradient(135deg, #ffc83e 0 10px, #14101a 10px 20px) 0 100% / 100% 8% no-repeat, linear-gradient(170deg, #6a7280, #2a2e38)',
                  "inset 0 0 0 3px #0e1218, inset 0 0 0 6px #3ee8ff, inset 0 0 0 8px #0e1218, 0 0 1.2rem rgba(62, 232, 255, 0.45)",
                  "border: 3px solid #0e1218; border-radius: 0.2rem; box-shadow: 0 0 0 3px #3ee8ff, 0 0 1rem rgba(62, 232, 255, 0.6);",
                  'color: #d6f6ff; letter-spacing: 0.1em; text-transform: uppercase; text-shadow: 0 0 0.6rem #3ee8ff;',
                  'background: url("core.svg") center / contain no-repeat; color: #0e1218;'),
    }[style]
    bg, shadow, art, name, count = dress
    extra = {
        "shonen": "", "magical": f"""/* the bow on its crimp */
{h} .booster-pack__flap {{
  border: 0;
  background: url("bow.svg") center 70% / 46% auto no-repeat;
  box-shadow: none;
}}
""", "ninja": f"""/* the paper seal tag across its top */
{h} .booster-pack__flap {{
  border: 0;
  background: url("ofuda.svg") 82% 0 / 16% auto no-repeat, linear-gradient(180deg, transparent 40%, #c4271c 40% 52%, transparent 52%);
  box-shadow: none;
}}
""", "mecha": f"""/* its crimp: a hazard stripe */
{h} .booster-pack__flap {{
  border: 0;
  background: repeating-linear-gradient(135deg, #ffc83e 0 10px, #14101a 10px 20px);
  box-shadow: inset 0 -3px 0 #0e1218;
}}
"""}[style]
    return wrap(STYLES[style]["parts"]["look"][3], "The sealed pack (its hook: data-booster-look): ") + font_face(style) + f"""{h} .booster-pack {{
  border-radius: {"1.6rem" if style == "magical" else "0.4rem"};
  background: {bg};
  box-shadow: {shadow};
}}
{h} .booster-pack__art {{
  inset: 14% 11% 32%;
  inline-size: 78%;
  block-size: 54%;
  {art}
  mask: none;
}}
{h} .booster-pack__stars {{
  opacity: 0;
}}
{extra}{h} .booster-pack__name {{
  inset: auto 4% 12%;
  font-family: "{family}", sans-serif;
  font-weight: {weight};
  font-size: clamp(1rem, 2.3vw, 1.4rem);
  line-height: 1.1;
  {name}
}}
{h} .booster-pack__subtitle {{
  inset: auto 4% 5%;
  color: {"#5a2a4a" if style == "magical" else "#e8e2ee"};
  font-family: "{family}", sans-serif;
}}
{h} .booster-pack__count {{
  inset: 0.5rem 0.5rem auto auto;
  display: grid;
  place-items: center;
  inline-size: 2.8rem;
  block-size: 2.8rem;
  padding: 0;
  border-radius: 0;
  {count}
  font-family: "{family}", sans-serif;
  font-weight: {weight};
  font-size: 0.85rem;
  box-shadow: none;
}}
/* tension while it waits: a pulse of the scene's light, added to Portalab's float (never replacing it) */
{h} .booster-stage__tear {{
  animation: booster-hover 4s ease-in-out infinite, manga-pulse 2.8s ease-in-out infinite;
}}
@keyframes manga-pulse {{
  0%, 70%, 100% {{ filter: none; }}
  80% {{ filter: drop-shadow(0 0 0.9rem {s["faces"]["legendary"][3]}); }}
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-stage__tear {{
    animation: none;
  }}
}}
"""


def back_css(style):
    h = f'[data-card-back="{style}"]'
    bg, sigil = {
        "shonen": ('url("flames-orange.svg") 0 50% / 140% auto, radial-gradient(circle, rgba(255, 138, 30, 0.3) 0 1px, transparent 1.6px) 0 0 / 7px 7px, linear-gradient(170deg, #2a2430, #0e0a12)', 'url("impact.svg")'),
        "magical": ('url("lace.svg") 0 0 / 34% auto repeat-x, url("lace.svg") 0 100% / 34% auto repeat-x, linear-gradient(160deg, #efe0ff, #d4b4ff 55%, #ffc4e4)', 'url("heart.svg") 50% 62% / 46% auto no-repeat, url("bow.svg")'),
        "ninja": ('url("wood.svg") 0 0 / 100% 100%, linear-gradient(170deg, #3a2a22, #140c0a)', 'url("shuriken.svg") 50% 50% / 40% auto no-repeat, url("moon.svg")'),
        "mecha": ('url("panel.svg") 0 0 / 100% 100%, url("hexes.svg") 0 0 / 18% auto, linear-gradient(170deg, #4a5260, #1e222a)', 'url("core.svg")'),
    }[style]
    return wrap(STYLES[style]["parts"]["back"][3], "Face down (its hook: the card, data-card-back), every card alike — a back never tells the rarity: ") + f"""{h} .booster-card__back {{
  border: 0;
  border-radius: {"1rem" if style == "magical" else "0.45rem"};
  background: {bg};
  box-shadow: inset 0 0 0 3px #0c0a10, inset 0 0 0 6px {STYLES[style]["faces"]["legendary"][3]}, inset 0 0 0 8px #0c0a10, 0 0.5rem 1rem rgba(0, 0, 0, 0.45);
}}
{h} .booster-card__back-pattern {{
  opacity: 0;
}}
{h} .booster-card__back-sigil {{
  inline-size: 60%;
  aspect-ratio: 1;
  border: 0;
  border-radius: 0;
  background: {sigil} center / contain no-repeat;
  box-shadow: none;
}}
{h} .booster-card__back-sigil svg {{
  opacity: 0;
}}
"""


def opening_css(style):
    h = f'[data-opening="{style}"]'
    fate = {"shonen": "the pack itself swells, trembling, white-hot, and explodes", "magical": "the pack itself whirls round and implodes into a point, the star's flash",
            "ninja": "the pack itself slumps and vanishes into the smoke", "mecha": "the pack itself glitches in shifting slices, then shuts off like a screen — crushed into a line, then a point"}[style]
    return wrap(STYLES[style]["parts"]["opening"][3] + f" Meanwhile {fate}.", "The opening (its hook: the scene's pack while it opens, data-opening), 2.6 s, drawn in EffectCraft and played as a video (24 frames a second): ") + f"""{h} .booster-stage__tear .booster-pack {{
  animation: manga-charge 2.6s linear both;
}}
{STYLES[style]["opening_pack"]}
/* room for the video: the pack at its size in the middle of a layer 4.8 pack-widths wide and 2.7 high, fading
   out towards its edges — never the outline of its box */
{h} .booster-stage__opening {{
  inset: -85% -190%;
  mask-image: radial-gradient(closest-side, #000 72%, transparent 100%);
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-stage__tear .booster-pack {{
    animation: manga-fade 2.6s linear both;
  }}
}}
@keyframes manga-fade {{
  0%, 30% {{ opacity: 1; }}
  45%, 100% {{ opacity: 0; }}
}}
"""


def element(folder, typ, look, names, descriptions, render):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "element.json").write_text(json.dumps({"type": typ, "look": look, "names": names, "descriptions": descriptions, "render": render}, ensure_ascii=False, indent=2) + "\n")


def write(style):
    s = STYLES[style]
    pack = ROOT / f"booster-{style}"
    elements = pack / "elements"
    p = s["parts"]
    for name, (draw, targets) in s["svgs"].items():
        text = draw()
        for target in targets:
            (elements / target).mkdir(parents=True, exist_ok=True)
            (elements / target / name).write_text(text)
    font = FONTS / s["font"][0]
    for target in (f"look-{style}", *(f"face-{r}" for r in RARE)):
        (elements / target).mkdir(parents=True, exist_ok=True)
        if font.exists():
            shutil.copy(font, elements / target / s["font"][0])
    texts = lambda part: ({"fr": p[part][0], "en": p[part][1]}, {"fr": p[part][2], "en": p[part][3]})
    # the stage: its GLSL (stages/<style>.glsl) played as a looping video (lighter for a phone than a full-screen
    # shader every frame) — tools/stage_video.mjs
    element(elements / f"backdrop-{style}", "booster_backdrop", style, *texts("backdrop"), {"kind": "video", "file": "stage.mp4"})
    (elements / f"look-{style}" / "pack.css").write_text(look_css(style))
    element(elements / f"look-{style}", "booster_look", style, *texts("look"), {"kind": "css", "css": ["pack.css"]})
    (elements / f"opening-{style}" / "opening.css").parent.mkdir(parents=True, exist_ok=True)
    (elements / f"opening-{style}" / "opening.css").write_text(opening_css(style))
    element(elements / f"opening-{style}", "booster_opening", style, *texts("opening"),
            {"kind": "video", "file": "opening.mp4", "alpha": "side", "css": ["opening.css"], "stage": True, "duration": 2.6})
    (elements / f"back-{style}").mkdir(parents=True, exist_ok=True)
    (elements / f"back-{style}" / "back.css").write_text(back_css(style))
    element(elements / f"back-{style}", "card_back", style, *texts("back"), {"kind": "css", "css": ["back.css"], "rarity": "common"})
    for r in RARE:
        (elements / f"face-{r}" / "face.css").write_text(face_css(style, r))
        _, _, _, _, en, fr = s["faces"][r]
        element(elements / f"face-{r}", "card_face", f"{style}-{r}", {"fr": fr, "en": en},
                {"fr": f"La carte {fr.lower().replace('face ', '')} de la scène, son cadre, son corps et son lettrage dans le style de la scène.",
                 "en": f"The scene's {en.lower().replace(' face', '')} card: its frame, its body and its lettering in the scene's style."},
                {"kind": "css", "css": ["face.css"], "rarity": r})
    for r in ("rare", "epic", "legendary"):
        folder = elements / f"reveal-{r}"
        folder.mkdir(parents=True, exist_ok=True)
        sel = f'[data-reveal="{style}-{r}"] .booster-fx__scene'
        (folder / "reveal.css").write_text(wrap(p[r][3], f"A {r} card turned (its hook: data-reveal), {DURATIONS[r]} s, drawn in EffectCraft and played as a video in its layer behind the card{' (and, for the near half, over it: ``over``)' if r == 'legendary' else ''}: ") + room(sel))
        render = {"kind": "video", "file": "reveal.mp4", "alpha": "side", "css": ["reveal.css"], "stage": True, "duration": DURATIONS[r], "rarity": r}
        if r == "legendary":
            render["over"] = "over.mp4"
        element(folder, "card_reveal", f"{style}-{r}", *texts(r), render)
    scene = {"type": "booster_scene", "look": style, "names": {"fr": f"Scène {s['names']['fr'].split(' — ')[0]}", "en": f"{s['names']['en'].split(' — ')[0]} scene"},
             "descriptions": {"fr": "Toute l'ouverture, jouée en vidéo. Les cartes tirées et leurs raretés restent celles de Portalab.",
                              "en": "The whole opening, played as videos. The cards drawn and their rarities stay Portalab's."},
             "render": {"kind": "data"},
             "payload": {"parts": {"booster_look": f"look-{style}", "backdrop": f"backdrop-{style}", "opening": f"opening-{style}", "back": {"common": f"back-{style}"},
                                   "face": {r: f"face-{r}" for r in RARE}, "reveal": {r: f"reveal-{r}" for r in ("rare", "epic", "legendary")}}}}
    (elements / f"scene-{style}").mkdir(parents=True, exist_ok=True)
    (elements / f"scene-{style}" / "element.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n")
    (pack / "pack.json").write_text(json.dumps({"format": 1, "id": style, "version": "1.0.0", "names": s["names"], "descriptions": s["descriptions"],
                                                "author": "Portalab (example)", "license": "CC0-1.0"}, ensure_ascii=False, indent=2) + "\n")
    font_name = {"shonen": "Dela Gothic One by artakana", "magical": "Mochiy Pop One by FONTDASU", "ninja": "Yuji Boku by Kinuta Font Factory", "mecha": "Chakra Petch by Cadson Demak"}[style]
    (pack / "CREDITS.txt").write_text(f"""{s['names']['en']} — an example booster scene for Portalab (CC0-1.0), one of the manga universe's four, every
shader, stylesheet and drawing original.

Font: {font_name} — SIL Open Font License 1.1 (https://openfontlicense.org), from Google Fonts (latin
subset); embedded unmodified in the pack and each card face as {s['font'][0]}.

Animations (*.mp4): drawn and rendered with EffectCraft (Apache-2.0, https://github.com/storytold/effectcraft),
made into videos with ffmpeg (../tools/alpha_video.py); still shapes (*.svg) drawn by gen_packs.py; sources and
build in ../booster-manga-source.
""")


if __name__ == "__main__":
    for style in STYLES:
        write(style)
    print("packs written")
