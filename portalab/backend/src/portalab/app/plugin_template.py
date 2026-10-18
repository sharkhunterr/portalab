# ruff: noqa: E501 — the templates below are written out verbatim (their lines are the generated files')
"""``portalab plugin new <key>`` (spec 030, US7): a confined plugin to start from — a manifest of version 2
(its capabilities, a labelled route, a page placed as a tab of one of Portalab's sections), its code (one
route reading its own storage), its own view drawn on the member's theme tokens, its messages in en and fr.
Validate it with ``portalab plugin validate <folder>``, install it like any package."""

import re
from pathlib import Path

KEY = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

MANIFEST = """schema_version = 2
key = "{key}"
name = "{name}"
description = "What {name} brings to the portal."
version = "0.1.0"
requires_portal = ">=0.1"
maturity = "experimental"
entry_point = "{key}_plugin:register"
migrations = "migrations"
permissions = [{{ name = "use", description = "Use {name}" }}]

[capabilities]
storage = {{ quota_mb = 10 }}
operations = true
pages = true

[[routes]]
path = "notes"
method = "GET"
permission = "plugin:{key}.use"
exposure = "read"

[[routes]]
path = "notes"
method = "POST"
permission = "plugin:{key}.use"
exposure = "action"

[ui]
# a tab of one of Portalab's sections (home, media, content, community, marketplace, support…)
nav = [{{ key = "main", label_key = "plugin.{key}:nav.main", route = "/plugins/{key}/main", permission = "plugin:{key}.use", section = "{section}", icon = "sparkles" }}]

[[ui.pages]]
key = "main"
title_key = "plugin.{key}:page.main"
permission = "plugin:{key}.use"
view = "main.js"  # its own look; the blocks below are what safe mode shows
blocks = [{{ kind = "list", title_key = "plugin.{key}:page.main", data = "notes" }}]

[i18n.en."plugin.{key}"]
"nav.main" = "{name}"
"page.main" = "{name}"
"view.add" = "Add"
"view.empty" = "Nothing yet."

[i18n.fr."plugin.{key}"]
"nav.main" = "{name}"
"page.main" = "{name}"
"view.add" = "Ajouter"
"view.empty" = "Rien pour l'instant."
"""

CODE = '''"""{name} — a confined plugin (spec 030). It runs in a process of its own: what it reaches (its storage,
portal data, outside hosts) goes through Portalab, within what the Admin granted. Import only ``portalab.sdk``."""


def register(ctx):
    async def notes(principal, query, body):
        rows = await ctx.db.execute(
            "SELECT text FROM notes WHERE member = :m ORDER BY id DESC LIMIT 50", {{"m": str(principal.user_id)}}
        )
        return {{"state": "available" if rows else "no-data", "items": [{{"label": r["text"]}} for r in rows]}}

    async def add(principal, query, body):
        text = str((body or {{}}).get("text") or "").strip()[:200]
        if text:
            await ctx.db.execute(
                "INSERT INTO notes (member, text) VALUES (:m, :t)", {{"m": str(principal.user_id), "t": text}}
            )
        return {{"state": "available"}}

    ctx.route("GET", "notes", notes, permission="plugin:{key}.use", exposure="read")
    ctx.route("POST", "notes", add, permission="plugin:{key}.use", exposure="action")
'''

MIGRATION = """CREATE TABLE notes (
  id bigserial PRIMARY KEY,
  member uuid NOT NULL,
  text text NOT NULL
)
"""

VIEW = """// {name} — the plugin's own view (spec 030): it runs in Portalab's sandbox (no network), talks to Portalab
// through `api` only, and draws with the member's tokens (var(--color-…), the pl- kit) to follow their theme.

export default function mount(root, api) {{
  const t = api.t;
  const list = document.createElement("ul");
  list.className = "pl-stack";
  const input = Object.assign(document.createElement("input"), {{ className: "pl-input", placeholder: t("view.add") }});
  const button = Object.assign(document.createElement("button"), {{ className: "pl-button", textContent: t("view.add") }});
  const form = document.createElement("form");
  form.className = "pl-row";
  form.append(input, button);
  form.addEventListener("submit", async (event) => {{
    event.preventDefault();
    await api.post("notes", {{ text: input.value }});
    input.value = "";
    draw();
  }});
  const card = document.createElement("div");
  card.className = "pl-card pl-stack";
  card.append(form, list);
  root.replaceChildren(card);

  async function draw() {{
    const data = await api.get("notes");
    const items = data.items || [];
    list.replaceChildren(
      ...(items.length ? items : [{{ label: t("view.empty") }}]).map((item) =>
        Object.assign(document.createElement("li"), {{ textContent: item.label }}),
      ),
    );
  }}
  draw();
}}
"""


def new_plugin(key: str, target: Path, *, name: str | None = None, section: str = "content") -> Path:
    if not KEY.match(key):
        raise ValueError("a key is lowercase letters, digits and _ (2 to 40), starting with a letter")
    folder = target / key
    if folder.exists():
        raise FileExistsError(f"{folder} exists already")
    title = name or key.replace("_", " ").title()
    values = {"key": key, "name": title, "section": section}
    (folder / f"{key}_plugin").mkdir(parents=True)
    (folder / "migrations").mkdir()
    (folder / "views").mkdir()
    (folder / "plugin.toml").write_text(MANIFEST.format(**values), encoding="utf-8")
    (folder / f"{key}_plugin" / "__init__.py").write_text(CODE.format(**values), encoding="utf-8")
    (folder / "migrations" / "0001_notes.sql").write_text(MIGRATION, encoding="utf-8")
    (folder / "views" / "main.js").write_text(VIEW.format(**values), encoding="utf-8")
    return folder
