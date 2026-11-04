/**
 * Where the stack under test runs and who signs in. The defaults match the
 * dev servers (npm run dev in each app, backend on :5000); CI points them at
 * the Compose stack.
 *
 * E2E_WORKERS runs that many Playwright workers in parallel, each with its
 * own club and account so no test sees another one's changes (sidebar
 * favourites, club settings, list contents). Worker 1 uses E2E_CLUB and
 * E2E_EMAIL as they are, worker n the club `<E2E_CLUB>-n` and the account
 * `<name>-n@<domain>`, all with E2E_PASSWORD. scripts/e2e-accounts.sh makes
 * them on a Compose stack. Pass the worker count as E2E_WORKERS, not
 * --workers, so the accounts and the workers match.
 */
export const APP_URL = process.env.E2E_APP_URL ?? 'http://localhost:5173'
export const MANAGE_URL = process.env.E2E_MANAGE_URL ?? 'http://localhost:5174'
export const SSO_URL = process.env.E2E_SSO_URL ?? 'http://localhost:5175'
export const PASSWORD = process.env.E2E_PASSWORD ?? 'Demo-Passwort-2026!'
export const WORKERS = Math.max(1, Number(process.env.E2E_WORKERS ?? 1) || 1)

const BASE_CLUB = process.env.E2E_CLUB ?? 'demo'
const BASE_EMAIL = process.env.E2E_EMAIL ?? 'admin@demo.test'

/** The club and account of worker `index` (0-based). */
export function accountFor(index: number) {
  if (index === 0) return { club: BASE_CLUB, email: BASE_EMAIL }
  const n = index + 1
  const at = BASE_EMAIL.indexOf('@')
  return {
    club: `${BASE_CLUB}-${n}`,
    email: `${BASE_EMAIL.slice(0, at)}-${n}@${BASE_EMAIL.slice(at + 1)}`,
  }
}

/** The signed-in cookies of worker `index`, written by global-setup.ts. */
export const stateFor = (index: number) => `e2e/.auth/state-${index}.json`

// Playwright sets TEST_PARALLEL_INDEX in each worker (0 .. workers-1) and
// loads the config and this file there again, so these are the worker's own.
const INDEX = Number(process.env.TEST_PARALLEL_INDEX ?? 0)
export const { club: CLUB, email: EMAIL } = accountFor(INDEX)
export const STATE = stateFor(INDEX)

/** A club app path such as `members` as a full URL. */
export const appUrl = (path: string) => `${APP_URL}/${CLUB}/app/${path}`
