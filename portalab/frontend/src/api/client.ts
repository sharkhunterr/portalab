import createClient, { type Middleware } from "openapi-fetch";
import { ApiError } from "../state/regions";
import type { paths } from "./generated/schema";

/**
 * Typed API client generated from the backend OpenAPI contract (`npm run gen:api`). Problem documents
 * (RFC 9457) become {@link ApiError}s carrying the stable `code`, so regions can map them to functional states.
 */

interface ProblemDocument {
  title?: string;
  detail?: string;
  code?: string;
  correlation_id?: string;
  [extension: string]: unknown;
}

const problems: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return undefined;
    let problem: ProblemDocument = {};
    try {
      problem = (await response.clone().json()) as ProblemDocument;
    } catch {
      problem = {};
    }
    const { title, detail, code, ...extensions } = problem;
    if (code === "terms.acceptance_required") {
      globalThis.dispatchEvent?.(new Event("portalab:terms-required")); // 027: the terms sheet comes back
    }
    throw new ApiError(response.status, detail ?? title ?? response.statusText, code, extensions);
  },
};

/** Readable companion of the HttpOnly session cookie (spec 002 research R6, double submit). */
export const CSRF_COOKIE = "__Host-portalab_csrf";
/** issue 395: its name on a portal reached in plain HTTP from the local network (no ``Secure`` cookie there). */
export const PLAIN_CSRF_COOKIE = "portalab_csrf";
export const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function readCookie(
  name: string,
  cookies: string = globalThis.document?.cookie ?? "",
): string | undefined {
  for (const part of cookies.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return undefined;
}

/** The CSRF token of this browser's session, whichever cookie carries it. */
export function csrfToken(cookies: string = globalThis.document?.cookie ?? ""): string | undefined {
  return readCookie(CSRF_COOKIE, cookies) ?? readCookie(PLAIN_CSRF_COOKIE, cookies);
}

const csrf: Middleware = {
  async onRequest({ request }) {
    if (SAFE_METHODS.has(request.method.toUpperCase())) return undefined;
    const token = csrfToken();
    if (token) request.headers.set(CSRF_HEADER, token);
    return request;
  },
};

export function createApiClient(baseUrl = "") {
  const client = createClient<paths>({ baseUrl, credentials: "include" });
  client.use(csrf);
  client.use(problems);
  return client;
}

export const api = createApiClient();
