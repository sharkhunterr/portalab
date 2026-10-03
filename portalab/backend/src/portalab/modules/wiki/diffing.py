"""Textual comparison (R9): line-level operations plus word-level operations (``diff-match-patch``,
semantic cleanup), returned as ``equal|insert|delete`` segments so the UI can mark changes with text and
symbols, never with color alone."""

import difflib
from typing import Any

from diff_match_patch import diff_match_patch

_OPS = {0: "equal", 1: "insert", -1: "delete"}


def compare(old: str, new: str) -> dict[str, list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    a, b = old.splitlines(), new.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            lines.extend({"op": "equal", "text": line} for line in a[i1:i2])
            continue
        if tag in ("replace", "delete"):
            lines.extend({"op": "delete", "text": line} for line in a[i1:i2])
        if tag in ("replace", "insert"):
            lines.extend({"op": "insert", "text": line} for line in b[j1:j2])
    engine = diff_match_patch()
    engine.Diff_Timeout = 2.0
    diffs = engine.diff_main(old, new)
    engine.diff_cleanupSemantic(diffs)
    words = [{"op": _OPS[op], "text": text} for op, text in diffs]
    return {"lines": lines, "words": words}
