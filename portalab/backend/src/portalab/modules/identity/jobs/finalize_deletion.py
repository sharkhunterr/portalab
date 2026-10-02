"""Job ``finalize_deletion`` (T043): runs the deletion saga for one request at its ``due_at``.

Idempotent: a cancelled or finalized request is a no-op; a failing participant raises so the job queue
retries with backoff, and participants already done are not called again (``saga_state``)."""

from typing import Any
from uuid import UUID

from portalab.modules.identity.services.deletion import FINALIZE_JOB, DeletionService

KIND = FINALIZE_JOB


async def run(deletion: DeletionService, payload: dict[str, Any]) -> None:
    done = await deletion.finalize(UUID(str(payload["request_id"])))
    if not done:
        raise RuntimeError("deletion not due yet")  # retried later by the queue backoff
