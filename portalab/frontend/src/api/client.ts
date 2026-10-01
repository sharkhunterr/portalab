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
    throw new ApiError(response.status, problem.detail ?? problem.title ?? response.statusText, problem.code);
  },
};

export function createApiClient(baseUrl = "") {
  const client = createClient<paths>({ baseUrl, credentials: "include" });
  client.use(problems);
  return client;
}

export const api = createApiClient();
