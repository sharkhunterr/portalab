import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// 002 T049 — auth screens: non-enumerating messages, focus on errors, CSRF header, gate behaviour.

const fake = vi.hoisted(() => {
  const state = {
    handler: (_: Request): Response | Promise<Response> => new Response(null, { status: 404 }),
    requests: [] as Request[],
  };
  return state;
});

vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler, set: (h) => (fake.handler = h) });
  installed.requests = fake.requests;
  return importOriginal();
});

import { readCookie } from "../../src/api/client";
import { AuthGate, LoginForm, loginErrorMessage, VerifyForm } from "../../src/features/auth";
import { ApiError } from "../../src/state/regions";
import { json, ME } from "../support/fake-api";

function withClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const INVALID = { code: "auth.invalid_credentials", title: "Invalid credentials", status: 401 };

beforeEach(() => {
  fake.requests.length = 0;
  fake.handler = () => json(404, {});
});

describe("loginErrorMessage", () => {
  it("never distinguishes unknown logins from wrong passwords", () => {
    expect(loginErrorMessage(new ApiError(401, "x", "auth.invalid_credentials"))).toBe(
      "The login or password is incorrect.",
    );
    expect(loginErrorMessage(new ApiError(401, "anything"))).toBe("The login or password is incorrect.");
  });

  it("explains throttling and pending deletion", () => {
    expect(loginErrorMessage(new ApiError(429, "x", "auth.throttled", { retry_after_seconds: 8 }))).toContain(
      "8 seconds",
    );
    const pending = new ApiError(403, "x", "auth.account_unavailable", {
      deletion_cancellable_until: "2026-11-01T00:00:00Z",
    });
    expect(loginErrorMessage(pending)).toContain("scheduled for deletion");
  });
});

describe("readCookie", () => {
  it("reads one cookie among several", () => {
    expect(readCookie("b", "a=1; b=two%20words; c=3")).toBe("two words");
    expect(readCookie("z", "a=1")).toBeUndefined();
  });
});

describe("LoginForm", () => {
  it("shows the generic error, focused, after a failed sign-in", async () => {
    fake.handler = () => json(401, INVALID);
    render(withClient(<LoginForm />));
    fireEvent.change(screen.getByLabelText("Login"), { target: { value: "ghost" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The login or password is incorrect.");
    await waitFor(() => expect(alert).toHaveFocus());
  });

  it("offers to cancel a pending deletion after valid credentials", async () => {
    fake.handler = (request) =>
      request.url.endsWith("/auth/login")
        ? json(403, { code: "auth.account_unavailable", deletion_cancellable_until: "2026-11-01T00:00:00Z" })
        : json(204, null);
    render(withClient(<LoginForm />));
    fireEvent.change(screen.getByLabelText("Login"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel the deletion" }));
    expect(await screen.findByRole("status")).toHaveTextContent("The deletion was cancelled");
    expect(fake.requests.at(-1)?.url).toContain("/api/v1/auth/deletion/cancel");
  });
});

describe("CSRF", () => {
  it("sends the CSRF header on unsafe methods only", async () => {
    // jsdom refuses __Host- cookies outside a secure context, so the cookie jar is stubbed
    const cookie = vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-portalab_csrf=abc123");
    fake.handler = () => json(400, { code: "auth.invalid_token" });
    render(withClient(<VerifyForm initialToken="0123456789abcdef0123" />));
    fireEvent.click(screen.getByRole("button", { name: "Activate" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(fake.requests.at(-1)?.headers.get("X-CSRF-Token")).toBe("abc123");
    cookie.mockRestore();
  });
});

describe("AuthGate", () => {
  it("shows the sign-in form to anonymous visitors", async () => {
    fake.handler = () => json(401, { code: "unauthorized" });
    render(withClient(<AuthGate location={{ pathname: "/", search: "" }}>{() => <p>portal</p>}</AuthGate>));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("portal")).not.toBeInTheDocument();
  });

  it("renders the portal for a signed-in user", async () => {
    fake.handler = () => json(200, ME);
    render(
      withClient(
        <AuthGate location={{ pathname: "/", search: "" }}>
          {(me) => <p>hello {me.display_name}</p>}
        </AuthGate>,
      ),
    );
    expect(await screen.findByText("hello Alice")).toBeInTheDocument();
  });

  it("routes /verify links to the activation form with the token prefilled", () => {
    render(
      withClient(
        <AuthGate location={{ pathname: "/verify", search: "?token=abcdefabcdefabcdef12" }}>
          {() => null}
        </AuthGate>,
      ),
    );
    expect(screen.getByLabelText("Activation code")).toHaveValue("abcdefabcdefabcdef12");
  });

  it("shows the unavailable state when the API is down", async () => {
    fake.handler = () => json(503, { code: "auth.unavailable" });
    render(withClient(<AuthGate location={{ pathname: "/", search: "" }}>{() => <p>portal</p>}</AuthGate>));
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
  });
});
