import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core'
import { IconCheck } from '@tabler/icons-react'
import { chooseHubraPlan, type HubraAddonOffer, type HubraPlanChoice } from '@/api/billing'
import { ConfirmModal } from '@/components/feedback'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatCHF } from '@/format'
import { useT } from '@/locales/i18n'
import { addonName, addonPrice, en, useAddonSwitch, useHubraCatalog } from './subscriptionHooks'

function PlanTile({
  plan,
  current,
  onPick,
}: {
  plan: HubraPlanChoice
  current: boolean
  onPick: () => void
}) {
  const { t } = useT()
  const name = en() ? plan.name_en || plan.name_de : plan.name_de
  const included = plan.modules.filter((m) => m.included)
  return (
    <Paper
      withBorder
      p="md"
      style={
        current ? { borderColor: 'var(--mantine-color-acc-filled)', borderWidth: 2 } : undefined
      }
    >
      <Stack gap={6} h="100%">
        <Group justify="space-between" gap={6}>
          <Text fw={700}>{name}</Text>
          {current && (
            <Badge variant="light" leftSection={<IconCheck size={12} />}>
              {t('subscription.currentPlan', 'Aktuell')}
            </Badge>
          )}
        </Group>
        <Text size="lg" fw={700}>
          {plan.price_month_chf == null
            ? t('subscription.onRequest', 'Preis auf Anfrage')
            : t('subscription.perMonthAmount', '{{amount}} pro Monat', {
                amount: `CHF ${formatCHF(Number(plan.price_month_chf))}`,
              })}
        </Text>
        {plan.limits.members != null && (
          <Text size="xs" c="dimmed">
            {t('subscription.planMembers', 'Bis {{n}} Mitglieder', { n: plan.limits.members })}
          </Text>
        )}
        {plan.features.slice(0, 5).map((f, i) => (
          <Text size="xs" key={i}>
            · {en() ? f.en || f.de : f.de}
          </Text>
        ))}
        {included.length > 0 && (
          <Text size="xs" c="dimmed">
            {t('subscription.planIncludes', 'Inklusive: {{list}}', {
              list: included.map((m) => (en() ? m.name_en : m.name_de)).join(', '),
            })}
          </Text>
        )}
        <div style={{ flex: 1 }} />
        {!current && (
          <Button size="xs" variant="light" onClick={onPick}>
            {t('subscription.switchPlan', 'Zu diesem Tarif wechseln')}
          </Button>
        )}
      </Stack>
    </Paper>
  )
}

/** The plans the club can switch to. */
export function PlanCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data } = useHubraCatalog()
  const [pick, setPick] = useState<HubraPlanChoice | null>(null)
  if (!data || data.plans.length < 2) return null

  const change = async (plan: HubraPlanChoice) => {
    try {
      await chooseHubraPlan(plan.key)
      await queryClient.invalidateQueries({ queryKey: qk.settings.subscription })
      notify('success', t('subscription.planChanged', 'Tarif gewechselt'))
    } catch (err) {
      notify(
        'error',
        t('subscription.planFailed', 'Tarif nicht gewechselt'),
        (err as Error).message,
      )
    }
  }

  return (
    <Paper withBorder p="lg">
      <Title order={4} mb={4}>
        {t('subscription.plansTitle', 'Tarif')}
      </Title>
      <Text size="sm" c="dimmed" mb={12}>
        {t(
          'subscription.plansHint',
          'Ein Wechsel gilt sofort. Die Differenz für den Rest des Monats kommt anteilig auf die nächste Rechnung.',
        )}
      </Text>
      <SimpleGrid cols={{ base: 1, sm: Math.min(3, data.plans.length) }} spacing="sm">
        {data.plans.map((p) => (
          <PlanTile key={p.key} plan={p} current={p.key === data.plan} onPick={() => setPick(p)} />
        ))}
      </SimpleGrid>
      {pick && (
        <ConfirmModal
          open
          title={t('subscription.switchTitle', 'Zu {{name}} wechseln?', {
            name: en() ? pick.name_en || pick.name_de : pick.name_de,
          })}
          body={t(
            'subscription.switchBody',
            'Der neue Tarif gilt sofort. Die Differenz für den Rest des Monats kommt anteilig auf die nächste Rechnung.',
          )}
          confirmLabel={t('subscription.switch', 'Wechseln')}
          onClose={() => setPick(null)}
          onConfirm={() => {
            const p = pick
            setPick(null)
            void change(p)
          }}
        />
      )}
    </Paper>
  )
}

function LicenseInput({
  addon,
  onSave,
  busy,
}: {
  addon: HubraAddonOffer
  onSave: (n: number) => void
  busy: boolean
}) {
  const { t } = useT()
  const [value, setValue] = useState<number>(addon.licenses ?? 1)
  return (
    <Group gap={6} align="flex-end">
      <NumberInput
        size="xs"
        w={110}
        label={t('subscription.licenses', 'Lizenzen')}
        min={1}
        max={10000}
        value={value}
        onChange={(v) => setValue(Math.max(1, Math.floor(Number(v) || 1)))}
      />
      <Button
        size="xs"
        variant="default"
        loading={busy}
        disabled={value === (addon.licenses ?? 1)}
        onClick={() => onSave(value)}
      >
        {t('subscription.save', 'Speichern')}
      </Button>
    </Group>
  )
}

/** Paid modules: what the plan includes, what the club took, what it can add. */
export function AddonsCard() {
  const { t } = useT()
  const { data } = useHubraCatalog()
  const sw = useAddonSwitch()
  if (!data || data.addons.length === 0) return null
  return (
    <Paper withBorder p="lg">
      <Title order={4} mb={4}>
        {t('subscription.addonsTitle', 'Zusatzmodule')}
      </Title>
      <Text size="sm" c="dimmed" mb={12}>
        {t(
          'subscription.addonsHint',
          'Module mit eigenem Preis. Dazubuchen schaltet das Modul ein; der Betrag für den Rest des Monats kommt anteilig auf die nächste Rechnung.',
        )}
      </Text>
      <Stack gap={0}>
        {data.addons.map((a) => {
          const on = a.source !== null
          const fixed = a.source === 'included' || a.source === 'plan'
          return (
            <Group
              key={a.code}
              justify="space-between"
              wrap="wrap"
              gap="sm"
              py={10}
              style={{ borderTop: '1px solid var(--hb-border)' }}
              data-addon={a.code}
            >
              <Stack gap={2} style={{ flex: '1 1 260px', minWidth: 0 }}>
                <Group gap={6}>
                  <Text fw={600}>{addonName(a)}</Text>
                  {a.source === 'included' && (
                    <Badge size="xs" variant="light" color="green">
                      {t('subscription.inPlan', 'Im Tarif inklusive')}
                    </Badge>
                  )}
                  {a.source === 'plan' && (
                    <Badge size="xs" variant="light">
                      {t('subscription.withPlan', 'Mit dem Tarif')}
                    </Badge>
                  )}
                </Group>
                <Text size="xs" c="dimmed">
                  {a.source === 'included'
                    ? t('subscription.noExtraCost', 'Ohne Aufpreis')
                    : addonPrice(t, a)}
                </Text>
                {(en() ? a.note_en : a.note_de) && (
                  <Text size="xs" c="dimmed" lineClamp={2}>
                    {en() ? a.note_en : a.note_de}
                  </Text>
                )}
              </Stack>
              <Group gap="md" align="flex-end">
                {on && a.unit === 'license' && (
                  <LicenseInput
                    addon={a}
                    busy={sw.busy === a.code}
                    onSave={(n) => void sw.apply(a.code, { licenses: n })}
                  />
                )}
                {!fixed && (
                  <Switch
                    checked={on}
                    disabled={sw.busy === a.code}
                    onChange={(e) => sw.ask(a, e.currentTarget.checked)}
                    aria-label={addonName(a)}
                  />
                )}
              </Group>
            </Group>
          )
        })}
      </Stack>
      {sw.modal}
    </Paper>
  )
}
