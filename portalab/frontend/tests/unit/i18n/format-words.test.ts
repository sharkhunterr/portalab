import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// issue 456: what useFormat() writes in words follows the interface's language, not the region's — an
// English page set in France reads « 2 hours ago », figures and dates still drawn the French way
vi.mock("../../../src/i18n/provider/I18nProvider", () => ({
  useLocaleContext: () => ({
    language: "en",
    locale: "fr-FR",
    time_zone: "Europe/Paris",
    direction: "ltr",
    fallback_chain: ["en"],
    hour_cycle: null,
    first_day_of_week: null,
    retained_language: null,
  }),
}));

const { useFormat } = await import("../../../src/i18n/format/useFormat");

describe("useFormat's words", () => {
  it("say a relative time in the interface's language", () => {
    const { result } = renderHook(() => useFormat());
    expect(result.current.relative(-7200)).toBe("2 hours ago");
    expect(result.current.list(["a", "b"])).toBe("a and b");
  });

  it("keep figures in the region's way", () => {
    const { result } = renderHook(() => useFormat());
    expect(result.current.number(1234.5)).toBe(new Intl.NumberFormat("fr-FR").format(1234.5));
  });
});
