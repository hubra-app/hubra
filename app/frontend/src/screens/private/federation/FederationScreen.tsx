import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Anchor, Badge, Button, Group, Paper, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { inviteMemberClub, listMemberClubs, removeMemberClub, type MemberClub } from '@/api/federation'
import { ConfirmModal, ErrorBanner, LoadingSpinner, PageHead, StatGrid, StatTile } from '@/components/ui'
import { useAuth, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { useT } from '@/locales/i18n'

function ClubCard({ club, canManage, onRemove }: { club: MemberClub; canManage: boolean; onRemove: () => void }) {
  const { t } = useT()
  const invited = club.status === 'invited'
  return (
    <Paper withBorder p="md" data-testid="member-club">
      <Stack gap="xs">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div style={{ minWidth: 0 }}>
            <Group gap="xs" wrap="nowrap">
              <Text fw={600} truncate>
                {club.name}
              </Text>
              {invited && (
                <Badge size="sm" variant="light" color="yellow">
                  {t('federation.invited', 'eingeladen')}
                </Badge>
              )}
            </Group>
            <Text size="xs" c="dimmed" ff="monospace">
              {club.slug}
            </Text>
          </div>
          {!invited && (
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <Text fw={700} size="xl" lh={1}>
                {club.members ?? 0}
              </Text>
              <Text size="xs" c="dimmed">
                {t('federation.activeMembers', 'aktive Mitglieder')}
              </Text>
            </div>
          )}
        </Group>
        {invited ? (
          <Text size="sm" c="dimmed">
            {t('federation.waiting', 'Eingeladen am {{date}}. Der Verein nimmt die Einladung in seinen Einstellungen an.', {
              date: formatDate(club.invitedAt),
            })}
          </Text>
        ) : club.shareContacts && club.contacts.length > 0 ? (
          <Stack gap={4}>
            <Text size="xs" fw={600} c="dimmed" tt="uppercase">
              {t('federation.contacts', 'Kontakte')}
            </Text>
            {club.contacts.map((c) => (
              <Text key={`${c.function}-${c.name}`} size="sm">
                <Text span fw={500}>
                  {c.function}
                </Text>
                {': '}
                {c.name}
                {c.email && (
                  <>
                    {' · '}
                    <Anchor href={`mailto:${c.email}`} size="sm">
                      {c.email}
                    </Anchor>
                  </>
                )}
              </Text>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">
            {club.shareContacts
              ? t('federation.noContacts', 'Der Verein hat noch keine Ämter besetzt.')
              : t('federation.contactsHidden', 'Der Verein teilt seine Kontakte nicht.')}
          </Text>
        )}
        {canManage && (
          <Group gap="xs">
            <Button size="xs" variant="default" color="red" onClick={onRemove}>
              {invited ? t('federation.withdraw', 'Einladung zurückziehen') : t('federation.remove', 'Aus dem Verband entfernen')}
            </Button>
          </Group>
        )}
      </Stack>
    </Paper>
  )
}

export function FederationScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const canManage = hasPermission('federation.federation.manage')
  const queryClient = useQueryClient()
  const clubs = useQuery({ queryKey: qk.memberClubs, queryFn: listMemberClubs })
  const [slug, setSlug] = useState('')
  const [busy, setBusy] = useState(false)
  const [removing, setRemoving] = useState<MemberClub | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.memberClubs })

  const invite = async (event: FormEvent) => {
    event.preventDefault()
    if (!slug.trim()) return
    setBusy(true)
    try {
      await inviteMemberClub(slug.trim())
      setSlug('')
      notify('success', t('federation.invitedToast', 'Einladung verschickt'))
      await refresh()
    } catch (err) {
      notify('error', t('federation.inviteFailed', 'Nicht eingeladen'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  const rows = clubs.data?.clubs ?? []
  const active = rows.filter((c) => c.status === 'active')
  const total = active.reduce((sum, c) => sum + (c.members ?? 0), 0)

  return (
    <div>
      <PageHead title={t('shell.nav.federation', 'Verband')} />
      <Stack gap="lg">
        <Text c="dimmed" size="sm" maw={720}>
          {t(
            'federation.intro',
            'Hier seht ihr eure Mitgliedvereine mit der Zahl ihrer aktiven Mitglieder und, wenn ein Verein sie teilt, den Kontakten seiner Ämter. Anlässe, die ihr «Mit Mitgliedvereinen teilen», erscheinen bei den Vereinen unter Anlässe.',
          )}
        </Text>
        {clubs.error ? (
          <ErrorBanner message={(clubs.error as Error).message} onRetry={() => clubs.refetch()} />
        ) : !clubs.data ? (
          <LoadingSpinner />
        ) : (
          <>
            <StatGrid columns={3}>
              <StatTile label={t('federation.clubCount', 'Mitgliedvereine')} value={active.length} />
              <StatTile label={t('federation.memberTotal', 'Aktive Mitglieder insgesamt')} value={total} />
              <StatTile label={t('federation.openInvites', 'Offene Einladungen')} value={rows.length - active.length} />
            </StatGrid>
            {canManage && (
              <Paper withBorder p="lg">
                <form onSubmit={invite}>
                  <Stack gap="xs">
                    <Title order={4}>{t('federation.inviteTitle', 'Verein einladen')}</Title>
                    <Text size="sm" c="dimmed">
                      {t(
                        'federation.inviteHint',
                        'Die Adresse des Vereins in Hubra, z. B. «rc-uri» aus hubra.club/rc-uri. Der Verein sieht die Einladung unter Einstellungen › Verein und entscheidet selbst.',
                      )}
                    </Text>
                    <Group align="flex-end" gap="xs">
                      <TextInput
                        label={t('federation.slug', 'Adresse des Vereins')}
                        value={slug}
                        onChange={(e) => setSlug(e.currentTarget.value)}
                        style={{ flex: '1 1 220px' }}
                        maxLength={255}
                      />
                      <Button type="submit" loading={busy} disabled={!slug.trim()}>
                        {t('federation.invite', 'Einladen')}
                      </Button>
                    </Group>
                  </Stack>
                </form>
              </Paper>
            )}
            {rows.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('federation.none', 'Noch keine Mitgliedvereine.')}
              </Text>
            ) : (
              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                {rows.map((club) => (
                  <ClubCard key={club.id} club={club} canManage={canManage} onRemove={() => setRemoving(club)} />
                ))}
              </SimpleGrid>
            )}
          </>
        )}
      </Stack>
      <ConfirmModal
        open={removing !== null}
        title={
          removing?.status === 'invited'
            ? t('federation.withdraw', 'Einladung zurückziehen')
            : t('federation.remove', 'Aus dem Verband entfernen')
        }
        body={t('federation.removeBody', '{{name}} ist dann kein Mitgliedverein mehr und sieht eure geteilten Anlässe nicht mehr.', {
          name: removing?.name ?? '',
        })}
        confirmLabel={t('federation.removeShort', 'Entfernen')}
        onConfirm={async () => {
          const target = removing
          setRemoving(null)
          if (!target) return
          try {
            await removeMemberClub(target.id)
            await refresh()
          } catch (err) {
            notify('error', t('federation.removeFailed', 'Nicht entfernt'), err instanceof Error ? err.message : undefined)
          }
        }}
        onClose={() => setRemoving(null)}
      />
    </div>
  )
}
