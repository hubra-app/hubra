import { useState, useEffect } from 'react'
import {
  Button,
  MultiSelect,
  Select,
  PasswordInput,
  TextInput,
  Textarea,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { Modal, Field } from '@/components/ui'
import type { Member } from '@/types'
import { createMember, updateMember, setMemberPassword } from '@/api/members'
import { getLookups } from '@/api/lookups'
import { roleLabel } from '@/roles'

const STATIC_STATUS = ['active', 'trial', 'inactive', 'suspended'] as const

const memberSchema = z.object({
  firstName: z.string().min(1, 'First name is required'),
  lastName: z.string(),
  email: z.string().email('Invalid email'),
  status: z.string(),
  tier: z.string(),
  roles: z.array(z.string()),
  groups: z.array(z.string()),
  notes: z.string(),
  clubUsername: z.string(),
  mustChangePw: z.boolean(),
  avatarColor: z.string(),
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
  onSaved: (m: Member) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [allTiers, setAllTiers] = useState<string[]>([])
  const [allGroups, setAllGroups] = useState<string[]>([])
  const [allRoles, setAllRoles] = useState<string[]>([])
  const [usernameError, setUsernameError] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [generatedPw, setGeneratedPw] = useState('')
  const [saving, setSaving] = useState(false)
  const [pwSaving, setPwSaving] = useState(false)

  const form = useForm<MemberForm>({
    validate: zodResolver(memberSchema),
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
      mustChangePw: false,
      avatarColor: '#7441e0',
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
            mustChangePw: false,
            avatarColor: '#7441e0',
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
            mustChangePw: member.mustChangePassword ?? false,
            avatarColor: member.avatarColor ?? '#7441e0',
          })
        }
        setUsernameError('')
        setNewPassword('')
        setGeneratedPw('')
      })
      .catch((err: unknown) => {
        notify(
          'error',
          t('common.error', 'Fehler'),
          err instanceof Error ? err.message : 'Could not load lookups',
        )
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, member, mode])

  const handleSave = async (data: MemberForm) => {
    setSaving(true)
    setUsernameError('')
    try {
      let saved: Member
      if (mode === 'create') {
        saved = await createMember({
          firstName: data.firstName,
          lastName: data.lastName,
          email: data.email,
          tierName: data.tier,
          roleNames: data.roles,
          groupNames: data.groups,
          status: data.status,
          notes: data.notes,
          avatarColor: data.avatarColor,
        })
        notify(
          'success',
          t('members.member.addedTitle'),
          t('members.member.added', { name: saved.name }),
        )
      } else {
        if (!member) return
        saved = await updateMember(member.id, {
          firstName: data.firstName,
          lastName: data.lastName,
          status: data.status,
          tierName: data.tier,
          roleNames: data.roles,
          groupNames: data.groups,
          email: data.email,
          notes: data.notes,
          clubUsername: data.clubUsername || null,
          mustChangePassword: data.mustChangePw,
          avatarColor: data.avatarColor,
        })
        notify(
          'success',
          t('members.member.updatedTitle'),
          t('members.member.updated', { name: saved.name }),
        )
      }
      onSaved(saved)
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler')
      if (msg.includes('already taken') || msg.includes('CONFLICT')) {
        setUsernameError(
          t('members.usernameTaken', 'Dieser Benutzername ist schon vergeben'),
        )
      } else {
        notify(
          'error',
          mode === 'create' ? t('members.addFailed') : t('common.updateFailed'),
          msg,
        )
      }
    } finally {
      setSaving(false)
    }
  }

  const handleSetPassword = async () => {
    if (!member) return
    setPwSaving(true)
    setGeneratedPw('')
    try {
      const res = await setMemberPassword(member.id, {
        password: newPassword || undefined,
        generate: !newPassword,
      })
      if (res.generatedPassword) setGeneratedPw(res.generatedPassword)
      setNewPassword('')
      notify(
        'success',
        t('members.password.updated', 'Passwort geändert'),
        t(
          'members.password.updatedMsg',
          'Das Passwort des Mitglieds wurde geändert.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('members.password.updateFailed'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setPwSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        mode === 'create'
          ? t('common.addMember')
          : t('members.editMemberModalTitle')
      }
      subtitle={
        mode === 'edit' ? member?.name : t('members.newMemberStatusNote')
      }
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="filled"
            onClick={() => form.onSubmit(handleSave)()}
            disabled={saving}
          >
            {mode === 'create'
              ? t('common.addMember')
              : t('common.saveChanges')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div
          className="grid-2"
          style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
        >
          <Field label={t('common.firstName')}>
            <TextInput
              {...form.getInputProps('firstName')}
              placeholder="Anna"
            />
          </Field>
          <Field label={t('common.lastName')}>
            <TextInput
              {...form.getInputProps('lastName')}
              placeholder="Zimmermann"
            />
          </Field>
        </div>
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
        <Field label={t('members.avatarColor', 'Avatar-Farbe')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="color"
              {...form.getInputProps('avatarColor')}
              style={{
                width: 48,
                height: 36,
                padding: '2px 4px',
                cursor: 'pointer',
                borderRadius: 6,
                border: '1px solid #d6d2e3',
              }}
            />
            <span
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: 'var(--mantine-color-ink-4)',
              }}
            >
              {form.values.avatarColor}
            </span>
          </div>
        </Field>
        <Field label={t('common.status')}>
          <Select
            data={STATIC_STATUS.map((s) => ({
              value: s,
              label: s.charAt(0).toUpperCase() + s.slice(1),
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
        <Field label={t('common.roles', 'Rollen')}>
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
        <Field label={t('members.notes')}>
          <Textarea
            rows={3}
            {...form.getInputProps('notes')}
            placeholder="Admin notes about this member\u2026"
          />
        </Field>
        {mode === 'edit' && (
          <>
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
                {...form.getInputProps('mustChangePw')}
                style={{ accentColor: 'var(--mantine-color-acc-4)' }}
              />
              {t('members.forcePasswordChange')}
            </label>
            <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 12 }}>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                {t('members.setPassword')}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <PasswordInput
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder={t('members.newPasswordPlaceholder')}
                  style={{ flex: 1 }}
                />
                <Button
                  variant="default"
                  onClick={handleSetPassword}
                  disabled={pwSaving}
                  type="button"
                >
                  {newPassword ? t('members.set') : t('members.generate')}
                </Button>
              </div>
              {generatedPw && (
                <div
                  style={{
                    marginTop: 8,
                    padding: '6px 10px',
                    background: 'var(--mantine-color-green-0)',
                    border: '1px solid var(--mantine-color-green-3)',
                    borderRadius: 6,
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontFamily: 'monospace',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span style={{ flex: 1 }}>{generatedPw}</span>
                  <button
                    type="button"
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      padding: '2px 6px',
                    }}
                    onClick={() => navigator.clipboard.writeText(generatedPw)}
                  >
                    {t('common.copy')}
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
