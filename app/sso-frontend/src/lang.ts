import { createLang } from '@hubra/ui'

export type { Lang } from '@hubra/ui'
export const { setLang, getLang, tr, useLang } = createLang('hubra_sso_language')

/** Names of the three appearance choices, for the theme buttons. */
export function themeLabels(t: (de: string, en: string) => string = tr) {
  return {
    light: t('Hell', 'Light'),
    dark: t('Dunkel', 'Dark'),
    system: t('Wie Gerät', 'Like device'),
  }
}
