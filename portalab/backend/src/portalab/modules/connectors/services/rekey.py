"""Issue 247 — the services' credentials after a restore: each field read with the backed-up portal's key and
encrypted again with this one's (bound to its service and field, as when written)."""

from typing import Any

from sqlalchemy import select

from portalab.core.secrets import SecretBox, SecretDecryptError
from portalab.modules.connectors.models import Service
from portalab.modules.connectors.services.manager import secret_context


class ServiceSecretsRekey:
    async def rekey(self, session: Any, old: SecretBox, new: SecretBox) -> tuple[int, int]:
        done = failed = 0
        for row in (await session.execute(select(Service))).scalars():
            credentials: dict[str, Any] = {}
            for name, token in (row.credentials or {}).items():
                context = secret_context(row.id, name)
                try:
                    plain = old.decrypt(str(token), context=context).reveal()
                except SecretDecryptError:
                    failed += 1  # left out: the administrator enters it again
                    continue
                credentials[name] = new.encrypt(plain, context=context)
                done += 1
            row.credentials = credentials
        return done, failed
