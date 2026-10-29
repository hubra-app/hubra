import { useMemo, useState } from 'react'
import { Select, type SelectProps } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { getMember } from '@/api/members'
import { qk } from '@/data/keys'
import { useMemberSearch } from '@/data/members'
import { useT } from '@/locales/i18n'
import type { Member } from '@/types'

export interface MemberPickerProps extends Omit<
  SelectProps,
  'data' | 'value' | 'onChange' | 'searchable' | 'filter'
> {
  /** The chosen member's id, or null / '' for none. */
  value?: string | number | null
  onChange: (id: string | null, member: Member | null) => void
  /** Ids that can't be picked, e.g. the member themself. */
  exclude?: string[]
  /** Shown as the first option, meaning "nobody". */
  noneLabel?: string
}

/** A searchable member select that asks the server as you type. */
export function MemberPicker({ value, onChange, exclude, noneLabel, ...rest }: MemberPickerProps) {
  const { t } = useT()
  const id = value == null || value === '' ? null : String(value)
  const [search, setSearch] = useState('')
  const [picked, setPicked] = useState<Member | null>(null)
  // Once a member is chosen the box shows their name: list everyone again
  // instead of searching for that name.
  const { data, isFetching } = useMemberSearch(picked && search === picked.name ? '' : search)
  // The chosen member may not be on the current page of results.
  const { data: current } = useQuery({
    queryKey: qk.members.one(id ?? ''),
    queryFn: () => getMember(id!),
    enabled: id !== null && picked?.id !== id && !data?.members.some((m) => m.id === id),
    staleTime: 60_000,
  })

  const members = useMemo(() => {
    const list = (data?.members ?? []).filter((m) => !exclude?.includes(m.id))
    const chosen = picked?.id === id ? picked : current
    if (chosen && chosen.id === id && !list.some((m) => m.id === id)) list.unshift(chosen)
    return list
  }, [data, exclude, picked, current, id])

  const options = [
    ...(noneLabel ? [{ value: '', label: noneLabel }] : []),
    ...members.map((m) => ({ value: m.id, label: m.name })),
  ]

  return (
    <Select
      {...rest}
      searchable
      // The server already filtered by what was typed.
      filter={({ options }) => options}
      data={options}
      value={id ?? (noneLabel ? '' : null)}
      onChange={(v) => {
        const m = members.find((x) => x.id === v) ?? null
        setPicked(m)
        onChange(v || null, m)
      }}
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage={
        isFetching
          ? t('common.loading', 'Wird geladen …')
          : t('common.noResults', 'Keine Ergebnisse.')
      }
    />
  )
}
