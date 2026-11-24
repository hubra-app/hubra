import type { ReactNode } from 'react'
import { HubraProvider } from '@hubra/ui'
import { useLang } from '@/lang'

/** The Hubra theme, with the shared components in the language this portal is set to. */
export function Providers({ children }: { children: ReactNode }) {
  const { lang } = useLang()
  return <HubraProvider locale={lang}>{children}</HubraProvider>
}
