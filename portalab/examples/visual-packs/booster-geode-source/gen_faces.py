"""Writes the Géode pack's four card faces (stone and cut gems) — one stylesheet per rarity, self-contained."""

import sys
import textwrap
from pathlib import Path

INK = "#1c1228"
MARBLE = "#f1edf5"
RARITIES = {
    "common": dict(rim='url("stone.svg") 0 0 / 200% auto, #4a4048', bezel="#c9c3cf", accent="#5b5160",
                   intro="A common card: a frame of polished grey stone, a silver bezel, veined pale stone, an engraved title."),
    "rare": dict(rim='url("facets.svg") 0 0 / 100% 100%, linear-gradient(160deg, #8fd0ff, #2e78d8 45%, #123f8c)', bezel="#dfe8f5",
                 accent="#2c6fd0", intro="A rare card: a frame cut in blue quartz, a silver bezel; as it turns, a prismatic gleam glides over it."),
    "epic": dict(rim='url("facets.svg") 0 0 / 100% 100%, linear-gradient(160deg, #d4a8ff, #8a3fe0 45%, #3e1180)', bezel="#e9dcff",
                 accent="#7a32cc", intro="An epic card: a frame cut in amethyst, a silver bezel; as it turns, a prismatic gleam glides over it."),
    "legendary": dict(rim='url("facets.svg") 0 0 / 100% 100%, conic-gradient(from 200deg at 40% 45%, #ffd6e8, #ffe9b0, #c8ffd9, #b8e4ff, #d9c4ff, #ffd6e8)',
                      bezel="#e2b04a", accent="#b07a12",
                      intro="A legendary card: a frame of rainbow opal cut in facets, set in gold; as it lands, gold sweeps over it and a glint crosses its art (its reveal brings the crown of crystals)."),
}


def face(rarity: str, p: dict) -> str:
    h = f'[data-card-face="geode-{rarity}"]'
    intro = textwrap.wrap(p["intro"] + " (Its hook: the card once turned, data-card-face.) The face turns in 3D: never its transform; a turned media card is never redrawn — what moves, moves once, as it is revealed.", 108)
    css = f"""/* {chr(10).join(('   ' if i else '') + line for i, line in enumerate(intro))} */
@font-face {{
  font-family: "Geode Cinzel";
  src: url("Cinzel.woff2") format("woff2");
  font-weight: 500 800;
  font-display: swap;
}}
/* the card: its frame of stone or cut gem, a bevel catching the light */
{h} .mcard__card {{
  padding: 3cqi;
  border-radius: 2.2cqi;
  background: {p['rim']};
  box-shadow:
    inset 0.5cqi 0.5cqi 0.6cqi rgba(255, 255, 255, 0.35),
    inset -0.5cqi -0.5cqi 0.8cqi rgba(0, 0, 0, 0.35),
    0 0 0 0.35cqi {INK},
    0 1.4cqi 3cqi rgba(0, 0, 0, 0.5);
}}
/* the body: polished pale stone in its bezel */
{h} .mcard__body {{
  border-radius: 1.2cqi;
  background: url("veins.svg") 0 0 / 100% 100%, {MARBLE};
  box-shadow: 0 0 0 0.5cqi {p['bezel']}, 0 0 0 0.8cqi {INK}, inset 0 0.4cqi 1cqi rgba(28, 18, 40, 0.18);
  color: {INK};
}}
/* the title, engraved */
{h} .mcard[data-rarity] .mcard__name {{
  font-family: "Geode Cinzel", var(--mcard-title);
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.15;
  color: {INK};
  text-shadow: 0 0.25cqi 0 rgba(255, 255, 255, 0.85), 0 -0.15cqi 0 rgba(28, 18, 40, 0.25);
}}
{h} .mcard__genre {{
  border-radius: 99cqi;
  background: linear-gradient(160deg, {p['accent']}, {INK});
  color: #ffffff;
  box-shadow: 0 0 0 0.3cqi {p['bezel']};
  font-family: "Geode Cinzel", var(--mcard-title);
  font-weight: 700;
  letter-spacing: 0.05em;
}}
{h} .mcard__emblem {{
  background: {INK};
  color: {p['bezel']};
}}
/* the art, set like a stone in its bezel */
{h} .mcard__art {{
  border-radius: 0.8cqi;
  box-shadow: 0 0 0 0.45cqi {p['bezel']}, 0 0 0 0.8cqi {INK}, 0 0.6cqi 1.4cqi rgba(28, 18, 40, 0.35);
}}
{h} .mcard__badge,
{h} .mcard__poster {{
  box-shadow: 0 0 0 0.4cqi {p['bezel']}, 0 0 0 0.7cqi {INK};
}}
{h} .mcard__strip {{
  border-radius: 0.5cqi;
  background: linear-gradient(90deg, {INK}, {p['accent']});
  color: #ffffff;
}}
{h} .mcard__cost {{
  background: {p['accent']};
  color: #ffffff;
  box-shadow: 0 0 0 0.3cqi {p['bezel']};
}}
{h} .mcard__figures strong {{
  font-family: "Geode Cinzel", var(--mcard-title);
  font-weight: 700;
}}
/* the rarity: a cut stone */
{h} .mcard__rarity {{
  border-radius: 0.6cqi;
  background: linear-gradient(135deg, #ffffff 0 12%, {p['accent']} 12% 55%, {INK});
  color: #ffffff;
  box-shadow: 0 0 0 0.3cqi {p['bezel']};
  font-family: "Geode Cinzel", var(--mcard-title);
  font-weight: 700;
  letter-spacing: 0.05em;
}}
"""
    if rarity in ("rare", "epic"):
        strength = {"rare": "0.5", "epic": "0.6"}[rarity]
        css += f"""/* a prismatic gleam gliding over the card once, as light through a cut stone */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 32%, rgba(255, 140, 170, 0.8) 42%, rgba(255, 236, 140, 0.8) 46%, rgba(150, 255, 190, 0.8) 50%, rgba(130, 200, 255, 0.8) 54%, rgba(200, 150, 255, 0.8) 58%, transparent 68%) 0 0 / 300% 300%;
  mix-blend-mode: soft-light;
  opacity: {strength};
  animation: geode-prism-{rarity} 1.7s ease-out both;
}}
@keyframes geode-prism-{rarity} {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 72% 72%; }}
}}
"""
    if rarity == "legendary":
        css += f"""/* gold sweeping over it once as it lands */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 224, 154, 0.9) 48%, rgba(255, 255, 255, 0.95) 50%, rgba(226, 176, 74, 0.9) 52%, transparent 62%) 0 0 / 300% 300%;
  mix-blend-mode: overlay;
  opacity: 0.6;
  animation: geode-gold-legendary 1.6s ease-in-out 1s both;
}}
@keyframes geode-gold-legendary {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 80% 80%; }}
}}
/* a glint crossing the art once — on its own small part, not the whole card */
{h} .mcard__art::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 44%, rgba(255, 255, 255, 0.95) 46%, transparent 49%) -150% 0 / 250% 100% no-repeat;
  animation: geode-glint-legendary 1.4s ease-in-out 1.7s both;
}}
@keyframes geode-glint-legendary {{
  0% {{ background-position: -150% 0; }}
  100% {{ background-position: 250% 0; }}
}}
"""
    passing = {"legendary": [".mcard__art::after"]}.get(rarity, [])
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
        (root / f"face-{rarity}").mkdir(parents=True, exist_ok=True)
        (root / f"face-{rarity}" / "face.css").write_text(face(rarity, palette))
    print("faces written")
