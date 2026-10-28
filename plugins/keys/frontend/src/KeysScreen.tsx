import { useMemo, useState } from 'react'
import { Button, Menu, NumberInput, Select, Textarea, TextInput, ActionIcon } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconDots, IconPlus } from '@tabler/icons-react'
import { useT } from '@hubra/plugin-sdk'
import { useAuth, useToast } from '@hubra/plugin-sdk'
import { ConfirmModal, DataTable, Field, Modal, PageHead } from '@hubra/plugin-sdk'
import { listMembers } from '@hubra/plugin-sdk'
import {
  createKey,
  deleteKey,
  getKey,
  issueKey,
  keyAction,
  listKeys,
  updateKey,
  type ClubKey,
  type KeyAction,
  type KeyInput,
  type KeyKind,
  type KeyStatus,
} from './api'

const STATUS_COLORS: Record<KeyStatus, string> = {
  available: '#1f9d57',
  issued: '#2f6fd6',
  lost: '#d64545',
  retired: '#99a2ac',
}

const EMPTY: KeyInput = {
  label: '',
  number: '',
  kind: 'key',
  opens: '',
  deposit_chf: null,
  notes: '',
}

export function KeysScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canManage = hasPermission('keys.keys.manage')

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ['keys'],
    queryFn: listKeys,
  })
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<KeyStatus | 'all'>('all')
  const [editing, setEditing] = useState<ClubKey | 'new' | null>(null)
  const [form, setForm] = useState<KeyInput>(EMPTY)
  const [issuing, setIssuing] = useState<ClubKey | null>(null)
  const [deleting, setDeleting] = useState<ClubKey | null>(null)
  const [historyId, setHistoryId] = useState<number | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['keys'] })

  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.error'),
      err instanceof Error ? err.message : t('common.unknownError'),
    )

  const openEdit = (k: ClubKey | 'new') => {
    setEditing(k)
    setForm(
      k === 'new'
        ? EMPTY
        : {
            label: k.label,
            number: k.number ?? '',
            kind: k.kind,
            opens: k.opens ?? '',
            deposit_chf: k.depositChf ? Number(k.depositChf) : null,
            notes: k.notes ?? '',
          },
    )
  }

  const save = async () => {
    if (!editing) return
    const body: KeyInput = {
      ...form,
      number: form.number || null,
      opens: form.opens || null,
      notes: form.notes || null,
    }
    try {
      if (editing === 'new') await createKey(body)
      else await updateKey(editing.id, body)
      await refresh()
      setEditing(null)
      notify('success', t('keys.saved', 'Key saved'))
    } catch (err) {
      fail(err)
    }
  }

  const run = async (k: ClubKey, action: KeyAction) => {
    try {
      await keyAction(k.id, action)
      await refresh()
    } catch (err) {
      fail(err)
    }
  }

  const remove = async () => {
    if (!deleting) return
    try {
      await deleteKey(deleting.id)
      await refresh()
      setDeleting(null)
    } catch (err) {
      fail(err)
    }
  }

  const filtered = keys.filter((k) => {
    const q = search.toLowerCase()
    const matches =
      !q ||
      [k.label, k.number, k.opens, k.holderName].some((v) => (v ?? '').toLowerCase().includes(q))
    return matches && (statusFilter === 'all' || k.status === statusFilter)
  })

  const statusLabel = (s: KeyStatus) => t(`keys.status.${s}`, s)

  return (
    <div>
      <PageHead
        title={t('keys.title', 'Keys')}
        desc={t('keys.count', '{{count}} keys', { count: filtered.length })}
        actions={
          canManage ? (
            <Button variant="default" onClick={() => openEdit('new')}>
              <IconPlus size={16} />
              {t('keys.add', 'Add key')}
            </Button>
          ) : undefined
        }
      />

      <DataTable
        breakpoint="wide"
        data={filtered}
        loading={isLoading}
        emptyMessage={t('keys.empty', 'No keys yet.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('keys.search', 'Search label, number, holder…')}
        onRowClick={(k) => setHistoryId(k.id)}
        getRowKey={(k) => k.id}
        filters={(['all', 'available', 'issued', 'lost'] as const).map((s) => ({
          label: s === 'all' ? t('common.all', 'All') : statusLabel(s),
          value: s,
          active: statusFilter === s,
          onClick: () => setStatusFilter(s),
        }))}
        columns={[
          {
            key: 'label',
            header: t('keys.label', 'Label'),
            render: (k) => (
              <span>
                <strong>{k.label}</strong>
                {k.number && (
                  <span className="num" style={{ color: '#6b7480', marginLeft: 8 }}>
                    {k.number}
                  </span>
                )}
              </span>
            ),
          },
          {
            key: 'kind',
            header: t('keys.kind', 'Type'),
            render: (k) => t(`keys.kinds.${k.kind}`, k.kind),
          },
          {
            key: 'opens',
            header: t('keys.opens', 'Opens'),
            render: (k) => <span style={{ color: '#6b7480' }}>{k.opens ?? '—'}</span>,
          },
          {
            key: 'status',
            header: t('keys.statusLabel', 'Status'),
            render: (k) => (
              <span
                className="chip"
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: STATUS_COLORS[k.status],
                }}
              >
                {statusLabel(k.status)}
              </span>
            ),
          },
          {
            key: 'holder',
            header: t('keys.holder', 'Holder'),
            render: (k) => k.holderName ?? '—',
          },
          {
            key: 'deposit',
            header: t('keys.deposit', 'Deposit'),
            render: (k) => (k.depositChf ? <span className="num">CHF {k.depositChf}</span> : '—'),
          },
          {
            key: 'actions',
            header: t('common.actions'),
            width: 60,
            render: (k) =>
              canManage ? (
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon
                      variant="subtle"
                      aria-label={t('common.actions')}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <IconDots size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown onClick={(e) => e.stopPropagation()}>
                    {k.status === 'available' && (
                      <Menu.Item onClick={() => setIssuing(k)}>
                        {t('keys.issue', 'Hand out')}
                      </Menu.Item>
                    )}
                    {k.status === 'issued' && (
                      <Menu.Item onClick={() => run(k, 'return')}>
                        {t('keys.return', 'Take back')}
                      </Menu.Item>
                    )}
                    {(k.status === 'available' || k.status === 'issued') && (
                      <Menu.Item onClick={() => run(k, 'lost')}>
                        {t('keys.markLost', 'Mark as lost')}
                      </Menu.Item>
                    )}
                    {k.status === 'lost' && (
                      <Menu.Item onClick={() => run(k, 'found')}>
                        {t('keys.markFound', 'Found again')}
                      </Menu.Item>
                    )}
                    {k.status !== 'retired' && k.status !== 'issued' && (
                      <Menu.Item onClick={() => run(k, 'retire')}>
                        {t('keys.retire', 'Retire')}
                      </Menu.Item>
                    )}
                    <Menu.Item onClick={() => openEdit(k)}>{t('common.edit', 'Edit')}</Menu.Item>
                    {k.status !== 'issued' && (
                      <Menu.Item color="red" onClick={() => setDeleting(k)}>
                        {t('common.delete', 'Delete')}
                      </Menu.Item>
                    )}
                  </Menu.Dropdown>
                </Menu>
              ) : null,
          },
        ]}
      />

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? t('keys.add', 'Add key') : t('keys.edit', 'Edit key')}
        footer={
          <>
            <Button variant="subtle" onClick={() => setEditing(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="default" onClick={save} disabled={!form.label?.trim()}>
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('keys.label', 'Label')}>
            <TextInput
              value={form.label ?? ''}
              onChange={(e) => setForm({ ...form, label: e.currentTarget.value })}
              placeholder={t('keys.labelPlaceholder', 'Front door')}
            />
          </Field>
          <Field label={t('keys.number', 'Number')}>
            <TextInput
              value={form.number ?? ''}
              onChange={(e) => setForm({ ...form, number: e.currentTarget.value })}
              placeholder="A-12"
            />
          </Field>
          <Field label={t('keys.kind', 'Type')}>
            <Select
              value={form.kind}
              onChange={(v) => setForm({ ...form, kind: (v as KeyKind) ?? 'key' })}
              data={(['key', 'card', 'fob'] as const).map((k) => ({
                value: k,
                label: t(`keys.kinds.${k}`, k),
              }))}
              allowDeselect={false}
            />
          </Field>
          <Field label={t('keys.opens', 'Opens')}>
            <TextInput
              value={form.opens ?? ''}
              onChange={(e) => setForm({ ...form, opens: e.currentTarget.value })}
              placeholder={t('keys.opensPlaceholder', 'Main entrance, workshop')}
            />
          </Field>
          <Field label={t('keys.deposit', 'Deposit')}>
            <NumberInput
              value={form.deposit_chf ?? ''}
              onChange={(v) => setForm({ ...form, deposit_chf: v === '' ? null : Number(v) })}
              min={0}
              decimalScale={2}
              prefix="CHF "
            />
          </Field>
          <Field label={t('keys.notes', 'Notes')}>
            <Textarea
              value={form.notes ?? ''}
              onChange={(e) => setForm({ ...form, notes: e.currentTarget.value })}
              rows={3}
            />
          </Field>
        </div>
      </Modal>

      {issuing && (
        <IssueModal
          clubKey={issuing}
          onClose={() => setIssuing(null)}
          onDone={async () => {
            await refresh()
            setIssuing(null)
          }}
          onError={fail}
        />
      )}

      {historyId !== null && <HistoryModal keyId={historyId} onClose={() => setHistoryId(null)} />}

      <ConfirmModal
        open={!!deleting}
        title={t('keys.delete', 'Delete key')}
        body={
          deleting
            ? t('keys.deleteConfirm', 'Delete {{name}} and its history?', {
                name: deleting.label,
              })
            : undefined
        }
        onConfirm={remove}
        onClose={() => setDeleting(null)}
      />
    </div>
  )
}

function IssueModal({
  clubKey,
  onClose,
  onDone,
  onError,
}: {
  clubKey: ClubKey
  onClose: () => void
  onDone: () => void
  onError: (err: unknown) => void
}) {
  const { t } = useT()
  const [memberId, setMemberId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({
    queryKey: ['members'],
    queryFn: () => listMembers({ pageSize: 500 }),
  })
  const options = useMemo(
    () => (data?.members ?? []).map((m) => ({ value: m.id, label: m.name })),
    [data],
  )

  const submit = async () => {
    if (!memberId) return
    setBusy(true)
    try {
      await issueKey(clubKey.id, Number(memberId), note || undefined)
      onDone()
    } catch (err) {
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('keys.issueTitle', 'Hand out {{name}}', { name: clubKey.label })}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="default" onClick={submit} loading={busy} disabled={!memberId}>
            {t('keys.issue', 'Hand out')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label={t('keys.member', 'Member')}>
          <Select
            searchable
            data={options}
            value={memberId}
            onChange={setMemberId}
            placeholder={t('keys.pickMember', 'Search member…')}
          />
        </Field>
        <Field label={t('keys.note', 'Note')}>
          <TextInput value={note} onChange={(e) => setNote(e.currentTarget.value)} />
        </Field>
      </div>
    </Modal>
  )
}

function HistoryModal({ keyId, onClose }: { keyId: number; onClose: () => void }) {
  const { t } = useT()
  const { data: key } = useQuery({
    queryKey: ['keys', keyId],
    queryFn: () => getKey(keyId),
  })
  return (
    <Modal
      open
      onClose={onClose}
      title={key?.label ?? t('keys.title', 'Keys')}
      subtitle={key?.opens ?? undefined}
    >
      {key?.notes && <p style={{ marginTop: 0, color: '#6b7480' }}>{key.notes}</p>}
      {(key?.history ?? []).length === 0 ? (
        <p style={{ color: '#99a2ac' }}>{t('keys.noHistory', 'No handovers yet.')}</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {key?.history?.map((h) => (
            <div
              key={h.id}
              style={{
                padding: '8px 0',
                borderBottom: '1px solid #f0f4f1',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              <strong>{t(`keys.actions.${h.action}`, h.action)}</strong>
              {h.memberName && <> · {h.memberName}</>}
              <div style={{ color: '#6b7480', fontSize: 'var(--mantine-font-size-xs)' }}>
                {new Date(h.at).toLocaleString()}
                {h.byName && <> · {h.byName}</>}
                {h.note && <> · {h.note}</>}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
