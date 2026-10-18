"""030 T052 (US7) — `portalab plugin new`: the plugin it writes is valid as it stands (a confined version 2
manifest, its code, its migration, its own view), placed as a tab of the section asked."""

from pathlib import Path

import pytest

from portalab.app.plugin_template import new_plugin
from portalab.modules.plugins.manifest.schema import parse_toml


def test_the_new_plugin_is_valid(tmp_path: Path) -> None:
    folder = new_plugin("journal", tmp_path, section="community")
    manifest = parse_toml((folder / "plugin.toml").read_text())
    assert manifest.runtime == "confined" and manifest.route_label("POST", "notes") == "action"
    assert manifest.raw["ui"]["nav"][0]["section"] == "community"
    assert (folder / "views" / "main.js").read_text().startswith("// Journal")
    assert "portalab.sdk" in (folder / "journal_plugin" / "__init__.py").read_text()
    compile((folder / "journal_plugin" / "__init__.py").read_text(), "journal", "exec")
    with pytest.raises(FileExistsError):
        new_plugin("journal", tmp_path)
    with pytest.raises(ValueError):
        new_plugin("Bad-Key", tmp_path)
