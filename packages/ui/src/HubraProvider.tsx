import type { MantineThemeOverride } from '@mantine/core'
import { BnbProvider, type Locale, type Translate } from '@bitsandbricks/ui'
import type { ReactNode } from 'react'
import { colorSchemeManager } from './colorScheme'
import { theme as hubraVioletTheme } from './theme'

/**
 * The shared BitsAndBricks provider with what every Hubra portal adds: the
 * Hubra theme (or the club's), the shared light/dark cookie, and the
 * portal's language for the shared components' words. It also renders
 * Mantine's toasts at the bottom right.
 */
export function HubraProvider({
  theme = hubraVioletTheme,
  locale,
  translate,
  children,
}: {
  theme?: MantineThemeOverride
  locale: Locale
  /** The app's own texts first (the club app's i18next). */
  translate?: Translate
  children: ReactNode
}) {
  return (
    <BnbProvider
      theme={theme}
      locale={locale}
      translate={translate}
      colorSchemeManager={colorSchemeManager}
      defaultColorScheme="auto"
    >
      {children}
    </BnbProvider>
  )
}
