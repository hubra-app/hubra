import { useQuery } from '@tanstack/react-query'
import { Paper } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { StatTile } from '@/components/ui'
import { listMailboxes, listAliases, listMailMembers } from '@/api/mail'

export function MailSettingsTab() {
  const { t } = useT()

  const { data: mailboxes } = useQuery({
    queryKey: ['mailboxes'],
    queryFn: () => listMailboxes(),
  })
  const { data: aliases } = useQuery({
    queryKey: ['aliases'],
    queryFn: () => listAliases(),
  })
  const { data: mailMembers } = useQuery({
    queryKey: ['mail-members'],
    queryFn: () => listMailMembers(),
  })

  const mailboxCount = mailboxes?.length ?? 0
  const totalMessages = mailboxes?.reduce((s, m) => s + m.messageCount, 0) ?? 0
  const totalUsed = mailboxes?.reduce((s, m) => s + m.quotaUsed, 0) ?? 0
  const totalCap = mailboxes?.reduce((s, m) => s + m.quotaTotal, 0) ?? 0
  const aliasCount = aliases?.length ?? 0
  const memberMailCount =
    mailMembers?.filter((m) => m.wildduckId !== null).length ?? 0

  return (
    <div>
      <div
        className="grid-4"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 24,
        }}
      >
        <StatTile
          label={t('mail.mailboxes', 'Mailboxe')}
          value={mailboxCount}
          sub={t('mail.activeInboxes', 'Aktivi Inboxe')}
        />
        <StatTile
          label={t('mail.aliases', 'Aliasse')}
          value={aliasCount}
          sub={t('mail.active.aliases', 'Aktivi Aliasse')}
          accent="#2596be"
        />
        <StatTile
          label={t('mail.storageUsed', 'Speicher brucht')}
          value={`${totalUsed.toFixed(1)} GB`}
          sub={t('mail.ofTotalGb', 'vo {{total}} GB insgsamt', {
            total: totalCap,
          })}
          accent="#8a6a00"
        />
        <StatTile
          label={t('mail.mailboxesProvisioned', 'Mitglid-Mailboxe')}
          value={memberMailCount}
          sub={t('mail.activeWildDuckAccounts', 'Aktivi WildDuck-Account')}
          accent="#1f9d57"
        />
      </div>

      <Paper withBorder shadow="sm" radius="lg" style={{ padding: 20 }}>
        <div
          style={{
            fontSize: 'var(--mantine-font-size-md)',
            fontWeight: 700,
            color: '#181818',
            marginBottom: 16,
          }}
        >
          {t('mail.domainStatus', 'Domain-Status')}
        </div>
        <div
          className="grid-3"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 12,
          }}
        >
          {['SPF', 'DKIM', 'DMARC'].map((proto) => (
            <div
              key={proto}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '12px 14px',
                background: '#f4f8f5',
                borderRadius: 10,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: '#e8f5e9',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 700,
                  color: '#1b7c2d',
                }}
              >
                {proto}
              </div>
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 600,
                    color: '#181818',
                  }}
                >
                  {t('mail.verified', 'Verifiziert')}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#6b7480',
                  }}
                >
                  {t('mail.records.configured', 'Records konfiguriert')}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Paper>

      <Paper
        withBorder
        shadow="sm"
        radius="lg"
        style={{ padding: 20, marginTop: 16 }}
      >
        <div
          style={{
            fontSize: 'var(--mantine-font-size-md)',
            fontWeight: 700,
            color: '#181818',
            marginBottom: 8,
          }}
        >
          {t('mail.messagesStored', 'Gspeichereti Nachrichtä')}
        </div>
        <div
          className="num"
          style={{ fontSize: 28, fontWeight: 700, color: '#181818' }}
        >
          {totalMessages.toLocaleString()}
        </div>
        <div
          style={{
            fontSize: 'var(--mantine-font-size-xs)',
            color: '#6b7480',
            marginTop: 4,
          }}
        >
          {t('mail.allInboxes', 'Alli Inboxe')}
        </div>
      </Paper>
    </div>
  )
}
