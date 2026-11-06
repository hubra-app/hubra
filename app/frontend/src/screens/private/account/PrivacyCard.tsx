import { useState } from 'react'
import { Button, Divider, Group, Paper, Stack, Switch, Text, Textarea } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconDownload, IconShieldLock } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { Modal } from '@/components/ui'
import { URL_CLUB } from '@/clubBase'
import { formatDate } from '@/format'
import { qk } from '@/data/keys'
import {
  downloadMyData,
  getMyPrivacy,
  requestMyDeletion,
  setMyPhotoConsent,
} from '@/api/members'

/** Data protection (revDSG): photo consent, a copy of my data, asking for deletion. */
export function PrivacyCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<'photo' | 'download' | 'delete' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [note, setNote] = useState('')
  const { data } = useQuery({ queryKey: qk.account.privacy, queryFn: getMyPrivacy })
  if (!data) return null

  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.error'),
      err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
    )

  const setPhotos = async (on: boolean) => {
    setBusy('photo')
    try {
      queryClient.setQueryData(qk.account.privacy, await setMyPhotoConsent(on))
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  const download = async () => {
    setBusy('download')
    try {
      await downloadMyData(URL_CLUB ?? 'club')
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  const askDeletion = async () => {
    setBusy('delete')
    try {
      queryClient.setQueryData(qk.account.privacy, await requestMyDeletion(note.trim()))
      setConfirming(false)
      notify(
        'success',
        t('account.privacy.deletionSent', 'Löschung beantragt'),
        t('account.privacy.deletionSentMsg', 'Du bekommst innerhalb von 30 Tagen Bescheid.'),
      )
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder data-testid="privacy-card">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconShieldLock size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.privacy.title', 'Datenschutz')}
        </Text>
      </Group>
      <Stack p="md" gap="md">
        <Switch
          label={t('account.privacy.photos', 'Der Verein darf Fotos von mir zeigen')}
          description={
            data.photo_consent === null
              ? t(
                  'account.privacy.photosUnasked',
                  'Noch nicht gewählt. In Galerien, Beiträgen und auf der Website des Vereins.',
                )
              : t(
                  'account.privacy.photosHint',
                  'In Galerien, Beiträgen und auf der Website des Vereins. Du kannst das jederzeit ändern.',
                )
          }
          checked={data.photo_consent === true}
          disabled={busy === 'photo'}
          onChange={(e) => setPhotos(e.currentTarget.checked)}
        />

        <Divider />

        <Group justify="space-between" wrap="wrap" gap="sm">
          <Text fz="sm" c="dimmed" style={{ flex: 1, minWidth: 220 }}>
            {t(
              'account.privacy.exportHint',
              'Alles, was der Verein über dich gespeichert hat, als Datei (JSON): Konto, Mitgliedschaft, Anmeldungen, Rechnungen und mehr.',
            )}
          </Text>
          <Button
            variant="default"
            leftSection={<IconDownload size={16} />}
            onClick={download}
            loading={busy === 'download'}
          >
            {t('account.privacy.export', 'Meine Daten herunterladen')}
          </Button>
        </Group>

        <Divider />

        <Group justify="space-between" wrap="wrap" gap="sm">
          <Text fz="sm" c="dimmed" style={{ flex: 1, minWidth: 220 }}>
            {data.deletion_request
              ? t('account.privacy.deletionPending', {
                  defaultValue:
                    'Du hast am {{date}} die Löschung deiner Daten beantragt. Sie wird bis am {{due}} erledigt.',
                  date: formatDate(data.deletion_request.received_on),
                  due: formatDate(data.deletion_request.due_on),
                })
              : t(
                  'account.privacy.deletionHint',
                  'Du kannst verlangen, dass der Verein deine Daten löscht. Du verlässt dann den Verein; Rechnungen und Buchungen bleiben ohne deinen Namen, weil der Verein seine Bücher aufbewahren muss. Dein Hubra-Konto bleibt.',
                )}
          </Text>
          {!data.deletion_request && (
            <Button variant="light" color="red" onClick={() => setConfirming(true)}>
              {t('account.privacy.deletion', 'Löschung beantragen')}
            </Button>
          )}
        </Group>

        {data.retention_years !== null && (
          <Text fz="xs" c="dimmed">
            {t('account.privacy.retention', {
              defaultValue:
                'Der Verein löscht die Daten ehemaliger Mitglieder {{count}} Jahre nach dem Austritt.',
              count: data.retention_years,
            })}
          </Text>
        )}
      </Stack>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title={t('account.privacy.deletionConfirmTitle', 'Löschung deiner Daten beantragen?')}
        footer={
          <>
            <Button variant="default" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
            <Button color="red" onClick={askDeletion} loading={busy === 'delete'}>
              {t('account.privacy.deletion', 'Löschung beantragen')}
            </Button>
          </>
        }
      >
        <Stack gap="sm">
          <Text fz="sm">
            {t(
              'account.privacy.deletionConfirmBody',
              'Hubra bearbeitet deinen Antrag innerhalb von 30 Tagen. Danach bist du nicht mehr Mitglied, und deine Daten im Verein sind gelöscht. Das lässt sich nicht rückgängig machen.',
            )}
          </Text>
          <Textarea
            label={t('account.privacy.deletionNote', 'Nachricht (freiwillig)')}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
            maxLength={2000}
            autosize
            minRows={2}
          />
        </Stack>
      </Modal>
    </Paper>
  )
}
