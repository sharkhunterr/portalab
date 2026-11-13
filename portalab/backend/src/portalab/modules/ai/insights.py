"""The assistant's insights (issue 176): the members' verdicts on its answers, and the administrators'
dashboard — who used it and when, how often it answered, how fast, with which tools, what the members
thought of it — and the answers rated « not as expected », to improve its instructions.

A conversation's content stays its member's: the dashboard shows figures only, except for the answers a
member rated (the member is told so when rating) — their question, the answer, its tools, the comment."""

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.models import Conversation, Feedback, Message

MAX_RATED = 30
MAX_MEMBERS = 20


class MessageNotFound(NotFound):
    default_code = "ai.message_not_found"
    default_title = "No such answer"


def _percentile(values: list[int], share: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


class Insights:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        events: EventPublisher | None = None,
    ):
        self.events = events  # issue 181: a first verdict is told (the achievements count them)
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    # --- the member's verdict ---------------------------------------------------------------------------
    async def rate(
        self, principal: Principal, message_id: UUID, rating: int | None, comment: str
    ) -> dict[str, Any]:
        """``rating``: 1 as expected, -1 not, ``None`` takes the verdict back. Only the conversation's owner
        rates its answers."""
        user = principal.acting_for or principal.user_id
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(
                    select(Message, Conversation.user_id)
                    .join(Conversation, Conversation.id == Message.conversation_id)
                    .where(Message.id == message_id)
                )
            ).first()
            if row is None or row[1] != user or row[0].role != "assistant":
                raise MessageNotFound("This answer does not exist.")
            if rating is None:
                existing = await uow.session.get(Feedback, message_id)
                if existing is not None:
                    await uow.session.delete(existing)
                return {"rating": None, "comment": ""}
            text = " ".join(comment.split())[:1000]
            if self.events is not None:
                # told once per answer: its first verdict (commented: false), then its first word on what
                # was expected (commented: true) — changing one's mind never counts twice
                for commented in (False, True) if text else (False,):
                    await self.events.publish(
                        uow.session,
                        "ai.answer_rated",
                        {"rating": "up" if rating > 0 else "down", "commented": commented},
                        occurred_at=now,
                        actor=principal,
                        subject=SubjectRef("ai_message", str(message_id)),
                        dedup_key=f"ai.answer_rated:{message_id}:{'commented' if commented else 'rated'}",
                    )
            await uow.session.execute(
                insert(Feedback)
                .values(
                    message_id=message_id,
                    user_id=user,
                    rating=rating,
                    comment=text,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["message_id"], set_={"rating": rating, "comment": text, "updated_at": now}
                )
            )
        return {"rating": rating, "comment": text}

    async def ratings_of(self, message_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        if not message_ids:
            return {}
        async with self.database.session() as session:
            rows = (
                await session.execute(select(Feedback).where(Feedback.message_id.in_(message_ids)))
            ).scalars()
            return {r.message_id: {"rating": r.rating, "comment": r.comment} for r in rows}

    # --- the administrators' dashboard --------------------------------------------------------------------
    async def _names(self, users: set[UUID]) -> dict[UUID, str]:
        try:
            providers = self.capabilities.system_providers(DIRECTORY)
        except Exception:
            return {}
        if not providers:
            return {}
        names: dict[UUID, str] = {}
        for user in users:
            try:
                summary = await providers[0].provider.get_user_summary(user)
            except Exception:
                summary = None
            if summary is not None and summary.display_name:
                names[user] = summary.display_name
        return names

    async def dashboard(self, days: int) -> dict[str, Any]:
        since = utc_now(self.clock) - timedelta(days=max(1, min(days, 365)))
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Message, Conversation.user_id)
                    .join(Conversation, Conversation.id == Message.conversation_id)
                    .where(Message.created_at >= since, Message.role.in_(("user", "assistant")))
                    .order_by(Message.conversation_id, Message.seq)
                )
            ).all()
            ratings = {
                r.message_id: r
                for r in (
                    await session.execute(select(Feedback).where(Feedback.updated_at >= since))
                ).scalars()
            }
        questions = [(m, u) for m, u in rows if m.role == "user"]
        answers = [(m, u) for m, u in rows if m.role == "assistant"]
        asked: dict[UUID, Message] = {}  # the question each answer replied to
        last_question: dict[UUID, Message] = {}
        for message, _ in rows:
            if message.role == "user":
                last_question[message.conversation_id] = message
            elif message.conversation_id in last_question:
                asked[message.id] = last_question[message.conversation_id]

        errors = Counter(
            str((m.blocks or {}).get("error")) for m, _ in answers if (m.blocks or {}).get("error")
        )
        answered = [(m, u) for m, u in answers if not (m.blocks or {}).get("error")]
        latencies = [  # issue 404: 0 ms is a latency too (a fast answer is not « no answer »)
            int((m.usage or {}).get("latency_ms") or 0)
            for m, _ in answered
            if (m.usage or {}).get("latency_ms") is not None
        ]
        tokens = [
            int((m.usage or {}).get("tokens_in") or 0) + int((m.usage or {}).get("tokens_out") or 0)
            for m, _ in answers
        ]
        tools: dict[str, Counter[str]] = defaultdict(Counter)
        for message, _ in answers:
            for call in (message.blocks or {}).get("tool_calls") or []:
                if isinstance(call, dict) and call.get("name"):
                    tools[str(call["name"])][str(call.get("state") or "ok")] += 1
        per_day: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"questions": 0, "errors": 0, "members": set()}
        )
        hours = [0] * 24
        members: dict[UUID, dict[str, Any]] = {}
        for message, user in questions:
            day = per_day[message.created_at.date().isoformat()]
            day["questions"] += 1
            day["members"].add(user)
            hours[message.created_at.hour] += 1
            seen = members.setdefault(user, {"questions": 0, "last_at": message.created_at})
            seen["questions"] += 1
            seen["last_at"] = max(seen["last_at"], message.created_at)
        for message, _ in answers:
            if (message.blocks or {}).get("error"):
                per_day[message.created_at.date().isoformat()]["errors"] += 1
        rated = [(m, u) for m, u in answers if m.id in ratings]
        up = sum(1 for m, _ in rated if ratings[m.id].rating > 0)
        down_rows = sorted(
            (r for r in rated if ratings[r[0].id].rating < 0),
            key=lambda r: ratings[r[0].id].updated_at,
            reverse=True,
        )
        names = await self._names({u for _, u in questions} | {u for _, u in down_rows})
        top = sorted(members.items(), key=lambda item: -item[1]["questions"])[:MAX_MEMBERS]
        return {
            "days": days,
            "totals": {
                "questions": len(questions),
                "members": len(members),
                "answered": len(answered),
                "errors": sum(errors.values()),
                "unanswered": max(0, len(questions) - len(answers)),  # refused before an answer (quota…)
                "sourced": sum(1 for m, _ in answered if (m.blocks or {}).get("sources")),
                "nudged": sum(1 for m, _ in answers if (m.usage or {}).get("nudged")),
                "latency_median_ms": int(median(latencies)) if latencies else None,
                "latency_p90_ms": _percentile(latencies, 0.9),
                "tokens_per_answer": int(sum(tokens) / len(tokens)) if tokens else None,
                "rated_up": up,
                "rated_down": len(rated) - up,
            },
            "errors": [{"code": code, "count": count} for code, count in errors.most_common()],
            "models": [
                {"model": model, "answers": count}
                for model, count in Counter(
                    str((m.usage or {}).get("model") or "") for m, _ in answers
                ).most_common()
                if model
            ],
            "per_day": [
                {"day": day, "questions": v["questions"], "members": len(v["members"]), "errors": v["errors"]}
                for day, v in sorted(per_day.items())
            ],
            "hours_utc": hours,
            "members": [
                {
                    "user_id": str(user),
                    "name": names.get(user),
                    "questions": v["questions"],
                    "last_at": v["last_at"].isoformat(),
                }
                for user, v in top
            ],
            "tools": sorted(
                (
                    {
                        "name": name,
                        "calls": sum(states.values()),
                        "failed": sum(n for s, n in states.items() if s != "ok"),
                    }
                    for name, states in tools.items()
                ),
                key=lambda t: -t["calls"],
            ),
            "rated_down": [
                {
                    "message_id": str(message.id),
                    "member": names.get(user),
                    "at": ratings[message.id].updated_at.isoformat(),
                    "comment": ratings[message.id].comment,
                    "question": (asked[message.id].content if message.id in asked else "")[:1000],
                    "answer": message.content[:2000],
                    "tools": [
                        str(c.get("name"))
                        for c in (message.blocks or {}).get("tool_calls") or []
                        if isinstance(c, dict)
                    ],
                    "error": (message.blocks or {}).get("error"),
                }
                for message, user in down_rows[:MAX_RATED]
            ],
        }
