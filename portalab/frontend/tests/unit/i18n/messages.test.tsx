import { type MessageFormatElement, parse, TYPE } from "@formatjs/icu-messageformat-parser";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { IntlMessageFormat } from "intl-messageformat";
import { describe, expect, it, vi } from "vitest";
import vectors from "../../../../backend/tests/data/icu_vectors.json";

// 026 T016 — the frontend renders the backend's golden ICU vectors identically; a missing key falls back
// (English, then the key) and never renders empty; a failed catalog keeps the last good copy; catalogs keep
// placeholder parity across languages and counts go through ICU plurals, not concatenation.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { BUNDLED, BUNDLED_MESSAGES } from "../../../src/i18n/bundled";
import { useT } from "../../../src/i18n/hooks/useT";
import { I18nProvider } from "../../../src/i18n/provider/I18nProvider";
import { pseudoMessage } from "../../../src/i18n/pseudo/pseudo";
import { json } from "../../support/fake-api";

interface Vector {
  locale: string;
  message: string;
  args: Record<string, string | number>;
  expected: string;
}

function Probe({ id, values }: { id: string; values?: Record<string, string | number> }) {
  const t = useT();
  return <p data-testid="out">{t(id, values)}</p>;
}

function withProvider(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <I18nProvider namespaces={["shell"]}>{node}</I18nProvider>
    </QueryClientProvider>,
  );
}

describe("ICU golden vectors", () => {
  it.each(vectors as Vector[])("$locale: $message", ({ locale, message, args, expected }) => {
    const rendered = String(new IntlMessageFormat(message, locale).format(args));
    expect(rendered.replace(/ | /g, " ")).toBe(expected.replace(/ | /g, " "));
  });
});

describe("catalog lookup", () => {
  it("renders bundled English outside a provider and falls back to the key", () => {
    render(<Probe id="shell:health.degraded" values={{ count: 2 }} />);
    expect(screen.getByTestId("out").textContent).toBe("2 services in trouble");
    render(<Probe id="shell:does.not.exist" />);
    expect(screen.getAllByTestId("out")[1]?.textContent).toBe("does.not.exist");
  });

  it("uses the server catalog of the user's language", async () => {
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/i18n/context"))
        return json(200, { language: "fr", locale: "fr-FR", time_zone: "Europe/Paris", direction: "ltr" });
      return json(200, { namespace: "shell", language: "fr", messages: { skip: "Aller au contenu" } });
    };
    withProvider(<Probe id="shell:skip" />);
    expect(await screen.findByText("Aller au contenu")).toBeTruthy();
    expect(document.documentElement.lang).toBe("fr");
  });

  it("counts and ordinals follow the messages' language, not the formats' region (issue 232)", async () => {
    fake.handler = (request) => {
      const url = new URL(request.url);
      if (url.pathname.endsWith("/i18n/context"))
        return json(200, { language: "en", locale: "fr-FR", time_zone: "Europe/Paris", direction: "ltr" });
      return json(200, {
        namespace: "shell",
        language: "en",
        messages: { role: "{place, selectordinal, one {#st} two {#nd} few {#rd} other {#th}} role" },
      });
    };
    withProvider(<Probe id="shell:role" values={{ place: 2 }} />);
    expect(await screen.findByText("2nd role")).toBeTruthy();
  });

  it("keeps the last good catalog, then English, when loading fails", async () => {
    window.localStorage.setItem("portalab.i18n.de.shell", JSON.stringify({ skip: "Zum Inhalt springen" }));
    fake.handler = (request) => {
      if (new URL(request.url).pathname.endsWith("/i18n/context"))
        return json(200, { language: "de", locale: "de-DE", time_zone: "UTC", direction: "ltr" });
      return json(503, { code: "unavailable" });
    };
    withProvider(
      <>
        <Probe id="shell:skip" />
        <Probe id="shell:menu" />
      </>,
    );
    expect(await screen.findByText("Zum Inhalt springen")).toBeTruthy();
    expect(screen.getByText("Menu")).toBeTruthy();
  });
});

describe("catalog hygiene", () => {
  const placeholders = (message: string): Set<string> => {
    const names = new Set<string>();
    const visit = (elements: MessageFormatElement[]) => {
      for (const element of elements) {
        if ("value" in element && element.type !== TYPE.literal && typeof element.value === "string")
          names.add(element.value);
        if ("options" in element)
          for (const option of Object.values(element.options) as { value: MessageFormatElement[] }[])
            visit(option.value);
      }
    };
    visit(parse(message));
    return names;
  };

  it("counts use ICU plurals, never concatenation", () => {
    for (const [id, message] of Object.entries(BUNDLED_MESSAGES)) {
      if (/\{count\b/.test(message)) expect(message, id).toMatch(/\{count, plural,/);
    }
  });

  it("French bundles have the same keys and placeholders as English", async () => {
    for (const namespace of Object.keys(BUNDLED)) {
      const fr = (await import(`../../../../backend/locales/fr/${namespace}.json`)).default as Record<
        string,
        string
      >;
      const en = BUNDLED[namespace] as Record<string, string>;
      expect(Object.keys(fr).sort(), namespace).toEqual(Object.keys(en).sort());
      for (const [key, message] of Object.entries(en)) {
        expect(placeholders(fr[key] ?? ""), `${namespace}:${key}`).toEqual(placeholders(message));
      }
    }
  });

  it("pseudo-locales keep ICU syntax intact", () => {
    const source = "{count, plural, one {# item} other {# items}} for {name}";
    const pseudo = pseudoMessage(source, "en-XA");
    expect(pseudo).toBe("[{count,plural,one{# îtém} other{# îtéms}} för {name} ~~~]");
    expect(String(new IntlMessageFormat(pseudo, "en").format({ count: 2, name: "Alex" }))).toContain("2");
    expect(pseudoMessage("Hello", "ar-XB").startsWith("‮")).toBe(true);
  });
});
