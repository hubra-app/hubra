import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Table,
  TextInput,
  Button,
  Badge,
  Group,
  Stack,
  Paper,
  Text,
  Modal,
  Alert,
  CopyButton,
  ActionIcon,
} from '@mantine/core'
import { IconPlus, IconTrash, IconCheck, IconCopy, IconStar } from '@tabler/icons-react'
import {
  listDomains,
  addDomain,
  verifyDomain,
  removeDomain,
  setPrimaryDomain,
  type Domain,
} from '@/api/admin'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'

const STATUS_COLORS: Record<string, string> = {
  verified: 'green',
  pending: 'orange',
  failed: 'red',
}

export function DomainsTab() {
  const { notify } = useToast()
  const { t } = useT()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [newDomain, setNewDomain] = useState('')
  const [adding, setAdding] = useState(false)
  const [txtInstructions, setTxtInstructions] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Domain | null>(null)

  const { data: domains = [], isLoading } = useQuery({
    queryKey: qk.settings.domains,
    queryFn: listDomains,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.settings.domains })

  const handleAdd = async () => {
    if (!newDomain.trim()) return
    setAdding(true)
    try {
      const result = await addDomain(newDomain.trim().toLowerCase())
      setTxtInstructions(result.txt_record.instructions)
      refresh()
      notify('success', t('domains.added', 'Domain hinzugefügt'), t('domains.addedMsg', 'Füge den TXT-Eintrag hinzu, um die Domain zu bestätigen.'))
    } catch (err) {
      notify('error', t('domains.addFailed', 'Domain konnte nicht hinzugefügt werden'), err instanceof Error ? err.message : undefined)
    } finally {
      setAdding(false)
    }
  }

  const handleVerify = async (domain: Domain) => {
    try {
      const result = await verifyDomain(domain.id)
      if (result.verified) {
        notify('success', t('domains.verified', 'Domain bestätigt'), domain.domain)
      } else {
        notify('error', t('domains.verifyFailed', 'Bestätigung fehlgeschlagen'), result.error ?? undefined)
      }
      refresh()
    } catch (err) {
      notify('error', t('domains.verifyFailed', 'Bestätigung fehlgeschlagen'), err instanceof Error ? err.message : undefined)
    }
  }

  const handleRemove = async (id: number) => {
    try {
      await removeDomain(id)
      notify('success', t('domains.removed', 'Domain entfernt'))
      refresh()
    } catch {
      notify('error', t('domains.removeFailed', 'Domain konnte nicht entfernt werden'))
    }
    setDeleteTarget(null)
  }

  const handleSetPrimary = async (domain: Domain) => {
    try {
      await setPrimaryDomain(domain.id)
      notify('success', t('domains.primarySet', 'Hauptdomain festgelegt'), domain.domain)
      refresh()
    } catch (err) {
      notify('error', t('domains.primaryFailed', 'Hauptdomain konnte nicht festgelegt werden'), err instanceof Error ? err.message : undefined)
    }
  }

  return (
    <Stack gap={20}>
      <Group justify="space-between">
        <Text fw={700} fz="lg">{t('domains.title', 'Eigene Domains')}</Text>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setAddOpen(true)}>
          {t('domains.add', 'Domain hinzufügen')}
        </Button>
      </Group>

      <Paper withBorder>
        {isLoading && <Text p={20} c="dimmed">{t('domains.loading', 'Domains werden geladen …')}</Text>}
        {!isLoading && domains.length === 0 && (
          <Text p={40} ta="center" c="dimmed">{t('domains.empty', 'Noch keine eigenen Domains eingerichtet.')}</Text>
        )}
        {domains.length > 0 && (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('domains.domain', 'Domain')}</Table.Th>
                <Table.Th>{t('common.status', 'Status')}</Table.Th>
                <Table.Th>{t('domains.primary', 'Hauptdomain')}</Table.Th>
                <Table.Th>{t('common.actions', 'Aktionen')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {domains.map((d) => (
                <Table.Tr key={d.id}>
                  <Table.Td fw={600}>{d.domain}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[d.verification_status] ?? 'gray'} size="sm">
                      {t(`domains.status.${d.verification_status}`, d.verification_status)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {d.is_primary ? (
                      <IconStar size={16} fill="#fece2b" color="#fece2b" />
                    ) : (
                      d.verified && (
                        <IconStar
                          size={16}
                          color="#8c86a0"
                          style={{ cursor: 'pointer' }}
                          onClick={() => handleSetPrimary(d)}
                        />
                      )
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={6}>
                      {d.verification_status !== 'verified' && (
                        <Button size="xs" variant="light" onClick={() => handleVerify(d)}>
                          {t('domains.verify', 'Bestätigen')}
                        </Button>
                      )}
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => setDeleteTarget(d)}
                        aria-label={t('common.delete')}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={addOpen} onClose={() => { setAddOpen(false); setTxtInstructions(null); setNewDomain('') }} title={t('domains.add', 'Domain hinzufügen')}>
        <Stack gap={14}>
          {txtInstructions ? (
            <Alert icon={<IconCheck size={16} />} color="blue" variant="light">
              <Stack gap={8}>
                <Text fw={600}>{t('domains.txtHint', 'Füge diesen TXT-Eintrag in deinem DNS hinzu:')}</Text>
                <Group gap={6}>
                  <Text className="num" fz="sm" style={{ wordBreak: 'break-all' }}>
                    {txtInstructions}
                  </Text>
                  <CopyButton value={txtInstructions} timeout={2000}>
                    {({ copied, copy }) => (
                      <ActionIcon
                        color={copied ? 'teal' : 'gray'}
                        onClick={copy}
                        aria-label={copied ? t('common.copied') : t('common.copy')}
                      >
                        {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                      </ActionIcon>
                    )}
                  </CopyButton>
                </Group>
                <Text size="sm" c="dimmed">
                  {t('domains.txtAfter', 'Sobald der Eintrag gesetzt ist, klicke auf «Bestätigen».')}
                </Text>
              </Stack>
            </Alert>
          ) : (
            <>
              <TextInput
                label={t('domains.domain', 'Domain')}
                placeholder="example.com"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={() => setAddOpen(false)}>{t('common.cancel', 'Abbrechen')}</Button>
                <Button loading={adding} onClick={handleAdd}>{t('common.add', 'Hinzufügen')}</Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>

      <Modal
        opened={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('domains.removeTitle', 'Domain entfernen')}
        size="sm"
      >
        <Stack gap={14}>
          <Text>{t('domains.removeConfirm', 'Willst du {{domain}} wirklich entfernen?', { domain: deleteTarget?.domain ?? '' })}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)}>{t('common.cancel', 'Abbrechen')}</Button>
            <Button color="red" onClick={() => deleteTarget && handleRemove(deleteTarget.id)}>
              {t('domains.remove', 'Entfernen')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
