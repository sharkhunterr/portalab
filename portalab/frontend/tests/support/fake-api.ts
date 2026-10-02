/**
 * Fake backend for component tests. Installed through `vi.hoisted` *before* the API client module is
 * imported, because openapi-fetch captures `fetch`/`Request` when the client is created.
 */
export type Handler = (request: Request) => Response | Promise<Response>;

export interface FakeApi {
  handler: Handler;
  requests: Request[];
}

export function installFakeApi(): FakeApi {
  const state: FakeApi = { handler: () => json(404, {}), requests: [] };
  const NativeRequest = globalThis.Request;
  class AbsoluteRequest extends NativeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      super(typeof input === "string" && input.startsWith("/") ? `http://portal.test${input}` : input, init);
    }
  }
  globalThis.Request = AbsoluteRequest as typeof Request;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof NativeRequest ? input : new AbsoluteRequest(input, init);
    state.requests.push(request);
    return state.handler(request);
  }) as typeof fetch;
  return state;
}

export function json(status: number, body: unknown): Response {
  const type = status >= 400 ? "application/problem+json" : "application/json";
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": type },
  });
}

export const ME = {
  id: "0190f0a0-0000-7000-8000-000000000001",
  login: "alice",
  display_name: "Alice",
  email: null,
  state: "active",
  created_at: "2026-10-01T12:00:00Z",
  verified_at: "2026-10-01T12:00:00Z",
  has_avatar: false,
  onboarding: [],
  deletion_due_at: null,
};
