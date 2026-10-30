"""Writes the Sumi pack's four card faces (lacquer, washi and gold) — one stylesheet per rarity, self-contained."""

import sys
import textwrap
from pathlib import Path

INK = "#0e0a09"
GOLD = "#d9a43a"
WASHI = "#f3e9d3"
RARITIES = {
    "common": dict(lacquer=("#2a1c18", "#140c0a"), pattern="", line=GOLD, accent="#0e0a09", seal="#c42c18",
                   intro="A common card: black lacquer round washi paper, a fine gold line, ink lettering."),
    "rare": dict(lacquer=("#2c4d8c", "#13254d"), pattern='url("asanoha.svg") 0 0 / 7.5cqi auto repeat, ', line="#d9e2ee", accent="#24427a",
                 seal="#24427a", intro="A rare card: indigo lacquer laid with silver hemp leaves (asanoha), a silver line; mother-of-pearl glides over it as it turns."),
    "epic": dict(lacquer=("#d23a20", "#7e1209"), pattern='url("sakura.svg") 0 0 / 100% 100% no-repeat, ', line=GOLD, accent="#c42c18",
                 seal="#c42c18", intro="An epic card: vermillion lacquer, cherry blossoms in its corners, a gold line; as it turns, petals drift across it and mother-of-pearl glides over it."),
    "legendary": dict(lacquer=("#231614", "#0b0706"), pattern='url("kintsugi.svg") 0 0 / 100% 100% no-repeat, url("flecks.svg") 0 0 / 100% 100% no-repeat, ',
                      line=GOLD, accent="#8a560f", seal="#c42c18",
                      intro="A legendary card: black lacquer broken and mended in gold (kintsugi), cut gold leaf, a double gold line; as it lands, gold sweeps over it and a glint crosses its art (its reveal brings the ink dragon coiling round it)."),
}


def face(rarity: str, p: dict) -> str:
    h = f'[data-card-face="sumi-{rarity}"]'
    top, bottom = p["lacquer"]
    intro = textwrap.wrap(p["intro"] + " (Its hook: the card once turned, data-card-face.) The face turns in 3D: never its transform; a turned media card is never redrawn — what moves, moves once, as it is revealed.", 108)
    double = f", 0 0 0 1.2cqi {INK}, 0 0 0 1.5cqi {p['line']}" if rarity == "legendary" else ""
    css = f"""/* {chr(10).join(('   ' if i else '') + line for i, line in enumerate(intro))} */
@font-face {{
  font-family: "Sumi Yuji";
  src: url("YujiSyuku.woff2") format("woff2");
  font-display: swap;
}}
/* the card: lacquer, a soft gloss on its upper edge, inked round */
{h} .mcard__card {{
  padding: 3.2cqi;
  border-radius: 2.6cqi;
  background:
    radial-gradient(ellipse 80% 30% at 30% 0%, rgba(255, 255, 255, 0.16), transparent 70%),
    {p['pattern']}linear-gradient(165deg, {top}, {bottom});
  box-shadow: inset 0 0 0 0.35cqi rgba(255, 255, 255, 0.08), 0 0 0 0.45cqi {INK}, 0 1.6cqi 3cqi rgba(0, 0, 0, 0.45);
}}
/* the body: washi paper, a fine line of the rarity's metal round it */
{h} .mcard__body {{
  border-radius: 1.4cqi;
  background: url("washi.svg") 0 0 / 100% auto, {WASHI};
  box-shadow: 0 0 0 0.45cqi {p['line']}, 0 0 0 0.8cqi {INK}{double};
  color: {INK};
}}
/* the title, brushed */
{h} .mcard[data-rarity] .mcard__name {{
  font-family: "Sumi Yuji", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.02em;
  line-height: 1.2;
  color: {INK};
}}
/* the genre: a little seal */
{h} .mcard__genre {{
  border-radius: 0.6cqi;
  background: {p['seal']};
  color: {WASHI};
  box-shadow: 0 0 0 0.3cqi {INK};
  font-family: "Sumi Yuji", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.04em;
}}
{h} .mcard__emblem {{
  background: {INK};
  color: {GOLD};
}}
/* the art, mounted like a scroll painting: a fine gold line, inked */
{h} .mcard__art {{
  border-radius: 0.6cqi;
  box-shadow: 0 0 0 0.4cqi {GOLD}, 0 0 0 0.8cqi {INK};
}}
{h} .mcard__picture,
{h} .mcard__scene {{
  filter: sepia(0.12) saturate(1.05) contrast(1.04);
}}
{h} .mcard__badge {{
  box-shadow: 0 0 0 0.4cqi {GOLD}, 0 0 0 0.75cqi {INK};
}}
{h} .mcard__strip {{
  border-radius: 0.4cqi;
  background: {INK};
  color: {WASHI};
}}
{h} .mcard__poster {{
  box-shadow: 0 0 0 0.35cqi {GOLD}, 0 0 0 0.65cqi {INK};
}}
{h} .mcard__cost {{
  background: {p['accent']};
  color: {WASHI};
  box-shadow: 0 0 0 0.3cqi {INK};
}}
{h} .mcard__figures strong {{
  font-family: "Sumi Yuji", var(--mcard-title);
  font-weight: 400;
}}
/* the rarity: stamped in vermillion */
{h} .mcard__rarity {{
  border-radius: 0.5cqi;
  background: {p['seal']};
  color: {WASHI};
  box-shadow: 0 0 0 0.3cqi {INK};
  font-family: "Sumi Yuji", var(--mcard-title);
  font-weight: 400;
  letter-spacing: 0.05em;
  rotate: -4deg;
}}
"""
    if rarity in ("rare", "epic"):
        strength = {"rare": "0.42", "epic": "0.55"}[rarity]
        css += f"""/* mother-of-pearl (raden) gliding over the card once as it catches the light */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 30%, rgba(160, 215, 255, 0.85) 42%, rgba(255, 190, 228, 0.85) 50%, rgba(190, 255, 214, 0.8) 58%, transparent 70%) 0 0 / 300% 300%;
  mix-blend-mode: soft-light;
  opacity: {strength};
  animation: sumi-raden-{rarity} 1.8s ease-out both;
}}
@keyframes sumi-raden-{rarity} {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 70% 70%; }}
}}
"""
    if rarity == "epic":
        css += f"""/* as it turns: cherry petals drifting across it, once */
{h}::after {{
  content: "";
  position: absolute;
  inset: -20%;
  z-index: 3;
  pointer-events: none;
  background: url("petals.svg") center / 100% 100% no-repeat;
  animation: sumi-petals-epic 2.6s ease-out both;
}}
@keyframes sumi-petals-epic {{
  0% {{ translate: -18% -22%; rotate: -6deg; opacity: 0; }}
  12% {{ opacity: 1; }}
  70% {{ opacity: 1; }}
  100% {{ translate: 16% 24%; rotate: 8deg; opacity: 0; }}
}}
"""
    if rarity == "legendary":
        css += f"""/* gold foil sweeping over it once as it lands */
{h} .booster-card__face::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 224, 154, 0.9) 48%, rgba(255, 255, 255, 0.95) 50%, rgba(217, 164, 58, 0.9) 52%, transparent 62%) 0 0 / 300% 300%;
  mix-blend-mode: overlay;
  opacity: 0.55;
  animation: sumi-foil-legendary 1.6s ease-in-out 0.9s both;
}}
@keyframes sumi-foil-legendary {{
  0% {{ background-position: 0% 0%; }}
  100% {{ background-position: 80% 80%; }}
}}
/* a gold glint crossing the art once — on its own small part, not the whole card */
{h} .mcard__art::after {{
  content: "";
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 44%, rgba(255, 236, 190, 0.95) 46%, transparent 49%) -150% 0 / 250% 100% no-repeat;
  animation: sumi-glint-legendary 1.4s ease-in-out 1.6s both;
}}
@keyframes sumi-glint-legendary {{
  0% {{ background-position: -150% 0; }}
  100% {{ background-position: 250% 0; }}
}}
"""
    # what moves once: stilled when motion is reduced — the passing effects not shown at all
    passing = {"epic": ["::after"], "legendary": [".mcard__art::after"]}.get(rarity, [])
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
