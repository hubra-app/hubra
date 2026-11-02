import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import {
  IconAlertTriangle,
  IconCheck,
  IconDownload,
  IconPlus,
  IconTrash,
  IconUserSearch,
  IconX,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDate, formatDateTime } from '@/format'
import { tr } from '@/lang'
import {
  closeDataRequest,
  createDataRequest,
  deleteDataRequestMember,
  downloadDataExport,
  listDataRequests,
  listTenantMembers,
  listTenants,
  updateDataRequest,
  type DataRequest,
  type DataRequestKind,
  type DataRequestStatus,
} from '@/api/tenants'

const KIND: Record<DataRequestKind, () => string> = {
  export: () => tr('Auskunft (Kopie der Daten)', 'Copy of the data'),
  deletion: () => tr('Löschung', 'Deletion'),
}

const errorText = (err: unknown) => (err instanceof Error ? err.message : undefined)

function DeadlineBadge({ r }: { r: DataRequest }) {
  if (r.status === 'done')
    return (
      <Badge variant="light" color="green">
        {tr('Erledigt', 'Done')}
      </Badge>
    )
  if (r.status === 'rejected')
    return (
      <Badge variant="light" color="gray">
        {tr('Abgelehnt', 'Rejected')}
      </Badge>
    )
  const days = r.days_left ?? 0
  return (
    <Badge variant="light" color={r.overdue ? 'red' : r.due_soon ? 'orange' : 'blue'}>
      {r.overdue
        ? tr(`${-days} Tage überfällig`, `${-days} days overdue`)
        : days === 0
          ? tr('Heute fällig', 'Due today')
          : tr(`Noch ${days} Tage`, `${days} days left`)}
    </Badge>
  )
}

/**
 * Requests for a copy or the deletion of someone's data in a club, with the
 * 30-day deadline and the record of who handled each one and when. On the
 * club's page with `tenantId`, otherwise for every club.
 */
export function DataRequestsPanel({
  tenantId,
  tenantSlug,
}: {
  tenantId?: number
  tenantSlug?: string
}) {
  const [status, setStatus] = useState<DataRequestStatus | 'all'>(tenantId ? 'all' : 'open')
  const [creating, setCreating] = useState(false)
  const key = ['data-requests', tenantId ?? 'all', status]
  const { data, isLoading } = useQuery({
    queryKey: key,
    queryFn: () => listDataRequests({ status, tenant_id: tenantId }),
  })
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['data-requests'] })

  const list = (
    <Stack gap="sm">
      <Group justify="space-between" gap={8}>
        <SegmentedControl
          size="xs"
          value={status}
          onChange={(v) => setStatus(v as DataRequestStatus | 'all')}
          data={[
            { value: 'open', label: tr('Offen', 'Open') },
            { value: 'done', label: tr('Erledigt', 'Done') },
            { value: 'rejected', label: tr('Abgelehnt', 'Rejected') },
            { value: 'all', label: tr('Alle', 'All') },
          ]}
        />
        <Button size="xs" leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>
          {tr('Anfrage erfassen', 'Record a request')}
        </Button>
      </Group>
      {data && data.counts.overdue > 0 && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
          {tr(
            `${data.counts.overdue} offene Anfrage(n) sind über der Frist von 30 Tagen.`,
            `${data.counts.overdue} open request(s) are past the 30-day deadline.`,
          )}
        </Alert>
      )}
      {isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : !data?.requests.length ? (
        <Text size="sm" c="dimmed">
          {status === 'open'
            ? tr('Keine offenen Anfragen.', 'No open requests.')
            : tr('Keine Anfragen.', 'No requests.')}
        </Text>
      ) : (
        data.requests.map((r) => (
          <RequestCard key={r.id} r={r} showClub={!tenantId} slug={tenantSlug} onChange={refresh} />
        ))
      )}
      {creating && (
        <NewRequestModal
          tenantId={tenantId}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            void refresh()
          }}
        />
      )}
    </Stack>
  )

  if (!tenantId) return list
  return (
    <Paper withBorder p="lg" mb={20}>
      <Title order={3} mb={4}>
        {tr('Datenschutz-Anfragen', 'Data protection requests')}
      </Title>
      <Text size="sm" c="dimmed" mb={12}>
        {tr(
          'Auskunft und Löschung für Personen in diesem Verein, mit Frist und wer sie wann erledigt hat.',
          'Copies and deletions for people in this club, with the deadline and who handled them when.',
        )}
      </Text>
      {list}
    </Paper>
  )
}

function RequestCard({
  r,
  showClub,
  slug,
  onChange,
}: {
  r: DataRequest
  showClub: boolean
  slug?: string
  onChange: () => unknown
}) {
  const { notify } = useAdmin()
  const [busy, setBusy] = useState(false)
  const [closing, setClosing] = useState<'done' | 'rejected' | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [picking, setPicking] = useState(false)
  const open = r.status === 'open'
  const who = [r.subject_name, r.subject_email].filter(Boolean).join(', ')

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      notify('success', ok)
      await onChange()
    } catch (err) {
      notify('error', tr('Hat nicht geklappt', 'That did not work'), errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" align="flex-start" gap={8} mb={6}>
        <Stack gap={2}>
          <Group gap={8}>
            <Badge variant="outline" color={r.kind === 'deletion' ? 'red' : 'violet'}>
              {KIND[r.kind]()}
            </Badge>
            <DeadlineBadge r={r} />
          </Group>
          <Text fw={600}>{who || tr(`Mitglied #${r.member_id}`, `Member #${r.member_id}`)}</Text>
          <Text size="xs" c="dimmed">
            {showClub && `${r.tenant_name} · `}
            {tr(
              `Eingegangen ${formatDate(r.received_on)}`,
              `Received ${formatDate(r.received_on)}`,
            )}
            {r.received_via && ` (${r.received_via})`}
            {' · '}
            {tr(`Frist ${formatDate(r.due_on)}`, `Due ${formatDate(r.due_on)}`)}
            {r.member_id != null && ` · ${tr('Mitglied', 'Member')} #${r.member_id}`}
          </Text>
        </Stack>
      </Group>
      {r.note && (
        <Text size="sm" mb={6} style={{ whiteSpace: 'pre-wrap' }}>
          {r.note}
        </Text>
      )}
      {r.exports.length > 0 && (
        <Text size="xs" c="dimmed">
          {tr(
            `Heruntergeladen: ${r.exports.map((e) => formatDateTime(e.at)).join(', ')}`,
            `Downloaded: ${r.exports.map((e) => formatDateTime(e.at)).join(', ')}`,
          )}
          {r.result?.rows &&
            ` · ${Object.values(r.result.rows).reduce((a, b) => a + b, 0)} ${tr('Einträge aus', 'rows from')} ${Object.keys(r.result.rows).length} ${tr('Bereichen', 'areas')}`}
        </Text>
      )}
      {r.result?.deleted && (
        <Text size="xs" c="dimmed">
          {tr(
            `Gelöscht ${formatDateTime(r.result.deleted_at!)}. Ohne Namen behalten (Buchhaltung): ${r.result.kept_without_name?.invoices ?? 0} Rechnungen, ${r.result.kept_without_name?.transactions ?? 0} Buchungen.`,
            `Deleted ${formatDateTime(r.result.deleted_at!)}. Kept without the name (bookkeeping): ${r.result.kept_without_name?.invoices ?? 0} invoices, ${r.result.kept_without_name?.transactions ?? 0} bookings.`,
          )}
        </Text>
      )}
      {!open && (
        <Text size="sm" mt={6}>
          {tr(
            `${r.status === 'done' ? 'Erledigt' : 'Abgelehnt'} ${formatDateTime(r.handled_at!)}${r.handled_by_name ? ` von ${r.handled_by_name}` : ''}`,
            `${r.status === 'done' ? 'Done' : 'Rejected'} ${formatDateTime(r.handled_at!)}${r.handled_by_name ? ` by ${r.handled_by_name}` : ''}`,
          )}
          {r.outcome && `: ${r.outcome}`}
        </Text>
      )}
      {open && (
        <Group gap={8} mt={10}>
          {r.member_id == null ? (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconUserSearch size={16} />}
              onClick={() => setPicking(true)}
            >
              {tr('Mitglied zuordnen', 'Find the member')}
            </Button>
          ) : r.kind === 'export' ? (
            <Button
              size="xs"
              variant="light"
              loading={busy}
              leftSection={<IconDownload size={16} />}
              onClick={() =>
                run(() => downloadDataExport(r), tr('Daten heruntergeladen', 'Data downloaded'))
              }
            >
              {tr('Daten herunterladen', 'Download the data')}
            </Button>
          ) : (
            !r.result?.deleted && (
              <Button
                size="xs"
                variant="light"
                color="red"
                leftSection={<IconTrash size={16} />}
                onClick={() => setDeleting(true)}
              >
                {tr('Daten im Verein löschen', 'Delete the data in the club')}
              </Button>
            )
          )}
          <Button
            size="xs"
            variant="light"
            color="green"
            leftSection={<IconCheck size={16} />}
            disabled={r.kind === 'deletion' && !r.result?.deleted}
            onClick={() => setClosing('done')}
          >
            {tr('Erledigt', 'Done')}
          </Button>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            leftSection={<IconX size={16} />}
            onClick={() => setClosing('rejected')}
          >
            {tr('Ablehnen', 'Reject')}
          </Button>
        </Group>
      )}
      {closing && (
        <CloseModal
          status={closing}
          onClose={() => setClosing(null)}
          onSave={(outcome) =>
            run(
              () => closeDataRequest(r.id, closing, outcome),
              closing === 'done'
                ? tr('Als erledigt vermerkt', 'Marked done')
                : tr('Abgelehnt', 'Rejected'),
            ).then(() => setClosing(null))
          }
        />
      )}
      {deleting && (
        <DeleteModal
          r={r}
          slug={slug}
          onClose={() => setDeleting(false)}
          onDone={async () => {
            setDeleting(false)
            await onChange()
          }}
        />
      )}
      {picking && (
        <PickMemberModal
          r={r}
          onClose={() => setPicking(false)}
          onSave={(memberId) =>
            run(
              () => updateDataRequest(r.id, { member_id: memberId }),
              tr('Mitglied zugeordnet', 'Member set'),
            ).then(() => setPicking(false))
          }
        />
      )}
    </Paper>
  )
}

function useMemberOptions(tenantId: number | null) {
  const { data } = useQuery({
    queryKey: ['tenant-members', tenantId],
    queryFn: () => listTenantMembers(tenantId!),
    enabled: tenantId != null,
  })
  return {
    members: data?.members ?? [],
    options: (data?.members ?? []).map((m) => ({
      value: String(m.id),
      label: `${m.name || '–'} (${m.email}) #${m.id}`,
    })),
  }
}

function NewRequestModal({
  tenantId,
  onClose,
  onSaved,
}: {
  tenantId?: number
  onClose: () => void
  onSaved: () => void
}) {
  const { notify } = useAdmin()
  const [club, setClub] = useState<string | null>(tenantId ? String(tenantId) : null)
  const [kind, setKind] = useState<DataRequestKind>('export')
  const [member, setMember] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [received, setReceived] = useState(() => new Date().toISOString().slice(0, 10))
  const [via, setVia] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const { data: clubs } = useQuery({
    queryKey: ['tenants', 'picker'],
    queryFn: () => listTenants({ per_page: 100 }),
    enabled: !tenantId,
  })
  const clubId = club ? Number(club) : null
  const { members, options } = useMemberOptions(clubId)
  const ok = clubId != null && (member || name.trim() || email.trim())

  return (
    <Modal opened onClose={onClose} title={tr('Anfrage erfassen', 'Record a request')} size="lg">
      <Stack gap="md">
        {!tenantId && (
          <Select
            label={tr('Verein', 'Club')}
            searchable
            required
            value={club}
            onChange={(v) => {
              setClub(v)
              setMember(null)
            }}
            data={(clubs?.tenants ?? []).map((t) => ({ value: String(t.id), label: t.name }))}
          />
        )}
        <SegmentedControl
          fullWidth
          value={kind}
          onChange={(v) => setKind(v as DataRequestKind)}
          data={[
            { value: 'export', label: KIND.export() },
            { value: 'deletion', label: KIND.deletion() },
          ]}
        />
        <Select
          label={tr('Mitglied', 'Member')}
          description={tr(
            'Wenn schon klar ist, wer es ist; sonst später zuordnen',
            'If you already know who it is; otherwise set it later',
          )}
          searchable
          clearable
          disabled={clubId == null}
          value={member}
          onChange={(v) => {
            setMember(v)
            const m = members.find((x) => String(x.id) === v)
            if (m) {
              if (!name) setName(m.name)
              if (!email) setEmail(m.email)
            }
          }}
          data={options}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={tr('Name', 'Name')}
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <TextInput
            label={tr('E-Mail', 'Email')}
            type="email"
            maxLength={320}
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
          />
          <TextInput
            type="date"
            label={tr('Eingegangen am', 'Received on')}
            description={tr(
              'Die Frist von 30 Tagen läuft ab hier',
              'The 30-day deadline starts here',
            )}
            value={received}
            onChange={(e) => setReceived(e.currentTarget.value)}
          />
          <TextInput
            label={tr('Eingegangen über', 'Received via')}
            description={tr('Mail, Brief, über den Verein …', 'Mail, letter, through the club …')}
            maxLength={100}
            value={via}
            onChange={(e) => setVia(e.currentTarget.value)}
          />
        </SimpleGrid>
        <Textarea
          label={tr('Notiz', 'Note')}
          autosize
          minRows={2}
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={!ok}
            onClick={async () => {
              setSaving(true)
              try {
                await createDataRequest(clubId!, {
                  kind,
                  member_id: member ? Number(member) : null,
                  subject_name: name,
                  subject_email: email,
                  received_on: received,
                  received_via: via,
                  note,
                })
                notify('success', tr('Anfrage erfasst', 'Request recorded'))
                onSaved()
              } catch (err) {
                notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), errorText(err))
              } finally {
                setSaving(false)
              }
            }}
          >
            {tr('Erfassen', 'Record')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function PickMemberModal({
  r,
  onClose,
  onSave,
}: {
  r: DataRequest
  onClose: () => void
  onSave: (memberId: number) => Promise<void>
}) {
  const { options } = useMemberOptions(r.tenant_id)
  const [member, setMember] = useState<string | null>(null)
  return (
    <Modal opened onClose={onClose} title={tr('Mitglied zuordnen', 'Find the member')}>
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {tr(
            `Wer ist «${r.subject_name || r.subject_email}» in ${r.tenant_name}?`,
            `Who is “${r.subject_name || r.subject_email}” in ${r.tenant_name}?`,
          )}
        </Text>
        <Select
          searchable
          data={options}
          value={member}
          onChange={setMember}
          aria-label={tr('Mitglied', 'Member')}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button disabled={!member} onClick={() => onSave(Number(member))}>
            {tr('Zuordnen', 'Set')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function CloseModal({
  status,
  onClose,
  onSave,
}: {
  status: 'done' | 'rejected'
  onClose: () => void
  onSave: (outcome: string) => Promise<void>
}) {
  const [outcome, setOutcome] = useState('')
  const [saving, setSaving] = useState(false)
  const reject = status === 'rejected'
  return (
    <Modal
      opened
      onClose={onClose}
      title={
        reject
          ? tr('Anfrage ablehnen', 'Reject the request')
          : tr('Als erledigt vermerken', 'Mark as done')
      }
    >
      <Stack gap="md">
        <Textarea
          label={reject ? tr('Grund', 'Reason') : tr('Was wurde gemacht', 'What was done')}
          description={
            reject
              ? tr(
                  'Zum Beispiel: keine Person mit dieser Adresse im Verein',
                  'For example: nobody with this address in the club',
                )
              : tr(
                  'Zum Beispiel: Datei am 3.11. per Mail an die Person geschickt',
                  'For example: file sent to the person by mail on 3 Nov',
                )
          }
          required={reject}
          autosize
          minRows={3}
          maxLength={2000}
          value={outcome}
          onChange={(e) => setOutcome(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            loading={saving}
            color={reject ? 'gray' : 'green'}
            disabled={reject && !outcome.trim()}
            onClick={async () => {
              setSaving(true)
              try {
                await onSave(outcome)
              } finally {
                setSaving(false)
              }
            }}
          >
            {reject ? tr('Ablehnen', 'Reject') : tr('Erledigt', 'Done')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function DeleteModal({
  r,
  slug,
  onClose,
  onDone,
}: {
  r: DataRequest
  slug?: string
  onClose: () => void
  onDone: () => Promise<void>
}) {
  const { notify } = useAdmin()
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)
  return (
    <Modal
      opened
      onClose={onClose}
      title={tr('Daten im Verein löschen', 'Delete the data in the club')}
      size="lg"
    >
      <Stack gap="md">
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
          {tr(
            `Mitglied #${r.member_id} verlässt ${r.tenant_name} und wird gelöscht: Profil im Verein, Anmeldungen, Gruppen, Mitteilungen, Mailbox. Rechnungen und Buchungen bleiben ohne Namen (Aufbewahrungspflicht), Audit-Einträge ohne Person. Das lässt sich nicht rückgängig machen. Das Hubra-Konto bleibt; es gehört der Person.`,
            `Member #${r.member_id} leaves ${r.tenant_name} and is deleted: club profile, registrations, groups, notifications, mailbox. Invoices and bookings stay without the name (records must be kept), audit entries without the person. This cannot be undone. The Hubra account stays; it belongs to the person.`,
          )}
        </Alert>
        <TextInput
          label={tr(
            'Zum Bestätigen den Kurznamen des Vereins eintippen',
            'Type the club’s short name to confirm',
          )}
          placeholder={slug}
          value={confirm}
          onChange={(e) => setConfirm(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            color="red"
            loading={saving}
            disabled={!confirm.trim()}
            onClick={async () => {
              setSaving(true)
              try {
                await deleteDataRequestMember(r.id, confirm.trim())
                notify('success', tr('Daten gelöscht', 'Data deleted'))
                await onDone()
              } catch (err) {
                notify('error', tr('Löschen fehlgeschlagen', 'Could not delete'), errorText(err))
              } finally {
                setSaving(false)
              }
            }}
          >
            {tr('Endgültig löschen', 'Delete for good')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
