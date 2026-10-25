"""Issue 247 — the plugins' secrets after a restore: their settings read with the backed-up portal's key and
encrypted again with this one's; a confined plugin's database password is forgotten (its role belongs to the
former server: a new one is set when the plugin first needs it)."""

from typing import Any

from sqlalchemy import select

from portalab.core.secrets import SecretBox, SecretDecryptError
from portalab.modules.plugins.confined.storage import DB_SECRET
from portalab.modules.plugins.models import SecretSetting


class PluginSecretsRekey:
    async def rekey(self, session: Any, old: SecretBox, new: SecretBox) -> tuple[int, int]:
        done = failed = 0
        for row in (await session.execute(select(SecretSetting))).scalars():
            if row.name == DB_SECRET:
                await session.delete(row)
                continue
            context = f"plugins.setting:{row.plugin_key}:{row.name}"
            try:
                plain = old.decrypt(row.ciphertext, context=context).reveal()
            except SecretDecryptError:
                failed += 1
                continue
            row.ciphertext = new.encrypt(plain, context=context)
            done += 1
        return done, failed
