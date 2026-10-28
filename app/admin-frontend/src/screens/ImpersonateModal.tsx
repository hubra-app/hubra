import { useState } from 'react'
import { Modal, TextInput, Button, Stack, Group, Text, Alert } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconReplaceUser } from '@tabler/icons-react'
import { impersonateTenant } from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'

const TENANT_APP_URL = import.meta.env.VITE_TENANT_APP_URL ?? 'https://cos.vollbuild.ch'

const schema = z.object({
  reason: z.string().min(1, 'Reason is required'),
})

type FormValues = z.infer<typeof schema>

export function ImpersonateModal({
  opened,
  onClose,
  tenantId,
  tenantName,
}: {
  opened: boolean
  onClose: () => void
  tenantId: number
  tenantName: string
}) {
  const { notify } = useAdmin()
  const [loading, setLoading] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { reason: '' },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await impersonateTenant(tenantId, { reason: values.reason.trim() })
      notify('success', 'Impersonation started', `Redirecting to tenant app...`)
      window.location.assign(`${TENANT_APP_URL}/app/dashboard`)
    } catch (err) {
      notify('error', 'Impersonation failed', err instanceof Error ? err.message : undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Impersonate Tenant User" size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap={16}>
          <Alert
            icon={<IconReplaceUser size={16} />}
            color="orange"
            variant="light"
          >
            You will be redirected to the tenant app at <strong>{tenantName}</strong> acting as the tenant admin.
            All actions will be logged with your impersonation context.
          </Alert>
          <TextInput
            label="Reason / Justification"
            required
            {...form.getInputProps('reason')}
            placeholder="Support ticket #12345"
            description="Required for audit trail. This is logged permanently."
          />
          <Text size="xs" c="dimmed">
            Session timeout: 30 minutes. Restricted actions (delete tenant, change plan) are blocked during impersonation.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Start Impersonation
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
