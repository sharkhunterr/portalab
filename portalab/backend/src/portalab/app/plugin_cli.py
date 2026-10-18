"""``portalab plugin validate|pack|install|enable|disable|update|purge`` (spec 023 T014, T026, T034).

``validate`` and ``pack`` work offline on a package directory; the others act on the portal database as
the system (operator at the console) with the same lifecycle, checks and audit as the admin API."""

import argparse
import asyncio
import sys
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from portalab.core.logging import configure_logging
from portalab.core.settings import load_settings


def validate(path: Path) -> int:
    from portalab.core.errors import PortalError
    from portalab.modules.plugins.scanner.scanner import scan_package
    from portalab.modules.plugins.store.package import read_manifest

    try:
        manifest = read_manifest(path)
    except PortalError as error:
        sys.stdout.write(f"invalid: {error.detail}\n")
        for problem in error.extensions.get("problems", []):
            sys.stdout.write(f"  - {problem}\n")
        return 1
    findings = (
        scan_package(path, manifest.entry_point.split(":")[0].split(".")[0])
        if manifest.entry_point and path.is_dir()
        else []
    )
    for finding in findings:
        sys.stdout.write(f"forbidden: {finding.path}:{finding.line} {finding.problem}\n")
    sys.stdout.write(f"{manifest.key} {manifest.version}: {'ok' if not findings else 'refused'}\n")
    return 1 if findings else 0


def pack(source: Path, output: Path) -> int:
    if validate(source):
        return 1
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(source).as_posix())
    sys.stdout.write(f"packed {output}\n")
    return 0


async def _with_plugins(action: Callable[[Any], Awaitable[str]]) -> int:
    from portalab.app.composition import import_all_models
    from portalab.app.wiring import wire_platform
    from portalab.capabilities.catalog import new_registry
    from portalab.core.db import Database
    from portalab.core.errors import PortalError

    settings = load_settings()
    import_all_models()
    database = Database.from_url(settings.database_url.reveal())
    try:
        platform = wire_platform(
            database, data_dir=settings.data_dir, capabilities=new_registry(), secret_key=settings.secret_key
        )
        await platform.refresh_config()
        await platform.authz.catalog.sync()
        try:
            sys.stdout.write(await action(platform.plugins) + "\n")
        except PortalError as error:
            sys.stderr.write(f"refused: {error.detail} {dict(error.extensions)}\n")
            return 3
        return 0
    finally:
        await database.dispose()


def command(args: argparse.Namespace) -> int:
    from portalab.core.authz_port import Principal

    if args.plugin_command == "validate":  # offline: no portal settings needed
        return validate(Path(args.path))
    if args.plugin_command == "pack":
        return pack(Path(args.path), Path(args.output))
    if args.plugin_command == "new":  # offline: a confined plugin to start from (030)
        from portalab.app.plugin_template import new_plugin

        folder = new_plugin(args.key, Path(args.path), name=args.name, section=args.section)
        print(f"created {folder} — next: portalab plugin validate {folder}")
        return validate(folder)
    configure_logging(load_settings().log_level)
    system = Principal(channel="system")
    match args.plugin_command:
        case "install":

            async def install(module: Any) -> str:
                plugin, review = await module.lifecycle.install(system, Path(args.path), origin="local_dir")
                if args.approve:
                    await module.lifecycle.approve(system, plugin.key)
                return f"installed {plugin.key} {plugin.current_version}; review: {review}"

            return asyncio.run(_with_plugins(install))
        case "enable":

            async def enable(module: Any) -> str:
                plugin = await module.lifecycle.enable(system, args.key)
                return f"enabled {plugin.key}" + (" (restart needed)" if plugin.needs_restart else "")

            return asyncio.run(_with_plugins(enable))
        case "disable":

            async def disable(module: Any) -> str:
                keys = await module.lifecycle.disable(system, args.key, cascade=args.cascade)
                return f"disabled {', '.join(keys)}"

            return asyncio.run(_with_plugins(disable))
        case "update":

            async def update(module: Any) -> str:
                run = await module.updates.stage(system, args.key, Path(args.path))
                return f"staged {run.from_version} → {run.to_version}: restart to apply"

            return asyncio.run(_with_plugins(update))
        case _:

            async def purge(module: Any) -> str:
                row = await module.purges.purge(system, args.key, export=not args.no_export)
                return f"purged {args.key}; export: {row.export_ref}"

            return asyncio.run(_with_plugins(purge))


def add_parser(sub: Any) -> None:
    plugin = sub.add_parser("plugin", help="plugin packages and lifecycle").add_subparsers(
        dest="plugin_command", required=True
    )
    validate_cmd = plugin.add_parser("validate", help="validate a plugin package (manifest + import scan)")
    validate_cmd.add_argument("path")
    new_cmd = plugin.add_parser("new", help="create a confined plugin to start from (spec 030)")
    new_cmd.add_argument("key")
    new_cmd.add_argument("--path", default=".")
    new_cmd.add_argument("--name", default=None)
    new_cmd.add_argument("--section", default="content", help="the section whose tab it becomes")
    pack_cmd = plugin.add_parser("pack", help="validate and zip a plugin directory")
    pack_cmd.add_argument("path")
    pack_cmd.add_argument("output")
    install_cmd = plugin.add_parser("install", help="install a package (review shown; --approve to consent)")
    install_cmd.add_argument("path")
    install_cmd.add_argument("--approve", action="store_true")
    for name in ("enable", "disable", "purge"):
        cmd = plugin.add_parser(name, help=f"{name} a plugin")
        cmd.add_argument("key")
        if name == "disable":
            cmd.add_argument("--cascade", action="store_true")
        if name == "purge":
            cmd.add_argument("--no-export", action="store_true")
    update_cmd = plugin.add_parser("update", help="stage a new version (applied at restart)")
    update_cmd.add_argument("key")
    update_cmd.add_argument("path")
    for parser in plugin.choices.values():
        parser.set_defaults(func=command)
