import { Group, Text } from '@mantine/core'
import { useClubLogo, useClubProfile } from '@/data/clubProfile'

/**
 * The club's logo and name, or the Hubra mark while the club has no logo
 * (the phone menu's head; the top bar has the ClubSwitcher).
 */
export function ClubMark() {
  const { data: club } = useClubProfile()
  const logo = useClubLogo()

  if (!logo) {
    return (
      <Group gap={8} wrap="nowrap" style={{ flexShrink: 0 }}>
        <div className="logo-mark" />
        <Text fz={22} className="wordmark">
          hubra
        </Text>
      </Group>
    )
  }
  return (
    <Group gap={10} wrap="nowrap" style={{ flexShrink: 1, minWidth: 0, maxWidth: 280 }}>
      <img src={logo} alt="" className="club-logo" />
      <Text fz="lg" fw={700} truncate>
        {club?.club_name}
      </Text>
    </Group>
  )
}
