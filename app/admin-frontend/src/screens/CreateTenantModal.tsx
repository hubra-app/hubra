import { useState } from 'react'
import { usePlanChoices } from '@/plans'
import {
  Modal,
  TextInput,
  Select,
  Button,
  Stack,
  Group,
  Alert,
  Switch,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useQueryClient } from '@tanstack/react-query'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconAlertCircle } from '@tabler/icons-react'
import { createTenant } from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'

const makeSchema = () =>
  z.object({
    name: z.string().min(1, tr('Name ist erforderlich', 'Name is required')),
    slug: z
      .string()
      .min(3, tr('Mindestens 3 Zeichen', 'At least 3 characters'))
      .max(64, tr('Höchstens 64 Zeichen', 'At most 64 characters'))
      .regex(
        /^[a-z0-9][a-z0-9-]*[a-z0-9]$/,
        tr(
          'Nur Kleinbuchstaben, Ziffern und Bindestriche, nicht am Anfang oder Ende',
          'Only lowercase letters, digits and hyphens, not at the start or end',
        ),
      ),
    plan: z.string(),
    adminEmail: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')).or(z.literal('')),
    adminPassword: z.string(),
    sandbox: z.boolean(),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    // é → e and the like: drop the accent, keep the letter.
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-')
}

export function CreateTenantModal({
  opened,
  onClose,
}: {
  opened: boolean
  onClose: () => void
}) {
  const { notify } = useAdmin()
  const { data: planChoices } = usePlanChoices()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)

  const form = useForm<FormValues>({
    validate: zod4Resolver(makeSchema()),
    initialValues: {
      name: '',
      slug: '',
      plan: 'starter',
      adminEmail: '',
      adminPassword: '',
      sandbox: false,
    },
  })

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    form.setFieldValue('name', val)
    if (!slugEdited) {
      form.setFieldValue('slug', slugify(val))
    }
  }

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSlugEdited(true)
    form.setFieldValue('slug', e.target.value)
  }

  const queryClient = useQueryClient()

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    setError('')
    try {
      await createTenant({
        name: values.name,
        slug: values.slug,
        plan: values.plan,
        admin_email: values.adminEmail || undefined,
        admin_password: values.adminPassword || undefined,
        sandbox: values.sandbox || undefined,
      })
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      queryClient.invalidateQueries({ queryKey: ['backup-clubs'] })
      notify('success', tr('Verein erstellt', 'Club created'), tr(`${values.name} ist eingerichtet.`, `${values.name} has been set up.`))
      onClose()
      form.reset()
      setSlugEdited(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : tr('Verein konnte nicht erstellt werden', 'Could not create the club'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={tr('Neuen Verein erstellen', 'Create a new club')} size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap={16}>
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
              {error}
            </Alert>
          )}
          <TextInput
            label={tr('Vereinsname', 'Club name')}
            required
            {...form.getInputProps('name')}
            onChange={handleNameChange}
            placeholder={tr('Kanuclub Seeblick', 'Lakeside Canoe Club')}
          />
          <TextInput
            label={tr('Kürzel', 'Slug')}
            required
            {...form.getInputProps('slug')}
            onChange={handleSlugChange}
            placeholder="kanuclub-seeblick"
            description={tr('Erscheint in der Adresse: 3–64 Zeichen, Kleinbuchstaben und Bindestriche', 'Used in the address: 3–64 characters, lowercase letters and hyphens')}
          />
          <Select
            label={tr('Plan', 'Plan')}
            {...form.getInputProps('plan')}
            onChange={(v) => v && form.setFieldValue('plan', v)}
            data={(
              planChoices?.plans ?? [
                { key: 'starter', name_de: 'Starter', name_en: 'Starter', hidden: false },
              ]
            )
              .filter((p) => !p.hidden)
              .map((p) => ({ value: p.key, label: tr(p.name_de, p.name_en) }))}
          />
          <TextInput
            label={tr('E-Mail der Admin-Person', 'Admin email')}
            type="email"
            {...form.getInputProps('adminEmail')}
            placeholder="praesidium@kanuclub-seeblick.ch"
            description={tr('Optional. Mit E-Mail und Passwort wird gleich ein Admin-Konto angelegt.', 'Optional. With an email and a password an admin account is created right away.')}
          />
          <TextInput
            label={tr('Passwort der Admin-Person', 'Admin password')}
            type="password"
            {...form.getInputProps('adminPassword')}
            description={tr('Nur zusammen mit der E-Mail-Adresse.', 'Only together with the email address.')}
          />
          <Switch
            label={tr('Sandbox-Verein (Demo / Test)', 'Sandbox club (demo / test)')}
            description={tr(
              'Zahlungen und Hubra-Abo laufen immer über die Stripe-Sandbox-Schlüssel; es fliesst kein echtes Geld.',
              'Payments and the Hubra subscription always use the Stripe sandbox keys; no real money moves.',
            )}
            {...form.getInputProps('sandbox', { type: 'checkbox' })}
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={onClose}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button type="submit" loading={loading}>
              {tr('Verein erstellen', 'Create club')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
