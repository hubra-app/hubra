import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@mantine/core/styles.css'
import '@mantine/dates/styles.css'
import '@mantine/notifications/styles.css'
import '@bitsandbricks/tokens/tokens.css'
import '@bitsandbricks/ui/styles.css'
import { BuildBadge } from '@hubra/ui'
// After the shared styles and before the app's own, so those win.
import '@hubra/ui/ui.css'
import './index.css'
import App from '@/App'
import { Providers } from '@/Providers'
import { AuthProvider } from '@/auth'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error: unknown) => {
        const status = (error as { status?: number })?.status
        if (status === 401 || status === 403 || status === 404) return false
        return failureCount < 2
      },
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <BuildBadge />
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </QueryClientProvider>
      </BrowserRouter>
    </Providers>
  </StrictMode>,
)
