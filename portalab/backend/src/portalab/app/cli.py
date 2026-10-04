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
    if args.status:
        return asyncio.run(_migration_status(settings.database_url.reveal()))
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


async def _migration_status(url: str) -> int:
    from portalab.app.migrations import current_heads, expected_heads
    from portalab.core.db import Database

    database = Database.from_url(url)
    try:
        current = await current_heads(database)
    finally:
        await database.dispose()
    expected = expected_heads(url)
    sys.stdout.write(f"current={sorted(current)}\nexpected={sorted(expected)}\n")
    up_to_date = current == expected
    sys.stdout.write("up to date\n" if up_to_date else "migrations pending: run `portalab migrate`\n")
    return 0 if up_to_date else 1


def _cmd_backup(args: argparse.Namespace) -> int:
    from portalab.app.migrations import expected_heads
    from portalab.app.operations import OperationError, backup

    settings = load_settings()
    url = settings.database_url.reveal()
    try:
        folder = backup(
            url, settings.data_dir, Path(args.output), heads=expected_heads(url), pg_dump=args.pg_dump
        )
    except OperationError as exc:
        sys.stderr.write(f"backup failed: {exc}\n")
        return 5
    sys.stdout.write(f"backup written to {folder}\n")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    from portalab.app.operations import OperationError, restore

    if not args.yes:
        sys.stderr.write("restore replaces the database and DATA_DIR: re-run with --yes to confirm\n")
        return 2
    settings = load_settings()
    try:
        restore(
            settings.database_url.reveal(), settings.data_dir, Path(args.input), pg_restore=args.pg_restore
        )
    except (OperationError, OSError) as exc:
        sys.stderr.write(f"restore failed: {exc}\n")
        return 5
    sys.stdout.write("restore completed; run `portalab migrate` if the backup is older than this release\n")
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
        platform = wire_platform(
            database, data_dir=settings.data_dir, capabilities=new_registry(), secret_key=settings.secret_key
        )
        await platform.refresh_config()
        module = platform.identity
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


async def _demo_seed(args: argparse.Namespace) -> int:
    from portalab.app.composition import import_all_models
    from portalab.app.demo_seed import seed_demo
    from portalab.app.wiring import wire_platform
    from portalab.capabilities.catalog import new_registry
    from portalab.core.db import Database

    settings = load_settings()
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    try:
        platform = wire_platform(
            database, data_dir=settings.data_dir, capabilities=new_registry(), secret_key=settings.secret_key
        )
        await platform.refresh_config()
        users_file = Path(args.users_file) if args.users_file else None
        report = await seed_demo(platform, users_file=users_file)
    finally:
        await database.dispose()
    for step, status in report.steps.items():
        sys.stdout.write(f"{step}: {status}\n")
    if report.created_users:
        where = args.users_file or "(no file: reset their passwords to sign in)"
        sys.stdout.write(f"demo members created: {', '.join(report.created_users)}; credentials in {where}\n")
    return 0 if report.ok else 5


def _cmd_demo_seed(args: argparse.Namespace) -> int:
    """Fill the portal with demo data through the module services (idempotent)."""
    configure_logging(load_settings().log_level)
    return asyncio.run(_demo_seed(args))


async def _audit_verify(args: argparse.Namespace) -> int:
    from portalab.app.composition import import_all_models
    from portalab.core.db import Database
    from portalab.core.event_port import OutboxEventPublisher
    from portalab.modules.authz.audit.verify import verify

    settings = load_settings()
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    try:
        report = await verify(database, OutboxEventPublisher(), from_seq=args.from_seq, to_seq=args.to_seq)
    finally:
        await database.dispose()
    sys.stdout.write(f"checked={report.checked} pruned={report.pruned} failures={len(report.failures)}\n")
    for failure in report.failures:
        sys.stdout.write(f"FAIL {failure}\n")
    return 0 if report.ok else 4


def _cmd_audit_verify(args: argparse.Namespace) -> int:
    """Verify the audit hash chain (spec 021 T020); exit code 4 when tampering is detected."""
    configure_logging(load_settings().log_level)
    return asyncio.run(_audit_verify(args))


async def _economy_verify() -> int:
    from portalab.app.composition import import_all_models
    from portalab.core.db import Database
    from portalab.modules.gamification.verify.verifier import verify

    settings = load_settings()
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    try:
        report = await verify(database)
    finally:
        await database.dispose()
    sys.stdout.write(f"checked={report.checked} drifts={len(report.drifts)}\n")
    for drift in report.drifts:
        sys.stdout.write(
            f"DRIFT user={drift.user_id} value={drift.value} ledger={drift.ledger} balance={drift.balance}\n"
        )
    return 0 if report.ok else 4


def _cmd_economy_verify(_: argparse.Namespace) -> int:
    """Recompute balances from the economy ledger (spec 013 T011); exit code 4 when they drift."""
    configure_logging(load_settings().log_level)
    return asyncio.run(_economy_verify())


def _cmd_i18n(args: argparse.Namespace) -> int:
    """Catalog tooling (spec 026 T010): check ICU validity and parity, extract used keys, pseudo-locales."""
    import json
    from pathlib import Path

    from portalab.modules.i18n.catalog.service import LOCALES_DIR
    from portalab.modules.i18n.tools.check import check, extract, pseudo

    locales = Path(args.locales) if args.locales else LOCALES_DIR
    if args.i18n_command == "check":
        problems = check(locales)
        for problem in problems:
            sys.stdout.write(f"{problem}\n")
        sys.stdout.write(f"i18n check: {len(problems)} problem(s)\n")
        return 1 if problems else 0
    if args.i18n_command == "extract":
        roots = [Path(p) for p in args.sources]
        found = {ns: sorted(keys) for ns, keys in extract(roots).items()}
        sys.stdout.write(json.dumps(found, indent=2, ensure_ascii=False) + "\n")
        return 0
    sys.stdout.write(json.dumps(pseudo(locales, args.code), indent=2, ensure_ascii=False) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portalab", description="Portalab — personal extensible portal")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the HTTP API").set_defaults(func=_cmd_serve)
    sub.add_parser("worker", help="run the background job worker").set_defaults(func=_cmd_worker)
    migrate = sub.add_parser("migrate", help="apply database migrations")
    migrate.add_argument("revision", nargs="?", default="heads")
    migrate.add_argument("--status", action="store_true", help="only report whether migrations are pending")
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
    audit = sub.add_parser("audit", help="audit log commands").add_subparsers(
        dest="audit_command", required=True
    )
    audit_verify = audit.add_parser("verify", help="verify the audit hash-chain checkpoints")
    audit_verify.add_argument("--from", dest="from_seq", type=int, default=None)
    audit_verify.add_argument("--to", dest="to_seq", type=int, default=None)
    audit_verify.set_defaults(func=_cmd_audit_verify)
    economy = sub.add_parser("economy", help="economy ledger commands").add_subparsers(
        dest="economy_command", required=True
    )
    economy.add_parser("verify", help="recompute balances from the ledger").set_defaults(
        func=_cmd_economy_verify
    )
    demo = sub.add_parser("demo", help="demo data for manual tests").add_subparsers(
        dest="demo_command", required=True
    )
    demo_seed = demo.add_parser("seed", help="fill the portal with demo data (idempotent)")
    demo_seed.add_argument(
        "--users-file", default=None, help="file receiving the demo members' generated credentials (0600)"
    )
    demo_seed.set_defaults(func=_cmd_demo_seed)
    from portalab.app.plugin_cli import add_parser as add_plugin_parser

    add_plugin_parser(sub)
    backup_cmd = sub.add_parser("backup", help="back up the database and DATA_DIR (operator command)")
    backup_cmd.add_argument("--output", required=True)
    backup_cmd.add_argument("--pg-dump", default=None)
    backup_cmd.set_defaults(func=_cmd_backup)
    restore_cmd = sub.add_parser("restore", help="restore a backup (replaces data; operator command)")
    restore_cmd.add_argument("--input", required=True)
    restore_cmd.add_argument("--pg-restore", default=None)
    restore_cmd.add_argument("--yes", action="store_true")
    restore_cmd.set_defaults(func=_cmd_restore)
    i18n = sub.add_parser("i18n", help="translation catalog tooling").add_subparsers(
        dest="i18n_command", required=True
    )
    for name, help_text in (
        ("check", "validate catalogs (ICU syntax, placeholder parity, missing/unused keys)"),
        ("extract", "list keys used in source files"),
        ("pseudo", "print a pseudo-locale catalog (en-XA, ar-XB)"),
    ):
        command = i18n.add_parser(name, help=help_text)
        command.add_argument("--locales", default=None)
        if name == "extract":
            command.add_argument("sources", nargs="+")
        if name == "pseudo":
            command.add_argument("--code", default="en-XA", choices=["en-XA", "ar-XB"])
        command.set_defaults(func=_cmd_i18n)
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
