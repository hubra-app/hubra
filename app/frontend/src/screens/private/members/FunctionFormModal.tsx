import { useMemo } from 'react'
import { Button, MultiSelect, SimpleGrid, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT, zmsg } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { Field, Modal, useSubmitOnce } from '@/components/ui'
import type { ClubFunction } from '@/types'
import { createFunction, updateFunction } from '@/api/functions'
import { lookupsQuery } from '@/api/lookups'
import { qk } from '@/data/keys'
import { roleLabel } from '@/roles'

const functionSchema = z.object({
  name: z.string().min(1, zmsg('common.nameRequired', 'Name ist erforderlich')),
  description: z.string(),
  maxHolders: z.number().min(1),
  grantsRoleIds: z.array(z.string()),
})
type FunctionForm = z.infer<typeof functionSchema>

/** Create a function ('new') or change one, from the list or its own page.
 * Mount it with a `key` per target so the form starts from that function. */
export function FunctionFormModal({
  target,
  onClose,
}: {
  target: ClubFunction | 'new' | null
  onClose: () => void
}) {
  const { notify } = useToast()
  const { t } = useT()
  const queryClient = useQueryClient()
  const fn = target && target !== 'new' ? target : null
  const form = useForm<FunctionForm>({
    validate: zod4Resolver(functionSchema),
    initialValues: fn
      ? {
          name: fn.name,
          description: fn.description ?? '',
          maxHolders: fn.maxHolders,
          grantsRoleIds: fn.grantsRoleIds.map(String),
        }
      : { name: '', description: '', maxHolders: 1, grantsRoleIds: [] },
  })
  const { data: lookups } = useQuery(lookupsQuery)
  // Owners are named one by one, never through a function.
  const roleOptions = useMemo(
    () =>
      lookups
        ? [...lookups.roles.entries()]
            .filter(([, name]) => name !== 'Owner')
            .map(([id, name]) => ({ value: String(id), label: roleLabel(name) }))
        : [],
    [lookups],
  )

  const save = async (data: FunctionForm) => {
    const body = {
      name: data.name,
      description: data.description || undefined,
      maxHolders: data.maxHolders,
      grantsRoleIds: data.grantsRoleIds.map(Number),
    }
    try {
      if (fn) await updateFunction(fn.id, body)
      else await createFunction(body)
      queryClient.invalidateQueries({ queryKey: qk.functions })
      onClose()
      notify(
        'success',
        t('common.saved', 'Gespeichert'),
        fn ? t('common.updated', 'Gespeichert') : t('common.created', 'Erstellt'),
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
      title={fn ? t('common.edit', 'Bearbeiten') : t('common.add', 'Hinzufügen')}
      subtitle={fn?.name}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" type="submit" loading={saving}>
            {fn ? t('common.save', 'Speichern') : t('common.create', 'Erstellen')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('common.name', 'Name')}>
            <TextInput {...form.getInputProps('name')} placeholder={t('common.namePlaceholder', 'Name')} />
          </Field>
          <Field label={t('functions.maxHolders', 'Max. Anzahl Personen')}>
            <TextInput
              type="number"
              min={1}
              {...form.getInputProps('maxHolders', { valueAsNumber: true })}
            />
          </Field>
        </SimpleGrid>
        <Field label={t('common.description', 'Beschreibung')}>
          <Textarea
            rows={2}
            {...form.getInputProps('description')}
            placeholder={t('functions.descPlaceholder', 'Kurze Beschreibung …')}
          />
        </Field>
        <Field
          label={t('functions.grantsRoles', 'Gibt die Rollen')}
          hint={t(
            'functions.grantsRolesHint',
            'Wer die Funktion innehat, hat diese Rollen, bis die Funktion endet (zum Beispiel Vorstand und Kassier/in).',
          )}
        >
          <MultiSelect
            data={roleOptions}
            value={form.values.grantsRoleIds}
            onChange={(v) => form.setFieldValue('grantsRoleIds', v)}
            placeholder={form.values.grantsRoleIds.length ? undefined : t('functions.noRole', 'Keine Rolle')}
            clearable
            searchable
          />
        </Field>
      </div>
    </Modal>
  )
}
