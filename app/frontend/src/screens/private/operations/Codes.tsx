import { useState } from 'react'
import {
  Button,
  TextInput,
  Textarea,
  ActionIcon,
  CopyButton,
  Group,
  Paper,
  PinInput,
  Slider,
  Text,
  Tooltip,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT, zmsg } from '@/locales/i18n'
import { IconPlus, IconEye, IconEyeOff, IconCopy, IconCheck } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  Modal,
  Field,
  ConfirmModal,
  DataTable,
  ActionButtons,
  useSubmitOnce,
} from '@/components/ui'
import type { Code } from '@/types'
import { listCodes, createCode, updateCode, deleteCode } from '@/api/codes'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'

const codeSchema = z.object({
  name: z.string().min(1, zmsg('common.nameRequired', 'Name ist erforderlich')),
  code: z.string().min(1, zmsg('validation.codeRequired', 'Code ist erforderlich')),
  description: z.string(),
  isActive: z.boolean(),
})
type CodeForm = z.infer<typeof codeSchema>

export function CodesScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const { data: codes = [], isLoading: loading } = useQuery({
    queryKey: qk.codes,
    queryFn: () => listCodes(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Code | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Code | null>(null)
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [codeLength, setCodeLength] = useState(4)

  const form = useForm<CodeForm>({
    validate: zod4Resolver(codeSchema),
    initialValues: { name: '', code: '', description: '', isActive: true },
  })

  const canCreate = hasPermission('codes.codes.create')
  const canUpdate = hasPermission('codes.codes.update')
  const canDelete = hasPermission('codes.codes.delete')

  const openAdd = () => {
    form.setValues({ name: '', code: '', description: '', isActive: true })
    setCodeLength(4)
    setAddOpen(true)
  }

  const openEdit = (c: Code) => {
    setEditTarget(c)
    setCodeLength(c.code.length || 4)
    form.setValues({
      name: c.name,
      code: c.code,
      description: c.description ?? '',
      isActive: c.isActive,
    })
  }

  const saveAdd = async (data: CodeForm) => {
    try {
      await createCode({
        name: data.name,
        code: data.code,
        description: data.description || null,
      })
      queryClient.invalidateQueries({ queryKey: qk.codes })
      setAddOpen(false)
      notify('success', t('codes.saved'))
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : t('codes.saveError'))
    }
  }
  const [submitAdd, adding] = useSubmitOnce(saveAdd)

  const saveEdit = async (data: CodeForm) => {
    if (!editTarget) return
    try {
      await updateCode(editTarget.id, {
        name: data.name,
        code: data.code,
        description: data.description || null,
        isActive: data.isActive,
      })
      queryClient.invalidateQueries({ queryKey: qk.codes })
      setEditTarget(null)
      notify('success', t('codes.saved'))
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : t('codes.saveError'))
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteCode(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.codes })
      setDeleteTarget(null)
      notify('success', t('codes.deleted'))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('codes.deleteError'),
      )
    }
  }

  const toggleVisible = (id: string) => {
    setVisibleIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const renderCard = (c: Code) => {
    const visible = visibleIds.has(c.id)
    return (
      <Paper
        withBorder
        radius="lg"
        p="md"
        h="100%"
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Text fw={700} style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
            {c.name}
          </Text>
          <span
            className={`chip${c.isActive ? ' on' : ''}`}
            style={{ fontSize: 'var(--mantine-font-size-xs)', flexShrink: 0 }}
          >
            {c.isActive ? t('codes.active') : t('codes.inactive')}
          </span>
        </Group>
        <Group gap={6} wrap="nowrap">
          <code
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 'var(--mantine-font-size-xl)',
              fontWeight: 700,
              textAlign: 'center',
              background: 'var(--hb-surface-2)',
              padding: '10px 12px',
              borderRadius: 10,
              letterSpacing: visible ? '0.12em' : '0.2em',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {visible ? c.code : '\u2022'.repeat(c.code.length)}
          </code>
          <ActionIcon
            variant="subtle"
            onClick={() => toggleVisible(c.id)}
            title={visible ? t('codes.codeHidden') : t('codes.codeVisible')}
          >
            {visible ? <IconEyeOff size={18} /> : <IconEye size={18} />}
          </ActionIcon>
          <CopyButton value={c.code} timeout={1500}>
            {({ copied, copy }) => (
              <Tooltip
                label={copied ? t('common.copied', 'Kopiert') : t('common.copy', 'Kopieren')}
                withArrow
              >
                <ActionIcon variant="subtle" color={copied ? 'green' : undefined} onClick={copy}>
                  {copied ? <IconCheck size={18} /> : <IconCopy size={18} />}
                </ActionIcon>
              </Tooltip>
            )}
          </CopyButton>
        </Group>
        {c.description && (
          <Text size="sm" c="dimmed">
            {c.description}
          </Text>
        )}
        <Group
          justify="space-between"
          mt="auto"
          pt={8}
          style={{ borderTop: '1px solid var(--hb-border)' }}
        >
          <Text size="xs" c="dimmed" className="num">
            {formatDate(c.updatedAt)}
          </Text>
          <ActionButtons
            onEdit={canUpdate ? () => openEdit(c) : undefined}
            onDelete={canDelete ? () => setDeleteTarget(c) : undefined}
          />
        </Group>
      </Paper>
    )
  }

  const filtered = codes.filter((c) => {
    const q = search.toLowerCase()
    const matchSearch = !q || c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q)
    const matchStatus =
      statusFilter === 'All' ||
      (statusFilter === 'Active' && c.isActive) ||
      (statusFilter === 'Inactive' && !c.isActive)
    return matchSearch && matchStatus
  })

  return (
    <div>
      <PageHead
        title={t('codes.title')}
        desc={t('codes.count', '{{count}} Codes', { count: filtered.length })}
        actions={
          canCreate ? (
            <Button variant="default" onClick={openAdd}>
              <IconPlus size={16} />
              {t('codes.add')}
            </Button>
          ) : undefined
        }
      />

      <DataTable
        breakpoint="wide"
        columns={[
          {
            key: 'name',
            header: t('codes.name'),
            render: (c) => c.name,
          },
          {
            key: 'code',
            header: t('codes.code'),
            render: (c) => {
              const visible = visibleIds.has(c.id)
              return (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <code
                    style={{
                      fontFamily: '"JetBrains Mono", monospace',
                      fontSize: 'var(--mantine-font-size-sm)',
                      background: 'var(--hb-surface-2)',
                      padding: '2px 8px',
                      borderRadius: 4,
                      letterSpacing: visible ? '0.06em' : '0.15em',
                    }}
                  >
                    {visible ? c.code : '\u2022'.repeat(c.code.length)}
                  </code>
                  <ActionIcon
                    variant="subtle"
                    style={{ width: 28, height: 28, padding: 0 }}
                    onClick={() => toggleVisible(c.id)}
                    title={visible ? t('codes.codeHidden') : t('codes.codeVisible')}
                  >
                    {visible ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                  </ActionIcon>
                </span>
              )
            },
          },
          {
            key: 'description',
            header: t('codes.description'),
            render: (c) => <span style={{ color: 'var(--hb-text-2)' }}>{c.description ?? '—'}</span>,
          },
          {
            key: 'status',
            header: t('codes.status'),
            render: (c) => (
              <span
                className={`chip${c.isActive ? ' on' : ''}`}
                style={{ fontSize: 'var(--mantine-font-size-xs)' }}
              >
                {c.isActive ? t('codes.active') : t('codes.inactive')}
              </span>
            ),
          },
          {
            key: 'updatedAt',
            header: t('codes.lastUpdated'),
            render: (c) => (
              <span
                className="num"
                style={{
                  color: 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {formatDate(c.updatedAt)}
              </span>
            ),
          },
          {
            key: 'actions',
            header: t('common.actions'),
            width: 80,
            render: (c) => (
              <ActionButtons
                onEdit={canUpdate ? () => openEdit(c) : undefined}
                onDelete={canDelete ? () => setDeleteTarget(c) : undefined}
              />
            ),
          },
        ]}
        data={filtered}
        loading={loading}
        emptyMessage={t('codes.noCodes')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('codes.searchPlaceholder', 'Suchen …')}
        filters={[
          {
            label: t('common.all', 'Alle'),
            value: 'all',
            active: statusFilter === 'All',
            onClick: () => setStatusFilter('All'),
          },
          {
            label: t('codes.active'),
            value: 'active',
            active: statusFilter === 'Active',
            onClick: () => setStatusFilter('Active'),
          },
          {
            label: t('codes.inactive'),
            value: 'inactive',
            active: statusFilter === 'Inactive',
            onClick: () => setStatusFilter('Inactive'),
          },
        ]}
        getRowKey={(c) => c.id}
        renderCard={renderCard}
        viewKey="codes"
      />

      {/* Add Modal */}
      <Modal
        onSubmit={form.onSubmit(submitAdd)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('codes.add')}
        footer={
          <>
            <Button variant="subtle" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="default" type="submit" loading={adding}>
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('codes.name')}>
            <TextInput {...form.getInputProps('name')} placeholder={t('codes.namePlaceholder')} />
          </Field>
          <Field
            label={t('codes.code')}
            hint={t('codes.lengthHint', 'Mit dem Regler stellst du die Länge des Codes ein')}
          >
            <Slider
              value={codeLength}
              onChange={setCodeLength}
              min={2}
              max={16}
              label={(val) => `${val} chars`}
              mb="sm"
            />
            <PinInput
              value={form.values.code}
              onChange={(val) => form.setFieldValue('code', val)}
              length={codeLength}
              type="alphanumeric"
              mask={false}
              aria-label={t('codes.code', 'Code')}
              size="sm"
            />
          </Field>
          <Field label={t('codes.description')}>
            <Textarea
              {...form.getInputProps('description')}
              placeholder={t('codes.descriptionPlaceholder')}
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </Field>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        onSubmit={form.onSubmit(saveEdit)}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('codes.edit')}
        footer={
          <>
            <Button variant="subtle" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="default" type="submit">
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('codes.name')}>
            <TextInput {...form.getInputProps('name')} />
          </Field>
          <Field
            label={t('codes.code')}
            hint={t('codes.lengthHint', 'Mit dem Regler stellst du die Länge des Codes ein')}
          >
            <Slider
              value={codeLength}
              onChange={setCodeLength}
              min={2}
              max={16}
              label={(val) => `${val} chars`}
              mb="sm"
            />
            <PinInput
              value={form.values.code}
              onChange={(val) => form.setFieldValue('code', val)}
              length={codeLength}
              type="alphanumeric"
              mask={false}
              aria-label={t('codes.code', 'Code')}
              size="sm"
            />
          </Field>
          <Field label={t('codes.description')}>
            <Textarea
              {...form.getInputProps('description')}
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </Field>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 'var(--mantine-font-size-sm)',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              {...form.getInputProps('isActive')}
              style={{ width: 16, height: 16 }}
            />
            {t('codes.active')}
          </label>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmModal
        open={!!deleteTarget}
        title={t('codes.delete')}
        body={deleteTarget ? t('codes.deleteConfirm', { name: deleteTarget.name }) : undefined}
        onConfirm={handleDelete}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}
