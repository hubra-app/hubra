import { useState, useCallback } from 'react'

/**
 * Paging for a list the API pages: ask the API for `page` and `perPage`,
 * then hand its `total` to `withTotal` for the <Pagination> props. A new
 * `resetKey` (search, filters) starts again on page 1.
 */
export function useServerPagination(resetKey: string, defaultPerPage = 25) {
  const [state, setState] = useState({ key: resetKey, page: 1 })
  const [perPage, setPerPageState] = useState(defaultPerPage)
  const page = state.key === resetKey ? state.page : 1

  const goPage = useCallback(
    (p: number) => setState({ key: resetKey, page: Math.max(1, p) }),
    [resetKey],
  )
  const setPerPage = useCallback(
    (n: number) => {
      setPerPageState(n)
      setState({ key: resetKey, page: 1 })
    },
    [resetKey],
  )
  const withTotal = (total: number) => ({
    page,
    perPage,
    goPage,
    setPerPage,
    total,
    totalPages: Math.max(1, Math.ceil(total / perPage)),
  })

  return { page, perPage, withTotal }
}
