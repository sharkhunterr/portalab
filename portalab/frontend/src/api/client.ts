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
    throw new ApiError(response.status, detail ?? title ?? response.statusText, code, extensions);
  },
};

/** Readable companion of the HttpOnly session cookie (spec 002 research R6, double submit). */
export const CSRF_COOKIE = "__Host-portalab_csrf";
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

const csrf: Middleware = {
  async onRequest({ request }) {
    if (SAFE_METHODS.has(request.method.toUpperCase())) return undefined;
    const token = readCookie(CSRF_COOKIE);
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
