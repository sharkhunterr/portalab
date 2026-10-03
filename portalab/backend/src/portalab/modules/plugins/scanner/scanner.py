"""Import scanner (T008; R3) — **defense in depth, not a sandbox**: a static AST pass over every Python
file of a code plugin. Plugins may import ``portalab.sdk`` and a small standard-library allow-list (plus
their own package); process, FFI, network, dynamic-import and database-engine primitives and Portalab
internals are refused, as are ``eval``/``exec``/``compile``/``__import__``/``open``. A trusted Admin still
decides what to install."""

import ast
from dataclasses import dataclass
from pathlib import Path

ALLOWED_STDLIB = frozenset(
    {
        "__future__",
        "asyncio",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "itertools",
        "json",
        "math",
        "re",
        "statistics",
        "string",
        "textwrap",
        "typing",
        "uuid",
        "zoneinfo",
    }
)
FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "open", "globals", "breakpoint"})
FORBIDDEN_ATTRIBUTES = frozenset({"system", "popen", "create_engine", "create_async_engine", "spawn", "fork"})


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    problem: str


def _module_allowed(name: str, own: str) -> bool:
    root = name.split(".")[0]
    if name == "portalab.sdk" or name.startswith("portalab.sdk."):
        return True
    if root == own:
        return True
    return root in ALLOWED_STDLIB


def scan_source(source: str, path: str, own: str) -> list[Finding]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [Finding(path, exc.lineno or 0, "syntax error")]
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _module_allowed(alias.name, own):
                    findings.append(Finding(path, node.lineno, f"import of {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and not _module_allowed(node.module, own):
                findings.append(Finding(path, node.lineno, f"import from {node.module}"))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                findings.append(Finding(path, node.lineno, f"call to {func.id}()"))
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTRIBUTES:
                findings.append(Finding(path, node.lineno, f"call to .{func.attr}()"))
        elif (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("__")
            and node.attr not in ("__name__", "__init__")
        ):
            findings.append(Finding(path, node.lineno, f"dunder access {node.attr}"))
    return findings


def scan_package(root: Path, own: str) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.py")):
        findings.extend(scan_source(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix(), own))
    return findings
