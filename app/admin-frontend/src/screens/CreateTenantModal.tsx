import { useState } from 'react'
import {
  Modal,
  TextInput,
  Select,
  Button,
  Stack,
  Group,
  Alert,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
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
      .max(64, tr('Höchstens 64 Zeichen', 'At most 64 characters')),
    plan: z.string(),
    adminEmail: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')).or(z.literal('')),
    adminPassword: z.string(),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

function slugify(name: string): string {
  return name
    .toLowerCase()
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(makeSchema()),
    initialValues: {
      name: '',
      slug: '',
      plan: 'starter',
      adminEmail: '',
      adminPassword: '',
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
      })
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
            data={[
              { value: 'starter', label: 'Starter' },
              { value: 'growth', label: 'Growth' },
              { value: 'enterprise', label: 'Enterprise' },
            ]}
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
