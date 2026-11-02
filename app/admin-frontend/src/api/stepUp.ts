import { apiFetch } from '@hubra/api-client'

/** The destructive platform actions (plugin installs, restores, key
 * rotation, impersonation) need a freshly confirmed password — the backend
 * answers 403 STEP_UP_REQUIRED otherwise. `withStepUp` wraps such a call:
 * on that error it opens the confirm dialog (registered by StepUpProvider)
 * and runs the call again. */

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

/** Confirm the password (and the 2FA code, when set up) for a few minutes. */
export async function stepUp(password: string, code?: string): Promise<void> {
  await apiFetch('/account/step-up', {
    method: 'POST',
    body: JSON.stringify(code ? { password, code } : { password }),
  })
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
  return apiFetch<StepUpStatus>('/account/step-up')
}

/** Passkeys belong to the SSO portal's address, so manage cannot ask for
 * one itself: the passkey confirmation runs there, in a small window. It
 * counts for the same sign-in, which manage then sees in getStepUpStatus. */
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
