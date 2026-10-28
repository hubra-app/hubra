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

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  slug: z.string().min(3, 'Slug must be at least 3 chars').max(64, 'Slug must be at most 64 chars'),
  plan: z.string(),
  adminEmail: z.string().email('Invalid email').or(z.literal('')),
  adminPassword: z.string(),
})

type FormValues = z.infer<typeof schema>

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
    validate: zodResolver(schema),
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
      notify('success', 'Tenant created', `${values.name} has been provisioned.`)
      onClose()
      form.reset()
      setSlugEdited(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create tenant')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Create New Tenant" size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap={16}>
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
              {error}
            </Alert>
          )}
          <TextInput
            label="Tenant Name"
            required
            {...form.getInputProps('name')}
            onChange={handleNameChange}
            placeholder="Acme Canoe Club"
          />
          <TextInput
            label="Slug"
            required
            {...form.getInputProps('slug')}
            onChange={handleSlugChange}
            placeholder="acme-canoe-club"
            description="URL-safe identifier (3-64 chars, lowercase, hyphens)"
          />
          <Select
            label="Plan"
            {...form.getInputProps('plan')}
            onChange={(v) => v && form.setFieldValue('plan', v)}
            data={[
              { value: 'starter', label: 'Starter' },
              { value: 'growth', label: 'Growth' },
              { value: 'enterprise', label: 'Enterprise' },
            ]}
          />
          <TextInput
            label="Admin Email (optional)"
            type="email"
            {...form.getInputProps('adminEmail')}
            placeholder="admin@acmecanoe.ch"
            description="Initial admin user email"
          />
          <TextInput
            label="Admin Password (optional)"
            type="password"
            {...form.getInputProps('adminPassword')}
            description="Initial admin password"
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Create Tenant
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
