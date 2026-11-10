import { useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Checkbox, Group, Paper, SimpleGrid, Stack, Switch, Text, TextInput, Title } from '@mantine/core'
import {
  createWebhook,
  deleteWebhook,
  listWebhookDeliveries,
  listWebhooks,
  retryWebhookDelivery,
  rollWebhookSecret,
  testWebhook,
  updateWebhook,
  type Webhook,
} from '@/api/webhooks'
import { ConfirmModal, Modal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { useT } from '@/locales/i18n'
import { Copyable } from './SignInAppsSection'

function useEventLabel() {
  const { t } = useT()
  return (event: string) =>
    ({
      'member.joined': t('webhooks.ev.memberJoined', 'Mitglied beigetreten'),
      'member.left': t('webhooks.ev.memberLeft', 'Mitglied ausgetreten'),
      'invoice.created': t('webhooks.ev.invoiceCreated', 'Rechnung erstellt'),
      'invoice.paid': t('webhooks.ev.invoicePaid', 'Rechnung bezahlt'),
      'invoice.overdue': t('webhooks.ev.invoiceOverdue', 'Rechnung überfällig'),
      'invoice.deleted': t('webhooks.ev.invoiceDeleted', 'Rechnung gelöscht'),
      'event.published': t('webhooks.ev.eventPublished', 'Anlass veröffentlicht'),
      'event.changed': t('webhooks.ev.eventChanged', 'Anlass geändert'),
      'post.published': t('webhooks.ev.postPublished', 'Beitrag veröffentlicht'),
      'poll.published': t('webhooks.ev.pollPublished', 'Umfrage veröffentlicht'),
      'poll.closed': t('webhooks.ev.pollClosed', 'Umfrage beendet'),
      'group.membership_changed': t('webhooks.ev.groupChanged', 'Gruppe: Mitglieder geändert'),
      ping: t('webhooks.ev.ping', 'Test'),
    })[event] ?? event
}

function WebhookModal({
  open,
  hook,
  events,
  onClose,
  onSaved,
}: {
  open: boolean
  hook: Webhook | null
  events: string[]
  onClose: () => void
  onSaved: (made?: Webhook) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const label = useEventLabel()
  const [name, setName] = useState(hook?.name ?? '')
  const [url, setUrl] = useState(hook?.url ?? '')
  const [picked, setPicked] = useState<string[]>(hook?.events ?? ['member.joined', 'member.left'])
  const [busy, setBusy] = useState(false)

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    setBusy(true)
    const body = { name: name.trim(), url: url.trim(), events: picked }
    try {
      if (hook) {
        await updateWebhook(hook.id, body)
        onSaved()
      } else {
        onSaved(await createWebhook(body))
      }
    } catch (err) {
      notify('error', t('webhooks.saveFailed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={hook ? t('webhooks.edit', 'Webhook bearbeiten') : t('webhooks.new', 'Neuer Webhook')}
      onSubmit={submit}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('webhooks.cancel', 'Abbrechen')}
          </Button>
          <Button type="submit" loading={busy} disabled={!name.trim() || !url.trim() || picked.length === 0}>
            {hook ? t('webhooks.save', 'Speichern') : t('webhooks.create', 'Erstellen')}
          </Button>
        </>
      }
    >
      <TextInput
        label={t('webhooks.name', 'Name')}
        description={t('webhooks.nameHint', 'Wofür er ist, z. B. «Newsletter» oder «Zapier».')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
        required
        data-autofocus
      />
      <TextInput
        label={t('webhooks.url', 'Adresse')}
        description={t('webhooks.urlHint', 'Nur https und eine öffentliche Adresse.')}
        placeholder="https://"
        value={url}
        onChange={(e) => setUrl(e.currentTarget.value)}
        required
      />
      <Checkbox.Group
        label={t('webhooks.events', 'Ereignisse')}
        value={picked}
        onChange={setPicked}
        required
      >
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing={6} mt={6}>
          {events.map((e) => (
            <Checkbox key={e} value={e} label={label(e)} />
          ))}
        </SimpleGrid>
      </Checkbox.Group>
    </Modal>
  )
}

function SecretModal({ hook, onClose }: { hook: Webhook | null; onClose: () => void }) {
  const { t } = useT()
  return (
    <Modal
      open={hook !== null}
      onClose={onClose}
      title={t('webhooks.secretTitle', 'Signatur-Secret')}
      footer={<Button onClick={onClose}>{t('webhooks.done', 'Fertig')}</Button>}
    >
      {hook?.secret && (
        <Stack gap="sm">
          <Alert color="orange" variant="light" title={t('webhooks.onlyNow', 'Nur jetzt sichtbar')}>
            {t(
              'webhooks.onlyNowBody',
              'Trage das Secret in deinem Tool ein. Damit prüft es die Kopfzeile X-Hubra-Signature jeder Nachricht. Danach lässt es sich nur noch ersetzen.',
            )}
          </Alert>
          <Copyable label="Secret" value={hook.secret} testId="webhook-secret" />
        </Stack>
      )}
    </Modal>
  )
}

function Deliveries({ hook }: { hook: Webhook }) {
  const { t } = useT()
  const { notify } = useToast()
  const label = useEventLabel()
  const queryClient = useQueryClient()
  const rows = useQuery({
    queryKey: qk.settings.webhookDeliveries(hook.id),
    queryFn: () => listWebhookDeliveries(hook.id),
  })
  const retry = async (id: number) => {
    try {
      const d = await retryWebhookDelivery(id)
      notify(d.status === 'delivered' ? 'success' : 'error', d.status === 'delivered' ? t('webhooks.delivered', 'Zugestellt') : (d.error ?? t('webhooks.failed', 'Fehlgeschlagen')))
      await queryClient.invalidateQueries({ queryKey: qk.settings.webhooks })
    } catch (err) {
      notify('error', t('webhooks.failed', 'Fehlgeschlagen'), err instanceof Error ? err.message : undefined)
    }
  }
  const items = rows.data?.items ?? []
  if (rows.data && items.length === 0)
    return (
      <Text size="xs" c="dimmed">
        {t('webhooks.noDeliveries', 'Noch nichts gesendet.')}
      </Text>
    )
  return (
    <Stack gap={4}>
      {items.slice(0, 10).map((d) => (
        <Group key={d.id} gap="xs" wrap="nowrap" justify="space-between">
          <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
            <Badge
              size="xs"
              variant="light"
              color={d.status === 'delivered' ? 'green' : d.status === 'pending' ? 'orange' : 'red'}
            >
              {d.responseStatus ?? '–'}
            </Badge>
            <Text size="xs" truncate>
              {label(d.event)} · {formatDateTime(d.lastAttemptAt ?? d.createdAt)}
              {d.error ? ` · ${d.error}` : ''}
            </Text>
          </Group>
          {d.status === 'failed' && (
            <Button size="compact-xs" variant="subtle" onClick={() => void retry(d.id)}>
              {t('webhooks.retry', 'Nochmals')}
            </Button>
          )}
        </Group>
      ))}
    </Stack>
  )
}

/**
 * Einstellungen › API & Webhooks › Webhooks (docs/webhooks.md): the club's own
 * tools hear about changes, signed with a secret.
 */
export function WebhooksSection() {
  const { t } = useT()
  const { notify } = useToast()
  const label = useEventLabel()
  const queryClient = useQueryClient()
  const hooks = useQuery({ queryKey: qk.settings.webhooks, queryFn: listWebhooks })
  const [editing, setEditing] = useState<Webhook | 'new' | null>(null)
  const [shown, setShown] = useState<Webhook | null>(null)
  const [deleting, setDeleting] = useState<Webhook | null>(null)
  const [renewing, setRenewing] = useState<Webhook | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [testing, setTesting] = useState<number | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.settings.webhooks })
  const fail = (err: unknown) =>
    notify('error', t('webhooks.saveFailed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)

  const toggle = async (hook: Webhook, on: boolean) => {
    try {
      await updateWebhook(hook.id, { active: on })
      await refresh()
    } catch (err) {
      fail(err)
    }
  }
  const test = async (hook: Webhook) => {
    setTesting(hook.id)
    try {
      const d = await testWebhook(hook.id)
      if (d.status === 'delivered') notify('success', t('webhooks.testOk', 'Test zugestellt ({{status}})', { status: d.responseStatus }))
      else notify('error', t('webhooks.testFailed', 'Test fehlgeschlagen'), d.error ?? undefined)
      await refresh()
      await queryClient.invalidateQueries({ queryKey: qk.settings.webhookDeliveries(hook.id) })
      setOpen(hook.id)
    } catch (err) {
      fail(err)
    } finally {
      setTesting(null)
    }
  }

  const items = hooks.data?.items ?? []
  const full = hooks.data ? items.length >= hooks.data.max : true

  return (
    <Paper withBorder p="lg">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" gap="sm">
          <div style={{ minWidth: 0, flex: '1 1 260px' }}>
            <Title order={4}>{t('webhooks.title', 'Webhooks')}</Title>
            <Text size="sm" c="dimmed">
              {t(
                'webhooks.intro',
                'Hubra meldet euren eigenen Tools, was im Verein passiert, z. B. wenn jemand beitritt oder eine Rechnung bezahlt wird: als signierte Nachricht an eine https-Adresse.',
              )}
            </Text>
          </div>
          <Button size="sm" style={{ flexShrink: 0 }} disabled={full} onClick={() => setEditing('new')}>
            {t('webhooks.new', 'Neuer Webhook')}
          </Button>
        </Group>
        {hooks.data && items.length === 0 && (
          <Text size="sm" c="dimmed">
            {t('webhooks.none', 'Noch kein Webhook.')}
          </Text>
        )}
        {items.map((hook) => (
          <Paper key={hook.id} withBorder p="md">
            <Stack gap={6}>
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <div style={{ minWidth: 0 }}>
                  <Group gap="xs" wrap="nowrap">
                    <Text fw={600} truncate>
                      {hook.name}
                    </Text>
                    {!hook.active && (
                      <Badge size="sm" variant="light" color="gray">
                        {t('webhooks.off', 'aus')}
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed" ff="monospace" style={{ wordBreak: 'break-all' }}>
                    {hook.url}
                  </Text>
                </div>
                <Switch
                  aria-label={t('webhooks.on', 'Aktiv')}
                  checked={hook.active}
                  onChange={(e) => void toggle(hook, e.currentTarget.checked)}
                  style={{ flexShrink: 0 }}
                />
              </Group>
              {hook.disabledReason && (
                <Alert color="red" variant="light" p="xs">
                  {t('webhooks.autoOff', 'Ausgeschaltet nach {{count}} Fehlversuchen in Folge. Prüfe die Adresse und schalte ihn wieder ein.', { count: 20 })}
                </Alert>
              )}
              <Group gap={6}>
                {hook.events.map((e) => (
                  <Badge key={e} size="sm" variant="outline" color="gray">
                    {label(e)}
                  </Badge>
                ))}
              </Group>
              <Text size="xs" c="dimmed">
                {hook.lastDeliveryAt
                  ? `${t('webhooks.lastDelivery', 'Zuletzt gesendet')} ${formatDateTime(hook.lastDeliveryAt)}`
                  : t('webhooks.neverSent', 'Noch nichts gesendet')}
                {hook.failures > 0 && ` · ${t('webhooks.failures', '{{count}} Fehlversuche in Folge', { count: hook.failures })}`}
              </Text>
              <Group gap="xs">
                <Button size="xs" variant="default" loading={testing === hook.id} onClick={() => void test(hook)}>
                  {t('webhooks.test', 'Test senden')}
                </Button>
                <Button size="xs" variant="default" onClick={() => setOpen(open === hook.id ? null : hook.id)}>
                  {t('webhooks.deliveries', 'Verlauf')}
                </Button>
                <Button size="xs" variant="default" onClick={() => setEditing(hook)}>
                  {t('webhooks.editShort', 'Bearbeiten')}
                </Button>
                <Button size="xs" variant="default" onClick={() => setRenewing(hook)}>
                  {t('webhooks.newSecret', 'Neues Secret')}
                </Button>
                <Button size="xs" variant="subtle" color="red" onClick={() => setDeleting(hook)}>
                  {t('webhooks.delete', 'Löschen')}
                </Button>
              </Group>
              {open === hook.id && <Deliveries hook={hook} />}
            </Stack>
          </Paper>
        ))}
      </Stack>
      {editing !== null && (
        <WebhookModal
          open
          hook={editing === 'new' ? null : editing}
          events={hooks.data?.events ?? []}
          onClose={() => setEditing(null)}
          onSaved={(made) => {
            setEditing(null)
            void refresh()
            if (made) setShown(made)
          }}
        />
      )}
      <SecretModal hook={shown} onClose={() => setShown(null)} />
      <ConfirmModal
        open={deleting !== null}
        title={t('webhooks.deleteTitle', 'Webhook löschen')}
        body={t('webhooks.deleteBody', '{{name}} bekommt keine Nachrichten mehr.', { name: deleting?.name ?? '' })}
        onConfirm={async () => {
          const target = deleting
          setDeleting(null)
          if (!target) return
          try {
            await deleteWebhook(target.id)
            await refresh()
          } catch (err) {
            fail(err)
          }
        }}
        onClose={() => setDeleting(null)}
      />
      <ConfirmModal
        open={renewing !== null}
        title={t('webhooks.renewTitle', 'Neues Secret')}
        body={t('webhooks.renewBody', 'Das bisherige Secret gilt sofort nicht mehr. Trage das neue gleich in deinem Tool ein.')}
        onConfirm={async () => {
          const target = renewing
          setRenewing(null)
          if (!target) return
          try {
            setShown(await rollWebhookSecret(target.id))
          } catch (err) {
            fail(err)
          }
        }}
        onClose={() => setRenewing(null)}
      />
    </Paper>
  )
}
