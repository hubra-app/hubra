import { describe, expect, it } from 'vitest'
import { getParentPath } from './nav'

describe('getParentPath', () => {
  it('highlights a plugin entry on its own pages', () => {
    const nav = ['/app/dashboard', '/app/members', '/app/inbox']
    expect(getParentPath('/app/inbox', nav)).toBe('/app/inbox')
    expect(getParentPath('/app/inbox/42', nav)).toBe('/app/inbox')
  })

  it('prefers the longest matching sidebar path', () => {
    const nav = ['/app/inventory', '/app/inventory/keys']
    expect(getParentPath('/app/inventory/keys', nav)).toBe('/app/inventory/keys')
    expect(getParentPath('/app/inventory/7', nav)).toBe('/app/inventory')
  })

  it('keeps built-in sub-pages on their entry', () => {
    const nav = ['/app/operations/events', '/app/finance', '/app/account/settings']
    expect(getParentPath('/app/operations/polls', nav)).toBe('/app/operations/events')
    expect(getParentPath('/app/finance/invoices/3', nav)).toBe('/app/finance')
    expect(getParentPath('/app/account', nav)).toBe('/app/account/settings')
  })

  it('falls back to the dashboard for unknown pages', () => {
    expect(getParentPath('/app/inbox')).toBe('/app/dashboard')
    expect(getParentPath('/app/inboxes', ['/app/inbox'])).toBe('/app/dashboard')
  })
})
