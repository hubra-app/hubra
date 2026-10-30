import { useMemo } from 'react'
import { MantineProvider } from '@mantine/core'
import { colorSchemeManager, cssVariablesResolver, theme } from '@hubra/ui'
import { brandTheme, useClubColors } from '@/branding'

// The club's colours replace Hubra violet once they are known (branding.ts).
export function BrandedMantineProvider({ children }: { children: React.ReactNode }) {
  const colors = useClubColors()
  const branded = useMemo(() => brandTheme(theme, colors), [colors])
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
