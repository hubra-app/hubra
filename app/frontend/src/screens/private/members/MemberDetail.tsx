import { useState, type ReactNode } from 'react'
import { Anchor, Button, Paper, Table, Text, Title } from '@mantine/core'
import { formatCHF, formatDate } from '@/format'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useParams } from 'react-router-dom'
import {
  IconArrowLeft,
  IconPencil,
  IconLock,
  IconCircleCheck,
  IconMail,
  IconAddressBook,
  IconId,
  IconFirstAidKit,
} from '@tabler/icons-react'
import { useNav, useToast, useAuth } from '@/context/AppContext'
import {
  Avatar,
  TierTag,
  StatusBadge,
  Tag,
  LastSeenBadge,
  LoadingSpinner,
  InvoicePill,
  Tabs,
} from '@/components/ui'
import type { Member } from '@/types'
import { getMember, disableMember, enableMember } from '@/api/members'
import { listMemberInvoices } from '@/api/finance'
import { listFunctions } from '@/api/functions'
import { listAuditLog } from '@/api/settings'
import { MemberEditModal } from '@/components/MemberEditModal'
import { MemberPrivacySection } from './MemberPrivacySection'
import { MemberFeeSection } from './MemberFeeSection'
import {
  ActivityList,
  DetailEmpty as Empty,
  DetailFact as Fact,
  DetailMuted as Muted,
  DetailRow,
  DetailSection as Section,
} from '@/components/detail'
import { roleLabel, roleLabels } from '@/roles'
import { qk } from '@/data/keys'

/* ── Member Detail ──────────────────────────── */
export function MemberDetailScreen({
  member: propMember,
}: {
  member?: Member | null
}) {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canUpdate = hasPermission('members.members.update')
  const canDisable = hasPermission('members.members.disable')
  const canEnable = hasPermission('members.members.enable')
  // Each section below loads only with the right the club's own page needs.
  const canInvoices = hasPermission('finance.invoices.read')
  const canFunctions = hasPermission('functions.functions.read')
  const canAudit = hasPermission('audit.audit.read')
  const [tab, setTab] = useState('overview')
  const { data: member } = useQuery({
    queryKey: qk.members.one(id),
    queryFn: () => getMember(id!),
    enabled: !!id,
    initialData: propMember ?? undefined,
  })
  const invoicesQ = useQuery({
    queryKey: qk.invoices.member(id),
    queryFn: () => listMemberInvoices(id!),
    enabled: !!id && canInvoices,
  })
  const functionsQ = useQuery({
    queryKey: qk.functions,
    queryFn: listFunctions,
    enabled: canFunctions,
  })
  const activityQ = useQuery({
    queryKey: qk.audit.member(id),
    queryFn: () => listAuditLog({ memberId: id!, pageSize: 25 }),
    enabled: !!id && canAudit && tab === 'activity',
  })
  const [editOpen, setEditOpen] = useState(false)
  const [togglingDisable, setTogglingDisable] = useState(false)

  const m = member
  if (!m) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />

  const toggleDisable = async () => {
    if (!member) return
    setTogglingDisable(true)
    try {
      const updated = member.isDisabled
        ? await enableMember(member.id)
        : await disableMember(member.id)
      queryClient.invalidateQueries({ queryKey: qk.members.one(id) })
      notify(
        'success',
        updated.isDisabled ? t('members.disabled', 'Mitglied deaktiviert') : t('members.enabled', 'Mitglied aktiviert'),
        `${updated.name} has been ${
          updated.isDisabled ? 'disabled' : 'enabled'
        }.`,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setTogglingDisable(false)
    }
  }

  const invoices = invoicesQ.data ?? []
  const unpaid = invoices.filter((i) => i.status !== 'Paid')
  const openAmount = unpaid.reduce((sum, i) => sum + i.amount, 0)
  const overdue = invoices.filter((i) => i.status === 'Overdue').length
  const functions = (functionsQ.data ?? []).flatMap((f) =>
    f.holders
      .filter((h) => String(h.memberId) === m.id)
      .map((h) => ({ id: f.id, name: f.name, since: h.assignedAt })),
  )
  const roles = [
    roleLabels(m.roles),
    ...(m.functionRoles ?? [])
      .filter((fr) => !m.roles.includes(fr.name))
      .map((fr) =>
        t('members.roleViaFunction', '{{role}} (über {{fn}})', {
          role: roleLabel(fr.name),
          fn: fr.function,
        }),
      ),
    ...(m.scopedRoles ?? []).map((sr) =>
      t('members.roleForGroup', '{{role}} (nur {{group}})', {
        role: roleLabel(sr.name),
        group: sr.group,
      }),
    ),
  ].filter(Boolean)
  const address = m.address
  const addressLines = address
    ? [
        [address.street, address.houseNo].filter(Boolean).join(' '),
        [address.postalCode, address.city].filter(Boolean).join(' '),
      ].filter(Boolean)
    : []
  const contact = m.emergencyContact
  const hasContact = !!(contact && (contact.name || contact.phone))
  const customFields = Object.entries(m.customFields ?? {}).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  )

  const tabs = [
    { id: 'overview', label: t('members.detail.overview') },
    ...(canInvoices ? [{ id: 'payments', label: t('members.detail.payments') }] : []),
    ...(canAudit ? [{ id: 'activity', label: t('members.detail.activity') }] : []),
  ]

  return (
    <div>
      <Button
        size="sm"
        variant="subtle"
        px={6}
        leftSection={<IconArrowLeft size={16} />}
        onClick={() => go('/app/members')}
        style={{ marginBottom: 12, marginLeft: -6 }}
      >
        {t('members.detail.backToMembers')}
      </Button>

      {/* ── Who this is, at a glance ── */}
      <Paper withBorder p={{ base: 16, sm: 20 }} mb={16}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <Avatar name={m.name} color={m.avatarColor} size={72} lastSeen={m.lastSeen} />
          <div style={{ flex: '1 1 260px', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Title order={1} fz={{ base: 24, sm: 30 }}>
                {m.name}
              </Title>
              <span
                className="num"
                title={t('members.detail.numberHint', 'Mitgliedernummer')}
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--hb-text-3)',
                  background: 'var(--hb-surface-2)',
                  borderRadius: 6,
                  padding: '2px 8px',
                }}
              >
                {t('members.detail.number', 'Nr. {{id}}', { id: m.id })}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                flexWrap: 'wrap',
                marginTop: 8,
              }}
            >
              <StatusBadge status={m.status} />
              {m.tier && <TierTag tier={m.tier} />}
              {functions.map((f) => (
                <Tag key={f.id} color="var(--mantine-color-acc-text)">
                  {f.name}
                </Tag>
              ))}
              {m.isDisabled && (
                <span
                  style={{
                    background: 'rgba(239,68,68,.15)',
                    border: '1px solid rgba(239,68,68,.3)',
                    borderRadius: 6,
                    padding: '2px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--mantine-color-red-text)',
                  }}
                >
                  <IconLock size={12} />
                  {t('common.disabled')}
                </span>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {m.email && (
              <Button
                variant="default"
                component="a"
                href={`mailto:${m.email}`}
                leftSection={<IconMail size={16} />}
              >
                {t('members.detail.writeEmail', 'E-Mail schreiben')}
              </Button>
            )}
            {canUpdate && (
              <Button
                variant="default"
                leftSection={<IconPencil size={16} />}
                onClick={() => setEditOpen(true)}
              >
                {t('common.edit')}
              </Button>
            )}
            {((m.isDisabled && canEnable) || (!m.isDisabled && canDisable)) && (
              <Button
                variant="default"
                style={{ color: m.isDisabled ? 'var(--mantine-color-green-text)' : 'var(--mantine-color-red-text)' }}
                onClick={toggleDisable}
                disabled={togglingDisable}
              >
                {togglingDisable
                  ? '…'
                  : m.isDisabled
                    ? t('members.detail.enable')
                    : t('members.detail.disable')}
              </Button>
            )}
          </div>
        </div>

        <div className="member-facts" data-testid="member-facts">
          <Fact label={t('members.joined')}>
            {m.joined ? formatDate(m.joined) : '—'}
            {m.joined && (
              <Text span size="xs" c="dimmed" ml={6}>
                {membershipLength(m.joined, t)}
              </Text>
            )}
          </Fact>
          <Fact label={t('members.lastSeen')}>
            <LastSeenBadge lastSeen={m.lastSeen} />
          </Fact>
          <Fact label={t('members.detail.groups')}>{m.groups.length}</Fact>
          {canInvoices && (
            <Fact label={t('members.detail.openAmount', 'Offen')}>
              <span
                className="num"
                style={{ color: overdue ? 'var(--mantine-color-red-text)' : undefined }}
              >
                {invoicesQ.isLoading ? '…' : `CHF ${formatCHF(openAmount)}`}
              </span>
            </Fact>
          )}
        </div>
      </Paper>

      <div className="detail-grid">
        {/* ── Facts about the person and their membership ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Section icon={<IconAddressBook size={16} />} title={t('members.detail.contact', 'Kontakt')}>
            <DetailRow label={t('members.email')}>
              {m.email ? <Anchor href={`mailto:${m.email}`} size="sm">{m.email}</Anchor> : <Empty />}
            </DetailRow>
            {m.publicEmail && (
              <DetailRow label={t('account.clubEmail', 'Vereins-E-Mail')} mono>
                {m.publicEmail}
              </DetailRow>
            )}
            {m.phone && (
              <DetailRow label={t('members.phone')}>
                <Anchor href={`tel:${m.phone}`} size="sm">{m.phone}</Anchor>
              </DetailRow>
            )}
            {m.mobile && (
              <DetailRow label={t('members.detail.mobile', 'Mobile')}>
                <Anchor href={`tel:${m.mobile}`} size="sm">{m.mobile}</Anchor>
              </DetailRow>
            )}
            {addressLines.length > 0 && (
              <DetailRow label={t('account.directory.address', 'Adresse')}>
                <span style={{ textAlign: 'right', display: 'block' }}>
                  {addressLines.map((line) => (
                    <span key={line} style={{ display: 'block' }}>
                      {line}
                    </span>
                  ))}
                </span>
              </DetailRow>
            )}
            {m.birthday && (
              <DetailRow label={t('account.directory.birthday', 'Geburtstag')}>
                {formatDate(m.birthday)}
              </DetailRow>
            )}
          </Section>

          <Section icon={<IconId size={16} />} title={t('members.detail.membership', 'Mitgliedschaft')}>
            <DetailRow label={t('members.tier')}>
              {m.tier ? <TierTag tier={m.tier} /> : <Empty />}
            </DetailRow>
            {m.membershipType && m.membershipType !== 'regular' && (
              <DetailRow label={t('members.detail.membershipType', 'Art')}>
                {t(`members.detail.types.${m.membershipType}`, m.membershipType)}
              </DetailRow>
            )}
            {m.membershipUntil && (
              <DetailRow label={t('members.detail.until', 'Gültig bis')}>
                {formatDate(m.membershipUntil)}
              </DetailRow>
            )}
            <DetailRow label={t('members.clubUsername')} mono>
              {m.clubUsername || <Empty />}
            </DetailRow>
            <DetailRow label={t('members.emailVerified')}>
              {m.privateEmailVerified ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--mantine-color-green-text)' }}>
                  <IconCircleCheck size={14} />
                  {t('common.yes')}
                </span>
              ) : (
                <span style={{ color: 'var(--mantine-color-red-text)' }}>{t('common.no')}</span>
              )}
            </DetailRow>
            {/* Only worth a row while the member still has to set a new one. */}
            {m.mustChangePassword && (
              <DetailRow label={t('common.password')}>
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    color: 'var(--mantine-color-red-text)',
                  }}
                >
                  <IconLock size={14} /> {t('members.detail.mustChange')}
                </span>
              </DetailRow>
            )}
            {m.toolHours > 0 && (
              <DetailRow label={t('members.detail.toolHours')} mono>
                {m.toolHours}h
              </DetailRow>
            )}
          </Section>

          {id && <MemberFeeSection memberId={id} memberName={m.name} />}

          {hasContact && (
            <Section
              icon={<IconFirstAidKit size={16} />}
              title={t('members.detail.emergencyContact', 'Notfallkontakt')}
            >
              {contact?.name && (
                <DetailRow label={t('common.name', 'Name')}>{contact.name}</DetailRow>
              )}
              {contact?.relation && (
                <DetailRow label={t('members.detail.relation', 'Beziehung')}>
                  {contact.relation}
                </DetailRow>
              )}
              {contact?.phone && (
                <DetailRow label={t('members.phone')}>
                  <Anchor href={`tel:${contact.phone}`} size="sm">{contact.phone}</Anchor>
                </DetailRow>
              )}
            </Section>
          )}

          {id && <MemberPrivacySection memberId={id} />}
        </div>

        {/* ── What the member does in the club ── */}
        <Paper withBorder p={{ base: 16, sm: 20 }} pt={8}>
          {tabs.length > 1 && <Tabs tabs={tabs} activeTab={tab} onTabChange={setTab} />}

          {tab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
              <Block title={t('common.roles', 'Rollen')}>
                {roles.length ? (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {roles.map((r) => (
                      <Tag key={r}>{r}</Tag>
                    ))}
                  </div>
                ) : (
                  <Muted>{t('members.detail.noRoles', 'Keine Rollen')}</Muted>
                )}
              </Block>

              {canFunctions && (
                <Block title={t('shell.nav.functions', 'Funktionen')}>
                  {functions.length ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {functions.map((f) => (
                        <div
                          key={f.id}
                          style={{
                            display: 'flex',
                            alignItems: 'baseline',
                            gap: 8,
                            flexWrap: 'wrap',
                            fontSize: 'var(--mantine-font-size-sm)',
                          }}
                        >
                          <Anchor size="sm" fw={600} onClick={() => go(`/app/members/functions/${f.id}`)}>
                            {f.name}
                          </Anchor>
                          {f.since && (
                            <Text span size="xs" c="dimmed">
                              {t('members.detail.since', 'seit {{date}}', { date: formatDate(f.since) })}
                            </Text>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Muted>{t('members.detail.noFunctions', 'Keine Funktion im Verein')}</Muted>
                  )}
                </Block>
              )}

              <Block title={t('members.detail.groups')}>
                {m.groups.length ? (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {m.groups.map((g) => (
                      <Tag key={g}>{g}</Tag>
                    ))}
                  </div>
                ) : (
                  <Muted>{t('members.detail.noGroups', 'In keiner Gruppe')}</Muted>
                )}
              </Block>

              {m.profileNote && (
                <Block title={t('members.detail.about', 'Über mich')}>
                  <Note>{m.profileNote}</Note>
                </Block>
              )}

              {customFields.length > 0 && (
                <Block title={t('members.detail.moreFields', 'Weitere Angaben')}>
                  <div style={{ border: '1px solid var(--hb-border)', borderRadius: 9 }}>
                    {customFields.map(([k, v], i) => (
                      <DetailRow key={k} label={k} borderless={i === customFields.length - 1}>
                        {String(v)}
                      </DetailRow>
                    ))}
                  </div>
                </Block>
              )}

              {/* The club's own notes reach only those who may edit members. */}
              {canUpdate && (
                <Block title={t('members.detail.notes', 'Notizen')}>
                  <Note>{m.notes || t('members.noNotesYet', 'Noch keine Notizen')}</Note>
                </Block>
              )}
            </div>
          )}

          {tab === 'payments' && canInvoices && (
            <div>
              <div className="member-facts" style={{ marginTop: 0, marginBottom: 16, borderTop: 'none', paddingTop: 0 }}>
                <Fact label={t('members.detail.openAmount', 'Offen')}>
                  <span className="num">CHF {formatCHF(openAmount)}</span>
                </Fact>
                <Fact label={t('members.detail.overdue', 'Überfällig')}>
                  <span className="num" style={{ color: overdue ? 'var(--mantine-color-red-text)' : undefined }}>
                    {overdue}
                  </span>
                </Fact>
                <Fact label={t('members.detail.invoiceCount', 'Rechnungen')}>
                  <span className="num">{invoices.length}</span>
                </Fact>
              </div>
              {invoicesQ.isLoading ? (
                <LoadingSpinner />
              ) : invoices.length === 0 ? (
                <Muted>{t('members.detail.noInvoices', 'Noch keine Rechnungen')}</Muted>
              ) : (
                <Table.ScrollContainer minWidth={480}>
                  <Table highlightOnHover verticalSpacing="sm" data-testid="member-invoices">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>{t('finance.invoiceDescription', 'Beschreibung')}</Table.Th>
                        <Table.Th>{t('finance.invoiceDue', 'Fällig')}</Table.Th>
                        <Table.Th style={{ textAlign: 'right' }}>
                          {t('finance.invoiceAmount', 'Betrag')}
                        </Table.Th>
                        <Table.Th>{t('finance.invoiceStatus', 'Status')}</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {invoices.map((inv) => (
                        <Table.Tr
                          key={inv.id}
                          style={{ cursor: 'pointer' }}
                          onClick={() => go(`/app/finance/invoices/${inv.id}`)}
                        >
                          <Table.Td>
                            {inv.description ||
                              t('members.detail.invoiceNo', 'Rechnung {{id}}', { id: inv.id })}
                          </Table.Td>
                          <Table.Td>{formatDate(inv.due)}</Table.Td>
                          <Table.Td className="num" style={{ textAlign: 'right' }}>
                            {formatCHF(inv.amount)}
                          </Table.Td>
                          <Table.Td>
                            <InvoicePill status={inv.status} />
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
              )}
            </div>
          )}

          {tab === 'activity' && canAudit && (
            <div>
              {activityQ.isLoading ? (
                <LoadingSpinner />
              ) : !activityQ.data?.entries.length ? (
                <Muted>{t('members.detail.noActivity', 'Noch keine Einträge')}</Muted>
              ) : (
                <ActivityList page={activityQ.data} testId="member-activity" />
              )}
            </div>
          )}
        </Paper>
      </div>

      <MemberEditModal
        member={m}
        mode="edit"
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: qk.members.one(id) })
          setEditOpen(false)
        }}
      />
    </div>
  )
}

/** "3 Jahre", "5 Monate": how long someone has been a member. */
function membershipLength(joined: string, t: ReturnType<typeof useT>['t']): string {
  const from = new Date(joined)
  const now = new Date()
  const months =
    (now.getFullYear() - from.getFullYear()) * 12 + (now.getMonth() - from.getMonth()) -
    (now.getDate() < from.getDate() ? 1 : 0)
  if (months >= 12) {
    return t('members.detail.years', '{{count}} Jahre', { count: Math.floor(months / 12) })
  }
  if (months >= 1) return t('members.detail.months', '{{count}} Monate', { count: months })
  return t('members.detail.new', 'neu')
}

/* ── Detail helpers ───────────────────────────── */
function Note({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 'var(--mantine-font-size-sm)',
        color: 'var(--hb-text)',
        background: 'var(--hb-surface-2)',
        borderRadius: 9,
        padding: '12px 14px',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
      }}
    >
      {children}
    </div>
  )
}

/** A titled part of the overview tab. */
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-sm)',
          fontWeight: 600,
          color: 'var(--hb-text-2)',
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      {children}
    </section>
  )
}
