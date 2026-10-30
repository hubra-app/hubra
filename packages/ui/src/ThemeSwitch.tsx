import { useEffect } from 'react'
import {
  ActionIcon,
  SegmentedControl,
  useMantineColorScheme,
  type MantineColorScheme,
} from '@mantine/core'
import { readColorScheme } from './colorScheme'
import { IconDeviceDesktop, IconMoon, IconSun } from '@tabler/icons-react'

/** Light, dark or like the device: the same three buttons on every portal. */
export function ThemeSwitch({
  labels,
}: {
  /** Screen-reader names of light, dark and system, in the page's language. */
  labels: { light: string; dark: string; system: string }
}) {
  const { colorScheme, setColorScheme } = useMantineColorScheme()
  return (
    <SegmentedControl
      size="xs"
      value={colorScheme}
      onChange={(v) => setColorScheme(v as MantineColorScheme)}
      data={[
        { value: 'light', label: <IconSun size={14} aria-label={labels.light} /> },
        { value: 'dark', label: <IconMoon size={14} aria-label={labels.dark} /> },
        { value: 'auto', label: <IconDeviceDesktop size={14} aria-label={labels.system} /> },
      ]}
    />
  )
}

const NEXT: Record<MantineColorScheme, MantineColorScheme> = { light: 'dark', dark: 'auto', auto: 'light' }

/** One small button for tight spots (sign-in, join): light → dark → device. */
export function ThemeToggle({
  labels,
}: {
  /** Names of light, dark and system, in the page's language. */
  labels: { light: string; dark: string; system: string }
}) {
  const { colorScheme, setColorScheme } = useMantineColorScheme()
  // Sign-in sets the cookie from the account without a page load: take it
  // over when the next page frame mounts.
  useEffect(() => {
    const saved = readColorScheme()
    if (saved && saved !== colorScheme) setColorScheme(saved)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const name = { light: labels.light, dark: labels.dark, auto: labels.system }[colorScheme]
  const Icon = { light: IconSun, dark: IconMoon, auto: IconDeviceDesktop }[colorScheme]
  return (
    <ActionIcon
      variant="subtle"
      color="gray"
      size={36}
      onClick={() => setColorScheme(NEXT[colorScheme])}
      aria-label={name}
      title={name}
    >
      <Icon size={18} />
    </ActionIcon>
  )
}
