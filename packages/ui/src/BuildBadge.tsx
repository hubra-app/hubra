import { useEffect, useState } from 'react'

const REPO_URL = 'https://github.com/hubra-app/hubra'

/**
 * The commit this app was built from, small and faint in the lower right
 * corner (where notifications appear, under them). Read from /version.json,
 * which the image build writes; links to the commit on GitHub. A build
 * without a commit shows "dev"; without the file (the dev server) nothing.
 * Hidden on phones and in print (ui.css), where it would only be in the way.
 */
export function BuildBadge() {
  const [sha, setSha] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    fetch('/version.json', { cache: 'no-store', credentials: 'omit' })
      .then(async (res) => {
        if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) return undefined
        const data = (await res.json()) as { commit?: unknown }
        return typeof data.commit === 'string' && data.commit ? data.commit : null
      })
      .catch(() => undefined)
      .then((value) => {
        if (!cancelled) setSha(value)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (sha === undefined) return null
  if (sha === null) {
    return (
      <span className="hubra-build" title="Build: dev">
        dev
      </span>
    )
  }
  return (
    <a
      className="hubra-build"
      href={`${REPO_URL}/commit/${sha}`}
      target="_blank"
      rel="noreferrer"
      title={`Build ${sha}`}
    >
      {sha.slice(0, 7)}
    </a>
  )
}
