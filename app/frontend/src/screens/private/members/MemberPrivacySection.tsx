import { useQuery } from '@tanstack/react-query'
import { IconShieldLock } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { formatDate } from '@/format'
import { qk } from '@/data/keys'
import { getMemberConsents } from '@/api/members'
import { DetailRow, DetailSection as Section } from '@/components/detail'

/** The member's consents (photos, directory) and when they last changed them. */
export function MemberPrivacySection({ memberId }: { memberId: string }) {
  const { t } = useT()
  const { data } = useQuery({
    queryKey: qk.members.consents(memberId),
    queryFn: () => getMemberConsents(memberId),
  })
  if (!data) return null

  const directory: Record<string, string> = {
    email: t('account.directory.email', 'E-Mail'),
    phone: t('account.directory.phone', 'Telefon und Mobile'),
    address: t('account.directory.address', 'Adresse'),
    birthday: t('account.directory.birthday', 'Geburtstag'),
  }
  const photos =
    data.photo_consent === null
      ? t('members.detail.privacy.notAsked', 'Nicht gewählt')
      : data.photo_consent
        ? t('common.yes', 'Ja')
        : t('common.no', 'Nein')
  const last = data.log[0]

  return (
    <Section icon={<IconShieldLock size={16} />} title={t('account.privacy.title', 'Datenschutz')}>
      <DetailRow label={t('members.detail.privacy.photos', 'Fotos zeigen')}>{photos}</DetailRow>
      <DetailRow label={t('members.detail.privacy.directory', 'Im Verzeichnis')}>
        {data.directory_shared.length
          ? data.directory_shared.map((c) => directory[c] ?? c).join(', ')
          : t('members.detail.privacy.nothing', 'Nichts')}
      </DetailRow>
      {last && (
        <DetailRow label={t('members.detail.privacy.changedLabel', 'Zuletzt geändert')}>
          {formatDate(last.at)}
        </DetailRow>
      )}
    </Section>
  )
}
