/**
 * Thin fetch wrapper for the Skladchina API.
 *
 * Auth is a same-origin HttpOnly cookie, so requests only need
 * `credentials: "include"` — there is no token to attach by hand. Unsafe methods
 * additionally echo the readable CSRF cookie back in a header; the server rejects
 * the request if the two do not match.
 */

const API_BASE = "/api";

const CSRF_COOKIE = "skladchina_csrf";
const CSRF_HEADER = "X-CSRF-Token";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** 401 means "not signed in", which callers treat as a redirect, not a failure. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return null;
}

export type QueryValue = string | number | boolean | null | undefined;

function buildUrl(path: string, params?: Record<string, QueryValue>): string {
  const url = `${API_BASE}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.append(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; params?: Record<string, QueryValue> } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.body instanceof FormData) {
    // Leave Content-Type unset: the browser fills in the multipart boundary itself.
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.params), {
      method,
      headers,
      body,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "Не удалось связаться с сервером. Проверьте соединение.");
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && typeof (payload as { detail?: unknown }).detail === "string"
        ? (payload as { detail: string }).detail
        : `Запрос не выполнен (${response.status})`;
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, QueryValue>) =>
    request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown, params?: Record<string, QueryValue>) =>
    request<T>("POST", path, { body, params }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export function errorMessage(error: unknown, fallback = "Что-то пошло не так"): string {
  // Only the API speaks the user's language: every other Error carries an
  // English runtime message, so it stays in the console and the user sees the
  // fallback instead.
  if (error instanceof ApiError) return error.detail;
  return fallback;
}
