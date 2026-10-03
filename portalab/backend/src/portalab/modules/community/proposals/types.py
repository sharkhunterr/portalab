"""Slice D event types (T003; via 007, ids and counters only): ``project.created`` (dedup proposal),
``project.vote_added|vote_retracted`` (private: voters are never public), ``project.participation_added|
withdrawn``, ``community.contribution_recognized`` (dedup participation; a 013 reward rule turns it into
Contribution for the recognized member) and ``community.proposal_moderated``."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:community"


class ProjectCreated(BaseModel):
    proposal: str
    kind: str


class VoteChanged(BaseModel):
    proposal: str
    count: int


class ParticipationChanged(BaseModel):
    proposal: str
    participation: str
    role: str


class ContributionRecognized(BaseModel):
    proposal: str
    participation: str
    role: str
    recognizer: str


class ProposalModerated(BaseModel):
    proposal: str
    decision: str


def register_slice_d_types(registry: EventTypeRegistry) -> None:
    for name, schema, visibility, automatable in (
        ("project.created", ProjectCreated, "community", True),
        ("project.vote_added", VoteChanged, "private", False),
        ("project.vote_retracted", VoteChanged, "private", False),
        ("project.participation_added", ParticipationChanged, "community", True),
        ("project.participation_withdrawn", ParticipationChanged, "community", False),
        ("community.contribution_recognized", ContributionRecognized, "community", True),
        ("community.proposal_moderated", ProposalModerated, "restricted", False),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    automatable=automatable,
                    rewardable=frozenset({"role"})
                    if name == "community.contribution_recognized"
                    else frozenset(),
                    visibility_class=visibility,  # type: ignore[arg-type]
                )
            )
