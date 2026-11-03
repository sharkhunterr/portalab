"""Cards module facade (issue 229): the media trading cards — made in advance from the works present, given in
packs when a work is watched to the end, collected per set and per person."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import update

from portalab.capabilities.administration import BACKUP_LEFT_OUT_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.marketplace import ProductType, ProductTypeRegistry, default_product_types
from portalab.capabilities.media_core import CARD_FACES, CONTENT_BOOSTERS
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.cards import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.cards.artwork import FanArt
from portalab.modules.cards.backup import CardsLeftOut
from portalab.modules.cards.characters import CharacterSheets
from portalab.modules.cards.cutouts import ArtCutouts, Cutter
from portalab.modules.cards.events import register_event_types
from portalab.modules.cards.faces import FaceMatcher
from portalab.modules.cards.focus import ArtFocus
from portalab.modules.cards.frames import FilmFrames
from portalab.modules.cards.generator import CardForge
from portalab.modules.cards.integrations import COLLECTION_WIDGET, CollectionWidget
from portalab.modules.cards.models import Card
from portalab.modules.cards.packs import (
    BOOSTER_FIELDS,
    CARD_BOOSTER,
    CardBoosterHandler,
    ContentBoosters,
    Packs,
)
from portalab.modules.cards.participant import CardsParticipant
from portalab.modules.cards.roles import RoleArt
from portalab.modules.cards.search import RoleSearch
from portalab.modules.cards.service import CardFaces, CardService
from portalab.modules.cards.settings import SETTINGS, CardsConfig

OWNER = "module:cards"
SYNC_JOB = "cards.sync"
ROLES_JOB = "cards.role_art"
FAN_ART_JOB = "cards.fan_art"
SEARCH_JOB = "cards.role_search"
FRAMES_JOB = "cards.film_frames"
FOCUS_JOB = "cards.focus"
CUTOUTS_JOB = "cards.cutouts"
CHARACTERS_JOB = "cards.characters"
log = get_logger("portalab.cards")


class CardsModule:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        consumers: ConsumerRegistry = default_consumers,
        product_types: ProductTypeRegistry = default_product_types,
        events: EventPublisher | None = None,
        event_types: EventTypeRegistry = default_event_types,
        widgets: WidgetRegistry = default_widgets,
        blobs: BlobStore | None = None,
        root: Path | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.consumers = consumers
        self.product_types = product_types
        self.forge = CardForge(database, capabilities, clock=clock)
        self.packs = Packs(database, capabilities, clock=clock, events=events)
        self.event_types = event_types
        self.widgets = widgets
        self.service = CardService(database)
        self.roles = RoleArt(database, capabilities, clock=clock)
        self.fan_art = FanArt(database, capabilities, clock=clock)
        self.blobs = blobs
        self.matcher = FaceMatcher(root or Path("data/cards"))
        self.config = CardsConfig()
        self.characters = CharacterSheets(database, capabilities, blobs, clock=clock)
        self.frames = FilmFrames(
            database,
            capabilities,
            self.matcher,
            blobs,
            clock=clock,
            enabled=lambda: self.config.video_frames,
            characters_first=self.characters.available,
        )
        self.focus = ArtFocus(database, capabilities, self.matcher, blobs)
        self.cutouts = ArtCutouts(
            database,
            capabilities,
            Cutter(root or Path("data/cards")),
            blobs,
            enabled=lambda: self.config.cutouts,
        )
        self.search = RoleSearch(
            database,
            capabilities,
            self.matcher,
            blobs,
            clock=clock,
            face_check=lambda: self.config.face_check,
            frames_first=self.frames.available,
            enabled=lambda: self.config.web_search,
        )

    def register(self) -> None:
        register_event_types(self.event_types)  # issue 234: what the achievements count
        participant = CardsParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "cards" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="cards", owner=OWNER)
        # issue 234: the shop's boosters of cards (a genre, an edition…), sealed in the member's inventory
        if self.product_types.get(CARD_BOOSTER) is None:
            self.product_types.register(
                ProductType(
                    CARD_BOOSTER,
                    OWNER,
                    CardBoosterHandler(self.packs),
                    refundable_by_default=False,
                    payload_fields=BOOSTER_FIELDS,
                    label_key="marketplace:type.card_booster",
                )
            )
        # issue 247: its images left out of a restored backup are looked for again
        if not any(
            p.instance_ref == "cards" for p in self.capabilities.system_providers(BACKUP_LEFT_OUT_CAPABILITY)
        ):
            self.capabilities.provide(
                BACKUP_LEFT_OUT_CAPABILITY, CardsLeftOut(), instance_ref="cards", owner=OWNER
            )
        # issue 265: the memory game lays a member's own cards face down
        if not self.capabilities.system_providers(CARD_FACES):
            self.capabilities.provide(CARD_FACES, CardFaces(self.database), instance_ref="cards", owner=OWNER)
        # issue 234: a content's boosters, given by the reward rules the administrators set
        if not self.capabilities.system_providers(CONTENT_BOOSTERS):
            self.capabilities.provide(
                CONTENT_BOOSTERS, ContentBoosters(self.packs), instance_ref="cards", owner=OWNER
            )
        # #347: « My Mediacards » on the dashboard
        if self.widgets.get(COLLECTION_WIDGET.key) is None:
            widget = CollectionWidget(self.service, self.packs, self.clock)
            self.widgets.register(COLLECTION_WIDGET, widget, owner=OWNER)

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("cards configuration not refreshed")

    async def look_again(self, set_key: str) -> dict[str, int]:
        """A set's characters looked for again from the start, by its sources in their order — each giving
        only the cards still without an image: TheTVDB (the role's own image), TMDB (a still the actor is
        tagged in), the film itself (its images, their faces compared), the web (when switched on)."""
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(Card)
                .where(Card.set_key == set_key, Card.kind == "cast")
                .values(
                    role_art=None,
                    role_alt=None,
                    role_checked_at=None,
                    character_checked_at=None,
                    frame_checked_at=None,
                    search_checked_at=None,
                )
                .execution_options(synchronize_session=False)
            )
        return {
            "tvdb": await self.characters.run(set_key=set_key),
            "tmdb": await self.roles.run(set_key=set_key),
            "film": await self.frames.run(set_key=set_key),
            "web": await self.search.run(20, set_key=set_key),
        }

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def sync() -> None:
            report = await self.forge.sync()
            if report.made or report.gone:
                log.info("cards made again", extra={"fields": {"made": report.made, "gone": report.gone}})

        async def roles() -> None:
            await self.roles.run()

        async def fan_art() -> None:
            await self.fan_art.run()

        async def characters() -> None:
            await self.characters.run()

        async def frames() -> None:
            await self.frames.run()

        async def search() -> None:
            await self.search.run()

        async def focus() -> None:
            await self.focus.run()

        async def cutouts() -> None:
            await self.cutouts.run()

        return [
            self.refresh_config,
            # the works that changed are made again (their fingerprint), every half hour
            register_periodic(jobs, self.database, SYNC_JOB, timedelta(minutes=30), sync, owner=OWNER),
            # the actors' characters, a few people every five minutes (the rarest cards first)
            register_periodic(jobs, self.database, ROLES_JOB, timedelta(minutes=5), roles, owner=OWNER),
            # the works' full art from an art site (fanart.tv), a few works every five minutes
            register_periodic(jobs, self.database, FAN_ART_JOB, timedelta(minutes=5), fan_art, owner=OWNER),
            # the roles' own images from a community database (TheTVDB), a few works every five minutes
            register_periodic(
                jobs, self.database, CHARACTERS_JOB, timedelta(minutes=5), characters, owner=OWNER
            ),
            # the actors' characters in the film itself (its images, their faces compared), a film at a time
            register_periodic(
                jobs,
                self.database,
                FRAMES_JOB,
                timedelta(minutes=5),
                frames,
                owner=OWNER,
                timeout_seconds=900,
            ),
            # the actors' characters on the web (their faces compared), a few cards every five minutes
            register_periodic(jobs, self.database, SEARCH_JOB, timedelta(minutes=5), search, owner=OWNER),
            # where the faces are on the cards' images (the cards owned first), every two minutes
            register_periodic(
                jobs,
                self.database,
                FOCUS_JOB,
                timedelta(minutes=2),
                focus,
                owner=OWNER,
                timeout_seconds=600,
            ),
            # the characters cut out of their images (the cards owned first), every two minutes
            register_periodic(
                jobs,
                self.database,
                CUTOUTS_JOB,
                timedelta(minutes=2),
                cutouts,
                owner=OWNER,
                timeout_seconds=900,
            ),
        ]
