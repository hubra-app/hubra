import { useState, useEffect, useRef } from 'react'
import i18n from 'i18next'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Button, Group, Menu, NumberInput, Select, SimpleGrid, TextInput } from '@mantine/core'
import { DateField } from '@hubra/ui'
import { useModules } from '@/modules/useModules'
import { useT, zmsg } from '@/locales/i18n'
import { IconBell, IconCalendarDollar, IconDots, IconFileDownload, IconPencil, IconPlus, IconTrash } from '@tabler/icons-react'
import { useToast, useNav, useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useInvoices, useListCache } from '@/data/lists'
import type { Invoice } from '@/types'
import {
  Modal,
  Field,
  InvoicePill,
  usePagination,
  ConfirmModal,
  DataTable,
} from '@/components/ui'
import {
  createInvoice,
  createBulkInvoices,
  downloadInvoicePdf,
  listExternalParties,
  listTxCategories,
} from '@/api/finance'
import { MemberPicker } from '@/components/MemberPicker'
import { FeeRunPreviewModal } from '@/screens/private/finances/FeeRunPreview'
import { EditInvoiceModal } from '@/screens/private/finances/EditInvoiceModal'
import { listTiers, calculateTierCost } from '@/api/tiers'
import { formatCHF, formatDate } from '@/format'
import {
  useMarkInvoicePaid,
  useSendInvoiceReminder,
  useDeleteInvoice,
} from '@/screens/private/finances/useInvoiceActions'

/* -- Invoices ---------------------------------- */
const singleSchema = z
  .object({
    recipientType: z.enum(['member', 'external']),
    purpose: z.enum(['membership', 'other']),
    memberId: z.string(),
    externalPartyId: z.string(),
    amount: z.string(),
    due: z.string().min(1, zmsg('validation.dueRequired', 'Fälligkeitsdatum ist erforderlich')),
    description: z.string(),
    categoryId: z.string(),
    // Whether the Finances plugin keeps the books, so the invoice is booked
    // under a category.
    booksOn: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.recipientType === 'member' && !data.memberId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['memberId'],
        message: i18n.t('finance.validation.memberRequired', 'Bitte wähle ein Mitglied'),
      })
    }
    if (data.recipientType === 'external' && !data.externalPartyId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['externalPartyId'],
        message: i18n.t('finance.validation.partyRequired', 'Bitte wähle eine externe Partei'),
      })
    }
    if (!data.amount) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['amount'],
        message: i18n.t('finance.validation.amountRequired', 'Bitte gib einen Betrag ein'),
      })
    }
    if (
      data.booksOn &&
      (data.recipientType === 'external' || data.purpose === 'other') &&
      !data.categoryId
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['categoryId'],
        message: i18n.t('finance.validation.categoryRequired', 'Bitte wähle eine Kategorie'),
      })
    }
  })
type SingleForm = z.infer<typeof singleSchema>

const bulkSchema = z.object({
  tierId: z.string(),
  due: z.string().min(1, zmsg('validation.dueRequired', 'Fälligkeitsdatum ist erforderlich')),
  description: z.string(),
})
type BulkForm = z.infer<typeof bulkSchema>

export function InvoicesTab() {
  const { notify } = useToast()
  const { invoices } = useInvoices()
  const invoiceCache = useListCache<Invoice>(qk.invoices.all)
  const queryClient = useQueryClient()
  const { goInvoice } = useNav()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const markPaidMutation = useMarkInvoicePaid()
  const sendReminderMutation = useSendInvoiceReminder()
  const deleteInvoiceMutation = useDeleteInvoice()
  const canCreate = hasPermission('finance.invoices.create')
  const canBulkCreate = hasPermission('finance.invoices.bulk_create')
  const canUpdate = hasPermission('finance.invoices.update')
  const canDelete = hasPermission('finance.invoices.delete')
  const canRemind = hasPermission('finance.invoices.remind')
  const [editTarget, setEditTarget] = useState<Invoice | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [purposeFilter, setPurposeFilter] = useState('All')

  const singleForm = useForm<SingleForm>({
    validate: zod4Resolver(singleSchema),
    initialValues: {
      recipientType: 'member',
      purpose: 'membership',
      memberId: '',
      externalPartyId: '',
      amount: '',
      due: '',
      description: '',
      categoryId: '',
      booksOn: false,
    },
  })
  const bulkForm = useForm<BulkForm>({
    validate: zod4Resolver(bulkSchema),
    initialValues: { tierId: '', due: '', description: '' },
  })
  // The chosen member's tier sets the amount of a membership invoice.
  const [memberTier, setMemberTier] = useState<string | null>(null)
  const { data: tierOptions = [] } = useQuery({
    queryKey: qk.tiers.all,
    queryFn: () => listTiers(),
    enabled: addOpen || bulkOpen,
  })
  const { data: externalParties = [] } = useQuery({
    queryKey: qk.externalParties,
    queryFn: () => listExternalParties(),
    enabled: addOpen,
  })
  // The categories belong to the Finances plugin's books.
  const booksOn = useModules().has('finance.books')
  const { data: txCategories = [] } = useQuery({
    queryKey: qk.transactions.categories,
    queryFn: () => listTxCategories(),
    enabled: addOpen && booksOn,
  })
  const watchedMemberId = singleForm.values.memberId
  const watchedRecipientType = singleForm.values.recipientType
  const watchedPurpose = singleForm.values.purpose

  const filtered = invoices.filter((inv) => {
    const q = search.toLowerCase()
    const matchSearch =
      !q ||
      inv.id.toLowerCase().includes(q) ||
      inv.member.toLowerCase().includes(q)
    const matchStatus = statusFilter === 'All' || inv.status === statusFilter
    const matchPurpose =
      purposeFilter === 'All' || inv.purpose === purposeFilter
    return matchSearch && matchStatus && matchPurpose
  })
  const pg = usePagination(filtered, 25)
  const deleteTarget = invoices.find((i) => i.id === deleteTargetId) ?? null

  const openBulk = () => {
    bulkForm.initialize({ tierId: '', due: '', description: '' })
    setBulkOpen(true)
  }

  const handleBulk = async (data: BulkForm) => {
    setBulkSaving(true)
    try {
      const result = await createBulkInvoices({
        due: data.due,
        tierId: data.tierId || undefined,
        description: data.description || undefined,
      })
      invoiceCache.invalidate()
      queryClient.invalidateQueries({ queryKey: qk.dashboard })
      setBulkOpen(false)
      notify(
        'success',
        t('finance.invoicesCreated', 'Rechnungen erstellt'),
        t('finance.invoicesCreatedMsg', '{{count}} Rechnungen ausgestellt.', {
          count: result.created,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setBulkSaving(false)
    }
  }

  const openAdd = () => {
    singleForm.initialize({
      recipientType: 'member',
      purpose: 'membership',
      memberId: '',
      externalPartyId: externalParties[0]?.id ?? '',
      amount: '',
      due: '',
      description: '',
      categoryId: '',
      booksOn,
    })
    setAddOpen(true)
  }

  const handleCreate = async (data: SingleForm) => {
    setSaving(true)
    try {
      const today = new Date().toISOString().slice(0, 10)
      const inv = await createInvoice({
        memberId: data.recipientType === 'member' ? data.memberId : undefined,
        externalPartyId:
          data.recipientType === 'external' ? data.externalPartyId : undefined,
        issued: today,
        due: data.due,
        amount: parseFloat(data.amount),
        purpose: data.recipientType === 'external' ? 'other' : data.purpose,
        categoryId: data.categoryId || undefined,
        description: data.description || undefined,
      })
      invoiceCache.prepend(inv)
      queryClient.invalidateQueries({ queryKey: qk.dashboard })
      setAddOpen(false)
      notify(
        'success',
        t('finance.invoice.created', 'Rechnung erstellt'),
        t('finance.invoice.createdMsg', 'Die neue Rechnung wurde ausgestellt.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  // Read through a ref: useForm and t give new objects on every render, and
  // as effect dependencies they re-ran the preview on each keystroke, which
  // replaced a typed amount with the tier's price (0 for a free tier).
  const latest = useRef<{
    amount: string
    setAmount: (v: string) => void
    previewFailed: () => void
  } | null>(null)
  useEffect(() => {
    latest.current = {
      amount: singleForm.values.amount,
      setAmount: (v) => singleForm.setFieldValue('amount', v),
      previewFailed: () =>
        notify('error', t('finance.amountPreviewFailed', 'Betragsvorschau fehlgeschlagen')),
    }
  })

  // The tier's price fills the amount when the member, purpose or tier
  // changes; after that the amount is the user's to change.
  useEffect(() => {
    if (
      watchedRecipientType !== 'member' ||
      watchedPurpose !== 'membership' ||
      !watchedMemberId ||
      tierOptions.length === 0
    )
      return
    if (!memberTier) return
    const tier = tierOptions.find((tp) => tp.name === memberTier)
    if (!tier) return
    let cancelled = false
    // An amount typed while the preview loads wins over the preview.
    const typedBefore = latest.current?.amount
    const timer = setTimeout(() => {
      calculateTierCost({
        priceType: tier.priceType,
        billingCycle: tier.billingCycle,
        priceChf: tier.priceChf,
        percentageValue: tier.percentageValue,
        coefficient: tier.coefficient,
        roundTo: tier.roundTo,
        deductTierIds: tier.deductTierIds,
        tierId: parseInt(tier.id),
      })
        .then((r) => {
          // A free tier leaves the field empty to fill in, not at 0.
          if (cancelled || latest.current?.amount !== typedBefore) return
          latest.current?.setAmount(r.amount > 0 ? String(r.amount) : '')
        })
        .catch(() => {
          if (!cancelled) latest.current?.previewFailed()
        })
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [
    watchedRecipientType,
    watchedPurpose,
    watchedMemberId,
    tierOptions,
    memberTier,
  ])

  return (
    <div>
      <Group justify="flex-end" mb={16} className="page-actions">
        {canBulkCreate && (
          <Button
            variant="default"
            onClick={() => setPreviewOpen(true)}
            data-testid="fee-run-preview"
          >
            <IconCalendarDollar size={16} />
            {t('finance.feeRun.open', 'Vorschau Beitragslauf')}
          </Button>
        )}
        {canBulkCreate && (
          <Button variant="default" onClick={openBulk}>
            <IconPlus size={16} />
            {t('finance.bulk.create', 'Sammelrechnung')}
          </Button>
        )}
        {canCreate && (
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.issueInvoice', 'Rechnung ausstellen')}
          </Button>
        )}
      </Group>
      <DataTable
        breakpoint="xwide"
        columns={[
          {
            key: 'id',
            header: t('finance.invoice.numberShort', 'Nr.'),
            width: 1,
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {inv.id}
              </span>
            ),
          },
          {
            key: 'member',
            header: t('finance.recipient', 'Empfänger'),
            render: (inv) => (
              <div>
                <span style={{ fontWeight: 500 }}>{inv.member}</span>
                {inv.recipientType === 'external' && (
                  <span
                    style={{
                      display: 'block',
                      fontSize: 'var(--mantine-font-size-xs)',
                      color: 'var(--hb-text-3)',
                    }}
                  >
                    {t('finance.recipientType.external', 'Externe Partei')}
                  </span>
                )}
              </div>
            ),
          },
          {
            key: 'purpose',
            header: t('finance.purposeLabel', 'Zweck'),
            render: (inv) => (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: inv.purpose === 'membership' ? 'var(--mantine-color-acc-text)' : 'var(--hb-text-2)',
                }}
              >
                {inv.purpose === 'membership'
                  ? t('finance.purpose.membership', 'Mitgliedschaft')
                  : t('finance.purpose.other', 'Anderes')}
              </span>
            ),
          },
          {
            key: 'issued',
            header: t('finance.invoice.issued', 'Ausgestellt'),
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {inv.issued ? formatDate(inv.issued) : '—'}
              </span>
            ),
          },
          {
            key: 'due',
            header: t('finance.invoice.due', 'Fällig'),
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: inv.status === 'Overdue' ? 'var(--mantine-color-red-text)' : 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {inv.due ? formatDate(inv.due) : '—'}
              </span>
            ),
          },
          {
            key: 'amount',
            header: t('finance.amount', 'Betrag'),
            width: 110,
            render: (inv) => (
              <span className="num" style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                CHF {formatCHF(inv.amount)}
              </span>
            ),
          },
          {
            key: 'status',
            header: t('common.status', 'Status'),
            // Reserve room: a Mantine badge clips instead of wrapping when squeezed.
            width: 110,
            render: (inv) => <InvoicePill status={inv.status} />,
          },
          {
            key: 'actions',
            header: '',
            width: 1,
            render: (inv) => (
              <Group gap={4} wrap="nowrap" justify="flex-end">
                <Button size="sm" variant="subtle" onClick={() => goInvoice(inv)}>
                  {t('common.details', 'Details')}
                </Button>
                {inv.status !== 'Paid' && canUpdate && (
                  <Button
                    size="sm"
                    variant="filled"
                    onClick={() => markPaidMutation.mutate(inv.id)}
                    loading={markPaidMutation.isPending}
                  >
                    {t('finance.markPaid', 'Als bezahlt markieren')}
                  </Button>
                )}
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon
                      variant="subtle"
                      aria-label={t('common.moreActions', 'Weitere Aktionen')}
                      title={t('common.moreActions', 'Weitere Aktionen')}
                    >
                      <IconDots size={18} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    {canUpdate && inv.status !== 'Paid' && (
                      <Menu.Item
                        leftSection={<IconPencil size={16} />}
                        onClick={() => setEditTarget(inv)}
                      >
                        {t('common.edit', 'Bearbeiten')}
                      </Menu.Item>
                    )}
                    <Menu.Item
                      leftSection={<IconFileDownload size={16} />}
                      onClick={() => downloadInvoicePdf(inv.id)}
                    >
                      {t('finance.downloadQrBill', 'QR-Rechnung herunterladen')}
                    </Menu.Item>
                    {canRemind && inv.status !== 'Paid' && (
                      <Menu.Item
                        leftSection={<IconBell size={16} />}
                        onClick={() => sendReminderMutation.mutate(inv.id)}
                      >
                        {t('finance.sendReminder', 'Erinnerung senden')}
                      </Menu.Item>
                    )}
                    {canDelete && (
                      <Menu.Item
                        color="red"
                        leftSection={<IconTrash size={16} />}
                        onClick={() => setDeleteTargetId(inv.id)}
                      >
                        {t('common.delete', 'Löschen')}
                      </Menu.Item>
                    )}
                  </Menu.Dropdown>
                </Menu>
              </Group>
            ),
          },
        ]}
        data={pg.paged}
        emptyMessage={t('finance.noInvoices', 'Keine Rechnungen gefunden.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('finance.searchInvoices', 'Rechnungen suchen …')}
        filterGroups={[
          {
            key: 'status',
            label: t('common.status', 'Status'),
            value: statusFilter,
            defaultValue: 'All',
            options: [
              { value: 'All', label: t('common.all', 'Alle') },
              { value: 'Open', label: t('finance.invoiceFilter.open', 'Offen') },
              { value: 'Paid', label: t('finance.invoiceFilter.paid', 'Bezahlt') },
              { value: 'Overdue', label: t('finance.invoiceFilter.overdue', 'Überfällig') },
            ],
            onChange: setStatusFilter,
          },
          {
            key: 'purpose',
            label: t('finance.purposeLabel', 'Zweck'),
            value: purposeFilter,
            defaultValue: 'All',
            options: [
              { value: 'All', label: t('common.all', 'Alle') },
              { value: 'membership', label: t('finance.purpose.membership', 'Mitgliedschaft') },
              { value: 'other', label: t('finance.purpose.other', 'Anderes') },
            ],
            onChange: setPurposeFilter,
          },
        ]}
        page={pg.page}
        perPage={pg.perPage}
        total={pg.total}
        totalPages={pg.totalPages}
        onPageChange={pg.goPage}
        onPerPageChange={pg.setPerPage}
        getRowKey={(inv) => inv.id}
      />

      <ConfirmModal
        open={!!deleteTargetId}
        onClose={() => setDeleteTargetId(null)}
        title={t('finance.deleteInvoiceTitle', 'Rechnung {{id}} löschen?', {
          id: deleteTarget?.id ?? '',
        })}
        body={
          t('finance.deleteInvoiceBody', 'Die Rechnung wird endgültig gelöscht.') +
          (deleteTarget?.transactionId
            ? ' ' +
              t(
                'finance.linkedTransactionAlsoDeleted',
                'Die verknüpfte Buchung wird ebenfalls gelöscht.',
              )
            : '')
        }
        onConfirm={() => {
          if (deleteTargetId) {
            deleteInvoiceMutation.mutate(deleteTargetId)
          }
        }}
      />

      <FeeRunPreviewModal open={previewOpen} onClose={() => setPreviewOpen(false)} />
      <EditInvoiceModal invoice={editTarget} onClose={() => setEditTarget(null)} />
      <Modal
        onSubmit={bulkForm.onSubmit(handleBulk)}
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        wide
        title={t('finance.bulk.createTitle', 'Rechnungen für mehrere Mitglieder erstellen')}
        footer={
          <>
            <Button variant="default" onClick={() => setBulkOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              type="submit"
              disabled={bulkSaving}
            >
              {bulkSaving
                ? t('finance.creating', 'Wird erstellt …')
                : t('finance.createInvoices', 'Rechnungen erstellen')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
            <Field
              label={t('members.tier', 'Stufe')}
              hint={t(
                'finance.tierHint',
                'Leer lassen, um allen aktiven Mitgliedern eine Rechnung zu stellen',
              )}
            >
              <Select
                data={[
                  {
                    value: '',
                    label: t('finance.allActiveMembers', 'Alle aktiven Mitglieder'),
                  },
                  ...tierOptions.map((tierItem) => ({
                    value: tierItem.id,
                    label: `${tierItem.name}${
                      tierItem.priceChf != null
                        ? ` — CHF ${formatCHF(tierItem.priceChf)}`
                        : ` ${t('finance.noPrice', '(kein Preis)')}`
                    }`,
                  })),
                ]}
                searchable
                {...bulkForm.getInputProps('tierId')}
              />
            </Field>
            <Field label={t('finance.invoice.due', 'Fällig')}>
              <DateField {...bulkForm.getInputProps('due')} />
            </Field>
          </SimpleGrid>
          <Field
            label={t('common.description', 'Beschreibung')}
            hint={t(
              'finance.descriptionHint',
              'Optional, erscheint auf jeder Rechnung',
            )}
          >
            <TextInput
              placeholder={t(
                'common.descriptionPlaceholder',
                'Kurze Beschreibung …',
              )}
              {...bulkForm.getInputProps('description')}
            />
          </Field>
          <div
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              color: 'var(--hb-text-2)',
              background: 'var(--hb-surface-2)',
              borderRadius: 8,
              padding: '10px 14px',
            }}
          >
            {t(
              'finance.bulk.note',
              'Jedes Mitglied erhält eine Rechnung zum Preis seiner Stufe. Mitglieder ohne Preis in ihrer Stufe werden übersprungen.',
            )}
          </div>
        </div>
      </Modal>

      <Modal
        onSubmit={singleForm.onSubmit(handleCreate)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        wide
        title={t('finance.issueInvoice', 'Rechnung ausstellen')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              type="submit"
              disabled={saving}
            >
              {saving
                ? t('finance.creating', 'Wird erstellt …')
                : t('finance.createInvoice', 'Rechnung erstellen')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
            <Field label={t('finance.recipientTypeLabel', 'Empfängertyp')}>
              <Select
                data={[
                  {
                    value: 'member',
                    label: t('finance.recipientType.member', 'Mitglied'),
                  },
                  {
                    value: 'external',
                    label: t('finance.recipientType.external', 'Externe Partei'),
                  },
                ]}
                {...singleForm.getInputProps('recipientType')}
              />
            </Field>

            {watchedRecipientType === 'member' ? (
              <>
                <Field label={t('finance.recipientType.member', 'Mitglied')}>
                  <MemberPicker
                    {...singleForm.getInputProps('memberId')}
                    onChange={(id, m) => {
                      singleForm.setFieldValue('memberId', id ?? '')
                      setMemberTier(m?.tier ?? null)
                    }}
                  />
                </Field>
                <Field label={t('finance.purposeLabel', 'Zweck')}>
                  <Select
                    data={[
                      {
                        value: 'membership',
                        label: t('finance.purpose.membership', 'Mitgliedschaft'),
                      },
                      {
                        value: 'other',
                        label: t('finance.purpose.other', 'Anderes'),
                      },
                    ]}
                    {...singleForm.getInputProps('purpose')}
                  />
                </Field>
              </>
            ) : (
              <Field
                label={t('finance.recipientType.external', 'Externe Partei')}
                hint={
                  externalParties.length === 0
                    ? t(
                        'finance.externalParty.noneHint',
                        'Externe Parteien erfasst du im Tab «Extern».',
                      )
                    : undefined
                }
              >
                <Select
                  data={externalParties.map((p) => ({ value: p.id, label: p.name }))}
                  searchable
                  disabled={externalParties.length === 0}
                  placeholder={
                    externalParties.length === 0
                      ? t('finance.externalParty.none', 'Noch keine externen Parteien.')
                      : t('finance.externalParty.pick', 'Externe Partei wählen …')
                  }
                  {...singleForm.getInputProps('externalPartyId')}
                  value={singleForm.values.externalPartyId || null}
                />
              </Field>
            )}
          </SimpleGrid>

          <Field
            label={t('common.description', 'Beschreibung')}
            hint={t(
              'finance.descriptionOptionalHint',
              'Optional, z. B. Mitgliederbeitrag Oktober',
            )}
          >
            <TextInput
              placeholder={t(
                'common.descriptionPlaceholder',
                'Kurze Beschreibung …',
              )}
              {...singleForm.getInputProps('description')}
            />
          </Field>

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
            <Field
              label={t('finance.amount', 'Betrag') + ' (CHF)'}
              hint={
                watchedRecipientType === 'member' &&
                watchedPurpose === 'membership'
                  ? memberTier && watchedMemberId
                    ? t('finance.basedOnTier', 'Gemäss Stufe {{tier}}', {
                        tier: memberTier,
                      })
                    : undefined
                  : undefined
              }
            >
              <NumberInput
                min={0}
                decimalScale={2}
                thousandSeparator="’"
                hideControls
                placeholder="0.00"
                {...singleForm.getInputProps('amount')}
                // The form keeps the amount as text (empty: not entered).
                onChange={(v) => singleForm.setFieldValue('amount', v === '' ? '' : String(v))}
              />
            </Field>
            <Field label={t('finance.invoice.due', 'Fällig')}>
              <DateField {...singleForm.getInputProps('due')} />
            </Field>
          </SimpleGrid>

          {booksOn &&
            (watchedRecipientType === 'external' || watchedPurpose === 'other') && (
            <Field
              label={t('finance.categoryLabel', 'Kategorie')}
              hint={t(
                'finance.categoryHint',
                'Kategorie der verknüpften Buchung',
              )}
            >
              <Select
                data={txCategories.map((c) => ({ value: c.id, label: c.name }))}
                searchable
                placeholder={t('finance.selectCategory', 'Kategorie wählen …')}
                {...singleForm.getInputProps('categoryId')}
                value={singleForm.values.categoryId || null}
              />
            </Field>
          )}
        </div>
      </Modal>
    </div>
  )
}
