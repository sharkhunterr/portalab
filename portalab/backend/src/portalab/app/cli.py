"""Command-line entrypoints: ``serve``, ``worker``, ``migrate``, ``openapi`` (research R14).

Migrations are an explicit step (``portalab migrate``); ``serve`` and ``worker`` never migrate implicitly.
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from portalab.core.logging import configure_logging, get_logger
from portalab.core.settings import SettingsError, load_settings

log = get_logger("portalab.cli")


def _cmd_serve(_: argparse.Namespace) -> int:
    import uvicorn

    from portalab.app.main import create_app

    settings = load_settings()
    configure_logging(settings.log_level)
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.bind_host,
        port=settings.bind_port,
        log_config=None,
        access_log=False,  # one structured, correlated line per request is logged by the app
        proxy_headers=True,
    )
    return 0


def _cmd_worker(_: argparse.Namespace) -> int:
    from portalab.app.worker import run_worker

    settings = load_settings()
    configure_logging(settings.log_level)
    asyncio.run(run_worker(settings))
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    from portalab.app.migrations import upgrade

    settings = load_settings()
    configure_logging(settings.log_level)
    upgrade(settings.database_url.reveal(), args.revision)
    log.info("migrations applied", extra={"fields": {"revision": args.revision}})
    return 0


def _cmd_openapi(args: argparse.Namespace) -> int:
    from portalab.app.main import create_app

    schema = create_app(migration_heads=set()).openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portalab", description="Portalab — personal extensible portal")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the HTTP API").set_defaults(func=_cmd_serve)
    sub.add_parser("worker", help="run the background job worker").set_defaults(func=_cmd_worker)
    migrate = sub.add_parser("migrate", help="apply database migrations")
    migrate.add_argument("revision", nargs="?", default="heads")
    migrate.set_defaults(func=_cmd_migrate)
    openapi = sub.add_parser("openapi", help="export the OpenAPI schema")
    openapi.add_argument("--output", "-o", default="-")
    openapi.set_defaults(func=_cmd_openapi)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SettingsError as exc:
        sys.stderr.write(f"configuration error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
