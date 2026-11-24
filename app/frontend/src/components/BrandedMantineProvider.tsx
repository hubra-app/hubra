import { useMemo } from 'react'
import { mergeThemeOverrides } from '@mantine/core'
import { HubraProvider } from '@hubra/ui'
import i18n from 'i18next'
import { brandTheme, useClubColors } from '@/branding'
import { useT } from '@/locales/i18n'

/** The club app's texts first, for keys it has; the shared texts for the rest.
 *  Unknown keys are not asked of i18next, so they are not reported as missing. */
function translate(key: string, vars?: Record<string, string | number | undefined>) {
  return i18n.exists(key) ? i18n.t(key, vars) : undefined
}

// The club's colours replace Hubra violet once they are known (branding.ts).
export function BrandedMantineProvider({ children }: { children: React.ReactNode }) {
  const colors = useClubColors()
  const { t, i18n: current } = useT()
  const noResults = t('common.noResults', 'Keine Ergebnisse.')
  const branded = useMemo(
    () =>
      mergeThemeOverrides(brandTheme(colors), {
        // A search in a dropdown that finds nothing says so instead of
        // showing an empty box; plugins get this too.
        components: {
          Select: { defaultProps: { nothingFoundMessage: noResults } },
          MultiSelect: { defaultProps: { nothingFoundMessage: noResults } },
        },
      }),
    [colors, noResults],
  )
  // The shared components speak English or German; other club languages get German.
  const locale = current.language.startsWith('en') ? 'en' : 'de'
  return (
    <HubraProvider theme={branded} locale={locale} translate={translate}>
      {children}
    </HubraProvider>
  )
}
