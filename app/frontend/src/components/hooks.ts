import { useState, useCallback, useRef, type KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

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
 * Props that let a clickable row or card be reached with Tab and opened
 * with Enter or Space, like a button. Keys pressed inside a control in it
 * (a button, an input) are left to that control.
 */
export function clickableProps(onClick?: () => void) {
  if (!onClick) return {}
  return {
    onClick,
    tabIndex: 0,
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      if (e.target !== e.currentTarget) return
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onClick()
      }
    },
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

/**
 * A list page opened on one of its entries (``?event=3`` from a
 * notification): the linked id, and a function that drops it (and the
 * ``extra`` params that came with it) from the URL again.
 */
export function useLinkedId(param: string, extra: string[] = []) {
  const [params, setParams] = useSearchParams()
  const id = params.get(param)
  const clear = () =>
    setParams(
      (p) => {
        p.delete(param)
        for (const name of extra) p.delete(name)
        return p
      },
      { replace: true },
    )
  return { id, params, clear }
}
