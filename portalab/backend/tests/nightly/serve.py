"""Issue 469 — the portal served for the nightly regression suite: the real application on its database and
the production bundle (``frontend/dist``), as a member's browser sees it, with the rate limits and the
intrusion guard out of the way — the suite opens hundreds of pages a minute on purpose. Never used in
production (it lives with the tests).

    DATABASE_URL=… SECRET_KEY_FILE=… uv run python -m tests.nightly.serve PORT STATIC_DIR
"""

import sys
from pathlib import Path

import uvicorn

from portalab.app.main import create_app, guard_of
from portalab.core.logging import configure_logging
from portalab.core.settings import load_settings
from portalab.modules.privacy.settings import SecurityConfig

UNLIMITED = 10**9


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8098
    static = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../frontend/dist")
    if not (static / "index.html").is_file():
        sys.exit(f"no production bundle in {static} (npm run build first)")
    settings = load_settings()
    configure_logging("WARNING")
    app = create_app(
        settings,
        static_dir=static.resolve(),
        security_config=SecurityConfig(
            rate_limit_per_ip_per_minute=UNLIMITED,
            rate_limit_per_user_per_minute=UNLIMITED,
            rate_limit_sign_in_per_minute=UNLIMITED,
        ),
    )
    guard_of(app).enabled = False
    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
