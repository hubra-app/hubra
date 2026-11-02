// Plan names from manage › Einstellungen › Tarife, filled by usePlanNames.
const planNames: Record<string, [string, string]> = {
  starter: ['Starter', 'Starter'],
  growth: ['Growth', 'Growth'],
  enterprise: ['Enterprise', 'Enterprise'],
}

export function registerPlanNames(plans: { key: string; name_de: string; name_en: string }[]) {
  for (const p of plans) planNames[p.key] = [p.name_de, p.name_en || p.name_de]
}

/** Display names for tenant plans and statuses. */
export function planLabel(plan: string, tr: (de: string, en: string) => string) {
  const name = planNames[plan]
  return name ? tr(name[0], name[1]) : plan || tr('Kein Plan', 'No plan')
}

export function statusLabel(status: string, tr: (de: string, en: string) => string) {
  const labels: Record<string, [string, string]> = {
    active: ['Aktiv', 'Active'],
    suspended: ['Gesperrt', 'Suspended'],
    archived: ['Archiviert', 'Archived'],
    pending: ['Offen', 'Pending'],
    approved: ['Freigegeben', 'Approved'],
    rejected: ['Abgelehnt', 'Rejected'],
    // Member statuses
    trial: ['Probezeit', 'Trial'],
    inactive: ['Inaktiv', 'Inactive'],
  }
  const l = labels[status]
  return l ? tr(l[0], l[1]) : status
}
