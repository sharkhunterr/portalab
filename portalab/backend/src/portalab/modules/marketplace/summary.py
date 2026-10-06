"""« Since your last visit » for the shop (027): products put on sale since."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.marketplace.models import Product, ProductVersion
from portalab.modules.marketplace.permissions import READ


class ShopChanges:
    kind = "shop"

    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        if not await self.authorizer.is_allowed(principal, READ):
            return []
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(ProductVersion.names, ProductVersion.effective_from)
                    .join(
                        Product,
                        (Product.id == ProductVersion.product_id)
                        & (Product.current_version == ProductVersion.version),
                    )
                    .where(
                        Product.state == "available",
                        ProductVersion.version == 1,
                        ProductVersion.effective_from > since,
                    )
                    .order_by(ProductVersion.effective_from.desc())
                )
            ).all()
        if not rows:
            return []
        names = [n.get(ctx.language) or n.get("en") or next(iter(n.values()), "") for n, _ in rows]
        return [
            ChangeItem(
                kind="shop",
                occurred_at=rows[0][1],
                ref="/marketplace",
                title_key="dashboard:summary.shopNew",
                title_args={"count": len(rows)},
                detail=", ".join(names[:3]) + ("…" if len(names) > 3 else ""),
                priority=1,
            )
        ]
