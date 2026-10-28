import { useState, useEffect, useMemo } from 'react'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { Button, Group, Select, TextInput } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus } from '@tabler/icons-react'
import { useToast, useData, useNav, useAuth } from '@/context/AppContext'
import {
  Modal,
  Field,
  InvoicePill,
  usePagination,
  ConfirmModal,
  DataTable,
  ActionButtons,
} from '@/components/ui'
import {
  createInvoice,
  createBulkInvoices,
  downloadInvoicePdf,
  listExternalParties,
  listTxCategories,
} from '@/api/finance'
import { listMembers } from '@/api/members'
import { listTiers, calculateTierCost } from '@/api/tiers'
import { formatCHF } from '@/format'
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
    due: z.string().min(1, 'Due date is required'),
    description: z.string(),
    categoryId: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.recipientType === 'member' && !data.memberId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['memberId'],
        message: 'Member is required',
      })
    }
    if (data.recipientType === 'external' && !data.externalPartyId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['externalPartyId'],
        message: 'External party is required',
      })
    }
    if (!data.amount) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['amount'],
        message: 'Amount is required',
      })
    }
    if (
      (data.recipientType === 'external' || data.purpose === 'other') &&
      !data.categoryId
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['categoryId'],
        message: 'Category is required',
      })
    }
  })
type SingleForm = z.infer<typeof singleSchema>

const bulkSchema = z.object({
  tierId: z.string(),
  due: z.string().min(1, 'Due date is required'),
  description: z.string(),
})
type BulkForm = z.infer<typeof bulkSchema>

export function InvoicesTab() {
  const { notify } = useToast()
  const { invoices, setInvoices } = useData()
  const { goInvoice } = useNav()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const markPaidMutation = useMarkInvoicePaid()
  const sendReminderMutation = useSendInvoiceReminder()
  const deleteInvoiceMutation = useDeleteInvoice()
  const canCreate = hasPermission('invoices.invoices.create')
  const canBulkCreate = hasPermission('invoices.invoices.bulk_create')
  const canUpdate = hasPermission('invoices.invoices.update')
  const canDelete = hasPermission('invoices.invoices.delete')
  const canRemind = hasPermission('invoices.invoices.remind')
  const [addOpen, setAddOpen] = useState(false)
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [purposeFilter, setPurposeFilter] = useState('All')

  const singleForm = useForm<SingleForm>({
    validate: zodResolver(singleSchema),
    initialValues: {
      recipientType: 'member',
      purpose: 'membership',
      memberId: '',
      externalPartyId: '',
      amount: '',
      due: '',
      description: '',
      categoryId: '',
    },
  })
  const bulkForm = useForm<BulkForm>({
    validate: zodResolver(bulkSchema),
    initialValues: { tierId: '', due: '', description: '' },
  })
  const { data: membersData } = useQuery({
    queryKey: ['members'],
    queryFn: () => listMembers({ pageSize: 500 }),
  })
  const memberOptions = useMemo(
    () =>
      (membersData?.members ?? []).map((m) => ({
        id: m.id,
        name: m.name,
        tierName: m.tier,
      })),
    [membersData],
  )
  const { data: tierOptions = [] } = useQuery({
    queryKey: ['tiers'],
    queryFn: () => listTiers(),
    enabled: addOpen || bulkOpen,
  })
  const { data: externalParties = [] } = useQuery({
    queryKey: ['external-parties'],
    queryFn: () => listExternalParties(),
    enabled: addOpen,
  })
  const { data: txCategories = [] } = useQuery({
    queryKey: ['transaction-categories'],
    queryFn: () => listTxCategories(),
    enabled: addOpen,
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
      setInvoices((prev) => [...result.invoices, ...prev])
      setBulkOpen(false)
      notify(
        'success',
        t('finance.invoicesCreated', 'R?chnige erstellt'),
        t(
          'finance.invoicesCreatedMsg',
          `${result.created} invoice${result.created !== 1 ? 's' : ''} issued.`,
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekanni Fehler'),
      )
    } finally {
      setBulkSaving(false)
    }
  }

  const openAdd = () => {
    singleForm.initialize({
      recipientType: 'member',
      purpose: 'membership',
      memberId: memberOptions[0]?.id ?? '',
      externalPartyId: externalParties[0]?.id ?? '',
      amount: '',
      due: '',
      description: '',
      categoryId: '',
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
      setInvoices((prev) => [inv, ...prev])
      setAddOpen(false)
      notify(
        'success',
        t('finance.invoice.created', 'R?chnig erstellt'),
        t('finance.invoice.createdMsg', 'Neui R?chnig isch usgstellt worde.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekanni Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    if (
      watchedRecipientType !== 'member' ||
      watchedPurpose !== 'membership' ||
      !watchedMemberId ||
      tierOptions.length === 0
    )
      return
    const m = memberOptions.find((o) => o.id === watchedMemberId)
    if (!m) return
    const tier = tierOptions.find((tp) => tp.name === m.tierName)
    if (!tier) return
    let cancelled = false
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
          if (!cancelled) singleForm.setFieldValue('amount', String(r.amount))
        })
        .catch(() => {
          if (!cancelled)
            notify(
              'error',
              t(
                'finance.amountPreviewFailed',
                'Betrag-Vorschau fehlgeschlagen',
              ),
            )
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
    memberOptions,
    singleForm,
    notify,
    t,
  ])

  return (
    <div>
      <Group justify="flex-end" mb={16}>
        {canBulkCreate && (
          <Button variant="default" onClick={openBulk}>
            <IconPlus size={16} />
            {t('finance.bulk.create', 'Massenerstellig')}
          </Button>
        )}
        {canCreate && (
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.issueInvoice', 'Neui Rächnig')}
          </Button>
        )}
      </Group>
      <DataTable
        breakpoint="xwide"
        columns={[
          {
            key: 'id',
            header: t('finance.invoice.number', 'R�chnigs-Nr.'),
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: '#6b7480',
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
                      color: '#99a2ac',
                    }}
                  >
                    {t('finance.recipientType.external', 'Extern')}
                  </span>
                )}
              </div>
            ),
          },
          {
            key: 'purpose',
            header: t('finance.purpose', 'Zweck'),
            render: (inv) => (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: inv.purpose === 'membership' ? '#2596be' : '#6b7480',
                }}
              >
                {inv.purpose === 'membership'
                  ? t('finance.purpose.membership', 'Mitgliedschaft')
                  : t('finance.purpose.other', 'Anderers')}
              </span>
            ),
          },
          {
            key: 'issued',
            header: t('finance.invoice.issued', 'Usgstellt'),
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: '#6b7480',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {inv.issued}
              </span>
            ),
          },
          {
            key: 'due',
            header: t('finance.invoice.due', 'F�llig'),
            render: (inv) => (
              <span
                className="num"
                style={{
                  color: inv.status === 'Overdue' ? '#ff4d3d' : '#6b7480',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {inv.due}
              </span>
            ),
          },
          {
            key: 'amount',
            header: t('finance.amount', 'Betrag'),
            render: (inv) => (
              <span className="num" style={{ fontWeight: 700 }}>
                CHF {formatCHF(inv.amount)}
              </span>
            ),
          },
          {
            key: 'status',
            header: t('common.status', 'Status'),
            render: (inv) => <InvoicePill status={inv.status} />,
          },
          {
            key: 'actions',
            header: '',
            width: 280,
            render: (inv) => (
              <ActionButtons
                extra={
                  <>
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => goInvoice(inv)}
                    >
                      {t('common.details', 'Details')}
                    </Button>
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => downloadInvoicePdf(inv.id)}
                    >
                      {t('finance.downloadQrBill', 'QR-Rächnig')}
                    </Button>
                    {canRemind && (
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => sendReminderMutation.mutate(inv.id)}
                      >
                        {t('finance.sendReminder', 'Erinnerig')}
                      </Button>
                    )}
                    {inv.status !== 'Paid' && canUpdate && (
                      <Button
                        size="sm"
                        variant="filled"
                        onClick={() => markPaidMutation.mutate(inv.id)}
                      >
                        {t('finance.markPaid', 'Als bezahlt')}
                      </Button>
                    )}
                  </>
                }
                onDelete={
                  canDelete ? () => setDeleteTargetId(inv.id) : undefined
                }
              />
            ),
          },
        ]}
        data={pg.paged}
        emptyMessage={t('finance.noInvoices', 'Cheni R�chnige.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('finance.searchInvoices', 'Sueche?')}
        filters={[
          {
            label: t('common.all', 'All'),
            value: 'all',
            active: statusFilter === 'All',
            onClick: () => setStatusFilter('All'),
          },
          {
            label: 'Open',
            value: 'open',
            active: statusFilter === 'Open',
            onClick: () => setStatusFilter('Open'),
          },
          {
            label: 'Paid',
            value: 'paid',
            active: statusFilter === 'Paid',
            onClick: () => setStatusFilter('Paid'),
          },
          {
            label: 'Overdue',
            value: 'overdue',
            active: statusFilter === 'Overdue',
            onClick: () => setStatusFilter('Overdue'),
          },
          {
            label: t('finance.purpose.membership', 'Mitgliedschaft'),
            value: 'purpose-membership',
            active: purposeFilter === 'membership',
            onClick: () =>
              setPurposeFilter(
                purposeFilter === 'membership' ? 'All' : 'membership',
              ),
          },
          {
            label: t('finance.purpose.other', 'Anderers'),
            value: 'purpose-other',
            active: purposeFilter === 'other',
            onClick: () =>
              setPurposeFilter(purposeFilter === 'other' ? 'All' : 'other'),
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
        title={t('finance.deleteInvoiceTitle', 'R?chnig {{id}} l?sche?', {
          id: deleteTarget?.id ?? '',
        })}
        body={t(
          'finance.deleteInvoiceBody',
          `Die R?chnig wirde permanent entfernt.${
            deleteTarget?.transactionId
              ? t(
                  'finance.linkedTransactionAlsoDeleted',
                  ' Di verlinkti Transaktion wird au gl?scht.',
                )
              : ''
          }`,
        )}
        onConfirm={() => {
          if (deleteTargetId) {
            deleteInvoiceMutation.mutate(deleteTargetId)
            notify(
              'info',
              t('finance.invoice.deleted', 'R?chnig gl?scht'),
              t('finance.invoice.deletedMsg', 'R?chnig isch entfernt worde.'),
            )
          }
        }}
      />

      <Modal
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        title={t('finance.bulk.createTitle', 'Massenerstellig vo R?chnige')}
        footer={
          <>
            <Button variant="default" onClick={() => setBulkOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={() => bulkForm.onSubmit(handleBulk)()}
              disabled={bulkSaving}
            >
              {bulkSaving
                ? t('finance.creating', 'Wird erstellt…')
                : t('finance.createInvoices', 'R?chnige erstelle')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field
            label={t('members.tier', 'Stufe')}
            hint={t(
              'finance.tierHint',
              "Leer lasse f?r alli aktive Mitglider R?chnige z'erstelle",
            )}
          >
            <Select
              data={[
                {
                  value: '',
                  label: t('finance.allActiveMembers', 'Alli aktive Mitglider'),
                },
                ...tierOptions.map((tierItem) => ({
                  value: tierItem.id,
                  label: `${tierItem.name}${
                    tierItem.priceChf != null
                      ? ` — CHF ${formatCHF(tierItem.priceChf)}`
                      : ` ${t('finance.noPrice', ' (kei Preis)')}`
                  }`,
                })),
              ]}
              searchable
              {...bulkForm.getInputProps('tierId')}
            />
          </Field>
          <Field
            label={t('common.description', 'Beschribig')}
            hint={t(
              'finance.descriptionHint',
              'Optional ? wird uf jeder R?chnig azeigt',
            )}
          >
            <TextInput
              placeholder={t(
                'common.descriptionPlaceholder',
                'Monatlichi Mitgliedschaft',
              )}
              {...bulkForm.getInputProps('description')}
            />
          </Field>
          <Field label={t('finance.invoice.due', 'F?lligkeitsdatum')}>
            <TextInput type="date" {...bulkForm.getInputProps('due')} />
          </Field>
          <div
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              color: '#6b7480',
              background: '#f4f8f5',
              borderRadius: 8,
              padding: '10px 14px',
            }}
          >
            {t(
              'finance.bulk.note',
              'Pro Mitglid wird e R?chnig mit sym Stufepreis erstellt. Mitglider ohni Preis in ihrer Stufe werde ?bersprunge.',
            )}
          </div>
        </div>
      </Modal>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.issueInvoice', 'Neui R?chnig')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={() => singleForm.onSubmit(handleCreate)()}
              disabled={saving}
            >
              {saving
                ? t('finance.creating', 'Wird erstellt…')
                : t('finance.createInvoice', 'R?chnig erstelle')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('finance.recipientType', 'Empfänger-Typ')}>
            <Select
              data={[
                {
                  value: 'member',
                  label: t('finance.recipientType.member', 'Mitglid'),
                },
                {
                  value: 'external',
                  label: t('finance.recipientType.external', 'Externi Partei'),
                },
              ]}
              {...singleForm.getInputProps('recipientType')}
            />
          </Field>

          {watchedRecipientType === 'member' ? (
            <>
              <Field label={t('finance.recipientType.member', 'Mitglid')}>
                <Select
                  data={
                    memberOptions.length === 0
                      ? [
                          {
                            value: '',
                            label: t(
                              'finance.loadingMembers',
                              'Mitglider werde glade…',
                            ),
                          },
                        ]
                      : memberOptions.map((m) => ({
                          value: m.id,
                          label: m.name,
                        }))
                  }
                  searchable
                  {...singleForm.getInputProps('memberId')}
                />
              </Field>
              <Field label={t('finance.purpose', 'Zweck')}>
                <Select
                  data={[
                    {
                      value: 'membership',
                      label: t('finance.purpose.membership', 'Mitgliedschaft'),
                    },
                    {
                      value: 'other',
                      label: t('finance.purpose.other', 'Anderers'),
                    },
                  ]}
                  {...singleForm.getInputProps('purpose')}
                />
              </Field>
            </>
          ) : (
            <Field
              label={t('finance.recipientType.external', 'Externi Partei')}
              hint={
                externalParties.length === 0
                  ? t(
                      'finance.externalParty.noneHint',
                      'Erstellig externi Parteie im Tab "Externi".',
                    )
                  : undefined
              }
            >
              <Select
                data={
                  externalParties.length === 0
                    ? [
                        {
                          value: '',
                          label: t(
                            'finance.externalParty.none',
                            'No cheni externi Parteie.',
                          ),
                        },
                      ]
                    : externalParties.map((p) => ({
                        value: p.id,
                        label: p.name,
                      }))
                }
                searchable
                {...singleForm.getInputProps('externalPartyId')}
              />
            </Field>
          )}

          <Field
            label={t('common.description', 'Beschribig')}
            hint={t(
              'finance.descriptionOptionalHint',
              'Optional ? z.B. Monatlichi Mitgliedschaft',
            )}
          >
            <TextInput
              placeholder={t(
                'common.descriptionPlaceholder',
                'Monatlichi Mitgliedschaft',
              )}
              {...singleForm.getInputProps('description')}
            />
          </Field>

          <div
            className="grid-2"
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
          >
            <Field
              label={t('finance.amount', 'Betrag') + ' (CHF)'}
              hint={
                watchedRecipientType === 'member' &&
                watchedPurpose === 'membership'
                  ? (() => {
                      const m = memberOptions.find(
                        (o) => o.id === watchedMemberId,
                      )
                      if (!m) return undefined
                      return t(
                        'finance.basedOnTier',
                        `Basierend uf ${m.tierName} Stuf`,
                      )
                    })()
                  : undefined
              }
            >
              <TextInput
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                {...singleForm.getInputProps('amount')}
              />
            </Field>
            <Field label={t('finance.invoice.due', 'F?lligkeitsdatum')}>
              <TextInput type="date" {...singleForm.getInputProps('due')} />
            </Field>
          </div>

          {(watchedRecipientType === 'external' ||
            watchedPurpose === 'other') && (
            <Field
              label={t('finance.category', 'Kategorie')}
              hint={t(
                'finance.categoryHint',
                'Kategorie für di verlinkti Transaktion',
              )}
            >
              <Select
                data={[
                  {
                    value: '',
                    label: t('finance.selectCategory', 'Kategorie wähle…'),
                  },
                  ...txCategories.map((c) => ({
                    value: c.id,
                    label: c.name,
                  })),
                ]}
                {...singleForm.getInputProps('categoryId')}
              />
            </Field>
          )}
        </div>
      </Modal>
    </div>
  )
}
