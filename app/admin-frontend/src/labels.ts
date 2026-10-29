/** Display names for tenant plans and statuses. */
export function planLabel(plan: string, tr: (de: string, en: string) => string) {
  const labels: Record<string, string> = {
    starter: 'Starter',
    growth: 'Growth',
    enterprise: 'Enterprise',
  }
  return labels[plan] ?? (plan || tr('Kein Plan', 'No plan'))
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
