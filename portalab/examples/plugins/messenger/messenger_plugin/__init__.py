"""Messenger — a confined plugin (spec 030): direct messages between members. Live updates go through
Portalab's channels to the two members of a conversation only; names are read with the member's rights."""

from portalab.sdk import ActivationResult, ProductType
from portalab.sdk.confined.recording import Denied

MEMBERS = "GET /api/v1/community/members"
MEMBER = "GET /api/v1/community/members/{member_id}"


def _clean(text, limit):
    return " ".join(str(text or "").split())[:limit]


def _id(value):
    text = str(value or "")
    return int(text) if text.isdigit() else 0


def register(ctx):
    async def name_of(member_id):
        try:
            answer = await ctx.portal.call(MEMBER, {"member_id": str(member_id)})
            if answer.get("status") == 200:
                return _clean(answer["body"].get("display_name"), 60) or "?"
        except Denied:
            pass
        return "?"

    async def find(name):
        answer = await ctx.portal.call(MEMBERS, {"q": _clean(name, 64), "limit": 5})
        if answer.get("status") != 200:
            return None
        items = answer["body"].get("items") or []
        exact = [m for m in items if _clean(m.get("display_name"), 60).lower() == _clean(name, 60).lower()]
        chosen = exact or items
        return chosen[0] if len(chosen) == 1 else None

    async def conversation_of(me, conversation):
        rows = await ctx.db.execute(
            "SELECT id, a, b, a_name, b_name FROM conversations WHERE id = :c AND (a = :m OR b = :m)",
            {"c": conversation, "m": me},
        )
        return rows[0] if rows else None

    async def unread(principal, query, body):
        me = str(principal.user_id)
        rows = await ctx.db.execute(
            "SELECT count(*) AS n FROM messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE (c.a = :m OR c.b = :m) AND m.author <> :m AND NOT m.read",
            {"m": me},
        )
        return {"state": "available", "count": int(rows[0]["n"])}

    async def conversations(principal, query, body):
        me = str(principal.user_id)
        rows = await ctx.db.execute(
            "SELECT c.id, CASE WHEN c.a = :m THEN c.b_name ELSE c.a_name END AS other, "
            "(SELECT count(*) FROM messages x WHERE x.conversation_id = c.id AND x.author <> :m AND NOT x.read) AS unread "
            "FROM conversations c WHERE c.a = :m OR c.b = :m ORDER BY c.last_at DESC LIMIT 50",
            {"m": me},
        )
        if not rows:
            return {"state": "no-data", "items": []}
        return {
            "state": "available",
            "items": [
                {
                    "id": r["id"],
                    "label": r["other"],
                    "link": f"/plugins/messenger/chat?conversation={r['id']}",
                    "meta": str(r["unread"]) if r["unread"] else "",
                    "unread": int(r["unread"]),
                }
                for r in rows
            ],
        }

    async def messages(principal, query, body):
        me = str(principal.user_id)
        found = await conversation_of(me, _id(query.get("conversation")))
        if found is None:
            return {"state": "no-data", "items": []}
        await ctx.db.execute(
            "UPDATE messages SET read = true WHERE conversation_id = :c AND author <> :m AND NOT read",
            {"c": found["id"], "m": me},
        )
        rows = await ctx.db.execute(
            "SELECT id, author, body, created_at FROM messages WHERE conversation_id = :c ORDER BY id DESC LIMIT 200",
            {"c": found["id"]},
        )
        names = {str(found["a"]): found["a_name"], str(found["b"]): found["b_name"]}
        other = found["b_name"] if str(found["a"]) == me else found["a_name"]
        return {
            "state": "available",
            "title": other,
            "items": [
                {
                    "id": r["id"],
                    "author": names.get(str(r["author"]), "?"),
                    "at": r["created_at"].isoformat(),
                    "body": r["body"],
                    "mine": str(r["author"]) == me,
                }
                for r in reversed(rows)
            ],
        }

    async def send(principal, query, body):
        body = body or {}
        me = str(principal.user_id)
        text = str(body.get("body") or "").strip()[:2000]
        if not text:
            return {"state": "error", "message": "A message is needed."}
        conversation = _id(body.get("conversation"))
        if conversation:
            found = await conversation_of(me, conversation)
            if found is None:
                return {"state": "error", "message": "Not one of your conversations."}
            other = str(found["b"]) if str(found["a"]) == me else str(found["a"])
        else:
            member = await find(body.get("to"))
            if member is None or str(member.get("id")) == me:
                return {"state": "error", "message": "No single member has this name."}
            other = str(member["id"])
            a, b = sorted([me, other])
            names = {me: await name_of(me), other: _clean(member.get("display_name"), 60) or "?"}
            rows = await ctx.db.execute(
                "INSERT INTO conversations (a, b, a_name, b_name) VALUES (:a, :b, :an, :bn) "
                "ON CONFLICT (a, b) DO UPDATE SET last_at = now() RETURNING id",
                {"a": a, "b": b, "an": names[a], "bn": names[b]},
            )
            conversation = rows[0]["id"]
        await ctx.db.execute(
            "INSERT INTO messages (conversation_id, author, body) VALUES (:c, :a, :b)",
            {"c": conversation, "a": me, "b": text},
        )
        await ctx.db.execute("UPDATE conversations SET last_at = now() WHERE id = :c", {"c": conversation})
        await ctx.live.publish("new", {"conversation": conversation}, users=[me, other], author=me)
        return {
            "state": "available",
            "message": "Sent.",
            "conversation": conversation,
            "link": f"/plugins/messenger/chat?conversation={conversation}",
        }

    async def export(user_id):
        rows = await ctx.db.execute(
            "SELECT conversation_id, body, created_at FROM messages WHERE author = :a ORDER BY id", {"a": user_id}
        )
        return {"messages": [{"conversation": r["conversation_id"], "body": r["body"], "at": r["created_at"].isoformat()} for r in rows]}

    async def erase(user_id):
        await ctx.db.execute("DELETE FROM conversations WHERE a = :u OR b = :u", {"u": user_id})

    # --- the look of a member's bubbles: bought in the shop (a product of its own kind), chosen in Portalab's
    # Appearance page and worn in the chat (Portalab hands the choice to the view)
    class Bubble:
        async def activate(self, ownership):
            if not str((ownership.payload or {}).get("look") or ""):
                return ActivationResult("activation_failed", "no look")
            return ActivationResult("active", "chosen in Appearance, worn in the chat")

        async def deactivate(self, ownership):
            return None

    ctx.product_type(
        ProductType(
            key="plugin:messenger.bubble",
            owner="plugin:messenger",
            handler=Bubble(),
            payload_fields=("look",),
            label_key="plugin.messenger:type.bubble",
        )
    )

    use = "plugin:messenger.use"
    ctx.route("GET", "unread", unread, permission=use, exposure="read")
    ctx.route("GET", "conversations", conversations, permission=use, exposure="read")
    ctx.route("GET", "messages", messages, permission=use, exposure="read")
    ctx.route("POST", "send", send, permission=use, exposure="action")
    ctx.privacy(export=export, erase=erase)
