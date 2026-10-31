import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Button,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { getModules, type ModuleInfo } from '@/api/modules'
import { downloadStatement, sendStatement } from '@/api/finance'
import { localizeModule } from '@/modules/labels'
import { qk } from '@/data/keys'
import { SettingInput } from '@/screens/private/settings/ModulesTab'
import { useSaveSettings } from '@/screens/private/finances/useSaveSettings'

type FormValue = string | number | boolean | null

/** The settings the fee and statement cards edit; the invoice card shows the rest. */
const OWN_CARD_KEYS = new Set([
  'bill_on_join_date',
  'fee_anchor_month',
  'fee_anchor_day',
  'prorate_first_fee',
  'statement_enabled',
  'statement_email',
  // Edited on Finanzen › Beitragsgrundlage
  'fee_basis_source',
  'fee_basis_extra',
  'fee_basis_manual',
])

function FeeScheduleForm({ module }: { module: ModuleInfo }) {
  const { t, i18n } = useT()
  const [save, busy] = useSaveSettings(module)
  const config = module.config
  const [onJoinDate, setOnJoinDate] = useState(config.bill_on_join_date === true)
  const [month, setMonth] = useState(Number(config.fee_anchor_month) || 1)
  const [day, setDay] = useState(Number(config.fee_anchor_day) || 1)
  const [prorate, setProrate] = useState(config.prorate_first_fee !== false)

  const monthName = (m: number) =>
    new Date(2026, m - 1, 1).toLocaleString(i18n.language, { month: 'long' })
  const months = Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1),
    label: monthName(i + 1),
  }))
  // Someone who joins in the fourth month of the billing year.
  const exampleMonth = ((month + 2) % 12) + 1

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb={4}>
        {t('finance.fees.title', 'Mitgliederbeiträge')}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t(
          'finance.fees.intro',
          'Wann die jährlichen Beiträge verrechnet werden. Wie oft (jährlich, halbjährlich, …) bestimmen die Stufen und Zahlungspläne.',
        )}
      </Text>
      <Stack gap="md" maw={520}>
        <SegmentedControl
          fullWidth
          value={onJoinDate ? 'join' : 'fixed'}
          onChange={(v) => setOnJoinDate(v === 'join')}
          data={[
            { value: 'fixed', label: t('finance.fees.fixed', 'Am Stichtag für alle') },
            { value: 'join', label: t('finance.fees.join', 'Am Eintrittsdatum') },
          ]}
        />
        {onJoinDate ? (
          <Text size="sm">
            {t(
              'finance.fees.joinHint',
              'Jedes Mitglied bekommt die Rechnung an seinem Eintrittstag und danach jedes Jahr am selben Tag. Mitglieder ohne Eintrittsdatum werden am Stichtag verrechnet.',
            )}
          </Text>
        ) : (
          <>
            <Group grow align="flex-start">
              <NumberInput
                label={t('finance.fees.day', 'Tag')}
                value={day}
                min={1}
                max={31}
                allowDecimal={false}
                onChange={(v) => setDay(Math.min(Math.max(Number(v) || 1, 1), 31))}
              />
              <Select
                label={t('finance.fees.month', 'Monat')}
                data={months}
                value={String(month)}
                onChange={(v) => v && setMonth(Number(v))}
                allowDeselect={false}
              />
            </Group>
            <Switch
              label={t(
                'finance.fees.prorate',
                'Ersten Beitrag kürzen, wenn jemand während des Jahres eintritt',
              )}
              description={t(
                'finance.fees.prorateHint',
                'Nach den verbleibenden Monaten, der Eintrittsmonat zählt ganz. Beispiel: Eintritt im {{month}} bei CHF 120 im Jahr: 9 von 12 Monaten, CHF 90.',
                { month: monthName(exampleMonth) },
              )}
              checked={prorate}
              onChange={(e) => setProrate(e.currentTarget.checked)}
            />
          </>
        )}
      </Stack>
      <Group justify="flex-end" mt="md">
        <Button
          loading={busy}
          onClick={() =>
            save({
              bill_on_join_date: onJoinDate,
              fee_anchor_month: month,
              fee_anchor_day: day,
              prorate_first_fee: prorate,
            })
          }
        >
          {t('common.save', 'Speichern')}
        </Button>
      </Group>
    </Paper>
  )
}

function StatementForm({ module }: { module: ModuleInfo }) {
  const { t, i18n } = useT()
  const { notify } = useToast()
  const [save, busy] = useSaveSettings(module)
  const [enabled, setEnabled] = useState(module.config.statement_enabled === true)
  const [email, setEmail] = useState(String(module.config.statement_email ?? ''))
  const [sending, setSending] = useState(false)
  // This month so far, then the twelve before it.
  const months = Array.from({ length: 13 }, (_, i) => {
    const d = new Date()
    d.setDate(1)
    d.setMonth(d.getMonth() - i)
    return {
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      label: d.toLocaleString(i18n.language, { month: 'long', year: 'numeric' }),
    }
  })
  const [month, setMonth] = useState(months[1].value)
  const saved = String(module.config.statement_email ?? '')

  const sendNow = async () => {
    setSending(true)
    try {
      const res = await sendStatement(month)
      notify(
        'success',
        t('finance.statement.sent', 'Kontoauszug unterwegs'),
        t('finance.statement.sentTo', 'An {{email}}', { email: res.to }),
      )
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), (err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb={4}>
        {t('finance.statement.title', 'Monatlicher Kontoauszug')}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t(
          'finance.statement.intro',
          'Am 1. jedes Monats ein PDF mit Saldo, Summen pro Kategorie, allen Buchungen und den offenen Rechnungen des Vormonats, zum Beispiel an die Kassierin oder die Revision.',
        )}
      </Text>
      <Stack gap="md" maw={520}>
        <Switch
          label={t('finance.statement.enabled', 'Jeden Monat per E-Mail senden')}
          checked={enabled}
          onChange={(e) => setEnabled(e.currentTarget.checked)}
        />
        <TextInput
          type="email"
          label={t('finance.statement.email', 'An diese Adresse')}
          placeholder="kasse@verein.ch"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
          error={
            enabled && !email.includes('@')
              ? t('finance.statement.emailNeeded', 'Eine E-Mail-Adresse ist nötig.')
              : undefined
          }
        />
      </Stack>
      <Group justify="flex-end" mt="md">
        <Button
          loading={busy}
          disabled={enabled && !email.includes('@')}
          onClick={() => save({ statement_enabled: enabled, statement_email: email.trim() })}
        >
          {t('common.save', 'Speichern')}
        </Button>
      </Group>
      <Group mt="lg" gap="sm" align="flex-end" wrap="wrap">
        <Select
          label={t('finance.statement.month', 'Monat')}
          data={months}
          value={month}
          onChange={(v) => v && setMonth(v)}
          allowDeselect={false}
          w={200}
        />
        <Button variant="default" onClick={() => void downloadStatement(month)}>
          {t('finance.statement.download', 'PDF herunterladen')}
        </Button>
        <Button
          variant="default"
          loading={sending}
          disabled={!saved.includes('@')}
          onClick={() => void sendNow()}
        >
          {t('finance.statement.sendNow', 'Jetzt senden')}
        </Button>
      </Group>
    </Paper>
  )
}

function InvoiceSettingsForm({ module }: { module: ModuleInfo }) {
  const { t } = useT()
  const [save, busy] = useSaveSettings(module)
  const [values, setValues] = useState<Record<string, FormValue>>(() => ({ ...module.config }))

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb="md">
        {t('finance.settings.invoicesTitle', 'Rechnungen und Mahnungen')}
      </Title>
      <Stack gap="md" maw={480}>
        {module.settings
          .filter((field) => !OWN_CARD_KEYS.has(field.key))
          .map((field) => (
            <SettingInput
              key={field.key}
              field={field}
              value={values[field.key] ?? null}
              onChange={(v) => setValues((prev) => ({ ...prev, [field.key]: v }))}
            />
          ))}
      </Stack>
      <Group justify="flex-end" mt="md">
        <Button onClick={() => save(values)} loading={busy}>
          {t('common.save', 'Speichern')}
        </Button>
      </Group>
    </Paper>
  )
}

/** Finanzen › Einstellungen: billing rules, and where the bank account is set. */
export function FinanceSettingsTab() {
  const { t } = useT()
  const { go } = useNav()
  const { hasPermission } = useAuth()
  const { data: finance } = useQuery({
    queryKey: qk.modules,
    queryFn: getModules,
    select: (list) => list.map(localizeModule).find((m) => m.code === 'finance'),
  })

  return (
    <Stack gap={20}>
      {finance && <FeeScheduleForm key={`fees-${JSON.stringify(finance.config)}`} module={finance} />}
      {finance && <InvoiceSettingsForm key={JSON.stringify(finance.config)} module={finance} />}
      {finance && <StatementForm key={`statement-${JSON.stringify(finance.config)}`} module={finance} />}
      {hasPermission('settings.settings.read') && (
        <Paper withBorder p="lg">
          <Group justify="space-between" align="center" wrap="wrap" gap="md">
            <div style={{ minWidth: 0, flex: 1 }}>
              <Title order={3} mb={4}>
                {t('clubSettings.bank.title', 'Bank & QR-Rechnung')}
              </Title>
              <Text size="sm" c="dimmed">
                {t(
                  'finance.settings.bankHint',
                  'Das Konto und die Adresse auf den QR-Rechnungen stellst du in den Einstellungen des Vereins ein.',
                )}
              </Text>
            </div>
            <Button variant="default" onClick={() => go('/app/settings/bank')}>
              {t('finance.settings.openBank', 'Bankangaben öffnen')}
            </Button>
          </Group>
        </Paper>
      )}
    </Stack>
  )
}
