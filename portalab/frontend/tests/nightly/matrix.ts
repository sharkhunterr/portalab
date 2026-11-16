import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

/**
 * Issue 469 — what the journeys go over, written by the preparation (``backend/tests/nightly/prepare.py``)
 * before the tests are listed: the widgets an owner may place and their settings, the packs' add-ons, the
 * options the shop keeps locked for a member owning nothing, and the looks the packs bring.
 */
export interface CatalogWidget {
  key: string;
  locked: boolean;
  product: string | null;
  widget: {
    multiple: boolean;
    config_schema: { properties?: Record<string, { type?: string; enum?: unknown[]; default?: unknown }> };
  };
}

export interface Matrix {
  widgets: CatalogWidget[];
  addons: Array<{ look: string; for: string | null; product: string | null }>;
  locked: string[];
  looks: Record<string, string[]>;
}

const STATE = process.env.NIGHTLY_STATE ?? "";
export const MATRIX = JSON.parse(
  readFileSync(process.env.NIGHTLY_MATRIX ?? resolve(dirname(STATE), "matrix.json"), "utf8"),
) as Matrix;

/** Sample values for settings without a list (a label, a date, a link), so the widget has something to show. */
const SAMPLES: Record<string, unknown> = {
  label: "Nightly",
  text: "A note left by the nightly run.",
  date: "2027-06-21",
  url: "https://example.org",
  color: "amber",
};

export interface Variant {
  name: string;
  config: Record<string, unknown>;
}

/** Each setting value a widget offers (one at a time, the others at their default), and each add-on for it. */
export function variantsOf(widget: CatalogWidget): Variant[] {
  const base: Record<string, unknown> = {};
  const properties = widget.widget.config_schema.properties ?? {};
  for (const [field, schema] of Object.entries(properties))
    if (!schema.enum && field in SAMPLES && schema.type === "string") base[field] = SAMPLES[field];
  const variants: Variant[] = [{ name: "default", config: base }];
  for (const [field, schema] of Object.entries(properties)) {
    const values = schema.enum ?? (schema.type === "boolean" ? [true, false] : []);
    for (const value of values) {
      if (value === schema.default) continue;
      variants.push({ name: `${field}=${String(value)}`, config: { ...base, [field]: value } });
    }
  }
  for (const addon of MATRIX.addons)
    if (!addon.for || addon.for === widget.key)
      variants.push({ name: `add-on ${addon.look}`, config: { ...base, _options: [addon.look] } });
  return variants;
}
