import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dialog } from "../../../src/design-system/components/Overlays";
import { shieldSelector } from "../../../src/design-system/visuals/cssGuard";
import { PROTECTED_PAGES } from "../../../src/shell/AppShell";

// 028 (T096, R16): what a member confirms or protects is never restyled by an imported interface — the
// administration, the account and its security, privacy, every dialog, the purchase sheet and the booster's
// prices and balance carry ``data-protected``, and an interface's stylesheet is shielded from them. (The
// sign-in page loads no pack at all: nothing of a pack reaches a visitor.)

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "../../../src");
const source = (path: string) => readFileSync(resolve(SRC, path), "utf8");

describe("protected surfaces", () => {
  it("protects the administration, the account and privacy, never the rest", () => {
    for (const path of ["/admin", "/admin/visuals", "/account", "/privacy", "/privacy/export"])
      expect(PROTECTED_PAGES.test(path), path).toBe(true);
    for (const path of ["/", "/marketplace", "/settings/appearance", "/accounting", "/community/members"])
      expect(PROTECTED_PAGES.test(path), path).toBe(false);
  });

  it("draws every dialog on a protected surface", () => {
    render(
      <Dialog open title="Confirm" closeLabel="Cancel" trigger={<button type="button">open</button>}>
        <p>Spend 200 Coins?</p>
      </Dialog>,
    );
    expect(screen.getByText("Spend 200 Coins?").closest("[data-protected]")).not.toBeNull();
  });

  it("marks the purchase sheet and the booster's prices, balance and refunds", () => {
    expect(source("features/marketplace/catalog/ProductModal.tsx")).toContain('data-protected=""');
    expect(source("features/marketplace/product/ProductDetail.tsx")).toContain('data-protected=""');
    const booster = source("features/marketplace/boosters/BoosterReveal.tsx");
    for (const surface of [
      'className="booster-stage__preview" data-protected=""',
      'className="booster-stage__hint" aria-live="polite" data-protected=""',
      'className="booster-summary__refund" data-protected=""',
      'className="booster-summary__actions" data-protected=""',
    ])
      expect(booster).toContain(surface);
  });

  it("shields an interface's rule from what is protected", () => {
    document.body.innerHTML = `
      <main><button class="buy">Buy</button></main>
      <section data-protected=""><button class="buy">Confirm</button></section>
      <button class="buy" data-protected="">Pay</button>`;
    const reached = [...document.querySelectorAll(shieldSelector(".buy"))].map((e) => e.textContent);
    expect(reached).toEqual(["Buy"]);
    expect(shieldSelector(".buy::after")).toMatch(
      /:not\(\[data-protected\]\):not\(\[data-protected\] \*\)::after$/,
    );
  });
});
