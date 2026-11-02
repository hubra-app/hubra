import { expect, test, type BrowserContext, type CDPSession, type Page } from '@playwright/test'
import { MANAGE_URL, PASSWORD, SSO_URL } from './env'

// Manage's "Passwort bestätigen" dialog offers a passkey to accounts that
// have one. Passkeys belong to the SSO portal's address, so the passkey part
// runs on SSO /confirm in a small window; manage notices the confirmation
// and runs the action again. A Chrome virtual authenticator plays the
// person's device. The test adds a passkey to the e2e account and removes it
// at the end, so the account signs in with the password only afterwards.

const PASSKEY_NAME = 'E2E-Passkey'

async function virtualAuthenticator(context: BrowserContext, page: Page) {
  const cdp: CDPSession = await context.newCDPSession(page)
  await cdp.send('WebAuthn.enable')
  const { authenticatorId } = await cdp.send('WebAuthn.addVirtualAuthenticator', {
    options: {
      protocol: 'ctap2',
      transport: 'internal',
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  })
  return { cdp, authenticatorId }
}

async function removePasskey(page: Page) {
  await page.goto(`${SSO_URL}/account/zwei-faktor`)
  const row = page.getByText(PASSKEY_NAME, { exact: true })
  if (!(await row.isVisible().catch(() => false))) return
  await page.getByRole('button', { name: 'Entfernen' }).first().click()
  await page.getByLabel('Aktuelles Passwort').fill(PASSWORD)
  await page.getByRole('button', { name: new RegExp(`${PASSKEY_NAME}.*entfernen`) }).click()
  await expect(page.getByText(PASSKEY_NAME, { exact: true })).toHaveCount(0)
}

// Whatever happens in the test: the account goes back to password only.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await removePasskey(page)
})

test('a platform action can be confirmed with a passkey instead of the password', async ({
  context,
  page,
}) => {
  test.setTimeout(90_000)
  const device = await virtualAuthenticator(context, page)

  // A passkey on the account (SSO › Konto › Zwei-Faktor).
  await page.goto(`${SSO_URL}/account/zwei-faktor`)
  await page.getByRole('button', { name: 'Passkey hinzufügen' }).click()
  await page.getByLabel('Name').fill(PASSKEY_NAME)
  await page.getByLabel('Aktuelles Passwort').fill(PASSWORD)
  await page.getByRole('button', { name: 'Weiter' }).click()
  // The first second step hands out recovery codes first.
  await page.getByRole('button', { name: 'Ich habe sie gesichert' }).click()
  await expect(page.getByText(PASSKEY_NAME, { exact: true })).toBeVisible()

  // The popup gets its own virtual authenticator holding this passkey.
  const { credentials } = await device.cdp.send('WebAuthn.getCredentials', {
    authenticatorId: device.authenticatorId,
  })
  expect(credentials).toHaveLength(1)

  // The e2e stack does not enforce the step-up, so the first change of
  // the update mode is answered as if it did.
  let refused = false
  await page.route('**/api/v1/manager/plugins/updates', async (route) => {
    if (route.request().method() === 'PUT' && !refused) {
      refused = true
      await route.fulfill({
        status: 403,
        json: { error: 'STEP_UP_REQUIRED', message: 'Confirm your password to do this' },
      })
      return
    }
    await route.continue()
  })

  // The mode as the server has it (the select shows a default before that).
  const catalogue = page.waitForResponse(
    (r) => r.url().endsWith('/api/v1/manager/plugins/') && r.request().method() === 'GET',
  )
  await page.goto(`${MANAGE_URL}/app/plugins`)
  const { updateMode } = (await (await catalogue).json()) as { updateMode: string }
  const labels: Record<string, string> = {
    notify: 'Updates: nur melden',
    official: 'Updates: offizielle installieren',
    off: 'Updates: nicht prüfen',
  }
  const before = labels[updateMode]
  // A confirmation from an earlier run holds ten minutes; manage would then
  // (rightly) close the dialog at once.
  const open = await page.evaluate(async () => {
    const res = await fetch('/api/v1/account/step-up', { credentials: 'include' })
    return (await res.json()).sudoUntil as string | null
  })
  test.skip(!!open, 'this sign-in is still confirmed from an earlier run')
  const mode = page.getByRole('combobox', { name: 'Updates' })
  await expect(mode).toHaveValue(before)
  await mode.click()
  const next = before === 'Updates: nur melden' ? 'Updates: nicht prüfen' : 'Updates: nur melden'
  await page.getByRole('option', { name: next }).click()

  const dialog = page.getByRole('dialog', { name: 'Aktion bestätigen' })
  await expect(dialog).toBeVisible()
  // The password stays the fallback.
  await expect(dialog.getByLabel('Passwort')).toBeVisible()

  const popupOpened = context.waitForEvent('page')
  await dialog.getByRole('button', { name: 'Mit Passkey bestätigen' }).click()
  const popup = await popupOpened
  const other = await virtualAuthenticator(context, popup)
  await other.cdp.send('WebAuthn.addCredential', {
    authenticatorId: other.authenticatorId,
    credential: credentials[0],
  })
  await popup.waitForURL(`${SSO_URL}/confirm`)
  await expect(popup.getByRole('heading', { name: 'Aktion bestätigen' })).toBeVisible()
  await popup.getByRole('button', { name: 'Mit Passkey bestätigen' }).click()

  // Manage sees the confirmation, closes the dialog and runs the change.
  await expect(dialog).toBeHidden({ timeout: 15_000 })
  await expect(mode).toHaveValue(next)
  const status = await page.evaluate(async () => {
    const res = await fetch('/api/v1/account/step-up', { credentials: 'include' })
    return res.json()
  })
  expect(status.passkey).toBe(true)
  expect(status.sudoUntil).toBeTruthy()

  // Back to how it was (the window is open now, so no dialog).
  await mode.click()
  await page.getByRole('option', { name: before }).click()
  await expect(mode).toHaveValue(before)
})
