import { useMemo, useState } from 'react'
import { Button, Paper } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { IconCoins, IconPencil, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { ConfirmModal, LoadingSpinner, MemberRoster, Tabs, Tag, type SlideOverMember } from '@/components/ui'
import {
  DetailBack,
  DetailEmpty,
  DetailFact,
  DetailHeader,
  DetailIcon,
  DetailNotFound,
  DetailRow,
  DetailSection,
  RecordActivity,
} from '@/components/detail'
import { calculateTierCost, deleteTier, listTiers } from '@/api/tiers'
import { listTierMembers, updateMember } from '@/api/members'
import { useMemberSearch } from '@/data/members'
import { qk } from '@/data/keys'
import { TierFormModal } from './TierFormModal'
import { costSummary } from './tierCost'

/* ── One membership tier, as its own page ─────── */
export function TierDetailScreen() {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canUpdate = hasPermission('tiers.tiers.update')
  const canDelete = hasPermission('tiers.tiers.delete')
  const canMove = hasPermission('members.members.update')
  const canSeeMembers = hasPermission('members.members.read')
  const canAudit = hasPermission('audit.audit.read')
  const [tab, setTab] = useState('members')
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: tiers, isLoading } = useQuery({ queryKey: qk.tiers.all, queryFn: () => listTiers() })
  const tier = tiers?.find((x) => x.id === id)
  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: qk.tiers.members(id ?? ''),
    queryFn: () => listTierMembers(id!),
    enabled: !!tier,
  })
  const { data: cost } = useQuery({
    queryKey: qk.tiers.costs([tier]),
    queryFn: () =>
      calculateTierCost({
        priceType: tier!.priceType,
        billingCycle: tier!.billingCycle,
        priceChf: tier!.priceChf,
        percentageValue: tier!.percentageValue,
        coefficient: tier!.coefficient,
        roundTo: tier!.roundTo,
        deductTierIds: tier!.deductTierIds,
        tierId: Number(tier!.id),
      }),
    enabled: !!tier,
  })
  const { data: searchData } = useMemberSearch(searchQuery, { enabled: searchQuery.length >= 2 })

  const roster: SlideOverMember[] = useMemo(
    () => members.map((m) => ({ id: m.id, name: m.name, email: m.email, avatarColor: m.avatarColor, tier: m.tier })),
    [members],
  )
  const searchResults = useMemo(() => {
    if (!searchData || searchQuery.length < 2) return undefined
    const inTier = new Set(members.map((m) => m.id))
    return searchData.members
      .filter((m) => !inTier.has(m.id))
      .map((m) => ({ id: m.id, name: m.name, email: m.email, avatarColor: m.avatarColor, tier: m.tier }))
  }, [searchData, members, searchQuery])

  const back = '/app/members/tiers'
  const backLabel = t('tiers.backToTiers', 'Zurück zu den Stufen')
  if (isLoading) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
  if (!tier) {
    return (
      <DetailNotFound back={back} backLabel={backLabel} message={t('tiers.notFound', 'Diese Stufe gibt es nicht (mehr).')} />
    )
  }

  const price =
    costSummary(t, cost) ??
    (tier.priceType === 'formula'
      ? t('tiers.type.formula', 'Formel')
      : tier.priceType === 'percentage'
        ? `${tier.percentageValue ?? '?'}%`
        : tier.priceChf != null
          ? `CHF ${tier.priceChf}`
          : t('tiers.noPrice', 'Kein Beitrag'))
  const deducts = (tiers ?? []).filter((x) => tier.deductTierIds.includes(Number(x.id)))

  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
      err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
    )
  const moveIn = (m: SlideOverMember) =>
    updateMember(m.id, { tierName: tier.name })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: qk.tiers.members(tier.id) })
        notify(
          'success',
          t('tiers.updated', 'Stufe aktualisiert'),
          t('tiers.memberMoved', '{{member}} ist jetzt in {{tier}}.', { member: m.name, tier: tier.name }),
        )
      })
      .catch(fail)
  const destroy = async () => {
    try {
      await deleteTier(tier.id)
      queryClient.invalidateQueries({ queryKey: qk.tiers.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      notify('info', t('tiers.deleted', 'Stufe gelöscht'), t('tiers.deletedMsg', '{{name}} wurde entfernt.', { name: tier.name }))
      go(back)
    } catch (err) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const tabs = [
    { id: 'members', label: t('tiers.members', 'Mitglieder') },
    ...(canAudit ? [{ id: 'activity', label: t('members.detail.activity') }] : []),
  ]

  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <DetailHeader
        media={<DetailIcon color={tier.color}>{tier.name[0]}</DetailIcon>}
        title={tier.name}
        badges={
          <>
            <Tag>{t(`tiers.type.${tier.priceType}`, tier.priceType)}</Tag>
            {tier.billingCycle && <Tag>{t(`tiers.cycle.${tier.billingCycle}`, tier.billingCycle)}</Tag>}
          </>
        }
        actions={
          <>
            {canUpdate && (
              <Button variant="default" leftSection={<IconPencil size={16} />} onClick={() => setEditOpen(true)}>
                {t('common.edit')}
              </Button>
            )}
            {canDelete && (
              <Button
                variant="default"
                leftSection={<IconTrash size={16} />}
                style={{ color: 'var(--mantine-color-red-text)' }}
                onClick={() => setDeleteOpen(true)}
              >
                {t('common.delete', 'Löschen')}
              </Button>
            )}
          </>
        }
        facts={
          <>
            <DetailFact label={t('tiers.price', 'Preis')}>
              <span className="num" data-testid="tier-price">
                {price}
              </span>
            </DetailFact>
            <DetailFact label={t('tiers.members', 'Mitglieder')}>
              <span className="num">{membersLoading ? '…' : members.length}</span>
            </DetailFact>
          </>
        }
      />

      <div className="detail-grid">
        <DetailSection icon={<IconCoins size={16} />} title={t('tiers.detail.pricing', 'Beitrag')}>
          <DetailRow label={t('tiers.form.priceType', 'Preisart')}>
            {t(`tiers.type.${tier.priceType}`, tier.priceType)}
          </DetailRow>
          <DetailRow label={t('tiers.form.billingCycle', 'Abrechnung')}>
            {tier.billingCycle ? t(`tiers.cycle.${tier.billingCycle}`, tier.billingCycle) : t('tiers.cycle.none', 'Keine (manuell)')}
          </DetailRow>
          {tier.priceType === 'fixed' && (
            <DetailRow label={t('tiers.form.price', 'Preis (CHF)')} mono>
              {tier.priceChf ?? <DetailEmpty />}
            </DetailRow>
          )}
          {tier.priceType === 'percentage' && (
            <DetailRow label={t('tiers.form.percentage', 'Prozentsatz (%)')} mono>
              {tier.percentageValue ?? <DetailEmpty />}
            </DetailRow>
          )}
          {tier.priceType === 'formula' && (
            <>
              <DetailRow label={t('tiers.form.coefficient', 'Koeffizient')} mono>
                {tier.coefficient ?? <DetailEmpty />}
              </DetailRow>
              <DetailRow label={t('tiers.form.roundTo', 'Runden auf')} mono>
                {tier.roundTo ?? <DetailEmpty />}
              </DetailRow>
              <DetailRow label={t('tiers.form.deduct', 'Beiträge abziehen von')}>
                {deducts.length ? deducts.map((d) => d.name).join(', ') : <DetailEmpty />}
              </DetailRow>
            </>
          )}
          <DetailRow label={t('tiers.price', 'Preis')} mono>
            {price}
          </DetailRow>
        </DetailSection>

        <Paper withBorder p={{ base: 16, sm: 20 }} pt={8}>
          {tabs.length > 1 && <Tabs tabs={tabs} activeTab={tab} onTabChange={setTab} />}
          {tab === 'members' && (
            <MemberRoster
              members={roster}
              loading={membersLoading}
              addLabel={t('tiers.moveMember', 'Mitglied in diese Stufe verschieben')}
              addPlaceholder={t('tiers.searchMembers', 'Mitglieder suchen …')}
              searchResults={canMove ? searchResults : undefined}
              onAdd={canMove ? moveIn : undefined}
              onAddSearch={canMove ? setSearchQuery : undefined}
              onOpen={canSeeMembers ? (m) => go(`/app/members/${m.id}`) : undefined}
              testId="tier-members"
            />
          )}
          {tab === 'activity' && <RecordActivity type="tier" id={tier.id} testId="tier-activity" />}
        </Paper>
      </div>

      {editOpen && <TierFormModal key={tier.id} target={tier} onClose={() => setEditOpen(false)} />}
      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t('tiers.deleteTitle', 'Stufe «{{name}}» löschen?', { name: tier.name })}
        body={t(
          'tiers.deleteBody',
          'Mitglieder in dieser Stufe müssen einer anderen Stufe zugewiesen werden. Das kann nicht rückgängig gemacht werden.',
        )}
        onConfirm={destroy}
      />
    </div>
  )
}
