import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getHubraCatalog, setHubraAddon, type HubraAddonOffer } from '@/api/billing'
import { ConfirmModal } from '@/components/feedback'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatCHF } from '@/format'
import { getCurrentLanguage, useT } from '@/locales/i18n'

type TFn = ReturnType<typeof useT>['t']

export const en = () => (getCurrentLanguage() || 'de').startsWith('en')

export function useHubraCatalog() {
  return useQuery({ queryKey: qk.settings.subscriptionCatalog, queryFn: getHubraCatalog })
}

/** "CHF 2.00 pro Mitglied und Monat" for a paid module. */
export function addonPrice(t: TFn, a: Pick<HubraAddonOffer, 'price_month_chf' | 'unit'>) {
  if (a.price_month_chf == null) return t('subscription.onRequest', 'Preis auf Anfrage')
  const amount = `CHF ${formatCHF(Number(a.price_month_chf))}`
  if (a.unit === 'member')
    return t('subscription.perMemberMonth', '{{amount}} pro Mitglied und Monat', { amount })
  if (a.unit === 'license')
    return t('subscription.perLicenseMonth', '{{amount}} pro Lizenz und Monat', { amount })
  return t('subscription.perMonthAmount', '{{amount}} pro Monat', { amount })
}

export const addonName = (a: { name_de: string; name_en: string }) =>
  en() ? a.name_en || a.name_de : a.name_de

/** Take or drop a paid module, with a confirmation that names the price. */
export function useAddonSwitch() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<{ addon: HubraAddonOffer; on: boolean } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const apply = async (code: string, body: { on?: boolean; licenses?: number }) => {
    setBusy(code)
    try {
      await setHubraAddon(code, body)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: qk.settings.subscription }),
        queryClient.invalidateQueries({ queryKey: qk.modules }),
      ])
      notify('success', t('subscription.addonSaved', 'Abo angepasst'))
    } catch (err) {
      notify(
        'error',
        t('subscription.addonFailed', 'Konnte das Abo nicht ändern'),
        (err as Error).message,
      )
    } finally {
      setBusy(null)
    }
  }

  const modal = pending && (
    <ConfirmModal
      open
      title={
        pending.on
          ? t('subscription.addonOnTitle', '{{name}} dazubuchen?', {
              name: addonName(pending.addon),
            })
          : t('subscription.addonOffTitle', '{{name}} abbestellen?', {
              name: addonName(pending.addon),
            })
      }
      body={
        pending.on
          ? t(
              'subscription.addonOnBody',
              '{{price}}. Das Modul wird eingeschaltet. Für den Rest des laufenden Monats kommt der Betrag anteilig auf die nächste Rechnung.',
              { price: addonPrice(t, pending.addon) },
            )
          : t(
              'subscription.addonOffBody',
              'Das Modul wird ausgeschaltet, seine Daten bleiben. Für den Rest des Monats gibt es auf der nächsten Rechnung eine anteilige Gutschrift.',
            )
      }
      confirmLabel={
        pending.on
          ? t('subscription.addonOn', 'Dazubuchen')
          : t('subscription.addonOff', 'Abbestellen')
      }
      onClose={() => setPending(null)}
      onConfirm={() => {
        const p = pending
        setPending(null)
        void apply(p.addon.code, { on: p.on })
      }}
    />
  )
  return {
    ask: (addon: HubraAddonOffer, on: boolean) => setPending({ addon, on }),
    apply,
    busy,
    modal,
  }
}
