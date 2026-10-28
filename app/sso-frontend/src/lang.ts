import { useSyncExternalStore } from 'react'

/** The sign-in portal speaks German first, English second. */
export type Lang = 'de' | 'en'

const STORAGE_KEY = 'hubra_sso_language'
const listeners = new Set<() => void>()

function read(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'de'
  } catch {
    return 'de'
  }
}

let current: Lang = read()
document.documentElement.lang = current

export function setLang(lang: Lang) {
  current = lang
  document.documentElement.lang = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* private mode: keep the choice for this visit only */
  }
  listeners.forEach((fn) => fn())
}

export function getLang(): Lang {
  return current
}

/** Picks the German or English text for the current language. */
export function tr(de: string, en: string): string {
  return current === 'en' ? en : de
}

/** Re-renders the caller when the language changes. */
export function useLang() {
  const lang = useSyncExternalStore(
    (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    () => current,
  )
  return { lang, setLang, tr }
}
