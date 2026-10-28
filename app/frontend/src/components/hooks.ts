import { useState, useCallback, type KeyboardEvent } from 'react'

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
