import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  TextInput,
  Button,
  Badge,
  Group,
  Stack,
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
import { SimpleList } from '@/components/ui'
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
  const [recordFor, setRecordFor] = useState<Domain | null>(null)
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
      setAddOpen(false)
      setNewDomain('')
      setRecordFor({ ...result.domain, txt_record: result.txt_record })
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

      <SimpleList
        items={domains}
        loading={isLoading}
        emptyMessage={t('domains.empty', 'Noch keine eigenen Domains eingerichtet.')}
        getKey={(d) => d.id}
        row={(d) => ({
          leading: d.is_primary ? (
            <IconStar
              size={16}
              fill="var(--mantine-color-gold-4)"
              color="var(--mantine-color-gold-4)"
              aria-label={t('domains.primary', 'Hauptdomain')}
            />
          ) : d.verified ? (
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={() => handleSetPrimary(d)}
              aria-label={t('domains.primary', 'Hauptdomain')}
              title={t('domains.primary', 'Hauptdomain')}
            >
              <IconStar size={16} />
            </ActionIcon>
          ) : undefined,
          title: d.domain,
          subtitle: d.is_primary ? t('domains.primary', 'Hauptdomain') : undefined,
          meta: (
            <Badge variant="light" color={STATUS_COLORS[d.verification_status] ?? 'gray'} size="sm">
              {t(`domains.status.${d.verification_status}`, d.verification_status)}
            </Badge>
          ),
          actions: (
            <Group gap={6} wrap="nowrap">
              {!d.verified && d.txt_record && (
                <Button size="xs" variant="default" onClick={() => setRecordFor(d)}>
                  {t('domains.showRecord', 'DNS-Eintrag')}
                </Button>
              )}
              {!d.verified && (
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
          ),
        })}
      />

      <Modal opened={addOpen} onClose={() => { setAddOpen(false); setNewDomain('') }} title={t('domains.add', 'Domain hinzufügen')}>
        <Stack gap={14}>
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
        </Stack>
      </Modal>

      <Modal
        opened={!!recordFor}
        onClose={() => setRecordFor(null)}
        title={t('domains.recordTitle', 'DNS-Eintrag für {{domain}}', { domain: recordFor?.domain ?? '' })}
      >
        {recordFor?.txt_record && (
          <Alert icon={<IconCheck size={16} />} color="acc" variant="light">
            <Stack gap={10}>
              <Text fw={600}>{t('domains.txtHint', 'Füge diesen TXT-Eintrag im DNS deiner Domain hinzu:')}</Text>
              <RecordField label={t('domains.recordType', 'Typ')} value="TXT" />
              <RecordField label={t('domains.recordName', 'Name')} value={recordFor.txt_record.name} />
              <RecordField label={t('domains.recordValue', 'Wert')} value={recordFor.txt_record.value} />
              <Text size="sm" c="dimmed">
                {t('domains.txtAfter', 'Wir prüfen ihn 72 Stunden lang automatisch, oder klicke auf «Bestätigen». Eine Domain, die nicht innert 7 Tagen bestätigt ist, wird entfernt.')}
              </Text>
            </Stack>
          </Alert>
        )}
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

function RecordField({ label, value }: { label: string; value: string }) {
  const { t } = useT()
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">{label}</Text>
      <Group gap={6} wrap="nowrap">
        <Text className="num" fz="sm" style={{ wordBreak: 'break-all' }}>
          {value}
        </Text>
        <CopyButton value={value} timeout={2000}>
          {({ copied, copy }) => (
            <ActionIcon
              color={copied ? 'teal' : 'gray'}
              variant="subtle"
              onClick={copy}
              aria-label={copied ? t('common.copied') : t('common.copy')}
            >
              {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
            </ActionIcon>
          )}
        </CopyButton>
      </Group>
    </Stack>
  )
}
