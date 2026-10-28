// In production: VITE_API_BASE points to https://api.vollbuild.ch/api (Traefik → backend)
// In local dev: VITE_API_BASE points to http://localhost:5000/api (direct to Flask)
// VITE_API_BASE can fall back to relative "/api" (Vite proxy or Caddy proxy)
export const BASE = (import.meta.env.VITE_API_BASE ?? "/api") + "/v1";

export const SSO_URL = import.meta.env.VITE_SSO_URL ?? "https://sso.vollbuild.ch";

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
  for (const name of ["csrf_access_token", "csrf_refresh_token"]) {
    document.cookie = `${name}=; Max-Age=0; path=/`;
    document.cookie = `${name}=; Max-Age=0; path=/; domain=.vollbuild.ch`;
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
    try {
      const body = await res.json();
      message = body.message ?? body.error ?? message;
    } catch {
      /* ignore */
    }
    throw Object.assign(new Error(message), { status: res.status });
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
    try {
      const body = await res.json();
      message = body.message ?? body.error ?? message;
    } catch {
      /* ignore */
    }
    throw Object.assign(new Error(message), { status: res.status });
  }

  return res;
}
