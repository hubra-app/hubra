/**
 * The last API calls of this page load, for "Problem melden": the report
 * sends them along so Hubra staff can jump from a case to the request's log
 * lines and error group (X-Request-ID). Only the method, the path without
 * its query (no search terms), the status, the time and an error code are
 * kept, in memory, never stored.
 */
export interface RecentRequest {
  id: string;
  method: string;
  path: string;
  status: number;
  at: string;
  code?: string;
}

const MAX = 10;
const recent: RecentRequest[] = [];

/** Keeps one finished call (only when the backend sent a request id). */
export function noteRequest(res: Response, method: string | undefined, path: string, code?: string): void {
  const id = res.headers.get("X-Request-ID");
  if (!id) return;
  recent.push({
    id,
    method: (method ?? "GET").toUpperCase(),
    path: path.split("?", 1)[0].split("#", 1)[0].slice(0, 200),
    status: res.status,
    at: new Date().toISOString(),
    ...(code ? { code } : {}),
  });
  if (recent.length > MAX) recent.splice(0, recent.length - MAX);
}

/** The last calls, oldest first. */
export function recentRequests(): RecentRequest[] {
  return recent.map((r) => ({ ...r }));
}
