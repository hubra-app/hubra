import { expect, test } from '@playwright/test'
import { MANAGE_URL, SSO_URL, appUrl } from './env'

// Problem reports and ideas: sent from the account menu, answered in
// manage › Support, ideas on the public roadmap.
test('report a problem, answer it in manage, see the answer', async ({ page }) => {
  const title = `E2E Problem ${Date.now()}`
  await page.goto(appUrl('dashboard'))
  await page.getByTestId('user-card').first().click()
  await page.getByTestId('menu-report-bug').first().click()

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Problem melden').first()).toBeVisible()
  // Empty: says what is missing instead of sending.
  await dialog.getByRole('button', { name: 'Senden' }).click()
  await expect(dialog.getByText('Bitte gib einen kurzen Titel ein.')).toBeVisible()

  await dialog.getByLabel('Titel').fill(title)
  await dialog.getByLabel('Was ist passiert?').fill('Beim Speichern kommt ein Fehler.')
  await dialog.getByLabel('Wie kommt man dahin?').fill('1. Finanzen\n2. Speichern')
  // What goes along is shown before sending.
  await dialog.getByText('Wird mitgeschickt').click()
  await expect(dialog.getByText('Bildschirm:')).toBeVisible()
  await expect(dialog.getByText('/app/dashboard')).toBeVisible()
  await dialog.getByRole('button', { name: 'Senden' }).click()
  await expect(dialog).toHaveCount(0)

  // Staff answer and change the status.
  await page.goto(`${MANAGE_URL}/app/reports`)
  await page.getByText(title).click()
  await expect(page.getByText('Beim Speichern kommt ein Fehler.')).toBeVisible()
  await expect(page.getByText('Browser', { exact: true })).toBeVisible()
  await page.getByPlaceholder('Antwort an die meldende Person …').fill('Danke, ist behoben.')
  await page.getByRole('button', { name: 'Antworten' }).click()
  await page.getByRole('combobox', { name: 'Status' }).click()
  await page.getByRole('option', { name: 'Erledigt' }).click()
  await expect(page.getByText('Erledigt').first()).toBeVisible()

  // The reporter sees the answer and the new status.
  await page.goto(appUrl('feedback'))
  await page.getByText(title).click()
  await expect(page.getByText('Danke, ist behoben.')).toBeVisible()
  await expect(page.getByText('Hubra-Team', { exact: false }).first()).toBeVisible()
})

test('an idea on the roadmap gets votes, also on the public page', async ({ page, browser }) => {
  const title = `E2E Idee ${Date.now()}`
  await page.goto(appUrl('dashboard'))
  await page.getByTestId('user-card').first().click()
  await page.getByTestId('menu-report-feature').first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Titel').fill(title)
  await dialog.getByLabel('Was wünschst du dir?').fill('Etwas Neues')
  await dialog.getByRole('button', { name: 'Senden' }).click()
  await expect(dialog).toHaveCount(0)

  await page.goto(`${MANAGE_URL}/app/reports`)
  await page.getByRole('tab', { name: /Ideen/ }).click()
  await page.getByText(title).click()
  await page.locator('.mantine-Switch-track').click()
  await expect(page.getByRole('switch')).toBeChecked()

  // In the app: the reporter's own vote counts; take it back.
  await page.goto(appUrl('feedback/roadmap'))
  const card = page.locator('.mantine-Paper-root', { hasText: title })
  const vote = card.getByRole('button', { name: /stimmen|zurücknehmen/ })
  await expect(vote).toHaveAttribute('aria-pressed', 'true')
  await vote.click()
  await expect(vote).toHaveAttribute('aria-pressed', 'false')

  // Signed out: the public roadmap shows it, without names.
  const anon = await browser.newContext({ storageState: { cookies: [], origins: [] } })
  const pub = await anon.newPage()
  await pub.goto(`${SSO_URL}/roadmap`)
  await expect(pub.getByText(title)).toBeVisible()
  await expect(pub.getByRole('button', { name: 'Anmelden zum Abstimmen' })).toBeVisible()
  await anon.close()
})
