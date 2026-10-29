import { useSyncExternalStore } from 'react'

/** Manage and sign-in speak German first, English second. */
export type Lang = 'de' | 'en'

/**
 * A language store for an app that keeps its texts inline as tr(de, en).
 * The choice is kept in localStorage under `storageKey`.
 */
export function createLang(storageKey: string) {
  const listeners = new Set<() => void>()

  function read(): Lang {
    try {
      return localStorage.getItem(storageKey) === 'en' ? 'en' : 'de'
    } catch {
      return 'de'
    }
  }

  let current: Lang = read()
  document.documentElement.lang = current

  function setLang(lang: Lang) {
    current = lang
    document.documentElement.lang = lang
    try {
      localStorage.setItem(storageKey, lang)
    } catch {
      /* private mode: keep the choice for this visit only */
    }
    listeners.forEach((fn) => fn())
  }

  function getLang(): Lang {
    return current
  }

  /** Picks the German or English text for the current language. */
  function tr(de: string, en: string): string {
    return current === 'en' ? en : de
  }

  const subscribe = (fn: () => void) => {
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }

  /** Re-renders the caller when the language changes. */
  function useLang() {
    const lang = useSyncExternalStore(subscribe, () => current)
    return { lang, setLang, tr }
  }

  return { setLang, getLang, tr, useLang }
}
