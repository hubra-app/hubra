import { useT } from '@/locales/i18n'
import type { ContentLanguage } from '@/types'

/** The languages a post can be written in: Switzerland's and English. */
export const CONTENT_LANGUAGES: ContentLanguage[] = ['de', 'fr', 'it', 'en']

export function useLanguageNames(): Record<ContentLanguage, string> {
  const { t } = useT()
  return {
    de: t('content.languages.de', 'Deutsch'),
    fr: t('content.languages.fr', 'Französisch'),
    it: t('content.languages.it', 'Italienisch'),
    en: t('content.languages.en', 'Englisch'),
  }
}
