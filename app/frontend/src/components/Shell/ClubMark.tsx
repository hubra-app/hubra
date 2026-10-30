import { Group, Text } from '@mantine/core'
import { useClubLogo, useClubProfile } from '@/data/clubProfile'

/**
 * The club's logo and name, or the Hubra mark while the club has no logo.
 * `nameFrom` hides the name below that breakpoint (the phone top bar).
 */
export function ClubMark({ nameFrom }: { nameFrom?: 'xs' }) {
  const { data: club } = useClubProfile()
  const logo = useClubLogo()
  const nameClass = nameFrom ? `mantine-visible-from-${nameFrom}` : undefined

  if (!logo) {
    return (
      <Group gap={8} wrap="nowrap" style={{ flexShrink: 0 }}>
        <div className="logo-mark" />
        <Text fz={22} className={['wordmark', nameClass].filter(Boolean).join(' ')}>
          hubra
        </Text>
      </Group>
    )
  }
  return (
    <Group gap={10} wrap="nowrap" style={{ flexShrink: 1, minWidth: 0, maxWidth: 280 }}>
      <img src={logo} alt="" className="club-logo" />
      <Text fz="lg" fw={700} truncate className={nameClass}>
        {club?.club_name}
      </Text>
    </Group>
  )
}
