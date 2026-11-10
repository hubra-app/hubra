import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, CloseButton, Group, Modal, Text } from '@mantine/core'
import { IconGauge } from '@tabler/icons-react'
import { chooseHubraPlan, getHubraLimits, type HubraLimits, type LimitKind } from '@/api/billing'
import { useApp } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatCHF, formatDate } from '@/format'
import { useT } from '@/locales/i18n'
import { en } from '@/screens/private/settings/subscriptionHooks'

const DISMISSED_KEY = 'hubra.limitBanner.dismissed'
const KINDS: LimitKind[] = ['members', 'mail_month', 'storage_mb']

function readDismissed(): string | null {
  try {
    return sessionStorage.getItem(DISMISSED_KEY)
  } catch {
    return null
  }
}

/** What the banner says; a new level or a new plan shows it again after a dismiss. */
function signature(data: HubraLimits): string {
  return KINDS.map((k) => `${k}:${data.limits[k].level}`).join(',') + `|${data.plan}`
}

/**
 * Near or at a plan limit, the club's billing admins see it here with the
 * plan that fits, and switch to it in one click (services/quotas.py,
 * GET /app/billing/limits). At the member limit new members still join
 * until the grace period ends.
 */
export function LimitBanner() {
  const { hasPermission } = useApp()
  const allowed = hasPermission('billing.billing.manage')
  const { data } = useQuery({
    queryKey: qk.settings.subscriptionLimits,
    queryFn: getHubraLimits,
    enabled: allowed,
    staleTime: 10 * 60_000,
  })
  const [dismissed, setDismissed] = useState(readDismissed)
  if (!allowed || !data || data.code !== 'LIMIT_NEAR') return null
  const sig = signature(data)
  if (dismissed === sig) return null

  const dismiss = () => {
    try {
      sessionStorage.setItem(DISMISSED_KEY, sig)
    } catch {
      // private mode: hide for this page view only
    }
    setDismissed(sig)
  }
  return <LimitNotice data={data} onDismiss={dismiss} />
}

function LimitNotice({ data, onDismiss }: { data: HubraLimits; onDismiss: () => void }) {
  const { t } = useT()
  const { notify } = useApp()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)

  const members = data.limits.members
  const over = members.level === 'over'
  const graceOpen = over && !!data.grace_until && new Date(data.grace_until) > new Date()
  const kindName = (k: LimitKind) =>
    k === 'members'
      ? t('limits.kind.members', 'Mitglieder')
      : k === 'mail_month'
        ? t('limits.kind.mail', 'Mails in diesem Monat')
        : t('limits.kind.storage', 'Speicher')

  let text: string
  if (over && graceOpen) {
    text = t(
      'limits.banner.grace',
      'Euer Verein hat das Limit von {{limit}} Mitgliedern erreicht. Neue Mitglieder kommen noch bis {{date}} dazu.',
      { limit: members.limit, date: formatDate(data.grace_until as string) },
    )
  } else if (over) {
    text = t(
      'limits.banner.full',
      'Euer Verein hat das Limit von {{limit}} Mitgliedern erreicht. Neue Mitglieder können erst mit einem grösseren Tarif beitreten.',
      { limit: members.limit },
    )
  } else {
    const tight = KINDS.filter((k) => data.limits[k].level !== 'ok')
      .map((k) => `${kindName(k)} ${data.limits[k].percent ?? 100} %`)
      .join(', ')
    text = t('limits.banner.near', 'Euer Verein ist nahe am Limit seines Tarifs: {{tight}}.', {
      tight,
    })
  }

  const s = data.suggestion
  const name = s ? (en() ? s.name_en || s.name_de : s.name_de) : ''
  const price = s?.price_month_chf != null ? `CHF ${formatCHF(Number(s.price_month_chf))}` : ''
  const fits = s
    ? s.limits.members == null
      ? t('limits.fits.unlimited', '{{name}} hat kein Mitgliederlimit', { name })
      : t('limits.fits.members', '{{name}} hat Platz für {{limit}} Mitglieder', {
          name,
          limit: s.limits.members,
        })
    : ''

  const switchPlan = async () => {
    if (!s) return
    setBusy(true)
    try {
      await chooseHubraPlan(s.key)
      await queryClient.invalidateQueries({ queryKey: qk.settings.subscription })
      notify('success', t('subscription.planChanged', 'Tarif gewechselt'))
      setConfirm(false)
    } catch (err) {
      notify('error', t('subscription.planFailed', 'Tarif nicht gewechselt'), (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Group
        role="status"
        gap={10}
        wrap="wrap"
        px={16}
        py={8}
        data-testid="limit-banner"
        style={{
          background: 'var(--hb-notice-bg)',
          borderBottom: '1px solid var(--hb-notice-border)',
        }}
      >
        <IconGauge size={18} color="var(--mantine-color-gold-text)" style={{ flexShrink: 0 }} />
        <Text fz="sm" fw={500} style={{ flex: 1, minWidth: 220 }}>
          {text}
          {s && ` ${fits}${price ? ` (${price} ${t('limits.perMonth', 'pro Monat')})` : ''}.`}
        </Text>
        {s ? (
          <Button size="xs" onClick={() => setConfirm(true)} data-testid="limit-upgrade">
            {t('limits.switchTo', 'Zu {{name}} wechseln', { name })}
          </Button>
        ) : (
          <Button size="xs" variant="default" onClick={() => navigate('/app/settings/subscription')}>
            {t('limits.seePlans', 'Tarife ansehen')}
          </Button>
        )}
        <CloseButton size="sm" aria-label={t('shell.clubBanner.dismiss', 'Banner ausblenden')} onClick={onDismiss} />
      </Group>
      <Modal
        opened={confirm}
        onClose={() => setConfirm(false)}
        title={t('limits.confirmTitle', 'Zu {{name}} wechseln?', { name })}
        size="sm"
      >
        <Text size="sm" c="dimmed" lh={1.6}>
          {t(
            'subscription.plansHint',
            'Ein Wechsel gilt sofort. Die Differenz für den Rest des Monats kommt anteilig auf die nächste Rechnung.',
          )}
          {price && ` ${t('limits.newPrice', 'Neu: {{price}} pro Monat.', { price })}`}
        </Text>
        <Group justify="flex-end" gap="xs" mt="md">
          <Button variant="default" onClick={() => setConfirm(false)}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button loading={busy} onClick={() => void switchPlan()} data-testid="limit-upgrade-confirm">
            {t('limits.switch', 'Wechseln')}
          </Button>
        </Group>
      </Modal>
    </>
  )
}
