"""Visual packs (issue 1, POC): every customizable look — animated backgrounds, avatar frames, titles, name
fonts, badges, level-ups, celebrations, notifications, palettes, packs and boosters — imported from outside,
its animations in its own files (CSS, GLSL, JS) rather than in Portalab's code.

A pack is a folder or a ``.zip`` with ``pack.json`` at its root and one folder per element
(``elements/<name>/element.json``). Packs come from the inbox folder (``DATA_DIR/visuals/inbox``), an upload
in the administration or a GitHub repository; each version is stored apart, analysed (a report: blocking,
warning, info), shown in a sandbox, then validated by an administrator — who may change the price, rarity,
level and copies each element proposes — and published in the shop. A pack can be switched off at once (its
files are no longer served, its products leave the shop, their owners keep them) and rolled back.
"""
