import { useState, useCallback, useRef } from 'react'

export function usePagination<T>(items: T[], defaultPerPage = 10) {
  const [page, setPage] = useState(1)
  const [perPage, setPerPageState] = useState(defaultPerPage)

  const totalPages = Math.max(1, Math.ceil(items.length / perPage))
  const safePage = Math.min(page, totalPages)
  const paged = items.slice((safePage - 1) * perPage, safePage * perPage)

  const goPage = useCallback(
    (p: number) => setPage(Math.max(1, Math.min(p, totalPages))),
    [totalPages],
  )
  const setPerPage = useCallback((n: number) => {
    setPerPageState(n)
    setPage(1)
  }, [])

  return {
    page: safePage,
    perPage,
    goPage,
    setPerPage,
    paged,
    totalPages,
    total: items.length,
  }
}

/**
 * Wrap an async submit so a second click while it runs does nothing.
 * Returns the guarded function and whether it is running (for `loading`).
 */
export function useSubmitOnce<A extends unknown[]>(
  fn: (...args: A) => Promise<unknown>,
) {
  const [pending, setPending] = useState(false)
  const busy = useRef(false)
  const run = useCallback(
    async (...args: A) => {
      if (busy.current) return
      busy.current = true
      setPending(true)
      try {
        await fn(...args)
      } finally {
        busy.current = false
        setPending(false)
      }
    },
    [fn],
  )
  return [run, pending] as const
}
