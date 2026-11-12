import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { TextInput, Button, Stack, Text, Alert, Checkbox, SegmentedControl } from '@mantine/core'
import { Modal as SharedModal } from '@/components/ui'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconLock, IconReplaceUser } from '@tabler/icons-react'
import { askSupportAccess, getSupportAccess, impersonateTenant } from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'

const TENANT_APP_URL = import.meta.env.VITE_TENANT_APP_URL ?? 'https://app.hubra.club'

const schema = z.object({
  reason: z.string().min(1, tr('Bitte gib einen Grund an', 'Reason is required')),
  allowChanges: z.boolean(),
  minutes: z.enum(['15', '30', '60', '120']),
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

  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    validate: zod4Resolver(schema),
    initialValues: { reason: '', allowChanges: false, minutes: '30' },
  })
  // A club can ask Hubra staff to get its approval first.
  const access = useQuery({
    queryKey: ['support-access', tenantId],
    queryFn: () => getSupportAccess(tenantId),
    enabled: opened,
    refetchInterval: (q) => (q.state.data?.request?.status === 'pending' ? 15_000 : false),
  })
  const needsApproval = access.data?.requiresApproval ?? false
  const request = access.data?.request ?? null
  const approved = needsApproval && request?.status === 'approved' ? request : null
  const pending = needsApproval && request?.status === 'pending'
  const mustAsk = needsApproval && !approved && !pending

  // An approval runs as asked for: show those values (the server uses them).
  useEffect(() => {
    if (approved) {
      form.setValues({
        reason: approved.reason,
        allowChanges: approved.allowChanges,
        minutes: String(approved.minutes) as FormValues['minutes'],
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per approval
  }, [approved?.id])

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    if (mustAsk) {
      try {
        await askSupportAccess(tenantId, {
          reason: values.reason.trim(),
          allow_changes: values.allowChanges,
          minutes: Number(values.minutes),
        })
        notify('success', tr('Anfrage gesendet', 'Request sent'), tr('Die Admins des Vereins werden benachrichtigt.', "The club's admins are notified."))
        await queryClient.invalidateQueries({ queryKey: ['support-access', tenantId] })
      } catch (err) {
        notify('error', tr('Anfrage fehlgeschlagen', 'Request failed'), err instanceof Error ? err.message : undefined)
      } finally {
        setLoading(false)
      }
      return
    }
    try {
      const res = await impersonateTenant(tenantId, {
        reason: values.reason.trim(),
        allow_changes: values.allowChanges,
        minutes: Number(values.minutes),
        ...(approved ? { request_id: approved.id } : {}),
      })
      notify('success', tr('Stellvertretung gestartet', 'Impersonation started'), tr('Du wirst zum Verein weitergeleitet …', 'Redirecting to the club…'))
      // The club app's routes start with the club's slug.
      window.location.assign(
        `${TENANT_APP_URL}/${encodeURIComponent(res.tenant_slug)}/app/dashboard`,
      )
    } catch (err) {
      notify('error', tr('Stellvertretung fehlgeschlagen', 'Impersonation failed'), err instanceof Error ? err.message : undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <SharedModal
      open={opened}
      onClose={onClose}
      title={tr('Verein als Admin öffnen', 'Open the club as admin')}
      onSubmit={form.onSubmit(handleSubmit)}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button type="submit" loading={loading} disabled={pending || access.isLoading}>
            {mustAsk || pending
              ? tr('Beim Verein anfragen', 'Ask the club')
              : tr('Als Admin öffnen', 'Open as admin')}
          </Button>
        </>
      }
    >
      <Stack gap={16}>
        <Alert
          icon={<IconReplaceUser size={16} />}
          color="orange"
          variant="light"
        >
          {tr(
            `Du öffnest «${tenantName}» mit Admin-Rechten. Ohne «Änderungen erlauben» kannst du nur ansehen. Alles wird mit deinem Namen protokolliert.`,
            `You open "${tenantName}" with admin rights. Without "Allow changes" you can only look. Everything is logged under your name.`,
          )}
        </Alert>
        {needsApproval && (
          <Alert
            icon={<IconLock size={16} />}
            color={approved ? 'green' : pending ? 'blue' : 'gray'}
            variant="light"
            data-testid="support-approval-state"
          >
            {approved
              ? tr(
                  `Freigegeben von ${approved.decidedBy ?? 'einer Admin-Person'}. Die Sitzung läuft so, wie du sie angefragt hast.`,
                  `Approved by ${approved.decidedBy ?? 'an admin'}. The session runs as you asked for it.`,
                )
              : pending
                ? tr(
                    'Wartet auf die Freigabe durch eine Admin-Person des Vereins.',
                    "Waiting for one of the club's admins to approve.",
                  )
                : tr(
                    `Dieser Verein gibt Support-Zugriffe selbst frei. Frag an; eine Freigabe gilt einmal, ${access.data?.approvalHours ?? 24} Stunden lang.${request?.status === 'declined' ? ' Die letzte Anfrage wurde abgelehnt.' : ''}`,
                    `This club approves support access itself. Ask first; an approval works once, for ${access.data?.approvalHours ?? 24} hours.${request?.status === 'declined' ? ' The last request was declined.' : ''}`,
                  )}
          </Alert>
        )}
        <TextInput
          disabled={!!approved || pending}
          label={tr('Grund', 'Reason')}
          required
          {...form.getInputProps('reason')}
          placeholder={tr('Support-Ticket #12345', 'Support ticket #12345')}
          description={tr('Pflichtfeld für das Audit-Log. Wird dauerhaft gespeichert.', 'Required for the audit log. It is stored permanently.')}
        />
        <Checkbox
          disabled={!!approved || pending}
          label={tr('Änderungen erlauben', 'Allow changes')}
          description={tr(
            'Nur wenn du im Verein etwas ändern musst, z. B. eine Einstellung korrigieren.',
            'Only when you need to change something in the club, e.g. fix a setting.',
          )}
          {...form.getInputProps('allowChanges', { type: 'checkbox' })}
        />
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            {tr('Dauer', 'Length')}
          </Text>
          <SegmentedControl
            disabled={!!approved || pending}
            {...form.getInputProps('minutes')}
            data={[
              { value: '15', label: tr('15 Min.', '15 min') },
              { value: '30', label: tr('30 Min.', '30 min') },
              { value: '60', label: tr('1 Std.', '1 h') },
              { value: '120', label: tr('2 Std.', '2 h') },
            ]}
          />
          <Text size="xs" c="dimmed">
            {tr(
              `Die Support-Sitzung endet nach ${Number(form.values.minutes) >= 60 ? `${Number(form.values.minutes) / 60} Std.` : `${form.values.minutes} Minuten`}; im Verein steht die ganze Zeit ein Hinweis-Banner. Unter «Support-Zugriffe» lässt sie sich vorher beenden. Verein löschen und Plan ändern sind währenddessen gesperrt.`,
              `The support session ends after ${Number(form.values.minutes) >= 60 ? `${Number(form.values.minutes) / 60} h` : `${form.values.minutes} minutes`}; a banner shows in the club the whole time. It can be ended earlier under "Support access". Deleting the club and changing the plan are blocked meanwhile.`,
            )}
          </Text>
        </Stack>
      </Stack>
    </SharedModal>
  )
}
