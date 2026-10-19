# Crafting looks that work — a guide per element

The [authors' guide](visual-packs.md) says what a pack **may** do (its format, its hooks, its contracts). This
one says how to make each element **good**: where it is seen and how big, what makes it convincing, the
techniques that work, the traps the analysis does not catch, and which example to start from. Every rule here
comes from a look that was redone because it fell short — read the [pitfalls](#pitfalls-met-so-far) first.

Start from an example of [`examples/visual-packs/`](../examples/visual-packs/README.md) rather than a blank
page: `rouages/`, `ruee-vers-l-or/` and `olympe/` hold one element of every kind a member wears;
`booster-cinema/` is the most worked booster scene.

## Contents

1. [Principles](#principles)
2. [The toolbox](#the-toolbox)
3. [The interface and the palette](#the-interface-and-the-palette)
4. [Ambiences and profile backgrounds](#ambiences-and-profile-backgrounds)
5. [Profile looks: frames, banners, names, level badges, titles, badges](#profile-looks)
6. [Moments: level-ups and celebrations](#moments-level-ups-and-celebrations)
7. [Notifications](#notifications)
8. [Theme packs and boosters](#theme-packs-and-boosters)
9. [Booster scenes, part by part](#booster-scenes-part-by-part)
10. [Pitfalls met so far](#pitfalls-met-so-far)
11. [Before importing: the checklist](#before-importing-the-checklist)

## Principles

1. **One universe, one idea.** Every element of a pack tells the same story (an engine room, a western train, a
   movie palace). Find its materials (brass, leather, marble, velvet…), its light (a furnace, a sunset, a
   projector) and its sounds; every element then picks from them. Before making a universe, check none of the
   existing packs already tells it.
2. **Nothing perfectly geometric.** Straight edges and perfect circles read as a placeholder. Wear every
   silhouette with noise (`+ 0.01 * fbm(…)` on a profile), lean what stands, sag what hangs, vary what repeats
   (each brick its own tone, each building its own height).
3. **Depth.** A scene is layers: far ones small, pale and slow (haze), near ones large, dark and fast; a
   perspective where it helps (a street, a hall, a floor running to a vanishing point). Parallax — the near layer
   moving faster than the far one — is what makes it a place.
4. **Light.** Decide where it comes from, then let it touch things: a rim on the edge facing it, a glow on what
   is near, shafts through dust or smoke, reflections on a polished floor. Light makes a flat drawing volume.
5. **Everything breathes, a little.** A still image looks broken. Give each element one slow life (a sway, a
   flicker, a drift, a camera breathing by a few thousandths) and, now and then, one event (lightning, a train,
   a whistle, an eagle). Never overplay: the member came for the cards, the profile, the reward.
6. **Phone first.** On a phone a stage is a narrow slice: about ±0.24 half heights wide around the centre (a
   desktop sees ±0.86). Put what matters in the middle; let the sides be extra for wide screens. Check both.
7. **Portalab's words stay readable.** Texts, prices, rarities and buttons are drawn above your looks: keep the
   areas under them calm (darken or fade there), mind contrast on light themes.
8. **Reduced motion.** Every animation stops under `prefers-reduced-motion: reduce` (CSS) — Portalab stills the
   GPU looks itself. What remains must still look finished.
9. **Rarity is a staircase.** Common, rare, epic, legendary: each step adds something you can see (a shape, a
   holographic sheen, a pulse, the art leaning, a longer reveal). Never let a common outshine an epic.

## The toolbox

### GLSL coordinates and helpers

```glsl
// a stage: c in half heights, centred, y up — the same scale on every screen
vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
o = over(o, colour, alpha);           // paint a layer over what is below (premultiplied)
hash(vec2) noise(vec2) fbm(vec2)      // random, smooth noise, layered noise (4 octaves)
```

- **Wear a silhouette**: `float top = 0.12 + 0.02 * fbm(vec2(c.x * 20.0, 1.0));`
- **Domain warping** (clouds, smoke, steam that curl): `fbm(q + fbm(q * 1.4 + t * 0.03) * 1.2)`.
- **Parallax**: scroll each layer by its own speed, `s = c.x + t * speed` — far `0.005`, near `0.2`.
- **One-point perspective** (a floor, a street, a hall): a point of the floor at screen height `y < 0` is at
  depth `z = h / -y`; its world position `(c.x * z, z)`; walls at `x = ±W` are at depth `W / |c.x|`. Draw tiles,
  ruts or planks in world coordinates: they converge by themselves. Fade with depth into a haze colour.
- **Film or old screens**: change per frame, `frame = floor(t * 24.0)`, then flicker, gate weave and
  scratches from `hash(vec2(frame, …))`.
- **The camera breathes**: add `vec2(0.004 * sin(t * 0.3), 0.003 * sin(t * 0.23))` to `c`.
- **Grain and vignette** at the end: `o.rgb *= mix(0.4, 1.0, smoothstep(1.1, 0.3, length(c)))`, then
  `o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.03`.
- **Fade a stage's edges** (level-ups, effects, booster parts): end the body with an elliptical fade so the box
  never shows — the examples' `EDGES` (`EDGES_WIDE` for reveals).

### CSS

- Layer `background` images (gradients sized and placed) rather than adding elements: each layer is a shape.
- `::before` / `::after` carry the moving parts (a rider crossing a banner, a frame's ring turning).
- `clip-path: polygon(…)` shapes a card or a pack (torn paper, notches, an arch, a sunburst).
- Animate what is cheap: `transform`/`translate`/`rotate`, `opacity`, `background-position`, `filter`.

### Budget

A stage is drawn for every pixel, every frame, on phones too. Keep loops to a few dozen iterations, `fbm` calls
to about fifteen per pixel; prefer one well-placed light to many. Measure with the Test step's frames per
second, on the phone profile.

## The interface and the palette

**Seen**: everywhere — the header, the navigation, every card, the dashboard, on desktop and phone.

- Pick the scheme first (`dark` or `light`); a light one needs its own state colours (the examples'
  `LIGHT_STATES`) and stronger contrast for muted text.
- Colours: `surface`, `surfaceRaised`, `text`, `textMuted`, `border`, `accent` + `accentContrast` (text on the
  accent: check the contrast), `accentAlt`, `focus` (visible on both surfaces), one colour per rarity.
- Typography: a body font for reading, a display font for headings (`headingFamily`, `headingCase`,
  `headingEffect`) — that is where the universe speaks.
- Layout values are a closed list (`cards`: elevated, flat, outlined, glass, comic, neon, paper, pixel,
  terminal, ornate, hologram, console, window; `corners`: square, soft, round). The analysis tells you the
  allowed values when one is wrong.
- **Vocabulary** renames Portalab's places in the universe's words (« Le saloon », « Le marché d'Athènes »,
  coins « Drachmes ») — short, in both languages, never `{ } < >`.
- Its stylesheet adds the universe's touch (a Greek key under the header, a wood grain on cards): subtle, and
  only under `[data-theme="<key>"]`.
- A **palette** is the cheap version of the interface: its accent and second colour, for dark and light.

Start from: `olympe/` (light), `rouages/` (dark).

## Ambiences and profile backgrounds

**Ambience** — behind the whole portal, all the time, under every card. **Profile background** — behind the
profile header, seen by every visitor.

- An ambience is **mostly transparent**: a few things living at the edges and the top (dust in a sunbeam,
  leaves falling, vultures circling), never a busy picture under the text. Keep alpha low in the middle.
- A profile background may be a full picture (a campfire under the stars, columns above the clouds): it frames
  the avatar and the name — calm in the middle, the event on the side.
- Both are full shaders (`void main()`, `gl_FragColor`), drawn in `u_res` with `u_time`.

Start from: `olympe/elements/ambient-olivier`, `ruee-vers-l-or/elements/background-feu`.

## Profile looks

These are small (an avatar is 2.5 to 6 rem), seen in lists, on the profile and in the shop tile.

- **Avatar frame (CSS)**: a ring round the avatar (`::before`, `inset: -4%`, a `mask` keeping only the band) —
  readable at 2.5 rem: few, big shapes; a slow turn at most.
- **Avatar frame (GLSL)**: a shape (`shape`: 0 rounded box, 1 hexagon, 2 diamond, 3 shield, 4 star, 5
  triangle); draw on the band `abs(d - 0.05)`, light it from one side, one glint running along.
- **Banner**: a wide scene behind the profile header. **Never set `position` or `overflow`** on the banner
  itself: Portalab places it (in previews it is absolutely positioned; a `position: relative` of yours collapses
  it to nothing). Place layers with `background-position / background-size`; a moving detail in `::after`.
- **Name style, title**: the name must stay readable first — colour, a display font, a light shadow; no effect
  that hides letters.
- **Level badge**: holds a number; a shape (`clip-path`) and a material, a glint now and then.
- **Badge**: a token (a nugget, a coin, an owl): a radial gradient for volume and a glow.

Start from: `rouages/` (gears, a clock in GLSL), `ruee-vers-l-or/` (lasso, sheriff's star, mesas), `olympe/`.

## Moments: level-ups and celebrations

**Level-up** — over the whole screen, with the level's card in the middle. **Celebration** — when a reward is
earned, around the « +XP » bubble under the header (Portalab centres the GPU scene on the bubble).

- Write a **timeline** with `u_age`: an announcement, a build-up, the moment (`reveal` for a level-up: when the
  card shows), an afterglow, a fade. Keep celebrations to about 3 s, level-ups to about 7 s.
- Design **round the centre**: that is where the bubble or the card is.
- A level-up may restyle its card (`.levelup[data-look="<look>"] .levelup__card`, `.levelup__title`).
- End with the elliptical edge fade: a stage that stops at its box looks broken.

Start from: `ruee-vers-l-or/elements/levelup-duel`, `olympe/elements/effect-pluie-or`.

## Notifications

- **Style**: the toast's dress (`.ds-notifications[data-style] .ds-notification`) — readable text first; a
  material (marble, a wanted poster, a brass plate) and a shadow.
- **Animation**: how it comes in (`animation-name` and its keyframes), under a second, ending at rest
  (`transform: none`).

## Theme packs and boosters

- A **theme pack** (`bundle`) sells every product of the universe at once, cheaper than one by one.
- A **booster** names exactly what it may draw: `packs` (visual packs `visual:<id>`, the shop's packs) and/or
  `items` named one by one — never « everything ». A good booster holds at least about 40 looks, 8 epics and 4
  legendaries, of every kind; the admin preview (Shop › Boosters) shows the rarities it lacks.
- A universe does not need a booster of its own: a booster made of several universes (the Cinema booster, all
  the film universes) is often better. Its **scene** is what makes opening it a moment.

## Booster scenes, part by part

A scene is one place for the whole opening. Every part shares its universe; tension is built in (see the
examples' `tension.py`: the sealed pack breathing with a double heartbeat, the dark closing in while it opens —
lightly, unless the scene is made for dread).

| part | seen | what makes it good |
|---|---|---|
| **backdrop** | behind everything, full screen | a real place in depth (parallax, a perspective, light, things living); the centre calm enough for the pack and the cards; phone slice checked |
| **booster look** | the sealed pack, centre stage, and the shop tile | an object of the universe (a dynamite crate, an amphora, a clapperboard), shaped with `clip-path`, its flap `.booster-pack__flap` and pseudo-elements as parts (sticks, handles, a fuse); the pack's name stays readable — move the emblem if it covers it; a GLSL stage around it (a set light, sparks, a halo) |
| **opening** | when it is opened, ≤ 4 s | a gesture of the universe (the fuse burning down then the blast; the clap, the countdown, the film burning) — CSS moves the pack, GLSL draws the event; the cards come at its end |
| **card back** | every card face down, and as the booster's thumbnail in the shop | one design for all (it never tells the rarity), the universe's emblem in the middle; may be drawn by the GPU (light turning behind the emblem) |
| **faces** | each card turned | best drawn by the GPU (HD: a living panel — a film, swirling dyes, a curtain, a gala night — under the art) with a stylesheet for the frame and the words; the rarity staircase: common plain and material; rare cut corners + holographic sheen; epic a shape + pulse; legendary a radiant shape (sunburst) + leaning art + glitter. Each face styles **only its own look** |
| **reveals** | when a rare, epic or legendary card turns, ≤ 3 s | escalate too: a gesture (a lasso, searchlights), a burst (gunfire, a marquee lighting up), an apotheosis (the mother lode, the red carpet's flashes) — wide elliptical fade |

Everything is the pack's: its shaders and stylesheets; Portalab only draws what the pack brings, where the
contracts say. Start from: `booster-cinema/` (the whole scene, every part on the GPU), `ruee-vers-l-or/elements/scene-*`, `booster-horreur/` (dread).

## Pitfalls met so far

- **A banner that sets `position`** disappears in previews (its height falls to 0). Leave positioning to
  Portalab.
- **`exp()` of a large positive number** gives infinity; infinity × 0 is NaN, drawn black — a thin black line
  where a far-away depth explodes (the centre of a perspective). Clamp exponents: `exp(-max(x, 0.0))`.
- **Redeclaring `d`, `p`, `ax`, `t` or `o`** at the body's level is refused; use other names (`dk`, `q`).
- **A rectangle around a reveal**: the effect stops at its box. End stages with the elliptical fade.
- **Faces styling each other**: a face's stylesheet may only name its own `[data-card-face="<look>"]`
  (the shared keyframes go in each face that uses them).
- **Values outside the theme's lists** (`headingCase: "upper"`, `corners: "rounded"`, `cards: "solid"`) block
  the analysis: use the exact words it lists.
- **An emblem over the pack's name**, a name cut by a rounded pack: shrink the name (`font-size`,
  `white-space: nowrap`) or hide the emblem.
- **White under Portalab's white words** (clouds behind « Tap a card to turn it »): darken the lower part of a
  backdrop.
- **Speckles everywhere**: a noise layer not multiplied by its mask (`smoothstep(…, canopy)` alone) leaks over
  the whole stage — multiply by the shape (`* blob`).
- **Too still, too straight, too geometric** — the most common critique. Apply the [principles](#principles).

## Before importing: the checklist

1. `cd backend && uv run portalab visuals analyse <folder>` — nothing blocking, no warning.
2. Every shader compiles (the Test step compiles them; offline, a headless browser does).
3. Look at it on a **desktop and a phone** width, at a few moments of its timeline.
4. Turn reduced motion on: it still looks finished.
5. Texts in French and English, names and descriptions for every element; descriptions say what is seen.
6. A new version number for every change (a published version never changes); importing a pack never needs a
   rebuild of Portalab.
7. In the Test step: « Try it » on yourself, the frames per second on the phone profile, the scene's « Try the
   scene » from sealed to the last reveal.
