import { Badge, Group, Stack, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import type { LeaveAt, LeaveTerms } from '@/api/members'
import { formatCHF, formatDate } from '@/format'

/** "Leave at the end of the year, 3 months' notice" in words. */
function useNoticeText() {
  const { t } = useT()
  return (notice: LeaveTerms['notice']) => {
    const period: Record<LeaveAt, string> = {
      any: t('members.leave.at.any', 'jederzeit'),
      month_end: t('members.leave.at.monthEnd', 'auf Ende Monat'),
      quarter_end: t('members.leave.at.quarterEnd', 'auf Ende Quartal'),
      half_year_end: t('members.leave.at.halfYearEnd', 'auf Ende Halbjahr'),
      year_end: t('members.leave.at.yearEnd', 'auf Ende Jahr'),
    }
    return notice.months > 0
      ? t('members.leave.noticeRule', '{{months}} Monate Kündigungsfrist, {{period}}', {
          months: notice.months,
          period: period[notice.at],
        })
      : period[notice.at]
  }
}

/** The earliest exit date and the invoices still open, for a member who
 * leaves or the board deciding on a request. */
export function LeaveTermsNote({ terms, own }: { terms: LeaveTerms; own: boolean }) {
  const { t } = useT()
  const noticeText = useNoticeText()
  if (!terms.earliestExit && terms.openInvoices.length === 0) return null
  return (
    <Stack gap={4} data-testid="leave-terms">
      {terms.earliestExit && (
        <Text fz="sm">
          {t('members.leave.earliestExit', 'Frühester Austritt: {{date}}', {
            date: formatDate(terms.earliestExit),
          })}{' '}
          <Text span fz="xs" c="dimmed">
            ({noticeText(terms.notice)})
          </Text>
        </Text>
      )}
      {terms.openInvoices.length > 0 && (
        <>
          <Text fz="sm">
            {own
              ? t('members.leave.ownOpenInvoices', 'Diese Rechnungen sind noch offen und bleiben geschuldet:')
              : t('members.leave.openInvoices', 'Noch offene Rechnungen:')}
          </Text>
          {terms.openInvoices.map((inv) => (
            <Group key={inv.id} gap="xs" wrap="nowrap">
              <Text fz="sm" className="num">
                {formatCHF(Number(inv.amount))}
              </Text>
              <Text fz="xs" c="dimmed" style={{ flex: 1, minWidth: 0 }} truncate>
                {inv.description ?? t('members.leave.invoice', 'Rechnung')} ·{' '}
                {t('members.leave.due', 'fällig {{date}}', { date: formatDate(inv.due) })}
              </Text>
              {inv.overdue && (
                <Badge size="xs" color="red" variant="light">
                  {t('members.leave.overdue', 'überfällig')}
                </Badge>
              )}
            </Group>
          ))}
        </>
      )}
    </Stack>
  )
}
