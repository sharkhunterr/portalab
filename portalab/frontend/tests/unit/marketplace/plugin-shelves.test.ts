import { describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, sanitize } from "../../../src/design-system/a11y/preferences";
import {
  DEPARTMENTS,
  departmentOf,
  shelfLabel,
  withPluginShelves,
} from "../../../src/features/marketplace/catalog/CatalogPage";

// 030 — a plugin's kinds of products sit on the shelf its manifest names, in the department it names; a kind
// no shelf holds still shows (among the features); the looks chosen for plugins' kinds of visuals are kept.

const BUBBLES = {
  key: "plugin:messenger.bubbles",
  plugin: "messenger",
  department: "effects",
  label_key: "plugin.messenger:shelf.bubbles",
  icon: "message-circle",
  types: ["plugin:messenger.bubble"],
};

describe("plugin shelves", () => {
  it("puts a plugin's kind on the shelf its manifest declares", () => {
    const departments = withPluginShelves(DEPARTMENTS, [BUBBLES], ["plugin:messenger.bubble", "badge"]);
    expect(departmentOf("plugin:messenger.bubble", departments)).toBe("effects");
    const shelf = departments.find((d) => d.key === "effects")?.shelves.at(-1);
    expect(shelf).toMatchObject({ key: BUBBLES.key, types: BUBBLES.types, plugin: true });
    const t = (key: string) => (key === BUBBLES.label_key ? "Message bubbles" : key);
    expect(shelfLabel(t, shelf as NonNullable<typeof shelf>)).toBe("Message bubbles");
    // Portalab's own departments are untouched
    expect(departmentOf("badge", departments)).toBe("profile");
  });

  it("never hides a plugin's kind without a shelf", () => {
    const departments = withPluginShelves(DEPARTMENTS, [], ["plugin:other.thing"]);
    const shelf = departments.find((d) => d.key === "features")?.shelves.at(-1);
    expect(shelf?.types).toEqual(["plugin:other.thing"]);
    expect(withPluginShelves(DEPARTMENTS, [], ["badge"])).toBe(DEPARTMENTS);
  });
});

describe("plugin looks preference", () => {
  it("keeps well-formed kinds and looks only", () => {
    expect(DEFAULT_PREFERENCES.pluginLooks).toEqual({});
    const kept = sanitize({
      pluginLooks: { "plugin:messenger.bubble": "aurora", "ui.theme": "x", "plugin:messenger.bad": "<b>" },
    });
    expect(kept.pluginLooks).toEqual({ "plugin:messenger.bubble": "aurora" });
    expect(sanitize({ pluginLooks: ["aurora"] }).pluginLooks).toEqual({});
  });
});
