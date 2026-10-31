import { expect, test } from '@playwright/test'
import { api, unique } from './api'
import { EMAIL, appUrl } from './env'

type BackendMember = { id: number; email: string | null }

test('the member page shows contact, membership, functions, invoices and activity', async ({
  page,
}) => {
  await page.goto(appUrl('members'))
  const { data } = await api<{ data: BackendMember[] }>(
    page,
    'GET',
    `/members?search=${encodeURIComponent(EMAIL)}`,
  )
  const me = data.find((m) => m.email === EMAIL)!
  expect(me).toBeTruthy()

  // Something to show: a function the member holds and an open invoice.
  const fnName = unique('E2E Funktion')
  const fn = await api<{ id: number }>(page, 'POST', '/functions/', { name: fnName, maxHolders: 1 })
  await api(page, 'POST', `/functions/${fn.id}/holders`, { memberId: me.id })
  const today = new Date().toISOString().slice(0, 10)
  const description = unique('E2E Rechnung')
  const invoice = await api<{ id: number }>(page, 'POST', '/finance/invoices', {
    member_id: me.id,
    issued: today,
    due: today,
    amount: 42.5,
    purpose: 'other',
    description,
  })

  try {
    await page.goto(appUrl(`members/${me.id}`))

    // The header: the function as a badge and the key figures.
    await expect(page.getByText(fnName).first()).toBeVisible()
    const facts = page.getByTestId('member-facts')
    await expect(facts.getByText('Beigetreten')).toBeVisible()
    await expect(facts.getByText('Offen')).toBeVisible()

    // The cards beside the tabs, and nothing left that says "coming soon".
    for (const title of ['Kontakt', 'Mitgliedschaft']) {
      await expect(page.getByText(title, { exact: true })).toBeVisible()
    }
    await expect(page.getByRole('link', { name: 'E-Mail schreiben' })).toHaveAttribute(
      'href',
      `mailto:${EMAIL}`,
    )
    await expect(page.getByText(/folgt bald/)).toHaveCount(0)

    // The member's invoices, each one leading to its detail page.
    await page.getByRole('tab', { name: 'Zahlungen' }).click()
    const row = page.getByTestId('member-invoices').getByRole('row', { name: new RegExp(description) })
    await expect(row).toBeVisible()
    await row.click()
    await expect(page).toHaveURL(new RegExp(`/finance/invoices/${invoice.id}$`))

    // What the member did, from the audit log.
    await page.goBack()
    await page.getByRole('tab', { name: 'Aktivität' }).click()
    await expect(page.getByTestId('member-activity').getByText(fnName).first()).toBeVisible()
  } finally {
    await api(page, 'DELETE', `/finance/invoices/${invoice.id}`)
    await api(page, 'DELETE', `/functions/${fn.id}`)
  }
})

test('the member page fits a phone', async ({ browser }) => {
  const context = await browser.newContext({
    storageState: 'e2e/.auth/state.json',
    viewport: { width: 360, height: 740 },
  })
  const page = await context.newPage()
  await page.goto(appUrl('members'))
  const { data } = await api<{ data: BackendMember[] }>(
    page,
    'GET',
    `/members?search=${encodeURIComponent(EMAIL)}`,
  )
  await page.goto(appUrl(`members/${data[0].id}`))
  await expect(page.getByText('Kontakt', { exact: true })).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
  await context.close()
})
