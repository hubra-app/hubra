import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { saveModuleSettings, type ModuleInfo } from '@/api/modules'
import { qk } from '@/data/keys'

type FormValue = string | number | boolean | null

/** Save some of the finance module's settings, keeping the others. */
export function useSaveSettings(module: ModuleInfo) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const save = async (values: Record<string, FormValue>) => {
    setBusy(true)
    try {
      // The module's settings are saved as one set.
      await saveModuleSettings(module.code, { ...module.config, ...values })
      await queryClient.invalidateQueries({ queryKey: qk.modules })
      notify('success', t('finance.settings.saved', 'Einstellungen gespeichert'))
    } catch (err) {
      notify('error', module.name, (err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return [save, busy] as const
}
