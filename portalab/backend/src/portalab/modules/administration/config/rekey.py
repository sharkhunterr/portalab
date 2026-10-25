"""Issue 247 — the sensitive settings after a restore: each one read with the backed-up portal's key and
encrypted again with this one's (``config:<key>`` bound, as when written)."""

from typing import Any

from sqlalchemy import select

from portalab.core.secrets import SecretBox, SecretDecryptError
from portalab.modules.administration.models import Setting


class ConfigSecretsRekey:
    async def rekey(self, session: Any, old: SecretBox, new: SecretBox) -> tuple[int, int]:
        done = failed = 0
        for row in (await session.execute(select(Setting).where(Setting.value.has_key("enc")))).scalars():
            context = f"config:{row.key}"
            try:
                plain = old.decrypt(str(row.value["enc"]), context=context).reveal()
            except SecretDecryptError:
                failed += 1
                continue
            row.value = {"enc": new.encrypt(plain, context=context)}
            done += 1
        return done, failed
