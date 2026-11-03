"""``DashboardService`` (T018, T023, T026): the user's widget instances — add, hide, remove, reorder, resize,
configure — validated against the widget registry and **enforced against the policy server-side** on every
write (mandatory cannot be hidden/removed; locked cannot be moved/resized/reconfigured; disabled or
unpermitted widgets cannot be added). Optimistic concurrency through ``layout_version`` (``If-Match``).
The starter dashboard is applied once, permission- and policy-filtered (idempotent via
``starter_applied_at``)."""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.dashboard import RegisteredWidget, WidgetDefinition, WidgetRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.dashboard.arrangement import (
    VIEW_COLUMNS,
    derive,
    first_free,
    flow,
    normalize,
    reading_order,
)
from portalab.modules.dashboard.arrangement import Item as GridItem
from portalab.modules.dashboard.arrangement import Size as GridSize
from portalab.modules.dashboard.arrangement import move as grid_move
from portalab.modules.dashboard.arrangement import resize as grid_resize
from portalab.modules.dashboard.conditions.evaluator import ConditionEvaluator, parse_condition
from portalab.modules.dashboard.gateway.gateway import FRAME_KEYS, WidgetGateway, config_errors, worn
from portalab.modules.dashboard.models import UserDashboard, WidgetInstance
from portalab.modules.dashboard.observability import log, metrics
from portalab.modules.dashboard.overlay.overlay import (
    LOCKED,
    MANDATORY,
    EffectiveInstance,
    Overlay,
    StoredInstance,
    effective,
    pin_freedom,
    pin_of,
    policy_class,
)
from portalab.modules.dashboard.settings import DashboardConfig
from portalab.modules.dashboard.tastes import TASTES, wanted

# #347: the welcome's play gauge, which the starter dashboard follows
PLAY_SETTING = "shell.onboarding.play"


class PolicyLocked(Conflict):
    default_code = "dashboard.policy_locked"
    default_title = "Locked by your administrator"


class WidgetUnavailableError(ValidationFailed):
    default_code = "dashboard.widget_unavailable"
    default_title = "Widget not available"


class OptionLocked(ValidationFailed):
    default_code = "dashboard.option_locked"
    default_title = "Sold in the shop"


class ConfigInvalid(ValidationFailed):
    default_code = "dashboard.config_invalid"
    default_title = "Invalid widget settings"


class VersionConflict(Conflict):
    default_code = "dashboard.version_conflict"
    default_title = "The dashboard changed meanwhile"


class WidgetExists(Conflict):
    default_code = "dashboard.widget_exists"
    default_title = "This widget is already on your dashboard"


@dataclass
class DashboardView:
    instances: list[EffectiveInstance]
    layout_version: int
    diagnostics: list[str] = field(default_factory=list)
    layout_mode: str = "shared"  # 027: one arrangement for every screen, or one per screen
    views: dict[UUID, dict[str, Any]] = field(default_factory=dict)  # 027: tablet/phone places


@dataclass(frozen=True, slots=True)
class LayoutItem:
    id: UUID | None
    widget_key: str
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class ArrangedItem:
    """One widget of a desktop arrangement (027 R13): ``id`` null materializes a policy widget."""

    id: UUID | None
    widget_key: str
    x: int
    y: int
    w: int
    h: int


def _stored(row: WidgetInstance) -> StoredInstance:
    return StoredInstance(
        row.id, row.widget_key, row.status, row.position, row.w, row.h, row.config, row.origin, row.x, row.y
    )


def _user(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    if user is None:
        raise NotFound()
    return user


class DashboardService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        registry: WidgetRegistry,
        gateway: WidgetGateway,
        conditions: ConditionEvaluator,
        config: Callable[[], DashboardConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.registry = registry
        self.gateway = gateway
        self.conditions = conditions
        self.config = config
        self.clock = clock

    # --- reading -------------------------------------------------------------------------------------
    async def _allowed_and_conditions(
        self, principal: Principal, widgets: Sequence[RegisteredWidget]
    ) -> tuple[dict[str, bool], dict[str, bool], list[str]]:
        policies = self.config().widget_policies
        allowed: dict[str, bool] = {}
        conditions: dict[str, bool] = {}
        diagnostics: list[str] = []
        for widget in widgets:
            key = widget.definition.key
            allowed[key] = await self.gateway.allowed(widget, principal)
            wanted = list(widget.definition.conditions)
            if policy_class(policies, key) == "conditional":
                parsed = parse_condition((policies.get(key) or {}).get("condition"))
                if parsed is None:
                    conditions[key] = False
                    diagnostics.append(f"{key}: conditional policy without a valid condition")
                    continue
                wanted.append(parsed)
            if wanted:
                evaluation = await self.conditions.evaluate_all(wanted, principal)
                conditions[key] = evaluation.passed
                diagnostics.extend(f"{key}: {d}" for d in evaluation.diagnostics)
        return allowed, conditions, diagnostics

    async def _overlay(
        self, session: AsyncSession, principal: Principal
    ) -> tuple[Overlay, UserDashboard | None]:
        user = _user(principal)
        board = await session.get(UserDashboard, user)
        rows = (
            (await session.execute(select(WidgetInstance).where(WidgetInstance.user_id == user)))
            .scalars()
            .all()
        )
        widgets = self.registry.widgets()
        allowed, conditions, diagnostics = await self._allowed_and_conditions(principal, widgets)
        definitions: dict[str, WidgetDefinition] = {w.definition.key: w.definition for w in widgets}
        overlay = effective(
            [_stored(row) for row in rows],
            self.config().widget_policies,
            definitions,
            allowed,
            conditions,
            starter_applied=board is not None and board.starter_applied_at is not None,
        )
        overlay.diagnostics.extend(diagnostics)
        return overlay, board

    async def view(self, principal: Principal) -> DashboardView:
        board_exists = await self._has_board(principal)
        if not board_exists:
            await self.apply_starter(principal)
        async with self.database.session() as session:
            overlay, board = await self._overlay(session, principal)
            views = {
                row_id: dict(row_views)
                for row_id, row_views in await session.execute(
                    select(WidgetInstance.id, WidgetInstance.views).where(
                        WidgetInstance.user_id == _user(principal)
                    )
                )
                if row_views
            }
        # issue 115: a setting no longer owned shows as the default (the saved one waits to be owned again)
        locked = await self.gateway.locked_options(principal)
        instances = [
            replace(i, config=self.gateway.unlocked(i.widget_key, i.config, locked))
            if locked and any(f"{i.widget_key}:{k}={v}" in locked for k, v in i.config.items())
            else i
            for i in overlay.instances
        ]
        return DashboardView(
            instances,
            board.layout_version if board else 0,
            overlay.diagnostics,
            layout_mode=board.layout_mode if board else "shared",
            views=views if board and board.layout_mode == "per_device" else {},
        )

    async def _has_board(self, principal: Principal) -> bool:
        async with self.database.session() as session:
            return await session.get(UserDashboard, _user(principal)) is not None

    async def in_shop(self, principal: Principal) -> list[WidgetDefinition]:
        """027: Marketplace widgets the user may not add yet only because they do not own them — shown in
        the gallery as « in the shop » (permission and policy still apply)."""
        policies = self.config().widget_policies
        out = []
        sold = await self.gateway.sold_widgets()  # 027: existing widgets sold by a product too
        for widget in self.registry.widgets():
            definition = widget.definition
            if (definition.product is None and definition.key not in sold) or policy_class(
                policies, definition.key
            ) == "disabled":
                continue
            if await self.gateway.allowed(widget, principal):
                continue  # already owned: in the normal catalog
            try:
                permitted = await self.gateway.authorizer.is_allowed(
                    principal, definition.required_permission
                )
            except Exception:
                permitted = False
            if permitted:
                out.append(definition)
        return out

    async def catalog(self, principal: Principal) -> list[tuple[WidgetDefinition, bool]]:
        """Widgets the user may add: permitted, enabled, entitled, not disabled, condition holding.
        The flag says whether an instance is already placed (single-instance widgets)."""
        policies = self.config().widget_policies
        widgets = self.registry.widgets()
        allowed, conditions, _ = await self._allowed_and_conditions(principal, widgets)
        async with self.database.session() as session:
            placed = set(
                (
                    await session.execute(
                        select(WidgetInstance.widget_key).where(
                            WidgetInstance.user_id == _user(principal), WidgetInstance.status == "active"
                        )
                    )
                ).scalars()
            )
        out = []
        for widget in widgets:
            key = widget.definition.key
            if (
                not allowed.get(key)
                or policy_class(policies, key) == "disabled"
                or not conditions.get(key, True)
            ):
                continue
            out.append((widget.definition, key in placed))
        return out

    # --- writing -------------------------------------------------------------------------------------
    async def _board_for_update(
        self, session: AsyncSession, user: UUID, if_match: int | None
    ) -> UserDashboard:
        board = await session.get(UserDashboard, user, with_for_update=True)
        if board is None:
            board = UserDashboard(user_id=user, layout_version=0, updated_at=utc_now(self.clock))
            session.add(board)
            await session.flush()
        if if_match is not None and if_match != board.layout_version:
            raise VersionConflict(
                "Your dashboard changed on another device; reload it.",
                extensions={"layout_version": board.layout_version},
            )
        return board

    async def _bump(
        self, session: AsyncSession, board: UserDashboard, principal: Principal, *, starter: bool = False
    ) -> int:
        board.layout_version += 1
        board.updated_at = utc_now(self.clock)
        counts = (
            (
                await session.execute(
                    select(WidgetInstance.status).where(WidgetInstance.user_id == board.user_id)
                )
            )
            .scalars()
            .all()
        )
        user_ref = hashlib.sha256(str(board.user_id).encode()).hexdigest()[:20]
        await self.events.publish(
            session,
            "dashboard.layout_changed",
            {
                "layout_version": board.layout_version,
                "widgets": len(counts),
                "active": sum(1 for status in counts if status == "active"),
                "starter": starter,
            },
            occurred_at=board.updated_at,
            actor=principal,
            source="dashboard",
            dedup_key=f"dashboard.layout:{user_ref}:{board.layout_version}",
        )
        return board.layout_version

    async def _addable(self, principal: Principal, key: str) -> RegisteredWidget:
        widget = self.registry.get(key)
        policies = self.config().widget_policies
        if widget is None or policy_class(policies, key) == "disabled":
            raise WidgetUnavailableError("This widget is not available.")
        allowed, conditions, _ = await self._allowed_and_conditions(principal, [widget])
        if not allowed.get(key) or not conditions.get(key, True):
            raise WidgetUnavailableError("This widget is not available.")
        return widget

    async def _check_options(
        self, principal: Principal, widget: RegisteredWidget, values: Mapping[str, Any]
    ) -> None:
        """027: a setting value sold in the shop (another chart, a longer period…) needs its owner."""
        locked = await self.gateway.locked_options(principal)
        if not locked:
            return
        key = widget.definition.key
        refused = sorted(
            f"{field}={value}"
            for field, value in worn(values)
            # 028: a pack's widget style is sold for every widget (``*``)
            if f"{key}:{field}={value}" in locked or f"*:{field}={value}" in locked
        )
        if refused:
            raise OptionLocked(
                "This setting is sold in the shop: buy it to use it.", extensions={"options": refused}
            )

    def _check_config(self, widget: RegisteredWidget, config: Mapping[str, Any]) -> dict[str, Any]:
        merged = {**widget.definition.config_defaults, **config}
        errors = config_errors(widget, merged)
        if errors:
            raise ConfigInvalid("These widget settings are not valid.", extensions={"errors": errors[:5]})
        return merged

    async def add(
        self,
        principal: Principal,
        key: str,
        *,
        config: Mapping[str, Any] | None = None,
        w: int | None = None,
        h: int | None = None,
        x: int | None = None,
        y: int | None = None,
        if_match: int | None = None,
    ) -> tuple[UUID, int]:
        widget = await self._addable(principal, key)
        user = _user(principal)
        policies = self.config().widget_policies
        locked = policy_class(policies, key) == "locked"
        values = self._check_config(widget, {} if locked else (config or {}))
        await self._check_options(principal, widget, values)
        size = (
            widget.definition.size.default
            if locked
            else widget.definition.size.clamp(
                w or widget.definition.size.default.w, h or widget.definition.size.default.h
            )
        )
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            existing = (
                (
                    await session.execute(
                        select(WidgetInstance).where(
                            WidgetInstance.user_id == user, WidgetInstance.widget_key == key
                        )
                    )
                )
                .scalars()
                .all()
            )
            hidden = next((row for row in existing if row.status == "hidden"), None)
            if hidden is not None and not widget.definition.multiple:
                hidden.status = "active"  # re-adding a hidden widget restores its configuration
                hidden.updated_at = now
                await self._rearrange(session, user)
                version = await self._bump(session, board, principal)
                return hidden.id, version
            if existing and not widget.definition.multiple:
                raise WidgetExists("This widget is already on your dashboard.")
            position = await self._next_position(session, user)
            slot = await self._free_slot(session, user, size.w, size.h)
            row = WidgetInstance(
                user_id=user,
                widget_key=key,
                status="active",
                position=position,
                x=slot[0],
                y=slot[1],
                w=size.w,
                h=size.h,
                config=values,
                config_schema_version=widget.definition.schema_version,
                origin="user",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            if x is not None or y is not None:  # placed where it was dropped; neighbours make room
                await self._rearrange(session, user, move_to=(row.id, x if x is not None else row.x, y or 0))
            else:
                await self._rearrange(session, user)
            version = await self._bump(session, board, principal)
            return row.id, version

    # --- arrangement (027 R10) ------------------------------------------------------------------------
    def _grid(self, row: WidgetInstance, policies: Mapping[str, Mapping[str, Any]]) -> GridItem:
        widget = self.registry.get(row.widget_key)
        limits = widget.definition.size if widget is not None else None
        return GridItem(
            str(row.id),
            row.x,
            row.y,
            row.w,
            row.h,
            GridSize(limits.min.w, limits.min.h) if limits else None,
            GridSize(limits.max.w, limits.max.h) if limits else None,
            policy_class(policies, row.widget_key) in LOCKED and not pin_freedom(policies, row.widget_key)[0],
        )

    async def _rearrange(
        self,
        session: AsyncSession,
        user: UUID,
        *,
        move_to: tuple[UUID, int, int] | None = None,
        resize_to: tuple[UUID, int, int] | None = None,
        by_position: bool = False,
    ) -> None:
        """Re-run the engine on the user's active widgets after a write and store coordinates and reading
        order (``position``); hidden widgets keep their coordinates and come after."""
        await session.flush()
        rows = list(
            (
                await session.execute(
                    select(WidgetInstance).where(WidgetInstance.user_id == user).with_for_update()
                )
            ).scalars()
        )
        policies = self.config().widget_policies
        active = [r for r in rows if r.status == "active"]
        for row in active:  # 027: pinned widgets sit at the administrator's place (unless members move them)
            pin = pin_of(policies, row.widget_key)
            if pin is not None:
                move, resize = pin_freedom(policies, row.widget_key)
                if not move or row in session.new:
                    row.x, row.y = pin[0], pin[1]
                if not resize or row in session.new:
                    row.w, row.h = pin[2], pin[3]
        if by_position:  # an ordered list (legacy layout/position writes, starter): flow it into rows
            ordered = sorted(active, key=lambda r: (r.position, str(r.id)))
            pinned = [self._grid(r, policies) for r in ordered if pin_of(policies, r.widget_key)]
            others = [r for r in ordered if not pin_of(policies, r.widget_key)]
            # pinned widgets keep their place; the others flow in order and settle around them
            items = normalize([*pinned, *flow([self._grid(r, policies) for r in others], around=pinned)])
        else:
            items = [self._grid(r, policies) for r in active]
        if move_to is not None:
            items = grid_move(items, str(move_to[0]), move_to[1], move_to[2])
        elif resize_to is not None:
            items = grid_resize(items, str(resize_to[0]), resize_to[1], resize_to[2])
        else:
            items = normalize(items)
        by_id = {str(r.id): r for r in rows}
        for index, item in enumerate(reading_order(items)):
            row = by_id[item.id]
            row.x, row.y, row.w, row.h, row.position = item.x, item.y, item.w, item.h, index
        hidden = sorted((r for r in rows if r.status != "active"), key=lambda r: (r.position, str(r.id)))
        for offset, row in enumerate(hidden, start=len(items)):
            row.position = offset

    async def _free_slot(self, session: AsyncSession, user: UUID, w: int, h: int) -> tuple[int, int]:
        policies = self.config().widget_policies
        rows = (
            await session.execute(
                select(WidgetInstance).where(
                    WidgetInstance.user_id == user, WidgetInstance.status == "active"
                )
            )
        ).scalars()
        return first_free([self._grid(r, policies) for r in rows], w, h)

    async def arrangement(
        self,
        principal: Principal,
        items: Sequence[ArrangedItem],
        *,
        if_match: int | None,
        view: str = "desktop",
    ) -> int:
        """Store a desktop arrangement (027 R13): listed widgets take the given coordinates (bounded by
        their limits and the grid; locked widgets must not change), widgets left out keep theirs, then the
        engine resolves overlaps and compacts. Removal stays ``DELETE``; hide/show stays ``PATCH``."""
        if view != "desktop":
            return await self._view_arrangement(principal, items, if_match=if_match, view=view)
        user = _user(principal)
        policies = self.config().widget_policies
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(WidgetInstance).where(WidgetInstance.user_id == user).with_for_update()
                    )
                ).scalars()
            }
            for item in items:
                widget = self.registry.get(item.widget_key)
                if item.id is None:
                    if widget is None or policy_class(policies, item.widget_key) not in (
                        "mandatory",
                        "pinned",
                        "default",
                    ):
                        raise WidgetUnavailableError("This widget is not available.")
                    row = WidgetInstance(
                        user_id=user,
                        widget_key=item.widget_key,
                        status="active",
                        position=len(rows),
                        x=0,
                        y=0,
                        w=widget.definition.size.default.w,
                        h=widget.definition.size.default.h,
                        config=dict(widget.definition.config_defaults),
                        config_schema_version=widget.definition.schema_version,
                        origin="policy_default",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    found = rows.get(item.id)
                    if found is None:
                        raise NotFound(
                            "This widget is not on your dashboard.", code="dashboard.instance_not_found"
                        )
                    row = found
                pin = pin_of(policies, row.widget_key)
                if pin is not None:  # 027: pinned — at the administrator's place, unless members may move it
                    move, resize = pin_freedom(policies, row.widget_key)
                    row.x, row.y = (item.x, item.y) if move else (pin[0], pin[1])
                    row.w, row.h = (item.w, item.h) if resize else (pin[2], pin[3])
                    continue
                if policy_class(policies, row.widget_key) == "locked":
                    if (item.x, item.y, item.w, item.h) != (
                        row.x,
                        row.y,
                        row.w,
                        row.h,
                    ) and item.id is not None:
                        raise PolicyLocked(
                            "This widget is locked by your administrator.",
                            extensions={"widget": row.widget_key, "reason": "locked"},
                        )
                    continue
                size = widget.definition.size.clamp(item.w, item.h) if widget else None
                row.x = max(0, min(item.x, 12 - (size.w if size else row.w)))
                row.y = max(0, item.y)
                if size is not None:
                    row.w, row.h = size.w, size.h
                row.updated_at = now
            await self._rearrange(session, user)
            return await self._bump(session, board, principal)

    def _view_items(
        self, rows: Sequence[WidgetInstance], view: str, policies: Mapping[str, Mapping[str, Any]]
    ) -> list[GridItem]:
        """The arrangement of a tablet/phone view: stored places, the others derived from the desktop one."""
        columns = VIEW_COLUMNS[view]
        derived = {i.id: i for i in derive([self._grid(r, policies) for r in rows], columns)}
        out: list[GridItem] = []
        for row in rows:
            stored = (row.views or {}).get(view)
            base = derived[str(row.id)]
            if isinstance(stored, dict):
                base = GridItem(
                    str(row.id),
                    int(stored.get("x", 0)),
                    int(stored.get("y", 0)),
                    int(stored.get("w", base.w)),
                    int(stored.get("h", base.h)),
                    None,
                    None,
                    base.locked,
                )
            out.append(GridItem(base.id, base.x, base.y, base.w, base.h, None, None, base.locked))
        return out

    async def _view_arrangement(
        self, principal: Principal, items: Sequence[ArrangedItem], *, if_match: int | None, view: str
    ) -> int:
        """027: store the tablet or phone arrangement of a member who arranges each screen on its own."""
        if view not in VIEW_COLUMNS:
            raise ValidationFailed("Unknown view.", code="dashboard.unknown_view")
        user = _user(principal)
        columns = VIEW_COLUMNS[view]
        policies = self.config().widget_policies
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            rows = list(
                (
                    await session.execute(
                        select(WidgetInstance)
                        .where(WidgetInstance.user_id == user, WidgetInstance.status == "active")
                        .with_for_update()
                    )
                ).scalars()
            )
            wanted = {str(i.id): i for i in items if i.id is not None}
            current = self._view_items(rows, view, policies)
            placed = [
                GridItem(
                    c.id, wanted[c.id].x, wanted[c.id].y, wanted[c.id].w, wanted[c.id].h, None, None, False
                )
                if c.id in wanted and not c.locked
                else c
                for c in current
            ]
            by_id = {str(r.id): r for r in rows}
            for item in normalize(placed, columns):
                row = by_id[item.id]
                row.views = {**(row.views or {}), view: {"x": item.x, "y": item.y, "w": item.w, "h": item.h}}
            return await self._bump(session, board, principal)

    async def layout_mode(self, principal: Principal, mode: str, *, if_match: int | None) -> int:
        """027: one arrangement for every screen (``shared``) or one per screen (``per_device``). Switching
        to ``per_device`` starts each screen from what it showed until now."""
        if mode not in ("shared", "per_device"):
            raise ValidationFailed("Unknown layout mode.", code="dashboard.unknown_layout_mode")
        user = _user(principal)
        policies = self.config().widget_policies
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            if board.layout_mode == mode:
                return board.layout_version
            board.layout_mode = mode
            if mode == "per_device":
                rows = list(
                    (
                        await session.execute(
                            select(WidgetInstance)
                            .where(WidgetInstance.user_id == user, WidgetInstance.status == "active")
                            .with_for_update()
                        )
                    ).scalars()
                )
                for view in ("tablet", "phone"):
                    by_id = {str(r.id): r for r in rows}
                    for item in self._view_items(rows, view, policies):
                        row = by_id[item.id]
                        if view not in (row.views or {}):
                            cell = {"x": item.x, "y": item.y, "w": item.w, "h": item.h}
                            row.views = {**(row.views or {}), view: cell}
            return await self._bump(session, board, principal)

    async def _next_position(self, session: AsyncSession, user: UUID) -> int:
        positions = (
            (await session.execute(select(WidgetInstance.position).where(WidgetInstance.user_id == user)))
            .scalars()
            .all()
        )
        return max(positions, default=-1) + 1

    async def _owned(self, session: AsyncSession, user: UUID, instance_id: UUID) -> WidgetInstance:
        row = await session.get(WidgetInstance, instance_id, with_for_update=True)
        if row is None or row.user_id != user:
            raise NotFound("This widget is not on your dashboard.", code="dashboard.instance_not_found")
        return row

    async def update(
        self,
        principal: Principal,
        instance_id: UUID,
        *,
        status: str | None = None,
        position: int | None = None,
        w: int | None = None,
        h: int | None = None,
        x: int | None = None,
        y: int | None = None,
        config: Mapping[str, Any] | None = None,
        if_match: int | None = None,
    ) -> int:
        user = _user(principal)
        policies = self.config().widget_policies
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            row = await self._owned(session, user, instance_id)
            cls = policy_class(policies, row.widget_key)
            widget = self.registry.get(row.widget_key)
            if status is not None:
                if status not in ("active", "hidden"):
                    raise ValidationFailed("Unknown status.", code="dashboard.invalid_status")
                if status == "hidden" and cls in MANDATORY:
                    raise PolicyLocked("This widget is required by your administrator.")
                if status == "active" and widget is None:
                    raise WidgetUnavailableError("This widget is not available.")
                row.status = status
            if cls in LOCKED:
                # 027: a pinned widget may still be moved and/or resized when the administrator allows it
                move, resize = pin_freedom(policies, row.widget_key)
                refused = (
                    config is not None
                    or (not move and any(v is not None for v in (position, x, y)))
                    or (not resize and any(v is not None for v in (w, h)))
                )
                if refused:
                    raise PolicyLocked("This widget is locked by your administrator.")
            if position is not None:
                await self._move(session, user, row, position)
            resize_to: tuple[UUID, int, int] | None = None
            if w is not None or h is not None:
                if widget is None:
                    raise WidgetUnavailableError("This widget is not available.")
                size = widget.definition.size.clamp(w or row.w, h or row.h)
                resize_to = (row.id, size.w, size.h)
            if config is not None:
                if widget is None:
                    raise WidgetUnavailableError("This widget is not available.")
                checked = self._check_config(widget, config)
                await self._check_options(principal, widget, checked)
                row.config = checked
                row.config_schema_version = widget.definition.schema_version
            row.updated_at = utc_now(self.clock)
            if position is not None:  # legacy ordered write (deprecated): new size, then flow by order
                if resize_to is not None:
                    row.w, row.h = resize_to[1], resize_to[2]
                    row.x = min(row.x, 12 - row.w)  # stays inside the grid until the flow places it
                await self._rearrange(session, user, by_position=True)
            elif resize_to is not None:
                if x is not None or y is not None:
                    row.x, row.y = x if x is not None else row.x, y if y is not None else row.y
                await self._rearrange(session, user, resize_to=resize_to)
            elif x is not None or y is not None:
                await self._rearrange(
                    session,
                    user,
                    move_to=(row.id, x if x is not None else row.x, y if y is not None else row.y),
                )
            else:
                await self._rearrange(session, user)
            return await self._bump(session, board, principal)

    async def _move(self, session: AsyncSession, user: UUID, row: WidgetInstance, position: int) -> None:
        rows = list(
            (
                await session.execute(
                    select(WidgetInstance)
                    .where(WidgetInstance.user_id == user)
                    .order_by(WidgetInstance.position, WidgetInstance.id)
                    .with_for_update()
                )
            ).scalars()
        )
        rows.remove(row)
        rows.insert(max(0, min(position, len(rows))), row)
        await self._check_locked_order(rows)
        for index, item in enumerate(rows):
            item.position = index

    async def _check_locked_order(self, ordered: Sequence[WidgetInstance]) -> None:
        policies = self.config().widget_policies
        for index, item in enumerate(ordered):
            if policy_class(policies, item.widget_key) in LOCKED and item.position != index:
                raise PolicyLocked("A locked widget cannot be moved.")

    async def remove(self, principal: Principal, instance_id: UUID, *, if_match: int | None = None) -> int:
        user = _user(principal)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            row = await self._owned(session, user, instance_id)
            if policy_class(self.config().widget_policies, row.widget_key) in MANDATORY:
                raise PolicyLocked("This widget is required by your administrator.")
            await session.delete(row)  # removal discards the configuration (hide keeps it)
            await session.flush()
            await self._rearrange(session, user)
            return await self._bump(session, board, principal)

    async def layout(self, principal: Principal, items: Sequence[LayoutItem], *, if_match: int | None) -> int:
        """Atomic reorder/resize: ``items`` is the full order; unknown ids are refused; synthesized policy
        widgets (``id`` null) are materialized."""
        user = _user(principal)
        policies = self.config().widget_policies
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await self._board_for_update(session, user, if_match)
            rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(WidgetInstance).where(WidgetInstance.user_id == user).with_for_update()
                    )
                ).scalars()
            }
            ordered: list[WidgetInstance] = []
            for item in items:
                widget = self.registry.get(item.widget_key)
                if item.id is None:
                    if widget is None or policy_class(policies, item.widget_key) not in (
                        "mandatory",
                        "pinned",
                        "default",
                    ):
                        raise WidgetUnavailableError("This widget is not available.")
                    size = widget.definition.size.default
                    row = WidgetInstance(
                        user_id=user,
                        widget_key=item.widget_key,
                        status="active",
                        position=len(ordered),
                        w=size.w,
                        h=size.h,
                        config=dict(widget.definition.config_defaults),
                        config_schema_version=widget.definition.schema_version,
                        origin="policy_default",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    found = rows.pop(item.id, None)
                    if found is None:
                        raise NotFound(
                            "This widget is not on your dashboard.", code="dashboard.instance_not_found"
                        )
                    row = found
                locked = policy_class(policies, row.widget_key) in LOCKED
                if widget is not None and not locked:
                    size = widget.definition.size.clamp(item.w, item.h)
                    row.w, row.h = size.w, size.h
                    row.x = min(row.x, 12 - row.w)
                elif locked and (item.w, item.h) != (row.w, row.h):
                    raise PolicyLocked("A locked widget cannot be resized.")
                row.updated_at = now
                ordered.append(row)
            # rows not listed (e.g. hidden ones the client did not send) keep their relative order at the end
            ordered.extend(sorted(rows.values(), key=lambda r: r.position))
            await self._check_locked_order(ordered)
            for index, row in enumerate(ordered):
                row.position = index
            await self._rearrange(session, user, by_position=True)  # deprecated alias: flow the order
            return await self._bump(session, board, principal)

    # --- starter -------------------------------------------------------------------------------------
    async def reset(
        self, principal: Principal, *, if_match: int | None = None, tastes: frozenset[str] | None = None
    ) -> int:
        """027: back to the default dashboard — every widget of mine (and my per-screen places) goes, the
        starter layout is applied again; pinned widgets come back at their place. #347: made to the member's
        tastes when they are given."""
        user = _user(principal)
        async with self.database.unit_of_work() as uow:
            board = await self._board_for_update(uow.session, user, if_match)
            await uow.session.execute(delete(WidgetInstance).where(WidgetInstance.user_id == user))
            board.starter_applied_at = None
            board.layout_mode = "shared"  # one layout for every screen, like a first visit
        await self.apply_starter(principal, again=True, tastes=tastes)
        async with self.database.session() as session:
            refreshed = await session.get(UserDashboard, user)
        return int(refreshed.layout_version) if refreshed else 0

    async def apply_starter(
        self, principal: Principal, *, again: bool = False, tastes: frozenset[str] | None = None
    ) -> bool:
        """Apply the starter layout once (idempotent); filtered by permission, policy and availability. A
        failing widget definition never blocks the others. #347: to the member's tastes — the widgets of the
        tastes not chosen left out, those of the chosen ones it lacks added (never a pinned one removed)."""
        user = _user(principal)
        layout = self.config().starter_layout
        policies = self.config().widget_policies
        widgets = {w.definition.key: w for w in self.registry.widgets()}
        chosen: list[tuple[RegisteredWidget, int, int, dict[str, Any], tuple[int, int] | None]] = []
        # issue 250: the administrator's composition puts each widget at its very place (else rows of 12)
        placed = bool(layout) and all(
            isinstance(entry, dict) and "x" in entry and "y" in entry for entry in layout
        )
        # issue 186: the starter may place a widget on a tablet and a phone too — the member's dashboard
        # then starts arranged per screen
        views = {
            str(entry.get("widget_key", "")): {v: dict(entry[v]) for v in ("tablet", "phone") if v in entry}
            for entry in layout
            if isinstance(entry, dict) and ("tablet" in entry or "phone" in entry)
        }
        roles_ok = await self._roles(principal)
        profile = await self._profile(principal)
        pinned = [
            {"widget_key": key, "w": pin[2], "h": pin[3]}
            for key in sorted(policies)
            if (pin := pin_of(policies, key)) is not None
        ]
        for entry in [*pinned, *layout]:
            try:
                key = str(entry.get("widget_key", ""))
                widget = widgets.get(key)
                roles = entry.get("roles")
                kept = entry in pinned or policy_class(policies, key) == "mandatory"
                if not kept and not wanted(tastes, key):
                    continue
                if widget is None or policy_class(policies, key) == "disabled":
                    continue
                if roles and not (set(roles) & roles_ok):
                    continue
                profiles = entry.get("profiles")
                if profiles and profile not in profiles:  # #347: the dashboard of the member's play profile
                    continue
                if not await self.gateway.allowed(widget, principal):
                    continue
                size = widget.definition.size.clamp(int(entry.get("w", 0) or 0), int(entry.get("h", 0) or 0))
                given = dict(entry.get("config") or {})
                try:  # issue 250: its own settings too, as the administrator set them
                    values = self._check_config(widget, given)
                except ConfigInvalid:
                    values = self._check_config(widget, {k: v for k, v in given.items() if k in FRAME_KEYS})
                at = (int(entry["x"]), int(entry["y"])) if placed and "x" in entry else None
                chosen.append((widget, size.w, size.h, values, at))
            except Exception:
                log.warning("starter entry skipped")
        # #347: the chosen tastes' widgets the starter lacks, in their taste's order
        missing = [key for taste in sorted(tastes or ()) for key in TASTES.get(taste, ())]
        for key in missing:
            widget = widgets.get(key)
            if (
                widget is not None
                and policy_class(policies, key) != "disabled"
                and all(c[0].definition.key != key for c in chosen)
                and await self.gateway.allowed(widget, principal)
            ):
                size = widget.definition.size.default
                chosen.append((widget, size.w, size.h, dict(widget.definition.config_defaults), None))
        for key, widget in sorted(widgets.items()):
            if (
                policy_class(policies, key) == "default"
                and wanted(tastes, key)
                and all(c[0].definition.key != key for c in chosen)
                and await self.gateway.allowed(widget, principal)
            ):
                chosen.append(
                    (
                        widget,
                        widget.definition.size.default.w,
                        widget.definition.size.default.h,
                        dict(widget.definition.config_defaults),
                        None,
                    )
                )
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            board = await session.get(UserDashboard, user, with_for_update=True)
            if board is not None and board.starter_applied_at is not None:
                return False
            if board is None:
                board = UserDashboard(user_id=user, layout_version=0, updated_at=now)
                session.add(board)
                await session.flush()
            existing = set(
                (
                    await session.execute(
                        select(WidgetInstance.widget_key).where(WidgetInstance.user_id == user)
                    )
                ).scalars()
            )
            position = await self._next_position(session, user)
            for widget, w, h, values, at in chosen:
                if widget.definition.key in existing:
                    continue
                existing.add(widget.definition.key)
                session.add(
                    WidgetInstance(
                        user_id=user,
                        widget_key=widget.definition.key,
                        status="active",
                        position=position,
                        **({"x": at[0], "y": at[1]} if at else {}),
                        w=w,
                        h=h,
                        config=values,
                        config_schema_version=widget.definition.schema_version,
                        views=views.get(widget.definition.key, {}),
                        origin="starter",
                        created_at=now,
                        updated_at=now,
                    )
                )
                position += 1
            board.starter_applied_at = now
            if views:
                board.layout_mode = "per_device"
            await self._rearrange(session, user, by_position=not placed)
            await self._bump(session, board, principal, starter=True)
            await self.events.publish(
                session,
                "dashboard.starter_applied",
                {"widgets": len(chosen)},
                occurred_at=now,
                actor=principal,
                source="dashboard",
                dedup_key=f"dashboard.starter:{hashlib.sha256(str(user).encode()).hexdigest()[:20]}"
                + (f":{int(now.timestamp())}" if again else ""),
            )
        metrics.increment("dashboard.starter_applied")
        return True

    async def _roles(self, principal: Principal) -> set[str]:
        from portalab.capabilities.user_grants import ROLES_CAPABILITY

        try:
            providers = self.conditions.capabilities.system_providers(ROLES_CAPABILITY)
            user = principal.acting_for or principal.user_id
            if providers and user is not None:
                return set(await providers[0].provider.roles_of(user))
        except Exception:
            log.warning("roles unavailable for the starter dashboard")
        return {"user"}

    async def _profile(self, principal: Principal) -> str:
        """#347: the member's play profile (the welcome's play gauge); unanswered, they play it all."""
        try:
            providers = self.conditions.capabilities.system_providers(CONFIG)
            user = principal.acting_for or principal.user_id
            if providers and user is not None:
                value = (await providers[0].provider.get(PLAY_SETTING, user_id=user)).value
                if isinstance(value, str) and value:
                    return value
        except Exception:
            log.warning("play profile unavailable for the starter dashboard")
        return "full"

    async def stored_config(self, principal: Principal, instance_id: UUID) -> tuple[str, dict[str, Any]]:
        async with self.database.session() as session:
            row = await session.get(WidgetInstance, instance_id)
            if row is None or row.user_id != _user(principal):
                raise NotFound("This widget is not on your dashboard.", code="dashboard.instance_not_found")
            config: dict[str, Any] = dict(row.config)
            locked = self.config().widget_policies.get(row.widget_key) or {}
            if locked.get("class") in LOCKED and isinstance(locked.get("lockedConfig"), Mapping):
                config.update(locked["lockedConfig"])
            return row.widget_key, config

    def imposed_config(self, key: str) -> dict[str, Any] | None:
        """Issue 250: a pinned widget's settings imposed by the administrator, for a member who has no row of
        it yet (shown from the policy alone)."""
        policy = self.config().widget_policies.get(key) or {}
        widget = self.registry.get(key)
        imposed = policy.get("lockedConfig")
        if widget is None or policy.get("class") not in LOCKED or not isinstance(imposed, Mapping):
            return None
        return {**widget.definition.config_defaults, **imposed}

    async def erase(self, user: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(WidgetInstance).where(WidgetInstance.user_id == user))
            await uow.session.execute(delete(UserDashboard).where(UserDashboard.user_id == user))
