"""Writes the Impact pack's four card faces (comic style) — one stylesheet per rarity, self-contained."""

import sys
import textwrap
from pathlib import Path

INK = "#12061c"
RARITIES = {
    "common": dict(bands=("#f6f3fb", "#dcd5ea", "#bdb3d3"), paper="#fffaf0", accent="#8c84a8", title="#ffd21f", rim="#ff2a3d",
                   intro="A common card: inked all round, a pale rim in hard cel bands, the paper halftone, an outlined comic title."),
    "rare": dict(bands=("#7fefff", "#22bff0", "#0b84c4"), paper="#f1fbff", accent="#22bff0", title="#ffd21f", rim="#ff2a3d",
                 intro="A rare card: a cyan rim, a holographic film in hard rainbow bands."),
    "epic": dict(bands=("#ff8ae0", "#d21dc4", "#8a0f98"), paper="#fff3fb", accent="#ff2d8f", title="#ffffff", rim="#ff2d8f",
                 intro="An epic card: a magenta rim, a brighter film and glitter; as it turns, a white brush slash cuts across it."),
    "legendary": dict(bands=("#fff3a8", "#ffc81f", "#e8891a"), paper="#fffbea", accent="#ff2d8f", title="#ffd21f", rim="#ff2a3d",
                      intro="A legendary card: a gold rim, an intense film, glitter and a great glint crossing it; as it turns, a power vortex — energy ribbons drawn in EffectCraft — whirls round it, over and under it, then blasts away."),
}


def face(rarity: str, p: dict) -> str:
    h = f'[data-card-face="impact-{rarity}"]'
    b1, b2, b3 = p["bands"]
    intro = textwrap.wrap(p["intro"] + " (Its hook: the card once turned, data-card-face.) The face turns in 3D: never its transform; a turned media card is never redrawn — what moves, moves once, as it is revealed.", 108)
    css = f"""/* {chr(10).join(('   ' if i else '') + line for i, line in enumerate(intro))} */
@font-face {{
  font-family: "Impact Bangers";
  src: url("Bangers.woff2") format("woff2");
  font-display: swap;
}}
/* the card: inked, its rim the rarity's flat colour in hard cel bands, a hard drop shadow */
{h} .mcard__card {{
  padding: 3cqi;
  border-radius: 3.4cqi;
  background: linear-gradient(155deg, {b1} 0 28%, {b2} 28% 70%, {b3} 70%);
  box-shadow: 0 0 0 0.9cqi {INK}, 1.6cqi 1.9cqi 0 0.9cqi {INK};
}}
/* the body: printed paper, a light halftone */
{h} .mcard__body {{
  border-radius: 2.2cqi;
  background:
    radial-gradient(circle, rgba(18, 6, 28, 0.09) 0 0.35cqi, transparent 0.5cqi) 0 0 / 2.2cqi 2.2cqi,
    {p['paper']};
  box-shadow: inset 0 0 0 0.75cqi {INK};
  color: {INK};
}}
/* the title, comic lettering: yellow, rimmed with red, outlined in ink, a hard shadow */
{h} .mcard[data-rarity] .mcard__name {{
  overflow: visible;
  text-overflow: clip;
  padding-inline: 0.8cqi;
  font-family: "Impact Bangers", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.03em;
  line-height: 1.15;
  text-transform: uppercase;
  color: {p['title']};
  -webkit-text-stroke: 1.3cqi {p['rim']};
  paint-order: stroke fill;
  text-shadow:
    0.75cqi 0 0 {INK}, -0.75cqi 0 0 {INK}, 0 0.75cqi 0 {INK}, 0 -0.75cqi 0 {INK},
    0.55cqi 0.55cqi 0 {INK}, -0.55cqi 0.55cqi 0 {INK}, 0.55cqi -0.55cqi 0 {INK}, -0.55cqi -0.55cqi 0 {INK},
    1.4cqi 1.6cqi 0 {INK};
}}
/* the genre: a tilted sticker */
{h} .mcard__genre {{
  background: {p['accent']};
  color: #ffffff;
  box-shadow: 0 0 0 0.55cqi {INK}, 0.7cqi 0.8cqi 0 0.55cqi {INK};
  font-family: "Impact Bangers", var(--mcard-title);
  font-weight: 400;
  font-size: 3.4cqi;
  letter-spacing: 0.06em;
  rotate: 4deg;
}}
{h} .mcard__emblem {{
  background: {INK};
}}
/* the art, in an inked panel, its shadow the rarity's colour */
{h} .mcard__art {{
  border-radius: 1.6cqi;
  box-shadow: 0 0 0 0.8cqi {INK}, 1.2cqi 1.4cqi 0 0.8cqi {p['accent']};
}}
{h} .mcard__picture,
{h} .mcard__scene {{
  filter: saturate(1.3) contrast(1.08);
}}
{h} .mcard__strip {{
  border-radius: 0.8cqi;
  background: {INK};
  color: #ffffff;
}}
{h} .mcard__poster {{
  box-shadow: 0 0 0 0.6cqi {INK}, 0.6cqi 0.7cqi 0 0.6cqi {p['accent']};
  rotate: -3deg;
}}
{h} .mcard__cost {{
  background: {p['accent']};
  color: #ffffff;
  box-shadow: 0 0 0 0.45cqi {INK};
}}
{h} .mcard__figures strong {{
  font-family: "Impact Bangers", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.03em;
}}
{h} .mcard__rarity {{
  background: {INK};
  color: {p['accent']};
  box-shadow: 0.5cqi 0.6cqi 0 {p['accent']};
  font-family: "Impact Bangers", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.06em;
  rotate: -3deg;
}}
"""
    if rarity != "common":
        strength = {"rare": "0.3", "epic": "0.38", "legendary": "0.45"}[rarity]
        css += f"""/* the holographic film: hard rainbow bands, sliding over the card as it catches the light */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 0 40%, #ff2d8f 40% 42%, #ffd21f 42% 44%, #2bff6e 44% 46%, #22bff0 46% 48%, #9a45f0 48% 50%, transparent 50%) 0 0 / 300% 300%;
  mix-blend-mode: color-dodge;
  opacity: {strength};
  animation: impact-holo-{rarity} 1.4s steps(14, end) both;
}}
@keyframes impact-holo-{rarity} {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 55% 55%; }}
}}
"""
    if rarity in ("epic", "legendary"):
        css += f"""/* glitter over the card */
{h} .booster-card__face::before {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 4;
  pointer-events: none;
  border-radius: inherit;
  background-image:
    radial-gradient(circle at 20% 30%, #ffffff 0 1.2px, transparent 1.7px),
    radial-gradient(circle at 70% 20%, #fff6c8 0 1.3px, transparent 2px),
    radial-gradient(circle at 45% 75%, #ffffff 0 1px, transparent 1.5px);
  background-size: 23px 29px, 31px 37px, 19px 23px;
  mix-blend-mode: screen;
  opacity: 0.22;
}}
"""
    if rarity == "epic":
        css += f"""/* as it turns: a white brush slash cutting across it, over it, drawn in a few frames */
{h}::after {{
  content: "";
  position: absolute;
  inset: 30% -40%;
  z-index: 3;
  pointer-events: none;
  background: url("slash-a.svg") center / 100% 100% no-repeat;
  rotate: -28deg;
  clip-path: inset(0 100% 0 0);
  animation: impact-cut-epic 1.4s steps(28, end) both;
}}
@keyframes impact-cut-epic {{
  0%, 20% {{ clip-path: inset(0 100% 0 0); opacity: 1; }}
  38% {{ clip-path: inset(0 0 0 0); }}
  55% {{ clip-path: inset(0 0 0 0); opacity: 1; }}
  72%, 100% {{ clip-path: inset(0 0 0 100%); opacity: 0; }}
}}
"""
    if rarity == "legendary":
        css += f"""/* as it turns: the power vortex — energy ribbons whirling round the card, its back half under the card, its
   front half over it, then blasting away (drawn in EffectCraft at 24 frames a second, played frame by frame) */
{h}::before,
{h}::after {{
  content: "";
  position: absolute;
  inset: -80%;
  pointer-events: none;
  mask-image: radial-gradient(closest-side, #000 72%, transparent 100%);
}}
/* frames: begin (written by booster-impact-source/sheets.py) */
/* frames: end */
{h}::after {{
  z-index: 3;
  background-image: url("vortex-front.webp");
}}
/* on a phone, the cards' row scrolls sideways and cuts what overflows it 5rem above and below a card: the
   vortex has faded out before it */
@media (max-width: 40rem) {{
  {h}::before,
  {h}::after {{
    mask-image: radial-gradient(closest-side, #000 72%, transparent 100%), linear-gradient(to bottom, transparent calc(30.77% - 4.5rem), #000 calc(30.77% - 1.5rem), #000 calc(69.23% + 1.5rem), transparent calc(69.23% + 4.5rem));
    mask-composite: intersect;
  }}
}}
"""
        css += f"""/* a great glint crossing the art now and then — on its own small part, not the whole card */
{h} .mcard__art::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 44%, #ffffff 44% 47%, transparent 47% 50%, #ffffff 50% 51%, transparent 51%) -150% 0 / 250% 100% no-repeat;
  animation: impact-glint-legendary 1.6s steps(16, end) 0.5s both;
}}
@keyframes impact-glint-legendary {{
  0% {{ background-position: -150% 0; }}
  100% {{ background-position: 250% 0; }}
}}
"""
    # what moves once: stilled when motion is reduced — the passing effects not shown at all
    passing = {"epic": ["::after"], "legendary": ["::before", "::after", ".mcard__art::after"]}.get(rarity, [])
    staying = {"rare": [".booster-card__face::after"], "epic": [".booster-card__face::after"],
               "legendary": [".booster-card__face::after"]}.get(rarity, [])
    sel = lambda items: ",\n".join(f"  {h}{'' if s.startswith('::') else ' '}{s}" for s in items)
    if passing or staying:
        css += "@media (prefers-reduced-motion: reduce) {\n"
        if passing:
            css += f"{sel(passing)} {{\n    animation: none;\n    opacity: 0;\n  }}\n"
        if staying:
            css += f"{sel(staying)} {{\n    animation: none;\n  }}\n"
        css += "}\n"
    return css


if __name__ == "__main__":
    root = Path(sys.argv[1])
    for rarity, palette in RARITIES.items():
        (root / f"face-{rarity}" / "face.css").write_text(face(rarity, palette))
    print("faces written")
