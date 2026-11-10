import { apiFetch } from '@hubra/api-client'

/**
 * Risky club actions (bank details, deleting a member for good, giving admin
 * rights) need a freshly confirmed sign-in: the backend answers 403
 * STEP_UP_REQUIRED otherwise (account_token.ensure_club_step_up).
 * `withStepUp` wraps such a call: on that error it opens the confirm dialog
 * (StepUpDialog, mounted in the shell) and runs the call again.
 */

let handler: (() => Promise<boolean>) | null = null

export function setStepUpHandler(h: (() => Promise<boolean>) | null): void {
  handler = h
}

export async function withStepUp<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn()
  } catch (err) {
    const code = (err as { code?: string } | null)?.code
    if (code === 'STEP_UP_REQUIRED' && handler && (await handler())) {
      return await fn()
    }
    throw err
  }
}

export interface StepUpStatus {
  /** Until when this sign-in counts as confirmed, or null. */
  sudoUntil: string | null
  /** The account has a passkey: it can confirm on the SSO portal. */
  passkey: boolean
  /** The account has the authenticator app on. */
  code: boolean
}

export async function getStepUpStatus(): Promise<StepUpStatus> {
  return apiFetch<StepUpStatus>('/global/auth/step-up')
}

/** Confirm the password (and the 2FA code, when set up) for ten minutes. */
export async function stepUp(password: string, code?: string): Promise<void> {
  await apiFetch('/global/auth/step-up', {
    method: 'POST',
    body: JSON.stringify(code ? { password, code } : { password }),
  })
}

/** Passkeys belong to the SSO portal's address: the confirmation runs there,
 * in a small window, and counts for this same sign-in. */
export function openPasskeyConfirm(ssoUrl: string): Window | null {
  const w = 480
  const h = 640
  const left = Math.max(0, window.screenX + (window.outerWidth - w) / 2)
  const top = Math.max(0, window.screenY + (window.outerHeight - h) / 3)
  return window.open(
    `${ssoUrl}/confirm`,
    'hubra-confirm',
    `popup,width=${w},height=${h},left=${Math.round(left)},top=${Math.round(top)}`,
  )
}

/** Sent by the SSO page to its opener when it confirmed. */
export const STEP_UP_MESSAGE = 'hubra:step-up'
