"""023 T005 — the import scanner (defense in depth, not a sandbox) refuses process, FFI, network,
dynamic-import, engine-creation and Portalab-internal imports or calls; an SDK-only plugin passes."""

import pytest

from portalab.modules.plugins.scanner.scanner import scan_source

ALLOWED = """
import json
from datetime import UTC, datetime
from portalab.sdk import PluginContext, WidgetPayload
from portalab.sdk.pages import PageDefinition
from hello_plugin.helpers import tidy

def register(ctx: PluginContext) -> None:
    ctx.permission("view", "See it")
"""


def test_sdk_only_plugin_passes() -> None:
    assert scan_source(ALLOWED, "hello_plugin/__init__.py", "hello_plugin") == []


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess",
        "import ctypes",
        "import socket",
        "import os\nos.system('ls')",
        "from os import system",
        "import importlib",
        "import sys",
        "from portalab.modules.identity.models import User",
        "from portalab.core.db import Database",
        "import sqlalchemy",
        "from sqlalchemy.ext.asyncio import create_async_engine",
        "engine = something.create_engine('postgresql://')",
        "eval('1')",
        "exec('x = 1')",
        "__import__('os')",
        "open('/etc/passwd')",
        "x = ().__class__.__subclasses__()",
        "import httpx",
        "import pickle",
    ],
)
def test_forbidden_corpus(source: str) -> None:
    assert scan_source(source, "evil.py", "hello_plugin"), source
