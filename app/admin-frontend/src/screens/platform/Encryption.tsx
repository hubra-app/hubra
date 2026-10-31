import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { useLang, tr } from '@/lang'
import {
  getEncryption,
  rotateEncryption,
  setClubBackupKey,
  type ClubKeys,
  type KeyReport,
} from '@/api/platform'

/**
 * Platform settings › Encryption: every club has its own key for the
 * secrets it stores (door codes, mailbox passwords, binding values), locked
 * by the master key FERNET_KEY from env. Club keys can be renewed here; the
 * master key changes in env, then "Re-encrypt" moves everything onto it.
 * Each club can also have its own backup public key.
 */
export function PlatformEncryption() {
  const { notify } = useAdmin()
  useLang()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['platform-encryption'], queryFn: getEncryption })
  const [busy, setBusy] = useState<string | null>(null)
  const [keyDraft, setKeyDraft] = useState<Record<number, string>>({})

  const run = async (id: string, action: () => Promise<KeyReport>) => {
    setBusy(id)
    try {
      const r = await action()
      queryClient.invalidateQueries({ queryKey: ['platform-encryption'] })
      notify(
        r.clean ? 'success' : 'error',
        r.clean ? tr('Erledigt', 'Done') : tr('Nicht alles verschlüsselt', 'Not everything re-encrypted'),
        tr(
          `${r.rotated} Werte neu verschlüsselt, ${r.new_keys} neue Schlüssel` +
            (r.unreadable ? `, ${r.unreadable} mit keinem Schlüssel lesbar` : ''),
          `${r.rotated} values re-encrypted, ${r.new_keys} new keys` +
            (r.unreadable ? `, ${r.unreadable} no key opens` : ''),
        ),
      )
    } catch (err) {
      notify('error', tr('Fehlgeschlagen', 'Failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  const saveBackupKey = async (club: ClubKeys, value: string | null) => {
    setBusy(`backup-${club.tenant_id}`)
    try {
      await setClubBackupKey(club.tenant_id, value)
      setKeyDraft((d) => {
        const next = { ...d }
        delete next[club.tenant_id]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['platform-encryption'] })
      notify('success', tr('Backup-Schlüssel gespeichert', 'Backup key saved'), club.name)
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  if (isLoading || !data) {
    return (
      <Text size="sm" c="dimmed">
        {tr('Wird geladen …', 'Loading…')}
      </Text>
    )
  }

  const v = data.values
  return (
    <Stack gap={20} maw={960}>
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={4}>
          {tr('Hauptschlüssel', 'Master key')}
        </Title>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'FERNET_KEY aus der Umgebung sperrt die Schlüssel aller Vereine. Er gehört nicht in die Datenbank, sonst öffnet ein Datenbank-Dump alles. Zum Wechseln: neuen Schlüssel in FERNET_KEY, den alten in FERNET_OLD_KEYS, neu starten, hier «Neu verschlüsseln», dann den alten Schlüssel entfernen.',
            'FERNET_KEY from env locks every club\'s key. It does not belong in the database, or a database dump would open everything. To change it: new key in FERNET_KEY, the old one in FERNET_OLD_KEYS, restart, "Re-encrypt" here, then remove the old key.',
          )}
        </Text>
        <Group gap="xs" mb={12}>
          {data.master.fernet_key_set ? (
            <Badge color="green" variant="light">
              {tr('FERNET_KEY gesetzt', 'FERNET_KEY set')}
            </Badge>
          ) : (
            <Badge color="red" variant="light">
              {tr('FERNET_KEY fehlt', 'FERNET_KEY missing')}
            </Badge>
          )}
          {data.master.old_keys > 0 && (
            <Badge color="yellow" variant="light">
              {tr(`${data.master.old_keys} alte Schlüssel`, `${data.master.old_keys} old keys`)}
            </Badge>
          )}
          {v.clean ? (
            <Badge color="green" variant="light">
              {tr(`Alle ${v.total} Werte aktuell`, `All ${v.total} values current`)}
            </Badge>
          ) : (
            <Badge color="yellow" variant="light">
              {tr(`${v.old_key} auf altem Schlüssel`, `${v.old_key} on an old key`)}
            </Badge>
          )}
          {v.unreadable > 0 && (
            <Badge color="red" variant="light">
              {tr(`${v.unreadable} mit keinem Schlüssel lesbar`, `${v.unreadable} no key opens`)}
            </Badge>
          )}
        </Group>
        {data.master.old_keys > 0 && v.clean && (
          <Text size="sm" mb={12}>
            {tr(
              'Nichts liegt mehr auf einem alten Schlüssel: FERNET_OLD_KEYS kann geleert werden.',
              'Nothing is left on an old key: FERNET_OLD_KEYS can be emptied.',
            )}
          </Text>
        )}
        <Group>
          <Button loading={busy === 'rotate'} onClick={() => run('rotate', () => rotateEncryption())}>
            {tr('Neu verschlüsseln', 'Re-encrypt')}
          </Button>
          <Button
            variant="default"
            loading={busy === 'all'}
            onClick={() => run('all', () => rotateEncryption(true))}
          >
            {tr('Neue Schlüssel für alle Vereine', 'New keys for every club')}
          </Button>
        </Group>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={4}>
          {tr('Vereine', 'Clubs')}
        </Title>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'Jeder Verein hat einen eigenen Schlüssel; ein Wert öffnet sich nur im eigenen Verein. Ein neuer Schlüssel verschlüsselt die Werte des Vereins neu, ältere Versionen bleiben für alte Backups. Der Backup-Schlüssel (age1…) ist optional: die Backups des Vereins sind dann auch damit verschlüsselt, und der Verein kann sie selbst öffnen.',
            "Each club has its own key; a value only opens in its own club. A new key re-encrypts the club's values; older versions stay for old backups. The backup key (age1…) is optional: the club's backups are then encrypted to it too, so the club can open them itself.",
          )}
        </Text>
        <Table.ScrollContainer minWidth={640}>
          <Table verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Verein', 'Club')}</Table.Th>
                <Table.Th>{tr('Schlüssel', 'Key')}</Table.Th>
                <Table.Th>{tr('Backup-Schlüssel', 'Backup key')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.clubs.map((c) => {
                const draft = keyDraft[c.tenant_id]
                return (
                  <Table.Tr key={c.tenant_id}>
                    <Table.Td>
                      <Text size="sm">{c.name}</Text>
                      <Text size="xs" c="dimmed">
                        {c.slug}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {c.key_version ? (
                        <Text size="sm" title={c.key_created_at ?? ''}>
                          v{c.key_version}
                        </Text>
                      ) : (
                        <Text size="sm" c="dimmed">
                          —
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={6} wrap="nowrap">
                        <TextInput
                          size="xs"
                          placeholder="age1…"
                          value={draft ?? c.backup_public_key ?? ''}
                          onChange={(e) => {
                            const value = e.currentTarget.value
                            setKeyDraft((d) => ({ ...d, [c.tenant_id]: value }))
                          }}
                          style={{ flex: 1, minWidth: 200 }}
                        />
                        {draft !== undefined && draft !== (c.backup_public_key ?? '') && (
                          <Button
                            size="compact-xs"
                            loading={busy === `backup-${c.tenant_id}`}
                            onClick={() => saveBackupKey(c, draft.trim() || null)}
                          >
                            {tr('Speichern', 'Save')}
                          </Button>
                        )}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        loading={busy === `club-${c.tenant_id}`}
                        onClick={() => run(`club-${c.tenant_id}`, () => rotateEncryption(true, c.tenant_id))}
                      >
                        {tr('Neuer Schlüssel', 'New key')}
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Paper>
    </Stack>
  )
}
