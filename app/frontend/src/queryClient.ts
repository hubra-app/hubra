import { QueryClient } from '@tanstack/react-query'

/** The app's one query cache, also for API helpers outside components. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: unknown) => {
        const status = (error as { status?: number })?.status
        if (status === 401 || status === 403) return false
        return failureCount < 2
      },
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})
