/**
 * Where the stack under test runs and who signs in. The defaults match the
 * dev servers (npm run dev in each app, backend on :5000); CI points them at
 * the Compose stack.
 */
export const APP_URL = process.env.E2E_APP_URL ?? 'http://localhost:5173'
export const MANAGE_URL = process.env.E2E_MANAGE_URL ?? 'http://localhost:5174'
export const SSO_URL = process.env.E2E_SSO_URL ?? 'http://localhost:5175'
export const CLUB = process.env.E2E_CLUB ?? 'demo'
export const EMAIL = process.env.E2E_EMAIL ?? 'admin@demo.test'
export const PASSWORD = process.env.E2E_PASSWORD ?? 'Demo-Passwort-2026!'

export const STATE = 'e2e/.auth/state.json'

/** A club app path such as `members` as a full URL. */
export const appUrl = (path: string) => `${APP_URL}/${CLUB}/app/${path}`
