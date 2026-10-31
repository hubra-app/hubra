import { useState } from 'react'
import { CloseButton, Group, Text } from '@mantine/core'
import { IconSpeakerphone } from '@tabler/icons-react'
import { useClubProfile } from '@/data/clubProfile'
import { useT } from '@/locales/i18n'

const DISMISSED_KEY = 'hubra.clubBanner.dismissed'

function readDismissed(): string | null {
  try {
    return sessionStorage.getItem(DISMISSED_KEY)
  } catch {
    return null
  }
}

/**
 * The club's announcement banner (Settings > Verein > Ankündigungsbanner).
 * A member can hide it for the rest of the session; a new text shows again.
 */
export function ClubBanner() {
  const { t } = useT()
  const [dismissed, setDismissed] = useState(readDismissed)
  const { data } = useClubProfile()

  const text = data?.banner
  if (!text || dismissed === text) return null

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISSED_KEY, text)
    } catch {
      // private mode: hide for this page view only
    }
    setDismissed(text)
  }

  return (
    <Group
      role="status"
      gap={10}
      wrap="nowrap"
      px={16}
      py={8}
      style={{
        background: 'var(--hb-notice-bg)',
        borderBottom: '1px solid var(--hb-notice-border)',
      }}
    >
      <IconSpeakerphone size={18} color="var(--mantine-color-gold-text)" style={{ flexShrink: 0 }} />
      <Text fz="sm" fw={500} style={{ flex: 1 }}>
        {text}
      </Text>
      <CloseButton
        size="sm"
        aria-label={t('shell.clubBanner.dismiss', 'Banner ausblenden')}
        onClick={dismiss}
      />
    </Group>
  )
}
