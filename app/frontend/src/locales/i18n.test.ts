import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/i18n', () => ({
  fetchLanguages: vi.fn(async () => ['de-CH', 'en-GB']),
  reportMissingKeys: vi.fn(async () => ({})),
  fetchTranslations: vi.fn(async () => ({
    // Edited text: wins over the built-in one.
    'common.save': 'Sichern',
    // A row whose text is its own key.
    'common.cancel': 'common.cancel',
    // An old text over a group of built-in texts.
    'members.detail': 'Details',
    // An old child under a built-in text.
    'common.close.now': 'Jetzt schliessen',
    // A text the app doesn't ship.
    'custom.greeting': 'Grüezi',
  })),
}))

const { default: i18n, loadTranslationsFromApi } = await import('./i18n')

describe('loadTranslationsFromApi', () => {
  it('takes the API texts but never lets a broken row hide built-in ones', async () => {
    await i18n.changeLanguage('de-CH')
    await loadTranslationsFromApi('de-CH')

    expect(i18n.t('common.save')).toBe('Sichern')
    expect(i18n.t('custom.greeting')).toBe('Grüezi')
    expect(i18n.t('common.cancel')).toBe('Abbrechen')
    expect(i18n.t('members.detail.overview')).toBe('Übersicht')
    expect(i18n.t('common.close')).toBe('Schliessen')
  })
})
