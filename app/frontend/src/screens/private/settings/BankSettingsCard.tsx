import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Group, Paper, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import {
  getBankSettings,
  updateBankSettings,
  type BankSettings,
  type BankSettingsInput,
} from '@/api/admin'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { useToast } from '@/context/AppContext'

function BankForm({ initial }: { initial: BankSettings }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<BankSettingsInput>({
    iban: initial.iban,
    street: initial.street,
    houseNo: initial.houseNo,
    postalCode: initial.postalCode,
    city: initial.city,
    country: initial.country,
  })
  const [saved, setSaved] = useState(initial)
  const [saving, setSaving] = useState(false)
  const set = (key: keyof BankSettingsInput) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const save = async () => {
    setSaving(true)
    try {
      const next = await updateBankSettings(form)
      setSaved(next)
      setForm((prev) => ({ ...prev, iban: next.iban, country: next.country }))
      queryClient.setQueryData(qk.settings.bank, next)
      notify('success', t('clubSettings.bank.saved', 'Bankangaben gespeichert'))
    } catch (err: unknown) {
      notify(
        'error',
        t('clubSettings.saveFailed', 'Einstellungen nicht gespeichert'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb={4}>
        {t('clubSettings.bank.title', 'Bank & QR-Rechnung')}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t(
          'clubSettings.bank.hint',
          'Auf dieses Konto zahlen Mitglieder ihre Rechnungen. Mit einer QR-IBAN bekommt jede Rechnung eine QR-Referenz, über die der Bankimport Zahlungen zuordnet.',
        )}
      </Text>
      <Stack gap={14}>
        {!saved.complete ? (
          <Alert color="yellow" variant="light">
            {t(
              'clubSettings.bank.incomplete',
              'Ohne IBAN, PLZ und Ort können Rechnungen keinen QR-Einzahlungsschein enthalten.',
            )}
          </Alert>
        ) : (
          <Text size="sm" c={saved.isQrIban ? 'green' : 'dimmed'}>
            {saved.isQrIban
              ? t('clubSettings.bank.qrIban', 'QR-IBAN: Rechnungen erhalten eine QR-Referenz.')
              : t(
                  'clubSettings.bank.plainIban',
                  'Normale IBAN: Rechnungen haben einen QR-Einzahlungsschein ohne QR-Referenz.',
                )}
          </Text>
        )}
        <TextInput
          label={t('clubSettings.bank.iban', 'IBAN oder QR-IBAN')}
          placeholder="CH44 3199 9123 0008 8901 2"
          value={form.iban}
          onChange={set('iban')}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={t('clubSettings.bank.street', 'Strasse')}
            value={form.street}
            onChange={set('street')}
          />
          <TextInput
            label={t('clubSettings.bank.houseNo', 'Hausnummer')}
            value={form.houseNo}
            onChange={set('houseNo')}
          />
          <TextInput
            label={t('clubSettings.bank.postalCode', 'PLZ')}
            value={form.postalCode}
            onChange={set('postalCode')}
          />
          <TextInput
            label={t('clubSettings.bank.city', 'Ort')}
            value={form.city}
            onChange={set('city')}
          />
          <TextInput
            label={t('clubSettings.bank.country', 'Land (z. B. CH)')}
            value={form.country}
            maxLength={2}
            onChange={set('country')}
          />
        </SimpleGrid>
        <Group justify="flex-end">
          <Button loading={saving} onClick={save}>
            {t('clubSettings.bank.save', 'Bankangaben speichern')}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

/** Settings › Bank & QR-Rechnung: the account and address on the club's QR invoices. */
export function BankSettingsCard() {
  const { data } = useQuery({ queryKey: qk.settings.bank, queryFn: getBankSettings })
  if (!data) return null
  return <BankForm initial={data} />
}
