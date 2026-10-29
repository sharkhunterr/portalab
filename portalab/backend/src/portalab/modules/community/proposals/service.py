"""Proposals (T023; R7, CD-008): any active account may propose (``community.propose``; optionally limited
to roles); moderation is **on by default** — a proposal stays ``pending_moderation`` (visible to its
proposer and moderators only) until a moderator approves it, then it is visible and votable. The Markdown
body is sanitized by the 011 renderer. A ``project`` proposal registers a lifecycle record in Marketplace
through ``ProjectLifecycle`` (015) and never stores the lifecycle state; ``project.created`` is emitted once,
when the proposal becomes visible. Support (016) converts feedback through ``community.proposals.create``
keeping ``provenance_ref`` (idempotent)."""

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.content.render import RENDERER_VERSION, render_markdown_async
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.marketplace import LIFECYCLE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.community.models import ModerationLog, Proposal, VoteCount
from portalab.modules.community.observability import log, metrics
from portalab.modules.community.permissions import MODERATE

Kind = Literal["project", "feature"]
MAX_TAGS = 8


class ProposalNotFound(NotFound):
    default_code = "community.proposal_not_found"
    default_title = "Proposal not found"


class NotActiveAccount(Forbidden):
    default_code = "community.not_active_account"
    default_title = "Only active accounts can do this"


def user_of(principal: Principal) -> UUID | None:
    return principal.acting_for or principal.user_id


def clean_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        value = tag.strip().lower()[:32]
        if value and value not in out:
            out.append(value)
    return out[:MAX_TAGS]


class Proposals:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.config = config
        self.clock = clock

    # --- ports -----------------------------------------------------------------------------------------
    def lifecycle(self) -> Any | None:
        providers = self.capabilities.system_providers(LIFECYCLE)
        return providers[0].provider if providers else None

    async def active(self, user: UUID | None) -> bool:
        if user is None:
            return False
        providers = self.capabilities.system_providers(DIRECTORY)
        return bool(providers) and bool(await providers[0].provider.is_active_account(user))

    async def is_moderator(self, viewer: Principal) -> bool:
        return await self.authorizer.is_allowed(viewer, MODERATE)

    async def _may_propose(self, user: UUID) -> None:
        if not await self.active(user):
            raise NotActiveAccount("Only active accounts can propose.")
        allowed = self.config().proposals_allowed_roles
        if allowed:
            providers = self.capabilities.system_providers(ROLES_CAPABILITY)
            roles = set(await providers[0].provider.roles_of(user)) if providers else set()
            if not roles & set(allowed):
                raise Forbidden("Proposals are limited to some roles.", code="community.propose_not_allowed")

    # --- creation ------------------------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        kind: Kind,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
        author: UUID | None = None,
        provenance: str | None = None,
    ) -> Proposal:
        proposer = author if provenance is not None else user_of(actor)
        if provenance is None:
            if proposer is None:
                raise NotActiveAccount("Only active accounts can propose.")
            await self._may_propose(proposer)
        elif proposer is not None and not await self.active(proposer):
            proposer = None  # converted feedback of an account that is no longer active
        title = title.strip()
        if not title or len(title) > 200 or len(body) > 20_000:
            raise ValidationFailed(
                "A proposal needs a title (200 characters at most).", code="community.invalid_proposal"
            )
        if provenance is not None:
            async with self.database.session() as session:
                existing = await session.scalar(select(Proposal).where(Proposal.provenance_ref == provenance))
            if existing is not None:
                return existing
        now = utc_now(self.clock)
        moderated = bool(self.config().proposals_moderation)
        rendered = await render_markdown_async(body)
        proposal = Proposal(
            kind=kind,
            provenance_ref=provenance,
            proposer_id=proposer,
            title=title,
            body_md=body,
            rendered_html=rendered.html,
            renderer_version=RENDERER_VERSION,
            tags=clean_tags(tags),
            status="pending_moderation" if moderated else "open",
            help_wanted=False,
            created_at=now,
            updated_at=now,
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(proposal)
            await uow.session.flush()
            uow.session.add(VoteCount(proposal_id=proposal.id, count=0))
            if proposal.status == "open":
                await self._created(uow.session, proposal, actor)
        await self.ensure_lifecycle(proposal)
        metrics.increment(f"community.proposals.{proposal.status}")
        return proposal

    async def ensure_lifecycle(self, proposal: Proposal) -> None:
        """Register the lifecycle record of a ``project`` proposal (retried later when 015 is down)."""
        if proposal.kind != "project" or proposal.lifecycle_ref is not None:
            return
        lifecycle = self.lifecycle()
        if lifecycle is None:
            return
        try:
            ref = await lifecycle.register(str(proposal.id), proposal.proposer_id, proposal.title)
        except Exception:
            log.warning("project lifecycle not registered yet")
            return
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Proposal, proposal.id, with_for_update=True)
            if row is not None and row.lifecycle_ref is None:
                row.lifecycle_ref = str(ref.id)
        proposal.lifecycle_ref = str(ref.id)

    async def _created(self, session: AsyncSession, proposal: Proposal, actor: Principal) -> None:
        proposer = proposal.proposer_id
        await self.events.publish(
            session,
            "project.created",
            {"proposal": str(proposal.id), "kind": proposal.kind},
            occurred_at=utc_now(self.clock),
            actor=Principal(user_id=proposer, channel="system") if proposer else actor,
            subject=SubjectRef("proposal", str(proposal.id)),
            dedup_key=f"project.created:{proposal.id}",
        )

    # --- reads ---------------------------------------------------------------------------------------------
    async def visible(self, viewer: Principal, proposal: Proposal) -> bool:
        if proposal.status == "open":
            return True
        return proposal.proposer_id == user_of(viewer) or await self.is_moderator(viewer)

    async def get(self, viewer: Principal, proposal_id: UUID) -> Proposal:
        async with self.database.session() as session:
            proposal = await session.get(Proposal, proposal_id)
        if proposal is None or not await self.visible(viewer, proposal):
            raise ProposalNotFound("This proposal does not exist.")
        return proposal

    async def listing(
        self, viewer: Principal, *, mine: bool = False, status: str | None = None, limit: int = 50
    ) -> list[Proposal]:
        statement = (
            select(Proposal).order_by(Proposal.created_at.desc(), Proposal.id).limit(max(1, min(limit, 100)))
        )
        if mine:
            statement = statement.where(Proposal.proposer_id == user_of(viewer))
            if status:
                statement = statement.where(Proposal.status == status)
        else:
            statement = statement.where(Proposal.status == "open")
        async with self.database.session() as session:
            return list((await session.execute(statement)).scalars())

    async def by_member(self, member: UUID, limit: int = 20) -> list[Proposal]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Proposal)
                        .where(Proposal.proposer_id == member, Proposal.status == "open")
                        .order_by(Proposal.created_at.desc(), Proposal.id)
                        .limit(limit)
                    )
                ).scalars()
            )

    async def needing_support(self, limit: int) -> list[Proposal]:
        """Open proposals, those asking for help first (discovery)."""
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Proposal)
                        .where(Proposal.status == "open")
                        .order_by(Proposal.help_wanted.desc(), Proposal.created_at.desc(), Proposal.id)
                        .limit(limit)
                    )
                ).scalars()
            )

    async def count(self, proposal_id: UUID) -> int:
        async with self.database.session() as session:
            row = await session.get(VoteCount, proposal_id)
        return row.count if row else 0

    # --- changes by the proposer ---------------------------------------------------------------------------
    async def _own(self, session: AsyncSession, actor: Principal, proposal_id: UUID) -> Proposal:
        proposal = await session.get(Proposal, proposal_id, with_for_update=True)
        if proposal is None or proposal.proposer_id != user_of(actor):
            raise ProposalNotFound("This proposal does not exist.")
        return proposal

    async def edit(
        self, actor: Principal, proposal_id: UUID, title: str, body: str, tags: list[str] | None
    ) -> Proposal:
        async with self.database.unit_of_work() as uow:
            proposal = await self._own(uow.session, actor, proposal_id)
            if proposal.status != "pending_moderation":
                raise Conflict(
                    "A proposal can be edited until it is open for votes.", code="community.proposal_locked"
                )
            if not title.strip() or len(title) > 200 or len(body) > 20_000:
                raise ValidationFailed("A proposal needs a title.", code="community.invalid_proposal")
            rendered = await render_markdown_async(body)
            proposal.title, proposal.body_md = title.strip(), body
            proposal.rendered_html, proposal.renderer_version = rendered.html, RENDERER_VERSION
            proposal.tags, proposal.updated_at = clean_tags(tags), utc_now(self.clock)
        return proposal

    async def withdraw(self, actor: Principal, proposal_id: UUID) -> Proposal:
        async with self.database.unit_of_work() as uow:
            proposal = await self._own(uow.session, actor, proposal_id)
            if proposal.status not in ("pending_moderation", "open"):
                raise Conflict("This proposal is already closed.", code="community.proposal_locked")
            proposal.status, proposal.updated_at = "withdrawn", utc_now(self.clock)
        return proposal

    async def set_help(self, actor: Principal, proposal_id: UUID, wanted: bool, note: str | None) -> Proposal:
        async with self.database.unit_of_work() as uow:
            proposal = await uow.session.get(Proposal, proposal_id, with_for_update=True)
            if proposal is None or proposal.status != "open":
                raise ProposalNotFound("This proposal does not exist.")
            if proposal.proposer_id != user_of(actor) and not await self.is_moderator(actor):
                raise Forbidden(
                    "Only the proposer or a moderator can ask for help.", code="community.not_proposer"
                )
            proposal.help_wanted = wanted
            proposal.help_note = ((note or "").strip()[:500] or None) if wanted else None
            proposal.updated_at = utc_now(self.clock)
        return proposal

    # --- moderation (T023) ---------------------------------------------------------------------------------
    async def queue(self) -> list[Proposal]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Proposal)
                        .where(Proposal.status == "pending_moderation")
                        .order_by(Proposal.created_at, Proposal.id)
                    )
                ).scalars()
            )

    async def moderate(
        self,
        moderator: Principal,
        proposal_id: UUID,
        decision: Literal["approved", "rejected"],
        reason: str | None,
    ) -> Proposal:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            proposal = await session.get(Proposal, proposal_id, with_for_update=True)
            if proposal is None:
                raise ProposalNotFound("This proposal does not exist.")
            if proposal.status != "pending_moderation":
                raise Conflict("This proposal is not waiting for moderation.", code="community.not_pending")
            proposal.status = "open" if decision == "approved" else "rejected"
            proposal.updated_at = now
            session.add(
                ModerationLog(
                    proposal_id=proposal.id,
                    moderator_id=user_of(moderator),
                    decision=decision,
                    reason=(reason or "").strip()[:500] or None,
                    created_at=now,
                )
            )
            published = await self.events.publish(
                session,
                "community.proposal_moderated",
                {"proposal": str(proposal.id), "decision": decision},
                occurred_at=now,
                actor=moderator,
                subject=SubjectRef("proposal", str(proposal.id)),
                dedup_key=f"community.proposal_moderated:{proposal.id}",
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action=f"community.proposal_{decision}",
                    actor=moderator,
                    resource=ResourceRef("proposal", str(proposal.id)),
                    decision="allow",
                    context={"kind": proposal.kind},
                    sensitive=True,
                    event_id=getattr(published, "event_id", None),
                ),
            )
            if decision == "approved":
                await self._created(session, proposal, moderator)
        return proposal

    # --- ProposalCreator (016) -----------------------------------------------------------------------------
    async def create_from(
        self, kind: Kind, title: str, body: str, author: UUID | None, provenance: str, actor: Principal
    ) -> str:
        proposal = await self.create(actor, kind, title, body, author=author, provenance=provenance)
        return str(proposal.id)


class ProposalCreatorAdapter:
    """``community.proposals.create`` as Support (016) calls it."""

    def __init__(self, proposals: Proposals) -> None:
        self.proposals = proposals

    async def create(
        self, kind: Kind, title: str, body: str, author: UUID | None, provenance: str, actor: Principal
    ) -> str:
        return await self.proposals.create_from(kind, title, body, author, provenance, actor)
