import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Issue 408 — « Two-step verification » on the account page: the password asked again, the QR code, a first
// code turns it on and the recovery codes are shown once; once on, new codes or turning it off.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null, { status: 404 }),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { TwoFactorSection } from "../../src/features/auth/TwoFactorSection";
import { json } from "../support/fake-api";

const CODES = Array.from({ length: 10 }, (_, i) => `aaaa${i}-bbbbb`);

function show(hasPassword = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <TwoFactorSection hasPassword={hasPassword} />
    </QueryClientProvider>,
  );
}

let enabled = false;
const sent: { path: string; body: unknown }[] = [];

beforeEach(() => {
  enabled = false;
  sent.length = 0;
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (request.method === "POST") sent.push({ path, body: await request.json().catch(() => null) });
    if (path === "/api/v1/me/mfa") return json(200, { enabled, recovery_codes_left: enabled ? 10 : 0 });
    if (path === "/api/v1/me/mfa/setup") {
      const { password } = (sent.at(-1)?.body ?? {}) as { password?: string };
      return password === "right"
        ? json(200, { secret: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", uri: "otpauth://totp/x", qr_svg: "<svg/>" })
        : json(422, { code: "identity.password_current_wrong", title: "x", status: 422 });
    }
    if (path === "/api/v1/me/mfa/confirm") {
      enabled = true;
      return json(200, { codes: CODES });
    }
    if (path === "/api/v1/me/mfa/off") {
      enabled = false;
      return new Response(null, { status: 204 });
    }
    return json(404, {});
  };
});

describe("two-step verification", () => {
  it("turns on: password, QR code, a first code, then the recovery codes once", async () => {
    show();
    const password = await screen.findByLabelText(/Your password|twoFactor.password/);
    fireEvent.change(password, { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /Turn on|twoFactor.start/ }));
    expect(await screen.findByText(/password is not right|wrongPassword/)).toBeTruthy();

    fireEvent.change(password, { target: { value: "right" } });
    fireEvent.click(screen.getByRole("button", { name: /Turn on|twoFactor.start/ }));
    const qr = await screen.findByRole("img", { name: /QR code|qrAlt/ });
    expect(qr.getAttribute("src")).toMatch(/^data:image\/svg\+xml/);
    expect(screen.getByText("JBSW Y3DP EHPK 3PXP JBSW Y3DP EHPK 3PXP")).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/Code from the app|twoFactor.code/), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Confirm and turn on|twoFactor.confirm/ }));
    const list = await screen.findByRole("list", { name: /recovery codes|codesTitle/ });
    expect(list.querySelectorAll("li")).toHaveLength(10);
    expect(sent.map((s) => s.path)).toEqual([
      "/api/v1/me/mfa/setup",
      "/api/v1/me/mfa/setup",
      "/api/v1/me/mfa/confirm",
    ]);

    fireEvent.click(screen.getByRole("button", { name: /I kept them|codesDone/ }));
    expect(await screen.findByText(/10 recovery codes left|twoFactor.left/)).toBeTruthy();
  });

  it("turns off with the password and a code", async () => {
    enabled = true;
    show();
    const off = await screen.findByRole("button", { name: /Turn off two-step|twoFactor.off$/ });
    expect(off).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Your password|twoFactor.password/), {
      target: { value: "right" },
    });
    fireEvent.change(screen.getByLabelText(/or a recovery code|offCode/), { target: { value: "123456" } });
    fireEvent.click(off);
    expect(await screen.findByRole("button", { name: /Turn on|twoFactor.start/ })).toBeTruthy();
    expect(sent).toEqual([{ path: "/api/v1/me/mfa/off", body: { password: "right", code: "123456" } }]);
  });

  it("leaves a single sign-on account to its provider", () => {
    show(false);
    expect(screen.getByText(/single sign-on|notLocal/)).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});
