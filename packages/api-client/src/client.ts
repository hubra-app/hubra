// In production: VITE_API_BASE points to https://api.hubra.club/api (Traefik → backend)
// In local dev: VITE_API_BASE points to http://localhost:5000/api (direct to Flask)
// VITE_API_BASE can fall back to relative "/api" (Vite proxy or Caddy proxy)
import { localizeError } from "./errors";

export const BASE = (import.meta.env.VITE_API_BASE ?? "/api") + "/v1";

export const SSO_URL = import.meta.env.VITE_SSO_URL ?? "https://sso.hubra.club";

/** Where the SSO portal is, from GET /instance (public, no auth). */
export interface InstanceInfo {
  ssoUrl: string | null;
}

export async function getInstance(signal?: AbortSignal): Promise<InstanceInfo> {
  const res = await fetch(`${BASE}/instance`, { credentials: "include", signal });
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
  return res.json() as Promise<InstanceInfo>;
}

export function getCookie(name: string): string {
  return (
    document.cookie
      .split("; ")
      .find((r) => r.startsWith(`${name}=`))
      ?.split("=")[1] ?? ""
  );
}

/** True if the CSRF access cookie is present — proxy for "session exists". */
export function hasTokens(): boolean {
  return !!getCookie("csrf_access_token");
}

/** Read the remembered email cookie (set on login, 30-day max-age). */
export function getRememberedEmail(): string {
  return getCookie("remembered_email");
}

/** Clear auth cookies client-side and call the logout endpoint.
 *
 * The CSRF cookies (csrf_access_token, csrf_refresh_token) are JS-readable
 * (flask-jwt-extended double-submit pattern) so we expire them synchronously
 * — hasTokens() immediately returns false even when navigation aborts the
 * fire-and-forget server logout fetch. The HttpOnly JWT cookies are cleared
 * server-side by the /auth/logout call.
 */
export function clearTokens(): void {
  // JWT_COOKIE_DOMAIN is the parent of the app hosts (.hubra.club for
  // app.hubra.club), so expire the cookies there as well.
  const labels = window.location.hostname.split(".");
  const parentDomain = labels.length > 2 ? labels.slice(1).join(".") : "";
  for (const name of ["csrf_access_token", "csrf_refresh_token"]) {
    document.cookie = `${name}=; Max-Age=0; path=/`;
    if (parentDomain) document.cookie = `${name}=; Max-Age=0; path=/; domain=.${parentDomain}`;
  }
  fetch(`${BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-TOKEN": getCookie("csrf_access_token") },
  }).catch(() => {});
}

let onAuthFailure: (() => void) | null = null;

export function setAuthFailureHandler(handler: (() => void) | null): void {
  onAuthFailure = handler;
}

let _authFailed = false;

let _tenantSlug: string | null = null;

/** Set the active tenant slug — included as X-Tenant-Slug header on all API requests. */
export function setTenantSlug(slug: string | null): void {
  _tenantSlug = slug;
}

export function resetAuthFailure(): void {
  _authFailed = false;
}

const _pendingPromise = new Promise<never>(() => {});

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-TOKEN": getCookie("csrf_refresh_token") },
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  if (_authFailed) return _pendingPromise as Promise<T>;

  const makeReq = () =>
    fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": getCookie("csrf_access_token"),
        ...(_tenantSlug ? { "X-Tenant-Slug": _tenantSlug } : {}),
        ...(init.headers ?? {}),
      },
    });

  let res = await makeReq();

  if (res.status === 401) {
    const refreshed = await refreshAccess();
    if (refreshed) {
      res = await makeReq();
    } else if (!_authFailed && onAuthFailure) {
      _authFailed = true;
      onAuthFailure();
      return _pendingPromise as Promise<T>;
    }
  }

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    let code: string | undefined;
    let details: Record<string, unknown> | undefined;
    try {
      const body = await res.json();
      message = body.message ?? body.error ?? message;
      code = body.error;
      // Per-field problems, e.g. { smtp_port: "must be a number" }.
      if (body.details && typeof body.details === "object") details = body.details;
    } catch {
      /* ignore */
    }
    throw Object.assign(new Error(localizeError(res.status, code, message)), {
      status: res.status,
      code,
      details,
    });
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/**
 * Like apiFetch but returns the raw Response instead of parsed JSON.
 * Uses the same 401 → refresh → retry logic.
 * Does NOT set Content-Type: application/json (lets fetch infer for FormData).
 * Use for blob downloads and FormData uploads.
 */
export async function apiFetchRaw(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  if (_authFailed) return _pendingPromise as unknown as Promise<Response>;

  const makeReq = () =>
    fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "X-CSRF-TOKEN": getCookie("csrf_access_token"),
        ...(_tenantSlug ? { "X-Tenant-Slug": _tenantSlug } : {}),
        ...(init.headers ?? {}),
      },
    });

  let res = await makeReq();

  if (res.status === 401) {
    const refreshed = await refreshAccess();
    if (refreshed) {
      res = await makeReq();
    } else if (!_authFailed && onAuthFailure) {
      _authFailed = true;
      onAuthFailure();
      return _pendingPromise as unknown as Promise<Response>;
    }
  }

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    let code: string | undefined;
    try {
      const body = await res.json();
      message = body.message ?? body.error ?? message;
      code = body.error;
    } catch {
      /* ignore */
    }
    throw Object.assign(new Error(localizeError(res.status, code, message)), {
      status: res.status,
      code,
    });
  }

  return res;
}
