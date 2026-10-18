"""Commissions — a new kind of product for the shop, from a confined plugin (spec 030). The shop debits the
coins and records the ownership first, then tells the plugin; it never touches a balance or a price."""

from portalab.sdk import ActivationResult, ProductType


def register(ctx):
    class Avatar:
        async def activate(self, ownership):
            description = str((ownership.payload or {}).get("description") or "")[:400]
            await ctx.db.execute(
                "INSERT INTO requests (ownership, member, product, description) VALUES (:o, :m, :p, :d) "
                "ON CONFLICT (ownership) DO UPDATE SET status = 'open'",  # activations are retried: idempotent
                {"o": str(ownership.id), "m": str(ownership.user_id), "p": ownership.product_key, "d": description},
            )
            return ActivationResult("active", "request opened")

        async def deactivate(self, ownership):
            await ctx.db.execute("UPDATE requests SET status = 'cancelled' WHERE ownership = :o", {"o": str(ownership.id)})

    async def mine(principal, query, body):
        rows = await ctx.db.execute(
            "SELECT product, status, created_at FROM requests WHERE member = :m ORDER BY created_at DESC",
            {"m": str(principal.user_id)},
        )
        return {
            "state": "available" if rows else "no-data",
            "items": [{"product": r["product"], "status": r["status"], "since": r["created_at"].date().isoformat()} for r in rows],
        }

    async def export(user_id):
        rows = await ctx.db.execute("SELECT product, status, description FROM requests WHERE member = :m", {"m": user_id})
        return {"commissions": [dict(r) for r in rows]}

    async def erase(user_id):
        await ctx.db.execute("UPDATE requests SET description = '' WHERE member = :m", {"m": user_id})

    ctx.product_type(
        ProductType(
            key="plugin:commission.avatar",
            owner="plugin:commission",
            handler=Avatar(),
            payload_fields=("description",),
            label_key="plugin.commission:type.avatar",
        )
    )
    ctx.route("GET", "mine", mine, permission="plugin:commission.use", exposure="read")
    ctx.privacy(export=export, erase=erase)
