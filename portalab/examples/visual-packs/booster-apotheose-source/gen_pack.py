"""Writes the Apothéose pack but for its videos (build.sh): its still shapes, its stylesheets — the sealed pack, the
back, the four faces, the opening, and each rarity's reveal over the whole screen with the look of the rarity's
name Portalab writes there — and every manifest. Its font (Bangers, SIL OFL) is copied from the Impact pack."""

import json
import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent / "booster-apotheose"
E = PACK / "elements"
FONT = HERE.parent / "booster-impact" / "elements" / "look-impact" / "Bangers.woff2"
INK = "#14081f"
RARITY = {  # rim colours (light, main, dark), the name's look
    "common": ("#d9d2ea", "#8f84ad", "#4b4266"),
    "rare": ("#a8f2ff", "#25c6f2", "#0b5f9e"),
    "epic": ("#ffa8d0", "#ff2d78", "#8c0f4a"),
    "legendary": ("#fff0a8", "#ff8a14", "#a83a00"),
}
FACE = '@font-face {\n  font-family: "Apotheose Bangers";\n  src: url("Bangers.woff2") format("woff2");\n  font-display: swap;\n}\n'


def comment(text):
    lines = textwrap.wrap(text, 110)
    return "/* " + "\n".join(("   " if i else "") + line for i, line in enumerate(lines)) + " */\n"


def emblem():
    """A star burst cut like a gem: eight points, pink, gold and cyan facets, an ink outline."""
    import math
    pts = []
    for i in range(16):
        a = i / 16 * math.tau - math.pi / 2
        r = 46 if i % 2 == 0 else 20
        pts.append((50 + math.cos(a) * r, 50 + math.sin(a) * r))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    facets = "".join(
        f'<path d="M50,50 L{pts[i][0]:.1f},{pts[i][1]:.1f} L{pts[(i + 1) % 16][0]:.1f},{pts[(i + 1) % 16][1]:.1f} Z" fill="{c}"/>'
        for i, c in zip(range(16), ["#ff2d78", "#ffd23e", "#25c6f2", "#ff8a14"] * 4, strict=True))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">{facets}'
            f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>'
            '<circle cx="50" cy="50" r="7" fill="#ffffff" stroke="#14081f" stroke-width="2.5"/></svg>\n')


def look():
    h = '[data-booster-look="apotheose"]'
    return comment("The sealed pack (its hook: data-booster-look): deep violet foil crossed by neon bands in pink, cyan and gold, a gem-cut star burst, the work's art in a slanted window, its name in big comic letters, the card count on a gold tag; a sweep of light now and then.") + FACE + f"""{h} .booster-pack {{
  border-radius: 0.6rem;
  background:
    linear-gradient(118deg, transparent 0 58%, #ff2d78 58% 61%, transparent 61% 64%, #25c6f2 64% 66%, transparent 66% 69%, #ffd23e 69% 70.5%, transparent 70.5%),
    radial-gradient(circle at 30% 20%, rgba(255, 45, 120, 0.45), transparent 55%),
    linear-gradient(165deg, #5a1aa8, #2a0a5a 60%, #14081f);
  box-shadow: inset 0 0 0 3px {INK}, inset 0 0 0 6px #ff2d78, inset 0 0 0 8px {INK}, 0 1rem 2rem rgba(0, 0, 0, 0.55), 0 0 1.6rem rgba(255, 45, 120, 0.35);
}}
{h} .booster-pack__art {{
  inset: 13% 10% 33%;
  inline-size: 80%;
  block-size: 54%;
  border: 4px solid {INK};
  border-radius: 0.3rem;
  box-shadow: 6px 6px 0 #25c6f2, 6px 6px 0 3px {INK};
  clip-path: polygon(0 4%, 100% 0, 100% 96%, 0 100%);
  mask: none;
  filter: saturate(1.25) contrast(1.06);
}}
{h} .booster-pack__foil {{
  opacity: 1;
  background: linear-gradient(105deg, transparent 40%, rgba(255, 255, 255, 0.55) 48%, transparent 56%) -160% 0 / 200% 100% no-repeat;
  animation: apotheose-sweep 3.6s ease-in-out infinite;
}}
@keyframes apotheose-sweep {{
  0%, 55% {{ background-position: -160% 0; }}
  85%, 100% {{ background-position: 260% 0; }}
}}
{h} .booster-pack__stars {{
  opacity: 0;
}}
{h} .booster-pack__flap {{
  border: 0;
  background: repeating-linear-gradient(135deg, #ffd23e 0 8px, {INK} 8px 16px);
  box-shadow: inset 0 -3px 0 {INK};
}}
{h} .booster-pack__emblem {{
  inline-size: 64%;
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
  font-family: "Apotheose Bangers", sans-serif;
  font-weight: 400;
  font-size: clamp(1.15rem, 2.6vw, 1.6rem);
  letter-spacing: 0.04em;
  line-height: 1;
  color: #ffffff;
  -webkit-text-stroke: 5px {INK};
  paint-order: stroke fill;
  text-shadow: 3px 4px 0 #ff2d78, 5px 6px 0 {INK};
  rotate: -4deg;
}}
{h} .booster-pack__subtitle {{
  inset: auto 4% 4%;
  color: #e8dcff;
}}
{h} .booster-pack__count {{
  inset: 0.5rem 0.5rem auto auto;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  background: #ffd23e;
  color: {INK};
  font-family: "Apotheose Bangers", sans-serif;
  font-weight: 400;
  font-size: 1rem;
  box-shadow: 0 0 0 3px {INK}, 3px 3px 0 3px {INK};
  rotate: 6deg;
}}
@media (prefers-reduced-motion: reduce) {{
  {h} .booster-pack__foil {{
    animation: none;
  }}
}}
"""


def back():
    h = '[data-card-back="apotheose"]'
    return comment("Face down (its hook: the card, data-card-back), every card alike — a back never tells the rarity: deep violet, neon bands on a slant, the gem-cut star burst in the middle.") + f"""{h} .booster-card__back {{
  border: 0;
  border-radius: 0.55rem;
  background:
    linear-gradient(118deg, transparent 0 18%, #ff2d78 18% 21%, transparent 21% 24%, #25c6f2 24% 26%, transparent 26% 74%, #ffd23e 74% 75.5%, transparent 75.5% 78%, #ff2d78 78% 81%, transparent 81%),
    linear-gradient(165deg, #5a1aa8, #2a0a5a 60%, #14081f);
  box-shadow: inset 0 0 0 3px {INK}, inset 0 0 0 6px #ff2d78, inset 0 0 0 8px {INK}, 0 0.5rem 1rem rgba(0, 0, 0, 0.5);
}}
{h} .booster-card__back-pattern {{
  opacity: 0;
}}
{h} .booster-card__back-sigil {{
  inline-size: 62%;
  aspect-ratio: 1;
  border: 0;
  border-radius: 0;
  background: url("emblem.svg") center / contain no-repeat;
  box-shadow: none;
  filter: drop-shadow(0 0 0.7rem rgba(255, 45, 120, 0.6));
}}
{h} .booster-card__back-sigil svg {{
  opacity: 0;
}}
"""


def face(rarity):
    light, main, dark = RARITY[rarity]
    h = f'[data-card-face="apotheose-{rarity}"]'
    css = comment(f"A {rarity} card (its hook: the card once turned, data-card-face): a frame in the rarity's neon over deep violet, neon bands on a slant, comic lettering outlined in ink. The face turns in 3D: never its transform; a turned media card is never redrawn.") + FACE + f"""{h} .mcard__card {{
  padding: 3cqi;
  border-radius: 2.6cqi;
  background:
    linear-gradient(118deg, transparent 0 62%, {main} 62% 65%, transparent 65% 68%, {light} 68% 69.5%, transparent 69.5%),
    linear-gradient(160deg, {light}, {main} 40%, {dark});
  box-shadow: 0 0 0 0.8cqi {INK}, 0 0 3cqi {main};
}}
{h} .mcard__body {{
  border-radius: 1.8cqi;
  background: linear-gradient(170deg, #2a1050, #14081f);
  box-shadow: inset 0 0 0 0.6cqi {INK};
  color: #f4ecff;
}}
{h} .mcard[data-rarity] .mcard__name {{
  overflow: visible;
  text-overflow: clip;
  font-family: "Apotheose Bangers", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.03em;
  line-height: 1.15;
  text-transform: uppercase;
  color: #ffffff;
  -webkit-text-stroke: 1.2cqi {INK};
  paint-order: stroke fill;
  text-shadow: 0.9cqi 1.1cqi 0 {main};
}}
{h} .mcard__genre,
{h} .mcard__rarity,
{h} .mcard__cost {{
  background: {main};
  color: {INK};
  box-shadow: 0 0 0 0.45cqi {INK};
  font-family: "Apotheose Bangers", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.05em;
}}
{h} .mcard__emblem {{
  background: {INK};
  color: {main};
}}
{h} .mcard__art {{
  border-radius: 1cqi;
  box-shadow: 0 0 0 0.6cqi {INK}, 1cqi 1.1cqi 0 0.6cqi {main};
}}
{h} .mcard__strip {{
  background: {main};
  color: {INK};
}}
{h} .mcard__figures strong {{
  font-family: "Apotheose Bangers", var(--mcard-title);
  font-weight: 400;
}}
"""
    if rarity != "common":
        css += f"""/* a sweep of the rarity's light over it, once */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 36%, {light} 47%, rgba(255, 255, 255, 0.95) 50%, {main} 53%, transparent 64%) 0 0 / 300% 300%;
  mix-blend-mode: overlay;
  opacity: 0.6;
  animation: apotheose-sweep-{rarity} 1.5s ease-in-out 0.6s both;
}}
@keyframes apotheose-sweep-{rarity} {{
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


WORD = {
    "rare": "color: #ffffff;\n  -webkit-text-stroke: 0.5rem #0b2a5e;\n  paint-order: stroke fill;\n  text-shadow: 0.6rem 0.6rem 0 #0b2a5e;",
    "epic": "color: #ffffff;\n  -webkit-text-stroke: 0.55rem #14081f;\n  paint-order: stroke fill;\n  text-shadow: 0.6rem 0.6rem 0 #14081f;",
    "legendary": "color: #1a0904;\n  -webkit-text-stroke: 0.3rem #ffe08a;\n  paint-order: stroke fill;\n  text-shadow: 0.5rem 0.5rem 0 #ffd23e, 1rem 1rem 0 #1a0904;",
}
DESCRIPTIONS = {
    "rare": ("Éclat cyan", "Cyan burst", "Plein écran, joué en vidéo : d'abord RARE en lettres géantes (écrit par Portalab) sur un écran cyan balafré d'encre et d'éclairs ; puis la carte arrive de dos dans une explosion de rayons cyan et blancs, se retourne dans un éclair, une couronne blanche déchiquetée autour d'elle, des étincelles.",
             "Full screen, played as video: first RARE in huge letters (written by Portalab) over a cyan screen slashed with ink and lightning; then the card flung in face down amid bursting cyan and white rays, turning over in a flash, a torn white comic crown round it, sparks."),
    "epic": ("Explosion rose", "Pink explosion", "Plein écran, joué en vidéo : d'abord ÉPIQUE en lettres géantes sur un écran rose balafré d'encre et d'éclairs ; puis la carte arrive de dos dans une explosion de rayons roses et blancs, se retourne dans un éclair, une couronne blanche déchiquetée autour d'elle, des étincelles.",
             "Full screen, played as video: first EPIC in huge letters over a pink screen slashed with ink and lightning; then the card flung in face down amid bursting pink and white rays, turning over in a flash, a torn white comic crown round it, sparks."),
    "legendary": ("Apothéose", "Apotheosis", "Plein écran, joué en vidéo : d'abord LÉGENDAIRE en lettres géantes sur un écran orange balafré d'encre et d'éclairs blancs ; puis la carte arrive de dos dans une explosion de rayons orange et blancs, se retourne dans un éclair, une couronne blanche déchiquetée autour d'elle, des éclairs dorés le long de ses bords, des étincelles et deux grands éclats.",
                  "Full screen, played as video: first LEGENDARY in huge letters over an orange screen slashed with ink and white lightning; then the card flung in face down amid bursting orange and white rays, turning over in a flash, a torn white comic crown round it, gold lightning along its edges, sparks and two great glints."),
}
DURATION = {"rare": 3.2, "epic": 3.8, "legendary": 4.6}


def reveal(rarity):
    h = f'[data-reveal="apotheose-{rarity}"]'
    return comment(f"A {rarity} card turned (its hook: data-reveal), staged over the whole screen (place: screen): Portalab brings the card to the middle, big, between this reveal's two videos — behind it (reveal.mp4) and over it (over.mp4), square, cropped to cover any screen — and writes the rarity's name, which this stylesheet dresses.") + FACE + f"""{h} .booster-takeover__word {{
  font-family: "Apotheose Bangers", sans-serif;
  font-weight: 400;
  font-style: normal;
  letter-spacing: 0.04em;
  {WORD[rarity]}
}}
"""


def element(folder, typ, look, names, descriptions, render):
    (E / folder).mkdir(parents=True, exist_ok=True)
    (E / folder / "element.json").write_text(json.dumps({"type": typ, "look": look, "names": names, "descriptions": descriptions, "render": render}, ensure_ascii=False, indent=2) + "\n")


def main():
    for folder in ("look-apotheose", "back-apotheose"):
        (E / folder).mkdir(parents=True, exist_ok=True)
        (E / folder / "emblem.svg").write_text(emblem())
    for folder in ("look-apotheose", "face-common", "face-rare", "face-epic", "face-legendary", "reveal-rare", "reveal-epic", "reveal-legendary"):
        (E / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(FONT, E / folder / "Bangers.woff2")
    (E / "look-apotheose" / "pack.css").write_text(look())
    element("look-apotheose", "booster_look", "apotheose", {"fr": "Paquet néon", "en": "Neon pack"},
            {"fr": "Un paquet violet profond traversé de bandes néon rose, cyan et or, une étoile taillée comme une gemme, l'image de l'œuvre dans une fenêtre penchée, son nom en grandes lettres BD, le nombre de cartes sur une étiquette dorée.",
             "en": "A deep violet pack crossed by pink, cyan and gold neon bands, a gem-cut star burst, the work's art in a slanted window, its name in big comic letters, the card count on a gold tag."},
            {"kind": "css", "css": ["pack.css"]})
    (E / "back-apotheose" / "back.css").write_text(back())
    element("back-apotheose", "card_back", "apotheose", {"fr": "Dos néon", "en": "Neon back"},
            {"fr": "Violet profond, des bandes néon en biais, l'étoile taillée au centre.", "en": "Deep violet, neon bands on a slant, the gem-cut star in the middle."},
            {"kind": "css", "css": ["back.css"], "rarity": "common"})
    names = {"common": ("Face commune", "Common face"), "rare": ("Face rare", "Rare face"), "epic": ("Face épique", "Epic face"), "legendary": ("Face légendaire", "Legendary face")}
    for r in RARITY:
        (E / f"face-{r}" / "face.css").write_text(face(r))
        element(f"face-{r}", "card_face", f"apotheose-{r}", {"fr": names[r][0], "en": names[r][1]},
                {"fr": "Un cadre au néon de sa rareté sur violet profond, des bandes en biais, un lettrage BD cerné d'encre.",
                 "en": "A frame in its rarity's neon over deep violet, slanted bands, comic lettering outlined in ink."},
                {"kind": "css", "css": ["face.css"], "rarity": r})
    for r in ("rare", "epic", "legendary"):
        (E / f"reveal-{r}" / "reveal.css").write_text(reveal(r))
        fr_n, en_n, fr, en = DESCRIPTIONS[r]
        element(f"reveal-{r}", "card_reveal", f"apotheose-{r}", {"fr": fr_n, "en": en_n}, {"fr": fr, "en": en},
                {"kind": "video", "file": "reveal.mp4", "over": "over.mp4", "alpha": "side", "place": "screen", "css": ["reveal.css"], "duration": DURATION[r], "rarity": r})
    (E / "opening-apotheose" / "opening.css").write_text(comment("The opening (its hook: the scene's pack while it opens, data-opening), 2.6 s, drawn in EffectCraft and played as a video: the pack lifts, light leaking from its seams; a beam of light strikes down through it and slices it — the pack folds into the cut and is gone; a white flash, then a burst of pink, white and violet spikes, glints flying. The cards come out of it.") + """[data-opening="apotheose"] .booster-stage__tear .booster-pack {
  animation: apotheose-slice 2.6s linear both;
}
@keyframes apotheose-slice {
  0% { transform: none; clip-path: inset(0 0 0 0); filter: none; }
  15% { transform: translateY(-10px) scale(1.03); filter: brightness(1.15); }
  38% { transform: translateY(-14px) scale(1.05); clip-path: inset(0 0 0 0); filter: brightness(1.5); }
  46% { transform: translateY(-14px) scale(1.05); clip-path: inset(0 49% 0 49%); filter: brightness(3); }
  48%, 100% { transform: translateY(-14px) scale(1.05); clip-path: inset(0 50% 0 50%); filter: brightness(3); }
}
/* room for the video: the pack at its size in the middle of a layer 4.8 pack-widths wide and 2.7 high, fading
   out towards its edges */
[data-opening="apotheose"] .booster-stage__opening {
  inset: -85% -190%;
  mask-image: radial-gradient(closest-side, #000 70%, transparent 100%);
}
@media (prefers-reduced-motion: reduce) {
  [data-opening="apotheose"] .booster-stage__tear .booster-pack {
    animation: none;
  }
}
""")
    element("opening-apotheose", "booster_opening", "apotheose", {"fr": "Tranché de lumière", "en": "Sliced by light"},
            {"fr": "Dessinée dans EffectCraft, jouée en vidéo : le paquet s'élève, la lumière fuit par ses bords ; un faisceau de lumière s'abat et le tranche, des flammes roses lèchent la coupure, le paquet se replie dans la fente et disparaît ; un éclair blanc, puis une explosion de pointes roses, blanches et violettes et des étincelles.",
             "en": "Drawn in EffectCraft, played as a video: the pack lifts, light leaking from its edges; a beam of light strikes down and slices it, pink flames licking the cut, the pack folds into the slit and is gone; a white flash, then a burst of pink, white and violet spikes and sparks."},
            {"kind": "video", "file": "opening.mp4", "alpha": "side", "css": ["opening.css"], "stage": True, "duration": 2.6})
    element("backdrop-apotheose", "booster_backdrop", "apotheose", {"fr": "Néons", "en": "Neons"},
            {"fr": "Violet profond, des bandes néon rose, cyan et or qui glissent en biais, des trames dans les coins, une lueur rose au centre, des éclats qui scintillent — en vidéo en boucle.",
             "en": "Deep violet, pink, cyan and gold neon bands sliding on a slant, halftone in the corners, a pink glow in the middle, glints twinkling — as a looping video."},
            {"kind": "video", "file": "stage.mp4"})
    (E / "scene-apotheose").mkdir(parents=True, exist_ok=True)
    (E / "scene-apotheose" / "element.json").write_text(json.dumps({
        "type": "booster_scene", "look": "apotheose", "names": {"fr": "Scène Apothéose", "en": "Apothéose scene"},
        "descriptions": {"fr": "Chaque rareté mise en scène sur tout l'écran. Les cartes tirées, leurs raretés et leurs noms restent ceux de Portalab.",
                         "en": "Every rarity staged over the whole screen. The cards drawn, their rarities and names stay Portalab's."},
        "render": {"kind": "data"},
        "payload": {"parts": {"booster_look": "look-apotheose", "backdrop": "backdrop-apotheose", "opening": "opening-apotheose", "back": {"common": "back-apotheose"},
                              "face": {r: f"face-{r}" for r in RARITY}, "reveal": {r: f"reveal-{r}" for r in ("rare", "epic", "legendary")}}}}, ensure_ascii=False, indent=2) + "\n")
    (PACK / "pack.json").write_text(json.dumps({
        "format": 1, "id": "apotheose", "version": "1.1.0",
        "names": {"fr": "Apothéose — la rareté en plein écran", "en": "Apothéose — rarity over the whole screen"},
        "descriptions": {"fr": "Une ouverture de booster où chaque rareté prend tout l'écran, comme dans un jeu de cartes animé : la carte vient au centre, en grand, entre deux vidéos — derrière elle, l'écran qui explose de pointes cyan, roses ou orange et or ; devant elle, des coups de pinceau de lumière, des éclairs et des étincelles — et Portalab écrit la rareté en grandes lettres BD. Un paquet violet aux néons tranché par un faisceau de lumière, des cartes cadrées de néon, une scène de néons en vidéo en boucle.",
                         "en": "A booster opening where every rarity takes the whole screen, like an animated card game's: the card comes to the middle, big, between two videos — behind it the screen exploding in cyan, pink or orange and gold spikes; over it slashes of light, lightning and sparks — and Portalab writes the rarity in big comic letters. A neon violet pack sliced by a beam of light, neon-framed cards, a neon stage as a looping video."},
        "author": "Portalab (example)", "license": "CC0-1.0"}, ensure_ascii=False, indent=2) + "\n")
    (PACK / "CREDITS.txt").write_text("""Apothéose — an example booster scene for Portalab (CC0-1.0), every shader, stylesheet and drawing original.

Font: Bangers by Vernon Adams — SIL Open Font License 1.1 (https://openfontlicense.org), from @fontsource/bangers;
embedded unmodified as Bangers.woff2.

Animations (*.mp4): drawn and rendered with EffectCraft (Apache-2.0, https://github.com/storytold/effectcraft) on the
manga toolkit (../booster-manga-source/effectcraft/core.jsx), made into videos with ffmpeg (../tools/alpha_video.py,
../tools/stage_video.mjs); sources and build in ../booster-apotheose-source.
""")
    print("pack written")


if __name__ == "__main__":
    main()
