import { useState, useEffect } from 'react'
import {
  Button,
  MultiSelect,
  Select,
  SimpleGrid,
  TextInput,
  Textarea,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useT, zmsg } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { Modal, Field } from '@/components/ui'
import type { Member } from '@/types'
import { inviteMember, updateMember } from '@/api/members'
import { getLookups } from '@/api/lookups'
import { roleLabel } from '@/roles'

const STATIC_STATUS = ['active', 'trial', 'inactive', 'suspended'] as const

// Name, email and avatar come from the member's own account, so editing
// shows only what the club can change (name and email sit in the subtitle).
// A club invites by email and never sets a password.
const memberSchema = z.object({
  firstName: z.string(),
  lastName: z.string(),
  email: z.string().email(zmsg('validation.invalidEmail', 'Ungültige E-Mail-Adresse')),
  status: z.string(),
  tier: z.string(),
  roles: z.array(z.string()),
  groups: z.array(z.string()),
  notes: z.string(),
  clubUsername: z.string(),
})
type MemberForm = z.infer<typeof memberSchema>

export function MemberEditModal({
  member,
  mode = 'edit',
  open,
  onClose,
  onSaved,
}: {
  member: Member | null
  mode?: 'create' | 'edit'
  open: boolean
  onClose: () => void
  /** Called with the saved member; after an invite, with null. */
  onSaved: (m: Member | null) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [allTiers, setAllTiers] = useState<string[]>([])
  const [allGroups, setAllGroups] = useState<string[]>([])
  const [allRoles, setAllRoles] = useState<string[]>([])
  const [usernameError, setUsernameError] = useState('')
  const [saving, setSaving] = useState(false)

  const form = useForm<MemberForm>({
    validate: zod4Resolver(memberSchema),
    initialValues: {
      firstName: '',
      lastName: '',
      email: '',
      status: 'trial',
      tier: '',
      roles: ['Member'],
      groups: [],
      notes: '',
      clubUsername: '',
    },
  })

  const watchedGroups = form.values.groups
  const watchedRoles = form.values.roles

  useEffect(() => {
    if (!open) return
    getLookups()
      .then((l) => {
        const tiers = [...l.tiersByName.keys()]
        const roles = [...l.rolesByName.keys()]
        setAllTiers(tiers)
        setAllGroups([...l.groupsByName.keys()])
        setAllRoles(roles)
        if (mode === 'create') {
          form.setValues({
            firstName: '',
            lastName: '',
            email: '',
            status: 'trial',
            tier: tiers[0] ?? '',
            roles: ['Member'],
            groups: [],
            notes: '',
            clubUsername: '',
          })
        }
        if (mode === 'edit' && member) {
          form.setValues({
            firstName: member.firstName ?? '',
            lastName: member.lastName ?? '',
            email: member.email,
            status: member.status,
            tier: member.tier as string,
            roles: member.roles,
            groups: member.groups,
            notes: member.notes,
            clubUsername: member.clubUsername ?? '',
          })
        }
        setUsernameError('')
      })
      .catch((err: unknown) => {
        notify(
          'error',
          t('common.error', 'Fehler'),
          err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
        )
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, member, mode])

  const handleSave = async (data: MemberForm) => {
    setSaving(true)
    setUsernameError('')
    try {
      if (mode === 'create') {
        const res = await inviteMember({
          email: data.email,
          firstName: data.firstName || undefined,
          lastName: data.lastName || undefined,
          tierName: data.tier,
          groupNames: data.groups,
          status: data.status,
          notes: data.notes,
        })
        notify(
          'success',
          t('members.invite.sentTitle', 'Einladung gesendet'),
          t('members.invite.sent', '{{email}} erhält einen Link zum Beitreten.', {
            email: res.email,
          }),
        )
        onSaved(null)
        return
      }
      if (!member) return
      const saved = await updateMember(member.id, {
        status: data.status,
        tierName: data.tier,
        roleNames: data.roles,
        groupNames: data.groups,
        notes: data.notes,
        clubUsername: data.clubUsername || null,
      })
      notify(
        'success',
        t('members.member.updatedTitle'),
        t('members.member.updated', { name: saved.name }),
      )
      onSaved(saved)
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler')
      if (mode === 'edit' && (msg.includes('already taken') || msg.includes('CONFLICT'))) {
        setUsernameError(
          t('members.usernameTaken', 'Dieser Benutzername ist schon vergeben'),
        )
      } else {
        notify(
          'error',
          mode === 'create'
            ? t('members.invite.failed', 'Einladen fehlgeschlagen')
            : t('common.updateFailed'),
          msg,
        )
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      onSubmit={form.onSubmit(handleSave)}
      open={open}
      wide
      onClose={onClose}
      title={
        mode === 'create'
          ? t('members.invite.title', 'Mitglied einladen')
          : t('members.editMemberModalTitle')
      }
      subtitle={
        mode === 'edit'
          ? [member?.name, member?.email].filter(Boolean).join(' · ')
          : t(
              'members.invite.subtitle',
              'Die Person erhält einen persönlichen Link, meldet sich mit dieser Adresse an oder erstellt ein Konto und nimmt an. Name, E-Mail und Kontaktangaben bleiben ihre eigenen.',
            )
      }
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="filled"
            type="submit"
            disabled={saving}
          >
            {mode === 'create'
              ? t('members.invite.send', 'Einladung senden')
              : t('common.saveChanges')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {mode === 'create' && (
          <>
            <Field
              label={t('members.privateEmail')}
              hint={t('members.privateEmailHint')}
            >
              <TextInput
                type="email"
                {...form.getInputProps('email')}
                placeholder="anna@example.com"
              />
            </Field>
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
              <Field
                label={t('common.firstName')}
                hint={t('members.invite.nameHint', 'Nur für die Anrede in der E-Mail')}
              >
                <TextInput {...form.getInputProps('firstName')} placeholder="Anna" />
              </Field>
              <Field label={t('common.lastName')}>
                <TextInput {...form.getInputProps('lastName')} placeholder="Zimmermann" />
              </Field>
            </SimpleGrid>
          </>
        )}
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('common.status')}>
            <Select
              data={STATIC_STATUS.map((s) => ({
                value: s,
                label: t(`status.${s}`),
              }))}
              {...form.getInputProps('status')}
            />
          </Field>
          <Field label={t('members.tier')}>
            <Select
              data={allTiers.map((tp) => ({ value: tp, label: tp }))}
              searchable
              {...form.getInputProps('tier')}
            />
          </Field>
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: mode === 'edit' ? 2 : 1 }} spacing={12}>
          {mode === 'edit' && (
            <Field
              label={t('common.roles', 'Rollen')}
              hint={
                member?.functionRoles?.length
                  ? t('members.functionRolesHint', 'Über Funktionen: {{roles}}. Diese ändern sich mit der Funktion.', {
                      roles: member.functionRoles
                        .map((fr) => `${roleLabel(fr.name)} (${fr.function})`)
                        .join(', '),
                    })
                  : undefined
              }
            >
              <MultiSelect
                data={allRoles.map((r) => ({ value: r, label: roleLabel(r) }))}
                value={watchedRoles}
                onChange={(v) => form.setFieldValue('roles', v)}
                placeholder={t('members.noRolesSelected', 'Rollen wählen …')}
                searchable
                clearable
                hidePickedOptions
                size="sm"
                radius="md"
              />
            </Field>
          )}
          <Field label={t('members.groupsCol')}>
            <MultiSelect
              data={allGroups}
              value={watchedGroups}
              onChange={(v) => form.setFieldValue('groups', v)}
              placeholder={t('members.noGroupsSelected')}
              searchable
              clearable
              hidePickedOptions
              size="sm"
              radius="md"
            />
          </Field>
        </SimpleGrid>
        {mode === 'edit' && (
          <Field
            label={t('members.clubUsername')}
            hint={t('members.clubUsernameHint')}
          >
            <TextInput
              {...form.getInputProps('clubUsername')}
              onChange={(e) => {
                form.getInputProps('clubUsername').onChange(e)
                setUsernameError('')
              }}
              placeholder="firstname.lastname"
            />
            {usernameError && (
              <span
                style={{
                  color: 'var(--mantine-color-red-6)',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {t('members.usernameTaken')}
              </span>
            )}
          </Field>
        )}
        <Field label={t('members.notes')}>
          <Textarea
            rows={3}
            {...form.getInputProps('notes')}
          />
        </Field>
      </div>
    </Modal>
  )
}
