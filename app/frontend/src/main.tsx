import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/tiptap/styles.css'
import { theme } from '@/theme/theme'
import './index.css'
import './locales/i18n'
import App from '@/App.tsx'
import { ROUTER_BASENAME } from '@/clubBase'
import { queryClient } from '@/queryClient'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <Notifications position="bottom-right" />
      <BrowserRouter basename={ROUTER_BASENAME}>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </BrowserRouter>
    </MantineProvider>
  </StrictMode>,
)
