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
