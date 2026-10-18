"""Forum — a confined plugin (spec 030). It runs in a process of its own: its storage, the member names it
reads and the notifications it sends all go through Portalab, within what the Admin granted."""

from portalab.sdk import ProviderResult, SearchItem
from portalab.sdk.confined.recording import Denied

MEMBER = "GET /api/v1/community/members/{member_id}"


def _clean(text, limit):
    return " ".join(str(text or "").split())[:limit]


def register(ctx):
    async def name_of(principal):
        try:
            answer = await ctx.portal.call(MEMBER, {"member_id": str(principal.user_id)})
            if answer.get("status") == 200:
                return _clean(answer["body"].get("display_name"), 60) or "?"
        except Denied:
            pass
        return "?"

    async def topics(principal, query, body):
        rows = await ctx.db.execute(
            "SELECT t.id, t.title, t.author_name, t.last_at, count(p.id) AS posts FROM topics t "
            "LEFT JOIN posts p ON p.topic_id = t.id AND NOT p.removed GROUP BY t.id ORDER BY t.last_at DESC LIMIT 100",
            {},
        )
        if not rows:
            return {"state": "no-data", "items": []}
        return {
            "state": "available",
            "items": [
                {
                    "id": r["id"],
                    "label": r["title"],
                    "link": f"/plugins/forum/topic?topic={r['id']}",
                    "meta": f"{r['author_name']} · {max(0, int(r['posts']) - 1)}",
                    "author": r["author_name"],
                    "replies": max(0, int(r["posts"]) - 1),
                    "last_at": r["last_at"].isoformat(),
                }
                for r in rows
            ],
        }

    async def describe_topic(principal, query, body):
        body = body or {}
        return {"title": "Publish this topic?", "lines": [_clean(body.get("title"), 120), _clean(body.get("body"), 200)]}

    async def new_topic(principal, query, body):
        title, text = _clean((body or {}).get("title"), 120), str((body or {}).get("body") or "").strip()[:4000]
        if not title or not text:
            return {"state": "error", "message": "A title and a message are needed."}
        name = await name_of(principal)
        author = str(principal.user_id)
        rows = await ctx.db.execute(
            "INSERT INTO topics (title, author, author_name) VALUES (:t, :a, :n) RETURNING id",
            {"t": title, "a": author, "n": name},
        )
        topic = rows[0]["id"]
        await ctx.db.execute(
            "INSERT INTO posts (topic_id, author, author_name, body) VALUES (:t, :a, :n, :b)",
            {"t": topic, "a": author, "n": name, "b": text},
        )
        await ctx.emit("topic_posted", {"topic": topic}, subject_id=str(topic))
        return {"state": "available", "message": "Published.", "link": f"/plugins/forum/topic?topic={topic}"}

    async def thread(principal, query, body):
        topic = int(str(query.get("topic") or "0")) if str(query.get("topic") or "0").isdigit() else 0
        head = await ctx.db.execute("SELECT title FROM topics WHERE id = :t", {"t": topic})
        if not head:
            return {"state": "no-data", "items": []}
        rows = await ctx.db.execute(
            "SELECT id, author_name, body, created_at, removed FROM posts WHERE topic_id = :t ORDER BY id",
            {"t": topic},
        )
        return {
            "state": "available",
            "title": head[0]["title"],
            "items": [
                {
                    "id": r["id"],
                    "author": r["author_name"],
                    "at": r["created_at"].isoformat(),
                    "body": "" if r["removed"] else r["body"],
                    "removed": bool(r["removed"]),
                }
                for r in rows
            ],
        }

    async def describe_reply(principal, query, body):
        return {"title": "Publish this reply?", "lines": [_clean((body or {}).get("body"), 200)]}

    async def reply(principal, query, body):
        body = body or {}
        topic = int(str(body.get("topic") or query.get("topic") or "0")) if str(body.get("topic") or query.get("topic") or "0").isdigit() else 0
        text = str(body.get("body") or "").strip()[:4000]
        if not text:
            return {"state": "error", "message": "A message is needed."}
        head = await ctx.db.execute("SELECT title FROM topics WHERE id = :t", {"t": topic})
        if not head:
            return {"state": "error", "message": "This topic does not exist."}
        name = await name_of(principal)
        author = str(principal.user_id)
        await ctx.db.execute(
            "INSERT INTO posts (topic_id, author, author_name, body) VALUES (:t, :a, :n, :b)",
            {"t": topic, "a": author, "n": name, "b": text},
        )
        await ctx.db.execute("UPDATE topics SET last_at = now() WHERE id = :t", {"t": topic})
        others = await ctx.db.execute(
            "SELECT DISTINCT author FROM posts WHERE topic_id = :t AND author <> :a", {"t": topic, "a": author}
        )
        if others:
            await ctx.notify(
                [r["author"] for r in others], "replies", f"{name} replied in “{head[0]['title']}”",
                link=f"/plugins/forum/topic?topic={topic}",
            )
        return {"state": "available", "message": "Replied."}

    async def remove(principal, query, body):
        post = int((body or {}).get("post") or 0)
        await ctx.db.execute("UPDATE posts SET removed = true WHERE id = :p", {"p": post})
        return {"state": "available", "message": "Removed."}

    class Search:
        kind = "plugin:forum"
        label_key = "plugin.forum:nav.home"
        required_permission = "plugin:forum.read"

        def facets(self):
            return []

        async def search(self, query, principal, ctx_, *, limit, cursor):
            text = _clean(getattr(query, "text", "") or "", 80)
            if len(text) < 2:
                return ProviderResult(items=[], next_cursor=None)
            rows = await ctx.db.execute(
                "SELECT id, title FROM topics WHERE title ILIKE :q ORDER BY last_at DESC LIMIT :n",
                {"q": f"%{text}%", "n": int(limit)},
            )
            return ProviderResult(
                items=[
                    SearchItem(kind="plugin:forum", id=str(r["id"]), title=r["title"], url_ref=f"/plugins/forum/topic?topic={r['id']}")
                    for r in rows
                ],
                next_cursor=None,
            )

        async def hydrate(self, ids, principal):
            return []

    async def export(user_id):
        rows = await ctx.db.execute(
            "SELECT topic_id, body, created_at FROM posts WHERE author = :a ORDER BY id", {"a": user_id}
        )
        return {"posts": [{"topic": r["topic_id"], "body": r["body"], "at": r["created_at"].isoformat()} for r in rows]}

    async def erase(user_id):
        await ctx.db.execute(
            "UPDATE posts SET body = '', removed = true, author_name = '—' WHERE author = :a", {"a": user_id}
        )
        await ctx.db.execute("UPDATE topics SET author_name = '—' WHERE author = :a", {"a": user_id})

    ctx.route("GET", "topics", topics, permission="plugin:forum.read", exposure="read")
    ctx.route("POST", "topics", new_topic, permission="plugin:forum.post", exposure="committing", describe=describe_topic)
    ctx.route("GET", "thread", thread, permission="plugin:forum.read", exposure="read")
    ctx.route("POST", "replies", reply, permission="plugin:forum.post", exposure="committing", describe=describe_reply)
    ctx.route("POST", "remove", remove, permission="plugin:forum.moderate", exposure="action")
    ctx.search_provider(Search())
    ctx.privacy(export=export, erase=erase)
