import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { applySafeModeFromAddress, isSafeMode, setSafeMode } from "../../../src/shell/safeMode";
import { SafeModeBanner } from "../../../src/shell/status/SafeModeBanner";

// 029 — safe mode: entered from an address (``?safe=1``, removed from it) or the switch, kept in this
// browser; its banner says it and leaves it.

afterEach(() => {
  setSafeMode(false);
  window.history.replaceState(null, "", "/");
});

describe("safe mode", () => {
  it("is set and cleared from the address, which keeps no trace of it", () => {
    window.history.replaceState(null, "", "/media?safe=1#top");
    applySafeModeFromAddress();
    expect(isSafeMode()).toBe(true);
    expect(window.localStorage.getItem("portalab.safe")).toBe("1");
    expect(window.location.search).toBe("");
    expect(window.location.pathname + window.location.hash).toBe("/media#top");
    window.history.replaceState(null, "", "/?safe=0");
    applySafeModeFromAddress();
    expect(isSafeMode()).toBe(false);
    expect(window.localStorage.getItem("portalab.safe")).toBeNull();
  });

  it("leaves the address alone without the parameter", () => {
    window.history.replaceState(null, "", "/wiki?q=a");
    applySafeModeFromAddress();
    expect(isSafeMode()).toBe(false);
    expect(window.location.search).toBe("?q=a");
  });

  it("is said by its banner, which offers to leave it", () => {
    setSafeMode(true);
    render(<SafeModeBanner />);
    expect(screen.getByRole("status")).toHaveAttribute("data-safe", "true");
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
