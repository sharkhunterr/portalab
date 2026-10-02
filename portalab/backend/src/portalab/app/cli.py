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
    if args.revision == "heads":
        created = asyncio.run(_sync_permission_catalog(settings.database_url.reveal()))
        log.info("permission catalog synchronised", extra={"fields": {"created": created}})
    return 0


async def _sync_permission_catalog(url: str) -> int:
    from portalab.app.composition import import_all_models
    from portalab.core.db import Database
    from portalab.modules.authz.catalog import core_permissions  # noqa: F401 — declares the core catalog
    from portalab.modules.authz.catalog.sync import CatalogSync

    import_all_models()
    database = Database.from_url(url)
    try:
        return await CatalogSync(database).sync()
    finally:
        await database.dispose()


def _cmd_openapi(args: argparse.Namespace) -> int:
    from portalab.app.main import create_app

    schema = create_app(migration_heads=set()).openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


def _read_password(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8").rstrip("\n")
    import getpass

    first = getpass.getpass("Admin password: ")
    if first != getpass.getpass("Repeat the password: "):
        raise ValueError("the passwords do not match")
    return first


async def _bootstrap_admin(args: argparse.Namespace, password: str) -> str:
    from portalab.app.composition import import_all_models
    from portalab.app.wiring import wire_platform
    from portalab.capabilities.catalog import new_registry
    from portalab.core.db import Database

    settings = load_settings()
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    try:
        module = wire_platform(database, data_dir=settings.data_dir, capabilities=new_registry()).identity
        user_id = await module.bootstrap.create_first_admin(
            login=args.login, password=password, display_name=args.display_name, email=args.email
        )
        return str(user_id)
    finally:
        await database.dispose()


def _cmd_admin_bootstrap(args: argparse.Namespace) -> int:
    """Create the sole Admin of a fresh portal (refuses when an Admin exists, research R13)."""
    from portalab.core.errors import PortalError

    configure_logging(load_settings().log_level)
    try:
        password = _read_password(args.password_file)
        user_id = asyncio.run(_bootstrap_admin(args, password))
    except (PortalError, ValueError, OSError) as exc:
        detail = exc.detail if isinstance(exc, PortalError) else str(exc)
        sys.stderr.write(f"admin bootstrap refused: {detail}\n")
        return 3
    sys.stdout.write(f"Admin account created: {user_id}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portalab", description="Portalab — personal extensible portal")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the HTTP API").set_defaults(func=_cmd_serve)
    sub.add_parser("worker", help="run the background job worker").set_defaults(func=_cmd_worker)
    migrate = sub.add_parser("migrate", help="apply database migrations")
    migrate.add_argument("revision", nargs="?", default="heads")
    migrate.set_defaults(func=_cmd_migrate)
    admin = sub.add_parser("admin", help="administration commands").add_subparsers(
        dest="admin_command", required=True
    )
    bootstrap = admin.add_parser("bootstrap", help="create the sole Admin account of a fresh portal")
    bootstrap.add_argument("--login", required=True)
    bootstrap.add_argument("--display-name", default=None)
    bootstrap.add_argument("--email", default=None)
    bootstrap.add_argument(
        "--password-file", default=None, help="file containing the password (else prompted)"
    )
    bootstrap.set_defaults(func=_cmd_admin_bootstrap)
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
