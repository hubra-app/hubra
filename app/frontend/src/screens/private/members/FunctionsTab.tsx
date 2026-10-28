import { useState, useMemo } from 'react'
import { Button, Group, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT, zmsg } from '@/locales/i18n'
import {
  IconPlus,
  IconPencil,
  IconTrash,
  IconUserCog,
  IconMail as MailIcon,
} from '@tabler/icons-react'
import { useToast, useAuth, useData } from '@/context/AppContext'
import {
  Modal,
  Field,
  ConfirmModal,
  LoadingSpinner,
  EmptyState,
  CardGrid,
  CardItem,
  MemberSlideOver,
  type SlideOverMember,
} from '@/components/ui'
import type { ClubFunction } from '@/types'
import {
  listFunctions,
  createFunction,
  updateFunction,
  deleteFunction,
  assignHolder,
  removeHolder,
} from '@/api/functions'
import { listMembers } from '@/api/members'
import { withBase } from '@/clubBase'

const functionSchema = z.object({
  name: z.string().min(1, zmsg('common.nameRequired', 'Name ist erforderlich')),
  description: z.string(),
  maxHolders: z.number().min(1),
})
type FunctionForm = z.infer<typeof functionSchema>

export function FunctionsTab() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('functions.functions.create')
  const canUpdate = hasPermission('functions.functions.update')
  const canDelete = hasPermission('functions.functions.delete')
  const { data: functions = [], isLoading: loading } = useQuery({
    queryKey: ['functions'],
    queryFn: () => listFunctions(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ClubFunction | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClubFunction | null>(null)
  const [manageHolders, setManageHolders] = useState<ClubFunction | null>(null)

  const form = useForm<FunctionForm>({
    validate: zodResolver(functionSchema),
    initialValues: {
      name: '',
      description: '',
      maxHolders: 1,
    },
  })

  const openAdd = () => {
    form.setValues({
      name: '',
      description: '',
      maxHolders: 1,
    })
    setAddOpen(true)
  }

  const openEdit = (fn: ClubFunction) => {
    setEditTarget(fn)
    form.setValues({
      name: fn.name,
      description: fn.description ?? '',
      maxHolders: fn.maxHolders,
    })
  }

  const saveAdd = async (data: FunctionForm) => {
    try {
      await createFunction({
        name: data.name,
        description: data.description || undefined,
        maxHolders: data.maxHolders,
      })
      queryClient.invalidateQueries({ queryKey: ['functions'] })
      setAddOpen(false)
      notify(
        'success',
        t('common.saved', 'Gespeichert'),
        t('common.created', 'Erstellt'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : 'Unbekannter Fehler',
      )
    }
  }

  const saveEdit = async (data: FunctionForm) => {
    if (!editTarget) return
    try {
      await updateFunction(editTarget.id, {
        name: data.name,
        description: data.description || undefined,
        maxHolders: data.maxHolders,
      })
      queryClient.invalidateQueries({ queryKey: ['functions'] })
      setEditTarget(null)
      notify(
        'success',
        t('common.saved', 'Gespeichert'),
        t('common.updated', 'Gespeichert'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : 'Unbekannter Fehler',
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteFunction(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['functions'] })
      notify(
        'info',
        t('functions.deleted', 'Gelöscht'),
        t('functions.deletedMsg', 'Die Funktion wurde gelöscht.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : 'Unbekannter Fehler',
      )
    }
  }

  const functionForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('common.name', 'Name')}>
        <TextInput
          {...form.getInputProps('name')}
          placeholder={t('common.namePlaceholder', 'Name')}
        />
      </Field>
      <Field label={t('common.description', 'Beschreibung')}>
        <Textarea
          rows={2}
          {...form.getInputProps('description')}
          placeholder={t('functions.descPlaceholder', 'Kurze Beschreibung …')}
        />
      </Field>
      <Field label={t('functions.maxHolders', 'Max. Anzahl Personen')}>
        <TextInput
          type="number"
          min={1}
          {...form.getInputProps('maxHolders', { valueAsNumber: true })}
        />
      </Field>
    </div>
  )

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('common.add', 'Hinzufügen')}
          </Button>
        </Group>
      )}
      {loading ? (
        <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
      ) : functions.length === 0 ? (
        <EmptyState title={t('functions.empty', 'Noch keine Funktionen.')} />
      ) : (
        <CardGrid columns={3}>
          {functions.map((fn) => (
            <CardItem
              key={fn.id}
              icon={
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: '#f4f2f9',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <IconUserCog size={18} color="#5e5873" />
                </div>
              }
              title={fn.name}
              subtitle={fn.description ?? undefined}
              footer={
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ flex: 1 }}
                    onClick={() => setManageHolders(fn)}
                  >
                    <IconUserCog size={16} />
                    {t('functions.holders', 'Besetzt durch')} ({fn.holders.length}/
                    {fn.maxHolders})
                  </Button>
                  {canUpdate && (
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => openEdit(fn)}
                    >
                      <IconPencil size={16} />
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="subtle"
                      style={{ color: '#ff4d3d' }}
                      onClick={() => setDeleteTarget(fn)}
                    >
                      <IconTrash size={16} />
                    </Button>
                  )}
                </div>
              }
            >
              {fn.holders.length > 0 ? (
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    flexWrap: 'wrap',
                    marginBottom: 4,
                  }}
                >
                  {fn.holders.map((h) => (
                    <span
                      key={h.memberId}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#2e2940',
                        background: '#f4f2f9',
                        borderRadius: 6,
                        padding: '3px 8px',
                      }}
                    >
                      {h.memberName}
                    </span>
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#8c86a0',
                  }}
                >
                  {t('functions.noHolder', 'Unbesetzt')}
                </div>
              )}
            </CardItem>
          ))}
        </CardGrid>
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('common.add', 'Hinzufügen')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={() => form.onSubmit(saveAdd)()}>
              {t('common.create', 'Erstellen')}
            </Button>
          </>
        }
      >
        {functionForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('common.edit', 'Bearbeiten')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={() => form.onSubmit(saveEdit)()}>
              {t('common.save', 'Speichern')}
            </Button>
          </>
        }
      >
        {functionForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('functions.deleteTitle', 'Funktion löschen?')}
        body={t(
          'functions.deleteBody',
          'Die Funktion wird gelöscht. Ihre Mail-Adressen werden entfernt.',
        )}
        onConfirm={confirmDelete}
      />
      {manageHolders && (
        <HolderPanel
          fn={manageHolders}
          onClose={() => {
            setManageHolders(null)
            queryClient.invalidateQueries({ queryKey: ['functions'] })
          }}
        />
      )}
    </div>
  )
}

interface HolderEntry {
  memberId: number
  memberName: string
  memberColor: string
  assignedAt: string | null
}

function HolderPanel({
  fn,
  onClose,
}: {
  fn: ClubFunction
  onClose: () => void
}) {
  const { notify } = useToast()
  const { modules } = useData()
  const { t } = useT()
  const [searchQuery, setSearchQuery] = useState('')
  const [holders, setHolders] = useState<HolderEntry[]>(() =>
    fn.holders.map((h) => ({ ...h, memberColor: '#5e5873' })),
  )

  const { data: searchData } = useQuery({
    queryKey: ['members-search', searchQuery],
    queryFn: () => listMembers({ search: searchQuery, pageSize: 10 }),
    enabled: searchQuery.length >= 2,
  })

  const slideMembers: SlideOverMember[] = useMemo(
    () =>
      holders.map((h) => ({
        id: String(h.memberId),
        name: h.memberName,
        email: '',
        avatarColor: h.memberColor,
      })),
    [holders],
  )

  const searchResults = useMemo(() => {
    if (!searchData || searchQuery.length < 2) return undefined
    const holderIds = new Set(holders.map((h) => h.memberId))
    return searchData.members
      .filter((m) => !holderIds.has(Number(m.id)))
      .map((m) => ({
        id: m.id,
        name: m.name,
        email: m.email,
        avatarColor: m.avatarColor,
      }))
  }, [searchData, holders, searchQuery])

  const handleAdd = (m: SlideOverMember) => {
    assignHolder(fn.id, Number(m.id))
      .then(() => {
        setHolders((prev) => [
          ...prev,
          {
            memberId: Number(m.id),
            memberName: m.name,
            memberColor: m.avatarColor,
            assignedAt: new Date().toISOString(),
          },
        ])
        notify(
          'success',
          t('common.saved', 'Gespeichert'),
          `${m.name} → ${fn.name}`,
        )
      })
      .catch((err: unknown) =>
        notify(
          'error',
          t('common.error'),
          err instanceof Error ? err.message : 'Unbekannter Fehler',
        ),
      )
  }

  const handleRemove = (m: SlideOverMember) => {
    removeHolder(fn.id, Number(m.id))
      .then(() => {
        setHolders((prev) => prev.filter((h) => h.memberId !== Number(m.id)))
        notify(
          'info',
          t('common.removed', 'Entfernt'),
          `${m.name} ← ${fn.name}`,
        )
      })
      .catch((err: unknown) =>
        notify(
          'error',
          t('common.error'),
          err instanceof Error ? err.message : 'Unbekannter Fehler',
        ),
      )
  }

  const canAdd = holders.length < fn.maxHolders

  return (
    <MemberSlideOver
      title={fn.name}
      subtitle={`${t('functions.manageHolders', 'Personen verwalten')} · ${
        holders.length
      }/${fn.maxHolders}`}
      icon={
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: '#f4f2f9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <IconUserCog size={16} color="#5e5873" />
        </div>
      }
      members={slideMembers}
      addLabel={
        canAdd ? t('functions.assignHolder', 'Person zuweisen') : undefined
      }
      addPlaceholder={t('functions.searchMembers', 'Mitglieder suchen …')}
      searchResults={canAdd ? searchResults : undefined}
      onAdd={canAdd ? handleAdd : undefined}
      onAddSearch={setSearchQuery}
      onRemove={handleRemove}
      showRemove
      onClose={onClose}
      footer={
        modules.mail ? (
          <div
            style={{
              padding: '12px 0',
              borderTop: '1px solid #e6e3ef',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: 600,
                color: '#5e5873',
              }}
            >
              <MailIcon size={13} />
              {t('mail.mail', 'Mail')}
            </div>
            <a
              href={withBase('/app/mail?tab=functions')}
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#2596be',
                textDecoration: 'none',
              }}
            >
              {t('mail.admin.openInMailAdmin', 'In der Mail-Verwaltung öffnen')} →
            </a>
          </div>
        ) : null
      }
    />
  )
}
