import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { getModules, saveModuleSettings, type ModuleInfo } from '@/api/modules'
import { localizeModule } from '@/modules/labels'
import { qk } from '@/data/keys'
import { SettingInput } from '@/screens/private/settings/ModulesTab'

type FormValue = string | number | boolean | null

function InvoiceSettingsForm({ module }: { module: ModuleInfo }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<string, FormValue>>(() => ({ ...module.config }))
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try {
      await saveModuleSettings(module.code, values)
      await queryClient.invalidateQueries({ queryKey: qk.modules })
      notify('success', t('finance.settings.saved', 'Einstellungen gespeichert'))
    } catch (err) {
      notify('error', module.name, (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="lg">
      <Title order={3} mb="md">
        {t('finance.settings.invoicesTitle', 'Rechnungen und Mahnungen')}
      </Title>
      <Stack gap="md" maw={480}>
        {module.settings.map((field) => (
          <SettingInput
            key={field.key}
            field={field}
            value={values[field.key] ?? null}
            onChange={(v) => setValues((prev) => ({ ...prev, [field.key]: v }))}
          />
        ))}
      </Stack>
      <Group justify="flex-end" mt="md">
        <Button onClick={save} loading={busy}>
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
      {finance && <InvoiceSettingsForm key={JSON.stringify(finance.config)} module={finance} />}
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
