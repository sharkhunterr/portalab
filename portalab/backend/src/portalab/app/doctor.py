"""``portalab doctor`` (spec 030, issue 144): how this deployment stands — who Portalab runs as, whether its
own code could be changed, whether the kernel can confine plugins, where it may write, and (with the
database) whether the outbound allow-list is on and which plugins run unconfined. It changes nothing."""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from portalab.core.confinement import MIN_LANDLOCK_ABI, probe

OK, WARN, FAIL = "ok", "warn", "fail"


def _writable(path: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".doctor-", delete=True):
            return True
    except OSError:
        return False


def local_checks(data_dir: Path | None) -> list[tuple[str, str, str]]:
    import portalab

    checks: list[tuple[str, str, str]] = []
    uid = os.getuid()
    checks.append(
        ("user", FAIL if uid == 0 else OK, f"uid {uid}" + (" (root: run as a user)" if uid == 0 else ""))
    )
    code = Path(portalab.__file__).resolve().parent
    checks.append(
        (
            "code",
            WARN if _writable(code) else OK,
            f"{code} " + ("is writable (mount the image read-only)" if _writable(code) else "is read-only"),
        )
    )
    if data_dir is not None:
        checks.append(
            ("data", OK if _writable(data_dir) else FAIL, f"{data_dir} writable: {_writable(data_dir)}")
        )
    support = probe()
    detail = f"Landlock ABI {support.landlock_abi}, seccomp {'yes' if support.seccomp else 'no'}"
    if not support.ok:
        detail += f" (confined plugins need Landlock ABI ≥ {MIN_LANDLOCK_ABI} and seccomp: they will be held)"
    checks.append(("confinement", OK if support.ok else WARN, detail))
    checks.append(("python", OK, sys.version.split()[0]))
    return checks


async def database_checks(database: Any) -> list[tuple[str, str, str]]:
    from sqlalchemy import text

    checks: list[tuple[str, str, str]] = []
    async with database.session() as session:
        rows = dict(
            (
                await session.execute(
                    text(
                        "SELECT key, value::text FROM config.settings WHERE scope = 'global' AND key IN "
                        "('security.egress.enabled', 'plugins.unconfined')"
                    )
                )
            ).all()
        )
        unconfined = (
            (
                await session.execute(
                    text("SELECT key FROM plugins.plugins WHERE runtime = 'in_process' AND state = 'enabled'")
                )
            )
            .scalars()
            .all()
        )
    egress = str(rows.get("security.egress.enabled", "false")).strip('"') == "true"
    checks.append(("egress", OK if egress else WARN, "outbound allow-list " + ("on" if egress else "off")))
    checks.append(
        (
            "plugins",
            WARN if unconfined else OK,
            ("running unconfined: " + ", ".join(unconfined)) if unconfined else "no plugin runs unconfined",
        )
    )
    return checks


def render(checks: list[tuple[str, str, str]]) -> tuple[str, int]:
    marks = {OK: "✓", WARN: "!", FAIL: "✗"}
    lines = [f"{marks[state]} {name:<12} {detail}" for name, state, detail in checks]
    worst = 2 if any(c[1] == FAIL for c in checks) else 1 if any(c[1] == WARN for c in checks) else 0
    return "\n".join(lines), worst
