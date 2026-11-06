import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { Anchor, Text, type MantineSize } from '@mantine/core'
import { getLegalLinks, type LegalLinks } from '@hubra/api-client'

/** Hubra's privacy policy, terms and imprint (platform settings legal.*); null until known. */
export function useLegalLinks(): LegalLinks | null {
  const [links, setLinks] = useState<LegalLinks | null>(null)
  useEffect(() => {
    let alive = true
    getLegalLinks().then((l) => alive && setLinks(l))
    return () => {
      alive = false
    }
  }, [])
  return links
}

export interface LegalLabels {
  privacy: string
  terms: string
  imprint: string
}

/** "Privacy policy · Terms of service · Imprint", for footers and menus. Links that aren't set are left out. */
export function LegalFooter({
  labels,
  size = 'xs',
  ta,
}: {
  labels: LegalLabels
  size?: MantineSize
  ta?: 'left' | 'center' | 'right'
}) {
  const links = useLegalLinks()
  if (!links) return null
  const items = [
    [links.privacyUrl, labels.privacy],
    [links.termsUrl, labels.terms],
    [links.imprintUrl, labels.imprint],
  ].filter((x): x is [string, string] => !!x[0])
  if (items.length === 0) return null
  return (
    <Text size={size} c="dimmed" ta={ta} data-testid="legal-links">
      {items.map(([href, label], i) => (
        <Fragment key={href}>
          {i > 0 && ' · '}
          <Anchor href={href} target="_blank" rel="noopener" size={size} c="dimmed">
            {label}
          </Anchor>
        </Fragment>
      ))}
    </Text>
  )
}

/**
 * "By … you accept the terms and the privacy policy", with both linked:
 * `render(terms, privacy)` places the two links in the sentence.
 */
export function LegalConsent({
  labels,
  render,
}: {
  labels: Pick<LegalLabels, 'privacy' | 'terms'>
  render: (terms: ReactNode, privacy: ReactNode) => ReactNode
}) {
  const links = useLegalLinks()
  if (!links?.termsUrl || !links.privacyUrl) return null
  const link = (href: string, label: string) => (
    <Anchor href={href} target="_blank" rel="noopener" size="xs" c="dimmed" td="underline">
      {label}
    </Anchor>
  )
  return (
    <Text size="xs" c="dimmed" data-testid="legal-consent">
      {render(link(links.termsUrl, labels.terms), link(links.privacyUrl, labels.privacy))}
    </Text>
  )
}
