import { apiFetch } from '@hubra/api-client';

/** The most rows the API hands out per page (larger pageSize values are cut). */
export const API_PAGE_SIZE = 100;

interface Page<T> {
  data: T[];
  total: number;
  totalPages: number;
}

/**
 * Fetch up to `limit` rows of a paginated list. Asking for pageSize=1000 in
 * one request only ever returned the first 100 rows, so this asks page by
 * page: the first page, then the rest in parallel.
 */
export async function fetchPages<T>(
  path: string,
  params: URLSearchParams,
  limit: number,
): Promise<{ data: T[]; total: number }> {
  const pageSize = Math.min(limit, API_PAGE_SIZE);
  const url = (page: number) => {
    const qs = new URLSearchParams(params);
    qs.set('page', String(page));
    qs.set('pageSize', String(pageSize));
    return `${path}?${qs}`;
  };
  const first = await apiFetch<Page<T>>(url(1));
  const pages = Math.min(first.totalPages, Math.ceil(limit / pageSize));
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, pages - 1) }, (_, i) => apiFetch<Page<T>>(url(i + 2))),
  );
  const data = [first, ...rest].flatMap((p) => p.data).slice(0, limit);
  return { data, total: first.total };
}
