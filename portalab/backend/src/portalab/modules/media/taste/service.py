"""Issue 190: a member's taste and the recommendations made from it.

A work weighs on the taste by what the member did with it — a film watched to the end, a series followed
for many episodes, a book read through, the same film seen again — less as time goes by, and by what they
said of it: « I like it » counts most, « not for me » counts against. The traits of the works that weigh
(their genres, saga, people, keywords…) make the taste, a rare trait (a director) telling more than a common
one (a genre). A title not seen yet is recommended by the traits it shares with that taste, its rating
helping, never ten times the same saga or director in a row — and with the reason that most chose it.
"""

import asyncio
import math
import random
import secrets
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import (
    Activity,
    BookPosition,
    MediaObject,
    ObjectMetadata,
    TasteVerdict,
    UserProgress,
)
from portalab.modules.media.taste.features import FAMILY, WEIGHTS, Index, Trait, Work, build_index, fold

VERDICTS = ("like", "dislike", "later")  # what was seen, read or played: the services tell
USE_HISTORY = "media.taste.useHistory"
INTERESTS = "shell.onboarding.interests"
# what the welcome's « what did you come for? » says of the families of works (issue 243)
INTEREST_KINDS = {
    "movies": ("movie",),
    "series": ("series",),
    "books": ("book",),
    "audiobooks": ("audiobook",),
    "manga": ("book",),
    "comics": ("book",),
    "retro_games": ("game",),
}
HALF_LIFE_DAYS = 540  # a film seen a year and a half ago weighs half
FLOOR = 0.3  # …and never less than this: an old love is still one
LIKE, DISLIKE, LATER = 2.0, -2.0, 0.5
ELIGIBLE = 0.6  # a family recommended from: a film seen, a book read, a game played a while
# the traits a reason is best told by: a saga or a director before a genre
REASON_BIAS = {
    "saga": 1.4,
    "franchise": 1.25,
    "author": 1.15,
    "director": 1.15,
    "creator": 1.1,
    "cast": 1.0,
    "narrator": 0.9,
    "writer": 0.8,
    "genre": 0.75,
    "keyword": 0.6,
    "platform": 0.5,
    "studio": 0.45,
    "publisher": 0.45,
    "country": 0.3,
}
# the traits two recommendations in a row should not share (never ten films of one director)
STRONG = ("saga", "franchise", "director", "creator", "author")
POOL = 400
# what crosses the media, and how much of it: a saga, an author or a genre loved in films for a book
CROSS = ("saga", "franchise", "author", "genre", "keyword")
CROSSING = 0.35
# what leads to a medium I do not use: a saga, a franchise or an author — a genre in common is too little
BRIDGES = ("saga", "franchise", "author")


@dataclass(slots=True)
class Taste:
    weights: dict[UUID, float]  # what each work weighs on the taste (negative: against)
    verdicts: dict[UUID, str]
    known: set[UUID]  # seen, read, heard or judged: never recommended
    affinity: dict[str, dict[Trait, float]]  # per family
    support: dict[Trait, list[UUID]]  # the works that made a trait, the heaviest first
    opposed: Counter[Trait]  # how many works weigh against a trait
    families: set[str]
    interests: list[str] = field(default_factory=list)
    use_history: bool = True

    @property
    def empty(self) -> bool:
        return not any(w > 0 for w in self.weights.values()) and not self.interests


@dataclass(slots=True)
class Pick:
    work: Work
    score: float
    reason: dict[str, Any] | None
    seen: bool = False


def _engagement(
    kind: str, best: float, finished: int, episodes: int, recent: bool, played: float = 0.0
) -> float:
    """What a work weighs by what was done with it, before time: a film watched through 1, seen again more;
    abandoned early, a little against; a series by the episodes followed; a book read through more than a
    film (it took longer); a game by the time played and whether its player finished it — played at all, an
    interest (a game is seldom finished)."""
    if kind == "game":
        if best >= 0.8:
            return 1.2
        return 1.0 if played >= 7200 else 0.6 if played >= 1800 else 0.35
    if kind == "series":
        if not episodes:
            return 0.2 if recent else 0.0
        return min(1.5, 0.4 + 0.3 * math.log2(1 + episodes))
    full = 1.2 if kind in ("book", "audiobook") else 1.0
    if best >= 0.8:
        return full * (1.4 if finished >= 2 else 1.0)
    if best >= 0.4:
        return 0.5 * full
    if recent:
        return 0.2  # just started: an interest
    return -0.15 if best < 0.25 else 0.1  # a glance is no verdict: barely against


class TasteService:
    def __init__(
        self,
        database: Database,
        capabilities: Any,
        *,
        clock: Clock | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.rng = rng or secrets.SystemRandom()
        self._index: Index | None = None
        self._signature: tuple[Any, ...] | None = None
        self._lock = asyncio.Lock()

    # --- the library's traits ---------------------------------------------------------------------------
    async def index(self) -> Index:
        """Built again only when the library changed (a title added or updated, details fetched)."""
        async with self.database.session() as session:
            signature = (
                *(
                    await session.execute(
                        select(func.count(), func.max(MediaObject.updated_at)).where(
                            MediaObject.parent_id.is_(None)
                        )
                    )
                ).one(),
                *(await session.execute(select(func.count(), func.max(ObjectMetadata.fetched_at)))).one(),
            )
        if self._index is not None and signature == self._signature:
            return self._index
        async with self._lock:
            if self._index is None or signature != self._signature:
                async with self.database.session() as session:
                    self._index = await build_index(session)
                self._signature = signature
        assert self._index is not None
        return self._index

    # --- what a member says of a work -------------------------------------------------------------------
    async def _work_of(self, session: Any, object_id: UUID) -> UUID | None:
        """An episode's or a season's verdict goes to its series; a merged title's to the one it joined."""
        current: UUID | None = object_id
        for _ in range(4):
            row = (
                await session.execute(
                    select(MediaObject.parent_id, MediaObject.status, MediaObject.merged_into).where(
                        MediaObject.id == current
                    )
                )
            ).one_or_none()
            if row is None:
                return None
            parent, status, merged = row
            if status == "merged" and merged is not None:
                current = merged
            elif parent is not None:
                current = parent
            else:
                return current
        return current

    async def verdict(self, user: UUID, object_id: UUID) -> str | None:
        async with self.database.session() as session:
            work = await self._work_of(session, object_id)
            if work is None:
                return None
            return (
                await session.execute(
                    select(TasteVerdict.verdict).where(
                        TasteVerdict.user_id == user, TasteVerdict.object_id == work
                    )
                )
            ).scalar_one_or_none()

    async def judge(self, user: UUID, object_id: UUID, verdict: str) -> UUID | None:
        if verdict not in VERDICTS:
            raise ValueError(verdict)
        async with self.database.session() as session, session.begin():
            work = await self._work_of(session, object_id)
            if work is None:
                return None
            now = utc_now(self.clock)
            await session.execute(
                insert(TasteVerdict)
                .values(user_id=user, object_id=work, verdict=verdict, updated_at=now)
                .on_conflict_do_update(
                    index_elements=["user_id", "object_id"], set_={"verdict": verdict, "updated_at": now}
                )
            )
        return work

    async def unjudge(self, user: UUID, object_id: UUID) -> None:
        async with self.database.session() as session, session.begin():
            work = await self._work_of(session, object_id)
            if work is not None:
                await session.execute(
                    delete(TasteVerdict).where(TasteVerdict.user_id == user, TasteVerdict.object_id == work)
                )

    async def clear(self, user: UUID) -> int:
        async with self.database.session() as session, session.begin():
            result = await session.execute(delete(TasteVerdict).where(TasteVerdict.user_id == user))
        return int(getattr(result, "rowcount", 0) or 0)

    async def listed(self, user: UUID, verdict: str, *, limit: int = 50) -> list[tuple[UUID, datetime]]:
        async with self.database.session() as session:
            return [
                (object_id, at)
                for object_id, at in await session.execute(
                    select(TasteVerdict.object_id, TasteVerdict.updated_at)
                    .join(MediaObject, MediaObject.id == TasteVerdict.object_id)
                    .where(
                        TasteVerdict.user_id == user,
                        TasteVerdict.verdict == verdict,
                        MediaObject.status == "active",
                    )
                    .order_by(TasteVerdict.updated_at.desc())
                    .limit(limit)
                )
            ]

    # --- the taste --------------------------------------------------------------------------------------
    async def _preference(self, key: str, user: UUID, default: Any) -> Any:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if not providers:
                return default
            value = (await providers[0].provider.get(key, user_id=user)).value
        except Exception:
            return default
        return default if value is None else value

    async def _roots(self, session: Any, ids: Iterable[UUID]) -> dict[UUID, UUID]:
        """Each episode or season up to its series (two steps at most)."""
        out = {i: i for i in ids}
        for _ in range(3):
            parents = dict(
                (
                    await session.execute(
                        select(MediaObject.id, MediaObject.parent_id).where(
                            MediaObject.id.in_(set(out.values())), MediaObject.parent_id.is_not(None)
                        )
                    )
                ).all()
            )
            if not parents:
                break
            out = {start: parents.get(at, at) for start, at in out.items()}
        return out

    async def taste(self, user: UUID, index: Index | None = None) -> Taste:
        index = index or await self.index()
        now = utc_now(self.clock)
        use_history = bool(await self._preference(USE_HISTORY, user, True))
        interests = [str(i) for i in await self._preference(INTERESTS, user, []) if i in INTEREST_KINDS]
        best: dict[UUID, float] = defaultdict(float)
        finished: Counter[UUID] = Counter()
        episodes: dict[UUID, set[UUID]] = defaultdict(set)
        last: dict[UUID, datetime] = {}
        played: dict[UUID, float] = defaultdict(float)  # the seconds spent on it (a game's play time)
        known: set[UUID] = set()

        def seen(work: UUID, part: UUID | None, done: float, at: datetime | None, spent: float = 0.0) -> None:
            known.add(work)
            played[work] += spent
            best[work] = max(best[work], done)
            if done >= 0.8:
                finished[work] += 1
            if part is not None and part != work and done >= 0.5:
                episodes[work].add(part)
            if at is not None and (work not in last or at > last[work]):
                last[work] = at

        async with self.database.session() as session:
            verdicts: dict[UUID, str] = {
                object_id: verdict
                for object_id, verdict in await session.execute(
                    select(TasteVerdict.object_id, TasteVerdict.verdict).where(TasteVerdict.user_id == user)
                )
            }
            if use_history:
                for work, part, kind, progress, watched, duration, started, stopped in await session.execute(
                    select(
                        Activity.work_id,
                        Activity.object_id,
                        Activity.kind,
                        Activity.progress,
                        Activity.watched_s,
                        Activity.duration_s,
                        Activity.started_at,
                        Activity.stopped_at,
                    ).where(
                        Activity.user_id == user, Activity.counted.is_(True), Activity.work_id.is_not(None)
                    )
                ):
                    done = (
                        float(progress)
                        if progress is not None
                        else 0.0
                        if kind == "game"  # a game is finished when its player says so, never by time
                        else (watched / duration if duration else min(1.0, watched / 7200))
                    )
                    seen(work, part, done, stopped or started, watched or 0.0)
                # the portal's own player and reader
                rows = (
                    await session.execute(
                        select(
                            UserProgress.object_id, UserProgress.percent, UserProgress.last_occurred_at
                        ).where(UserProgress.user_id == user)
                    )
                ).all()
                books = (
                    await session.execute(
                        select(BookPosition.object_id, BookPosition.percent, BookPosition.updated_at).where(
                            BookPosition.user_id == user
                        )
                    )
                ).all()
                roots = await self._roots(session, {r[0] for r in rows} | {b[0] for b in books})
                for object_id, percent, at in [*rows, *books]:
                    done = float(percent or 0)
                    seen(roots.get(object_id, object_id), object_id, done if done <= 1 else done / 100, at)
        weights: dict[UUID, float] = {}
        for work in known:
            item = index.works.get(work)
            if item is None:
                continue
            at = last.get(work)
            age = (now - at).days if at else HALF_LIFE_DAYS
            weight = _engagement(
                item.kind, best[work], finished[work], len(episodes[work]), age < 21, played[work]
            )
            weights[work] = weight * max(FLOOR, 0.5 ** (age / HALF_LIFE_DAYS)) if weight > 0 else weight
        for work, verdict in verdicts.items():
            if work not in index.works:
                continue
            known.add(work)
            weight = weights.get(work, 0.0)
            weights[work] = {
                "like": max(weight, 0) + LIKE,
                "dislike": DISLIKE,
                "later": max(weight, 0) + LATER,
            }.get(verdict, weight)
        # per family: what the member's works have, against what the library's have — a trait counts by how
        # much more often it comes back in what they loved than in the library (a director twice in fifty
        # films tells more than « Comédie » in half of them)
        total: dict[str, dict[Trait, float]] = defaultdict(lambda: defaultdict(float))
        count: dict[str, Counter[Trait]] = defaultdict(Counter)
        backing: dict[Trait, list[tuple[float, UUID]]] = defaultdict(list)
        opposed: Counter[Trait] = Counter()
        families: dict[str, float] = defaultdict(float)
        for work, weight in weights.items():
            item = index.works[work]
            if weight > 0:
                families[item.family] += weight
            for trait in item.traits:
                total[item.family][trait] += weight
                count[item.family][trait] += 1
                if weight > 0:
                    backing[trait].append((weight, work))
                elif weight < 0:
                    opposed[trait] += 1
        affinity: dict[str, dict[Trait, float]] = {}
        for family, traits in total.items():
            mass = families.get(family, 0.0)
            scores: dict[Trait, float] = {}
            for trait, value in traits.items():
                n = count[family][trait]
                sure = n / (n + 2)  # one film says less than five
                base = index.share(family, trait)
                if value > 0 and mass > 0:
                    lift = (value / mass) / base
                    if lift > 1:
                        scores[trait] = WEIGHTS[trait[0]] * math.log(lift) * sure
                elif value < 0:  # what was disliked or left early: against, the more as it is rare
                    scores[trait] = -WEIGHTS[trait[0]] * min(2.0, -value * math.log(1 / base) / 4) * sure
            affinity[family] = scores
        eligible = {family for family, weight in families.items() if weight >= ELIGIBLE}
        for interest in interests:
            eligible.update(FAMILY[kind] for kind in INTEREST_KINDS[interest])
        return Taste(
            weights=weights,
            verdicts=verdicts,
            known=known,
            affinity=affinity,
            support={t: [w for _, w in sorted(v, key=lambda p: -p[0])] for t, v in backing.items()},
            opposed=opposed,
            families=eligible,
            interests=interests,
            use_history=use_history,
        )

    # --- recommendations --------------------------------------------------------------------------------
    @staticmethod
    def _fit(taste: Taste, work: Work) -> dict[Trait, float]:
        """What each trait of a work weighs for this taste: its own family's, and a little of the others'
        for what crosses the media (a saga, an author, a genre: the Alien films for the Alien audiobook)."""
        own = taste.affinity.get(work.family, {})
        out = {t: own[t] for t in work.traits if t in own}
        for family, scores in taste.affinity.items():
            if family == work.family:
                continue
            for trait in work.traits:
                if trait[0] in CROSS and scores.get(trait, 0) > 0:
                    out[trait] = out.get(trait, 0.0) + CROSSING * scores[trait]
        return out

    def _reason(
        self, index: Index, taste: Taste, work: Work, fit: dict[Trait, float] | None = None
    ) -> dict[str, Any] | None:
        fit = fit if fit is not None else self._fit(taste, work)
        told = [
            (value * REASON_BIAS.get(t[0], 0.5), t)
            for t, value in fit.items()
            if value > 0 and any(w != work.id for w in taste.support.get(t, ()))
        ]
        if not told:
            return None
        _, trait = max(told, key=lambda p: (p[0], p[1]))
        titles = [index.works[w].title for w in taste.support.get(trait, ()) if w != work.id][:2]
        return {"kind": trait[0], "name": index.labels.get(trait, trait[1]), "titles": titles}

    @staticmethod
    def _quality(work: Work) -> float:
        """0 for a title rated 5.5 or less, 1 from 9."""
        return min(1.0, max(0.0, (work.quality - 5.5) / 3.5))

    def _diverse(self, ranked: list[tuple[float, Work]], limit: int) -> list[tuple[float, Work]]:
        pool = ranked[:POOL]
        used: Counter[Trait] = Counter()
        kinds: Counter[str] = Counter()
        out: list[tuple[float, Work]] = []
        while pool and len(out) < limit:
            best_at, best_score = 0, -1.0
            for at, (score, work) in enumerate(pool):
                penalty = 0.9 ** kinds[work.kind]
                for trait in work.traits:
                    if trait[0] in STRONG and used[trait]:
                        penalty *= 0.55 ** used[trait]
                if score * penalty > best_score:
                    best_at, best_score = at, score * penalty
            score, work = pool.pop(best_at)
            out.append((score, work))
            kinds[work.kind] += 1
            used.update(t for t in work.traits if t[0] in STRONG)
        return out

    def _popular(self, index: Index, taste: Taste, families: set[str], limit: int) -> list[Pick]:
        """Without a taste yet: the best rated titles of the families chosen, the most voted first."""
        ranked = sorted(
            (
                w
                for w in index.works.values()
                if w.available and w.family in families and w.id not in taste.known and w.kind != "game"
            ),
            key=lambda w: -(self._quality(w) * math.log1p(w.votes) + self._quality(w)),
        )
        return [
            Pick(w, self._quality(w), {"kind": "rated", "name": None, "titles": []}) for w in ranked[:limit]
        ]

    async def recommend(
        self, user: UUID, *, limit: int, kinds: Sequence[str] | None = None, taste: Taste | None = None
    ) -> list[Pick]:
        index = await self.index()
        taste = taste or await self.taste(user, index)
        if taste.empty:
            return []
        families = taste.families
        if not any(w > 0 for w in taste.weights.values()):  # only the welcome's interests to go by
            return self._popular(index, taste, families, limit)
        scored: list[tuple[float, Work]] = []
        top = 0.0
        # another copy of a title I know (an edition, a version) is not something new
        copies = {
            (index.works[w].family, fold(index.works[w].title)) for w in taste.known if w in index.works
        }
        for work in index.works.values():
            if (
                not work.available
                or work.id in taste.known
                or (work.family, fold(work.title)) in copies
                or work.family not in families
                or (kinds and work.kind not in kinds)
            ):
                continue
            fit = self._fit(taste, work)
            raw = sum(fit.values())
            if raw <= 0:
                continue
            value = raw / math.sqrt(len(work.traits) + 2)
            top = max(top, value)
            scored.append((value, work))
        if not scored:
            return self._popular(index, taste, families, limit)
        ranked = sorted(
            (
                # a title its viewers found poor comes after, whatever it shares with the taste
                (
                    (0.75 * value / top + 0.25 * self._quality(work)) * (0.6 if work.quality < 5.0 else 1.0),
                    work,
                )
                for value, work in scored
            ),
            key=lambda p: (-p[0], str(p[1].id)),
        )
        return [Pick(w, s, self._reason(index, taste, w)) for s, w in self._diverse(ranked, limit)]

    async def deck(self, user: UUID, *, limit: int) -> list[Pick]:
        """The cards to judge one by one: mostly what the taste recommends, now and then a title seen and
        not judged yet (what was loved tells most), and a well-rated title out of the usual (to learn)."""
        index = await self.index()
        taste = await self.taste(user, index)
        if taste.empty:  # nothing to go by: the best rated films and series, books too
            taste.families = {"video", "books"}
            return self.rng.sample(
                pool := self._popular(index, taste, taste.families, limit * 3), min(limit, len(pool))
            )
        picks = await self.recommend(user, limit=limit * 2, taste=taste)
        ahead = sorted(
            self.rng.sample(picks, min(len(picks), max(1, limit * 6 // 10))), key=lambda p: -p.score
        )
        unjudged = sorted(
            (w for w, weight in taste.weights.items() if weight > 0.3 and w not in taste.verdicts),
            key=lambda w: -taste.weights[w],
        )[:30]
        seen = [
            Pick(index.works[w], taste.weights[w], None, seen=True)
            for w in self.rng.sample(unjudged, min(len(unjudged), max(1, limit * 2 // 10)))
        ]
        chosen = {p.work.id for p in picks}
        others = [
            w
            for w in index.works.values()
            if w.available
            and w.id not in taste.known
            and w.id not in chosen
            and w.family in taste.families
            and w.kind != "game"
            and w.quality >= 7.0
            and w.votes >= 200
        ]
        explore = [
            Pick(w, self._quality(w), {"kind": "rated", "name": None, "titles": []})
            for w in self.rng.sample(others, min(len(others), max(1, limit * 2 // 10)))
        ]
        out: list[Pick] = []
        streams = [ahead, seen, explore]
        pattern = (0, 0, 1, 0, 2)
        at = 0
        while len(out) < limit and any(streams):
            stream = streams[pattern[at % len(pattern)]] or next(s for s in streams if s)
            out.append(stream.pop(0))
            at += 1
        return out

    async def discover(self, user: UUID, *, limit: int) -> list[Pick]:
        """Off the beaten track, yet maybe for me: well-rated titles of a genre I seldom go to (« Something
        different: Western »), and titles of a medium I do not use yet that share a saga, an author or a theme
        with what I love (the Alien audiobook for the films' viewer) — never what my recommendations already
        offer, nor what I set aside twice. One per genre or saga, a little shuffled each visit."""
        index = await self.index()
        taste = await self.taste(user, index)
        if not any(w > 0 for w in taste.weights.values()):
            return []
        offered = {p.work.id for p in await self.recommend(user, limit=60, taste=taste)}
        copies = {
            (index.works[w].family, fold(index.works[w].title)) for w in taste.known if w in index.works
        }
        mass: dict[str, float] = defaultdict(float)
        genres: dict[str, dict[Trait, float]] = defaultdict(lambda: defaultdict(float))
        for work_id, weight in taste.weights.items():
            if weight <= 0:
                continue
            item = index.works[work_id]
            mass[item.family] += weight
            for trait in item.traits:
                if trait[0] == "genre":
                    genres[item.family][trait] += weight
        against = {trait for trait, n in taste.opposed.items() if n >= 2}
        ranked: list[tuple[float, Work, Trait, dict[str, Any]]] = []
        for work in index.works.values():
            if (
                not work.available
                or work.id in taste.known
                or work.id in offered
                or (work.family, fold(work.title)) in copies
                or any(t in against for t in work.traits)
            ):
                continue
            fit = self._fit(taste, work)
            if sum(fit.values()) < 0:
                continue
            liked = sum(v for v in fit.values() if v > 0)
            hook = max(
                (
                    (v * REASON_BIAS.get(t[0], 0.5), t)
                    for t, v in fit.items()
                    if v > 0 and any(w != work.id for w in taste.support.get(t, ()))
                ),
                default=None,
            )
            titles = (
                [index.works[w].title for w in taste.support[hook[1]] if w != work.id][:2] if hook else []
            )
            family = mass.get(work.family, 0.0)
            if family < ELIGIBLE:  # a medium I do not use: only by what it shares with my taste
                if hook is None or hook[1][0] not in BRIDGES or work.quality < 6.0:
                    continue
                trait = hook[1]
                reason = {"kind": "bridge", "name": index.labels.get(trait, trait[1]), "titles": titles}
            else:
                if work.quality < 7.0 or (work.family == "video" and work.votes < 100):
                    continue
                fresh = [
                    t
                    for t in work.traits
                    if t[0] == "genre"
                    and genres[work.family].get(t, 0.0) / family < 0.08
                    and index.share(work.family, t) >= 0.01  # a genre, not a tag of three titles
                ]
                if not fresh:
                    continue
                trait = max(fresh, key=lambda t: (index.share(work.family, t), t))
                reason = {"kind": "detour", "name": index.labels.get(trait, trait[1]), "titles": titles}
            score = self._quality(work) + 0.1 * min(1.0, math.log1p(work.votes) / 8.5) + 0.3 * min(1.0, liked)
            ranked.append((score * (0.85 + 0.3 * self.rng.random()), work, trait, reason))
        ranked.sort(key=lambda p: (-p[0], str(p[1].id)))
        out: list[Pick] = []
        used: set[Trait] = set()
        kinds: Counter[str] = Counter()
        for score, work, trait, reason in ranked:
            if trait in used or kinds[work.kind] >= max(2, limit // 3):
                continue
            used.add(trait)
            kinds[work.kind] += 1
            out.append(Pick(work, score, reason))
            if len(out) >= limit:
                break
        return out

    async def profile(self, user: UUID) -> dict[str, Any]:
        """What the member's taste is made of, as they may see it: the genres, people, sagas and themes that
        weigh most, the counts of their verdicts, how many works it is drawn from."""
        index = await self.index()
        taste = await self.taste(user, index)
        groups = {
            "genres": ("genre",),
            "people": ("director", "creator", "cast", "author", "narrator", "writer"),
            "sagas": ("saga",),
            "themes": ("keyword",),
        }
        merged: dict[Trait, float] = {}
        for scores in taste.affinity.values():
            for trait, value in scores.items():
                merged[trait] = (
                    max(merged.get(trait, value), value) if value > 0 else min(merged.get(trait, 0), value)
                )
        out: dict[str, Any] = {}
        for name, kinds in groups.items():
            least = 1 if name == "sagas" else 2  # a genre loved in one film only is not a taste yet
            rows = sorted(
                (
                    (value, trait)
                    for trait, value in merged.items()
                    if trait[0] in kinds and value > 0 and len(taste.support.get(trait, ())) >= least
                ),
                key=lambda p: -p[0],
            )[:12]
            top = rows[0][0] if rows else 1.0
            out[name] = [
                {
                    "name": index.labels.get(trait, trait[1]),
                    "role": trait[0],
                    "weight": round(value / top, 3),
                    "works": len(taste.support.get(trait, ())),
                    "titles": [index.works[w].title for w in taste.support.get(trait, ())[:3]],
                }
                for value, trait in rows
            ]
        against = sorted(
            # what was set aside twice at least: one film left early says nothing against its genre
            (
                (v, t)
                for t, v in merged.items()
                if v < 0 and t[0] in ("genre", "saga", "director", "cast") and taste.opposed[t] >= 2
            ),
            key=lambda p: p[0],
        )[:8]
        out["against"] = [{"name": index.labels.get(t, t[1]), "role": t[0]} for _, t in against]
        out["counts"] = dict(Counter(taste.verdicts.values()))
        out["works"] = sum(1 for w in taste.weights.values() if w > 0)
        out["families"] = sorted(taste.families)
        out["use_history"] = taste.use_history
        return out


class TasteRecommender:
    """The ``media.recommendations`` provider (the media page's shelf, the assistant): the taste's picks."""

    def __init__(self, taste: TasteService) -> None:
        self.taste = taste

    async def recommend(self, viewer: Principal, *, limit: int) -> Sequence[UUID]:
        user = viewer.acting_for or viewer.user_id
        if user is None:
            return []
        return [pick.work.id for pick in await self.taste.recommend(user, limit=limit)]
