import type { Page } from '@playwright/test'
import { APP_URL, CLUB } from './env'

/**
 * Calls the API as the signed-in user, with the page's cookies and the
 * headers the app sends. It goes through the browser context rather than
 * the page, so a reload in between does not cut it off.
 */
export async function api<T = unknown>(page: Page, method: string, path: string, body?: unknown) {
  const cookies = await page.context().cookies(APP_URL)
  const csrf = cookies.find((c) => c.name === 'csrf_access_token')?.value ?? ''
  const res = await page.request.fetch(`${APP_URL}/api/v1${path}`, {
    method,
    headers: {
      'X-CSRF-TOKEN': decodeURIComponent(csrf),
      'X-Tenant-Slug': CLUB,
    },
    data: body,
  })
  if (!res.ok()) throw new Error(`${method} ${path}: ${res.status()} ${await res.text()}`)
  return (res.status() === 204 ? null : await res.json()) as T
}

/** A name no other run has used. */
export const unique = (prefix: string) => `${prefix} ${Date.now().toString(36)}`
