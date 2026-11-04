import { SSO_URL } from '@hubra/api-client'

/** Where the person's own account lives (name, password, two-factor). */
export const ACCOUNT_URL = `${SSO_URL}/account`
/** The club app, for links into a club. */
export const APP_URL = import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club'

/** The SSO sign-in page, coming back to `back` (default: this page). */
export function signInUrl(back: string = window.location.href): string {
  return `${SSO_URL}/login?redirect=${encodeURIComponent(back)}`
}
