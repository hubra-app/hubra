import type { Page } from '@playwright/test'
import { CLUB } from './env'

/** Calls the API from the signed-in page, the way the app does. */
export async function api<T = unknown>(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ({ method, path, body, club }) => {
      const csrf = document.cookie.match(/(?:^|; )csrf_access_token=([^;]+)/)?.[1] ?? ''
      const res = await fetch(`/api/v1${path}`, {
        method,
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-TOKEN': decodeURIComponent(csrf),
          'X-Tenant-Slug': club,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${method} ${path}: ${res.status} ${await res.text()}`)
      return res.status === 204 ? null : res.json()
    },
    { method, path, body, club: CLUB },
  ) as Promise<T>
}

/** A name no other run has used. */
export const unique = (prefix: string) => `${prefix} ${Date.now().toString(36)}`
