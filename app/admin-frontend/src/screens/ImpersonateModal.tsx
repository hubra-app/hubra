import { useState } from 'react'
import { Modal, TextInput, Button, Stack, Group, Text, Alert } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconReplaceUser } from '@tabler/icons-react'
import { impersonateTenant } from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'

const TENANT_APP_URL = import.meta.env.VITE_TENANT_APP_URL ?? 'https://app.hubra.club'

const schema = z.object({
  reason: z.string().min(1, tr('Bitte gib einen Grund an', 'Reason is required')),
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
      notify('success', tr('Stellvertretung gestartet', 'Impersonation started'), tr('Du wirst zum Verein weitergeleitet …', 'Redirecting to the club…'))
      window.location.assign(`${TENANT_APP_URL}/app/dashboard`)
    } catch (err) {
      notify('error', tr('Stellvertretung fehlgeschlagen', 'Impersonation failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={tr('Verein als Admin öffnen', 'Open the club as admin')} size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap={16}>
          <Alert
            icon={<IconReplaceUser size={16} />}
            color="orange"
            variant="light"
          >
            {tr(
              `Du öffnest «${tenantName}» mit Admin-Rechten. Alles, was du dort tust, wird mit deinem Namen protokolliert.`,
              `You open "${tenantName}" with admin rights. Everything you do there is logged under your name.`,
            )}
          </Alert>
          <TextInput
            label={tr('Grund', 'Reason')}
            required
            {...form.getInputProps('reason')}
            placeholder={tr('Support-Ticket #12345', 'Support ticket #12345')}
            description={tr('Pflichtfeld für das Audit-Log. Wird dauerhaft gespeichert.', 'Required for the audit log. It is stored permanently.')}
          />
          <Text size="xs" c="dimmed">
            {tr(
              'Die Sitzung endet nach 30 Minuten. Verein löschen und Plan ändern sind währenddessen gesperrt.',
              'The session ends after 30 minutes. Deleting the club and changing the plan are blocked meanwhile.',
            )}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button type="submit" loading={loading}>
              {tr('Als Admin öffnen', 'Open as admin')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
