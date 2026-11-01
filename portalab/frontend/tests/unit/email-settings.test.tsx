import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 319: sending e-mails set up in one form, in order — a provider's preset fills the server, its port
// and security; the security follows the port the server expects; a saved password is kept when left empty.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { EmailSettings } from "../../src/features/admin/communication/EmailSettings";
import { json } from "../support/fake-api";

const SETTINGS = [
  { key: "notifications.email.enabled", value: true, source: "global" },
  { key: "notifications.email.from", value: "portail@example.org", source: "global" },
  { key: "notifications.email.portalUrl", value: "", source: "default" },
  { key: "notifications.email.smtp.host", value: "localhost", source: "default" },
  { key: "notifications.email.smtp.port", value: 25, source: "default" },
  { key: "notifications.email.smtp.tls", value: false, source: "default" },
  { key: "notifications.email.smtp.username", value: "", source: "default" },
  { key: "notifications.email.smtp.password", value: null, source: "global" },
];

describe("issue 319 — sending e-mails", () => {
  it("fills the server from a provider and saves it all together", async () => {
    const saved: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/config") return json(200, { settings: SETTINGS });
      if (path === "/api/v1/admin/notifications/email" && request.method === "PUT") {
        saved.push(await request.json());
        return json(200, {});
      }
      return json(404, {});
    };
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <EmailSettings />
      </QueryClientProvider>,
    );
    const provider = await screen.findByLabelText("Provider");
    await waitFor(() =>
      expect((screen.getByLabelText("Server address") as HTMLInputElement).value).toBe("localhost"),
    );
    expect((provider as HTMLSelectElement).value).toBe("local");
    expect(screen.getByText(/A password is saved/)).toBeInTheDocument();
    fireEvent.change(provider, { target: { value: "gmail" } });
    expect((screen.getByLabelText("Server address") as HTMLInputElement).value).toBe("smtp.gmail.com");
    expect((screen.getByLabelText("Port") as HTMLInputElement).value).toBe("587");
    expect((screen.getByLabelText("Security") as HTMLSelectElement).value).toBe("starttls");
    expect(screen.getByText(/app password/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Security"), { target: { value: "ssl" } });
    expect((screen.getByLabelText("Port") as HTMLInputElement).value).toBe("465");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0]).toMatchObject({
      host: "smtp.gmail.com",
      port: 465,
      tls: true,
      password: null,
      enabled: true,
    });
  });

  it("says why a test was refused: the account has no address", async () => {
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/config") return json(200, { settings: SETTINGS });
      if (path === "/api/v1/admin/notifications/email") return json(200, {});
      if (path === "/api/v1/admin/notifications/email/test")
        return json(422, { code: "notifications.no_address", status: 422, title: "No address" });
      return json(404, {});
    };
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <EmailSettings />
      </QueryClientProvider>,
    );
    await screen.findByDisplayValue("localhost"); // the settings are there: sending is on
    fireEvent.click(screen.getByRole("button", { name: /Save and send me a test/ }));
    expect(await screen.findByText(/your account has no e-mail address/)).toBeInTheDocument();
  });
});
