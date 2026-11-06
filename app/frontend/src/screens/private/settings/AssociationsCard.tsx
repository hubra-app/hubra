import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Checkbox, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core'
import {
  acceptAssociation,
  leaveAssociation,
  listAssociations,
  setAssociationContacts,
  type Association,
} from '@/api/federation'
import { ConfirmModal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { useT } from '@/locales/i18n'

function Invitation({ item, onDone }: { item: Association; onDone: () => Promise<unknown> }) {
  const { t } = useT()
  const { notify } = useToast()
  const [share, setShare] = useState(false)
  const [busy, setBusy] = useState<'accept' | 'decline' | null>(null)

  const run = async (what: 'accept' | 'decline') => {
    setBusy(what)
    try {
      if (what === 'accept') await acceptAssociation(item.id, share)
      else await leaveAssociation(item.id)
      await onDone()
    } catch (err) {
      notify('error', t('associations.failed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder p="md" data-testid="association-invite">
      <Stack gap="xs">
        <Group gap="xs">
          <Text fw={600}>{item.name}</Text>
          <Badge size="sm" variant="light" color="yellow">
            {t('associations.invitation', 'Einladung')}
          </Badge>
        </Group>
        <Text size="sm" c="dimmed">
          {t(
            'associations.inviteText',
            'Lädt euch am {{date}} als Mitgliedverein ein. Der Verband sieht dann, wie viele aktive Mitglieder ihr habt, und ihr seht seine geteilten Anlässe unter Anlässe.',
            { date: formatDate(item.invitedAt) },
          )}
        </Text>
        <Checkbox
          label={t('associations.shareContacts', 'Kontakte unserer Ämter teilen')}
          description={t(
            'associations.shareContactsHint',
            'Name und Vereinsadresse von allen, die ein Amt halten (z. B. Präsidium, Kassier). Private E-Mail-Adressen nie.',
          )}
          checked={share}
          onChange={(e) => setShare(e.currentTarget.checked)}
        />
        <Group gap="xs">
          <Button size="xs" loading={busy === 'accept'} disabled={busy !== null} onClick={() => void run('accept')}>
            {t('associations.accept', 'Beitreten')}
          </Button>
          <Button
            size="xs"
            variant="default"
            loading={busy === 'decline'}
            disabled={busy !== null}
            onClick={() => void run('decline')}
          >
            {t('associations.decline', 'Ablehnen')}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

/** The associations (Verbände) the club belongs to or is invited by. */
export function AssociationsCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: qk.settings.associations, queryFn: listAssociations })
  const [leaving, setLeaving] = useState<Association | null>(null)

  const items = query.data?.associations ?? []
  // A club in no association doesn't need the card.
  if (items.length === 0) return null

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: qk.settings.associations }),
      queryClient.invalidateQueries({ queryKey: qk.associationEvents }),
    ])

  const toggle = async (item: Association, share: boolean) => {
    try {
      await setAssociationContacts(item.id, share)
      await refresh()
    } catch (err) {
      notify('error', t('associations.failed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
    }
  }

  return (
    <Paper withBorder p="lg" data-testid="associations-card">
      <Title order={3} mb={4}>
        {t('associations.title', 'Verbände')}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t('associations.intro', 'Dachverbände, in denen euer Verein Mitglied ist. Was ein Verband sieht, entscheidet ihr hier.')}
      </Text>
      <Stack gap="sm">
        {items.map((item) =>
          item.status === 'invited' ? (
            <Invitation key={item.id} item={item} onDone={refresh} />
          ) : (
            <Paper key={item.id} withBorder p="md">
              <Stack gap="xs">
                <Group justify="space-between" wrap="nowrap" align="flex-start">
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} truncate>
                      {item.name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {item.acceptedAt
                        ? t('associations.since', 'Mitglied seit {{date}}', { date: formatDate(item.acceptedAt) })
                        : null}
                    </Text>
                  </div>
                  <Button size="xs" variant="default" color="red" onClick={() => setLeaving(item)}>
                    {t('associations.leave', 'Austreten')}
                  </Button>
                </Group>
                <Switch
                  label={t('associations.shareContacts', 'Kontakte unserer Ämter teilen')}
                  checked={item.shareContacts}
                  onChange={(e) => void toggle(item, e.currentTarget.checked)}
                />
                <Text size="xs" c="dimmed">
                  {t('associations.seesCount', 'Der Verband sieht die Zahl eurer aktiven Mitglieder, sonst keine Mitgliederdaten.')}
                </Text>
              </Stack>
            </Paper>
          ),
        )}
      </Stack>
      <ConfirmModal
        open={leaving !== null}
        title={t('associations.leaveTitle', 'Aus dem Verband austreten')}
        body={t('associations.leaveBody', '{{name}} sieht euren Verein nicht mehr, und ihr seht seine Anlässe nicht mehr.', {
          name: leaving?.name ?? '',
        })}
        confirmLabel={t('associations.leave', 'Austreten')}
        onConfirm={async () => {
          const target = leaving
          setLeaving(null)
          if (!target) return
          try {
            await leaveAssociation(target.id)
            await refresh()
          } catch (err) {
            notify('error', t('associations.failed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
          }
        }}
        onClose={() => setLeaving(null)}
      />
    </Paper>
  )
}
