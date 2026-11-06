"""Privacy participant (issue 363): the requests a member made or wanted are exported with their data; erased
with them, their « me too » go and the requests they stood for pass to the next member who wants them."""

from collections.abc import Sequence
from uuid import UUID

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.modules.requests.service import Requests


class RequestsParticipant:
    def __init__(self, requests: Requests) -> None:
        self.requests = requests

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        return [ExportRecord("requests.request", item) for item in await self.requests.export(user_id)]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        await self.requests.erase(user_id)
