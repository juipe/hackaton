/**
 * Network stubbing. The suite never opens a socket: `stubFetch` replaces the
 * global with a mock the test controls, and `setup.ts` restores the original
 * after every test.
 */

import { vi, type Mock } from "vitest";

export type FetchHandler = (
  url: string,
  init: RequestInit | undefined,
) => Response | Promise<Response>;

export type FetchMock = Mock<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>;

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/** Install a `fetch` that answers from `handler`. Returns the mock for assertions. */
export function stubFetch(handler: FetchHandler): FetchMock {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(urlOf(input), init),
  ) as FetchMock;
  vi.stubGlobal("fetch", mock);
  return mock;
}

/** A `fetch` reply carrying a JSON body. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The `{ detail }` error envelope every failing endpoint returns. */
export function errorResponse(status: number, detail: string): Response {
  return jsonResponse({ detail }, status);
}

/** A 204, which the API client maps to `undefined`. */
export function emptyResponse(status = 204): Response {
  return new Response(null, { status });
}

/** The URLs a fetch mock was called with, in order. */
export function requestedUrls(mock: FetchMock): string[] {
  return mock.mock.calls.map(([input]) => urlOf(input));
}
