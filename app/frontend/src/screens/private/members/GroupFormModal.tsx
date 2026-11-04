import { Badge, Button, SegmentedControl, SimpleGrid, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { IconEye, IconLock, IconWorld } from '@tabler/icons-react'
import { useT, zmsg } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { Field, Modal, useSubmitOnce } from '@/components/ui'
import { MemberPicker } from '@/components/MemberPicker'
import type { Group, GroupVisibility } from '@/types'
import { createGroup, updateGroup } from '@/api/groups'
import { qk } from '@/data/keys'
import { VISIBILITIES } from './groupVisibility'

const VISIBILITY_ICON = { open: IconWorld, visible: IconEye, private: IconLock }
const VISIBILITY_COLOR = { open: 'green', visible: 'gray', private: 'grape' }

export function VisibilityBadge({ visibility }: { visibility: GroupVisibility }) {
  const { t } = useT()
  const Icon = VISIBILITY_ICON[visibility]
  return (
    <Badge
      variant="light"
      color={VISIBILITY_COLOR[visibility]}
      leftSection={<Icon size={12} />}
      title={t(`groups.visibility.${visibility}Hint`)}
    >
      {t(`groups.visibility.${visibility}`)}
    </Badge>
  )
}

const groupSchema = z.object({
  name: z.string().min(1, zmsg('common.nameRequired', 'Name ist erforderlich')),
  description: z.string(),
  color: z.string(),
  sessions: z.string(),
  leadId: z.string(),
  visibility: z.enum(['open', 'visible', 'private']),
})
type GroupForm = z.infer<typeof groupSchema>

/** Create a group ('new') or change one, from the list or the group's page.
 * Mount it with a `key` per target so the form starts from that group. */
export function GroupFormModal({
  target,
  onClose,
}: {
  target: Group | 'new' | null
  onClose: () => void
}) {
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const group = target && target !== 'new' ? target : null
  // A leader edits how the group presents itself; the API keeps its name and
  // leader with the club.
  const leaderOnly =
    group != null &&
    !hasPermission('groups.groups.update') &&
    !hasPermission('groups.groups.update', group.id) &&
    currentUser != null &&
    group.leadId === Number(currentUser.id)

  const form = useForm<GroupForm>({
    validate: zod4Resolver(groupSchema),
    initialValues: group
      ? {
          name: group.name,
          description: group.description,
          color: group.color,
          sessions: group.sessions,
          leadId: '',
          visibility: group.visibility ?? 'visible',
        }
      : {
          name: '',
          description: '',
          color: '#2596be',
          sessions: '',
          leadId: '',
          visibility: 'visible',
        },
  })

  const save = async (data: GroupForm) => {
    try {
      if (group) {
        await updateGroup(group.id, {
          name: data.name,
          description: data.description,
          color: data.color,
          sessions: data.sessions,
          ...(data.leadId ? { leadId: Number(data.leadId) } : {}),
          visibility: data.visibility,
        })
      } else {
        await createGroup({
          name: data.name,
          description: data.description,
          color: data.color,
          sessions: data.sessions,
          leadId: data.leadId ? Number(data.leadId) : undefined,
          visibility: data.visibility,
        })
      }
      queryClient.invalidateQueries({ queryKey: qk.groups.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      onClose()
      notify(
        'success',
        t('groups.group.saved'),
        group
          ? t('groups.group.updatedMsg', { name: data.name })
          : t('groups.group.createdMsg', { name: data.name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }
  const [submit, saving] = useSubmitOnce(save)

  return (
    <Modal
      onSubmit={form.onSubmit(submit)}
      open={target != null}
      onClose={onClose}
      wide
      title={group ? t('groups.editGroup') : t('groups.addGroup')}
      subtitle={group?.name}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="filled" type="submit" loading={saving}>
            {group ? t('common.save') : t('groups.createGroup', 'Gruppe erstellen')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 72px', gap: 12 }}>
            <Field label={t('groups.group.name', 'Name der Gruppe')}>
              <TextInput
                {...form.getInputProps('name')}
                disabled={leaderOnly}
                placeholder={t('groups.group.namePlaceholder', 'z. B. Keramik')}
              />
            </Field>
            <Field label={t('common.color', 'Farbe')}>
              <TextInput
                type="color"
                {...form.getInputProps('color')}
                style={{ height: 38, padding: '2px 6px', cursor: 'pointer' }}
              />
            </Field>
          </div>
          <Field label={t('groups.lead', 'Gruppenleitung')}>
            <MemberPicker
              noneLabel={t('groups.noLead', 'Keine Leitung')}
              {...form.getInputProps('leadId')}
              disabled={leaderOnly}
              onChange={(id) => form.setFieldValue('leadId', id ?? '')}
            />
          </Field>
        </SimpleGrid>
        <Field label={t('common.description', 'Beschreibung')}>
          <Textarea
            rows={3}
            {...form.getInputProps('description')}
            placeholder={t('common.descriptionPlaceholder', 'Kurze Beschreibung …')}
          />
        </Field>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('groups.sessions', 'Treffen')} hint={t('groups.sessionsHint', 'z. B. 2× pro Woche')}>
            <TextInput
              {...form.getInputProps('sessions')}
              placeholder={t('groups.sessionsPlaceholder', '3× pro Woche')}
            />
          </Field>
        </SimpleGrid>
        <Field
          label={t('groups.visibility.label', 'Sichtbarkeit')}
          hint={t(`groups.visibility.${form.values.visibility}Hint`)}
        >
          <SegmentedControl
            fullWidth
            data={VISIBILITIES.map((v) => ({
              value: v,
              label: t(`groups.visibility.${v}`),
            }))}
            {...form.getInputProps('visibility')}
          />
        </Field>
      </div>
    </Modal>
  )
}
