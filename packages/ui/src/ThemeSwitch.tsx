import { ThemeToggle as SharedThemeToggle } from '@bitsandbricks/ui'
import { useSavedColorScheme } from './colorScheme'

/** The shared one-button switch (sign-in, join, support), which also takes
 *  over a scheme that sign-in saved without a page load. */
export function ThemeToggle() {
  useSavedColorScheme()
  return <SharedThemeToggle />
}
