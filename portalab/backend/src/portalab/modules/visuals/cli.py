"""``portalab visuals analyse <folder|zip> [--json]`` (spec 028 FR-042): a pack author runs the portal's own
analysis before sending a pack — no database, no portal running. Exit 0: no blocking finding; 1: blocking
findings; 2: the pack could not be read."""

import json
import sys
from pathlib import Path
from typing import Any

from portalab.capabilities.visuals import InterfaceRegistry
from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.store import PackageError, read_source

LEVELS = ("blocking", "warning", "info")


def analyse_command(
    path: Path, *, as_json: bool = False, interfaces: InterfaceRegistry | None = None, out: Any = sys.stdout
) -> int:
    try:
        files = read_source(path)
    except (PackageError, OSError) as error:
        out.write(f"cannot read the pack: {error}\n")
        return 2
    report = analyse(files, interfaces=interfaces)
    if as_json:
        out.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        by_element: dict[str, list[dict[str, Any]]] = {}
        for item in report["items"]:
            by_element.setdefault(item["element"] or "(pack)", []).append(item)
        for element, items in by_element.items():
            out.write(f"{element}\n")
            for item in sorted(items, key=lambda i: LEVELS.index(i["level"])):
                params = ", ".join(f"{k}={v}" for k, v in item["params"].items())
                out.write(f"  {item['level']:<8} {item['code']}{f' ({params})' if params else ''}\n")
        summary = report["summary"]
        out.write(
            f"{summary['elements']} element(s): {summary['blocking']} blocking, "
            f"{summary['warning']} warning(s), {summary['info']} info\n"
        )
    return 0 if report["summary"]["publishable"] else 1
