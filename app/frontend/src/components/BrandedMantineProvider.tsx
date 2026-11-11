import { useMemo } from 'react'
import { MantineProvider, mergeThemeOverrides } from '@mantine/core'
import { colorSchemeManager, cssVariablesResolver, theme } from '@hubra/ui'
import { brandTheme, useClubColors } from '@/branding'
import { useT } from '@/locales/i18n'

// The club's colours replace Hubra violet once they are known (branding.ts).
export function BrandedMantineProvider({ children }: { children: React.ReactNode }) {
  const colors = useClubColors()
  const { t } = useT()
  const noResults = t('common.noResults', 'Keine Ergebnisse.')
  const branded = useMemo(
    () =>
      mergeThemeOverrides(brandTheme(theme, colors), {
        // A search in a dropdown that finds nothing says so instead of
        // showing an empty box; plugins get this too.
        components: {
          Select: { defaultProps: { nothingFoundMessage: noResults } },
          MultiSelect: { defaultProps: { nothingFoundMessage: noResults } },
        },
      }),
    [colors, noResults],
  )
  return (
    <MantineProvider
      theme={branded}
      cssVariablesResolver={cssVariablesResolver}
      colorSchemeManager={colorSchemeManager}
      defaultColorScheme="auto"
    >
      {children}
    </MantineProvider>
  )
}
