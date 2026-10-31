import { useState } from 'react'
import { Button, CopyButton, Group, Modal, Text, TextInput } from '@mantine/core'
import { IconCalendarShare } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { getCalendarFeedUrl, renewCalendarFeedUrl } from '@/api/events'

/** Shows the member's personal calendar feed URL to add in a calendar app. */
export function CalendarSubscribeButton() {
  const { t } = useT()
  const { notify } = useToast()
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [renewing, setRenewing] = useState(false)

  const open = async () => {
    setLoading(true)
    try {
      setUrl(await getCalendarFeedUrl())
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setLoading(false)
    }
  }

  const renew = async () => {
    setRenewing(true)
    try {
      setUrl(await renewCalendarFeedUrl())
      notify(
        'success',
        t('events.subscribe.renew', 'Neuen Link erstellen'),
        t('events.subscribe.renewed', 'Neuer Link erstellt. Der alte funktioniert nicht mehr.'),
      )
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setRenewing(false)
    }
  }

  return (
    <>
      <Button variant="default" onClick={open} loading={loading}>
        <IconCalendarShare size={16} />
        {t('events.subscribe.button', 'Kalender abonnieren')}
      </Button>
      <Modal
        opened={url !== null}
        onClose={() => setUrl(null)}
        title={t('events.subscribe.title', 'Anlässe des Vereins abonnieren')}
        centered
      >
        <Text fz="sm" mb="sm">
          {t(
            'events.subscribe.hint',
            'Füge diese Adresse als Kalenderabo hinzu (Google Kalender: «Per URL», Apple Kalender: «Neues Kalenderabonnement»). Neue und geänderte Anlässe erscheinen dann automatisch. Der Link ist persönlich, gib ihn nicht weiter.',
          )}
        </Text>
        <Group gap="xs" wrap="nowrap">
          <TextInput
            value={url ?? ''}
            readOnly
            style={{ flex: 1 }}
            onFocus={(e) => e.currentTarget.select()}
          />
          <CopyButton value={url ?? ''}>
            {({ copied, copy }) => (
              <Button onClick={copy} variant={copied ? 'light' : 'filled'}>
                {copied
                  ? t('events.subscribe.copied', 'Kopiert')
                  : t('events.subscribe.copy', 'Kopieren')}
              </Button>
            )}
          </CopyButton>
        </Group>
        <Text fz="xs" c="dimmed" mt="md">
          {t(
            'events.subscribe.renewHint',
            'Hast du den Link weitergegeben oder verloren? Ein neuer Link macht den alten ungültig; trage ihn danach in deinem Kalender neu ein.',
          )}
        </Text>
        <Button variant="subtle" size="xs" mt={4} px={0} onClick={renew} loading={renewing}>
          {t('events.subscribe.renew', 'Neuen Link erstellen')}
        </Button>
      </Modal>
    </>
  )
}
