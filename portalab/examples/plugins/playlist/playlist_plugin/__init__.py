"""Playlists — a confined plugin (spec 030) that adds a « + Playlist » button to media pages. Each member sees
and changes only their own playlists; a title's name is read through Portalab with the member's rights."""

from portalab.sdk.confined.recording import Denied

TITLE = "GET /api/v1/media/{object_id}"


def _clean(text, limit):
    return " ".join(str(text or "").split())[:limit]


def _id(value):
    text = str(value or "")
    return int(text) if text.isdigit() else 0


def register(ctx):
    async def own(principal, playlist):
        rows = await ctx.db.execute(
            "SELECT id, name, description FROM playlists WHERE id = :p AND owner = :o",
            {"p": playlist, "o": str(principal.user_id)},
        )
        return rows[0] if rows else None

    async def title_of(principal, item):
        """(title, poster, kind) of a title this member may see, read through Portalab; None otherwise."""
        try:
            answer = await ctx.portal.call(TITLE, {"object_id": item})
        except Denied:
            return None
        if answer.get("status") != 200:
            return None
        body = answer["body"]
        title = _clean(body.get("title"), 160)
        image = str(body.get("image_id") or "")[:40] or None
        return (title, image, _clean(body.get("kind") or "movie", 20)) if title else None

    async def lists(principal, query, body):
        item = _clean(query.get("item"), 80)
        rows = await ctx.db.execute(
            "SELECT p.id, p.name, (e.item IS NOT NULL) AS checked FROM playlists p "
            "LEFT JOIN entries e ON e.playlist_id = p.id AND e.item = :i WHERE p.owner = :o ORDER BY p.name",
            {"i": item, "o": str(principal.user_id)},
        )
        if not rows:
            return {"state": "no-data", "items": []}
        return {"state": "available", "items": [{"id": r["id"], "label": r["name"], "checked": r["checked"]} for r in rows]}

    async def toggle(principal, query, body):
        body = body or {}
        playlist, item = _id(body.get("id")), _clean(body.get("item"), 80)
        if not item or await own(principal, playlist) is None:
            return {"state": "error", "message": "Not one of your playlists."}
        if body.get("checked"):
            found = await title_of(principal, item)
            if found is None:
                return {"state": "error", "message": "This title is not available."}
            await ctx.db.execute(
                "INSERT INTO entries (playlist_id, item, title, image_id, kind) VALUES (:p, :i, :t, :m, :k) "
                "ON CONFLICT DO NOTHING",
                {"p": playlist, "i": item, "t": found[0], "m": found[1], "k": found[2]},
            )
        else:
            await ctx.db.execute("DELETE FROM entries WHERE playlist_id = :p AND item = :i", {"p": playlist, "i": item})
        return {"state": "available"}

    async def create(principal, query, body):
        body = body or {}
        name = _clean(body.get("name"), 80)
        if not name:
            return {"state": "error", "message": "A name is needed."}
        rows = await ctx.db.execute(
            "INSERT INTO playlists (owner, name) VALUES (:o, :n) RETURNING id", {"o": str(principal.user_id), "n": name}
        )
        item = _clean(body.get("item"), 80)
        if item:  # created from a media page: the title goes in at once
            found = await title_of(principal, item)
            if found is not None:
                await ctx.db.execute(
                    "INSERT INTO entries (playlist_id, item, title, image_id, kind) VALUES (:p, :i, :t, :m, :k)",
                    {"p": rows[0]["id"], "i": item, "t": found[0], "m": found[1], "k": found[2]},
                )
        return {"state": "available", "message": "Created."}

    async def mine(principal, query, body):
        rows = await ctx.db.execute(
            "SELECT p.id, p.name, p.description, count(e.item) AS n, "
            "(array_agg(e.image_id ORDER BY e.added_at) FILTER (WHERE e.image_id IS NOT NULL))[1:4] AS covers "
            "FROM playlists p LEFT JOIN entries e ON e.playlist_id = p.id "
            "WHERE p.owner = :o GROUP BY p.id ORDER BY p.name",
            {"o": str(principal.user_id)},
        )
        if not rows:
            return {"state": "no-data", "items": []}
        return {
            "state": "available",
            "items": [
                {
                    "id": r["id"],
                    "title": r["name"],
                    "subtitle": str(r["n"]),
                    "count": int(r["n"]),
                    "description": r["description"],
                    "covers": list(r["covers"] or []),
                    "link": f"/plugins/playlist/list?playlist={r['id']}",
                }
                for r in rows
            ],
        }

    async def items(principal, query, body):
        found = await own(principal, _id(query.get("playlist")))
        if found is None:
            return {"state": "no-data", "items": []}
        rows = await ctx.db.execute(
            "SELECT item, title, image_id, kind FROM entries WHERE playlist_id = :p ORDER BY added_at",
            {"p": found["id"]},
        )
        return {
            "state": "available" if rows else "no-data",
            "title": found["name"],
            "items": [
                {"item": r["item"], "title": r["title"], "image_id": r["image_id"], "kind": r["kind"]} for r in rows
            ],
        }

    async def values(principal, query, body):
        found = await own(principal, _id(query.get("playlist")))
        if found is None:
            return {"state": "no-data", "values": {}}
        return {"state": "available", "values": {"name": found["name"], "description": found["description"]}}

    async def update(principal, query, body):
        body = body or {}
        found = await own(principal, _id(body.get("playlist")))
        name = _clean(body.get("name"), 80)
        if found is None or not name:
            return {"state": "error", "message": "Not one of your playlists."}
        await ctx.db.execute(
            "UPDATE playlists SET name = :n, description = :d WHERE id = :p",
            {"n": name, "d": str(body.get("description") or "")[:400], "p": found["id"]},
        )
        return {"state": "available", "message": "Saved."}

    async def describe_delete(principal, query, body):
        found = await own(principal, _id((body or {}).get("playlist")))
        return {"title": "Delete this playlist?", "lines": [found["name"] if found else "?"]}

    async def delete(principal, query, body):
        found = await own(principal, _id((body or {}).get("playlist")))
        if found is None:
            return {"state": "error", "message": "Not one of your playlists."}
        await ctx.db.execute("DELETE FROM playlists WHERE id = :p", {"p": found["id"]})
        return {"state": "available", "message": "Deleted.", "link": "/plugins/playlist/mine"}

    async def export(user_id):
        rows = await ctx.db.execute(
            "SELECT p.name, e.title FROM playlists p LEFT JOIN entries e ON e.playlist_id = p.id WHERE p.owner = :o",
            {"o": user_id},
        )
        return {"playlists": [{"name": r["name"], "title": r["title"]} for r in rows]}

    async def erase(user_id):
        await ctx.db.execute("DELETE FROM playlists WHERE owner = :o", {"o": user_id})

    use = "plugin:playlist.use"
    ctx.route("GET", "lists", lists, permission=use, exposure="read")
    ctx.route("POST", "toggle", toggle, permission=use, exposure="action")
    ctx.route("POST", "playlists", create, permission=use, exposure="action")
    ctx.route("GET", "mine", mine, permission=use, exposure="read")
    ctx.route("GET", "items", items, permission=use, exposure="read")
    ctx.route("GET", "values", values, permission=use, exposure="read")
    ctx.route("POST", "update", update, permission=use, exposure="action")
    ctx.route("POST", "delete", delete, permission=use, exposure="committing", describe=describe_delete)
    ctx.privacy(export=export, erase=erase)
