import { useMemo } from "react";
import i18n from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";
import en from "./en/translation.json";
import deCH from "./de-CH/translation.json";
import {
  fetchTranslations,
  fetchLanguages,
  reportMissingKeys,
} from "@/api/i18n";

const STORAGE_KEY = "cms_language";

export const resources = {
  "en-GB": { translation: en },
  "de-CH": { translation: deCH },
} as const;

const KNOWN_LANGUAGES = ["de-CH", "en-GB"];

// The club's languages, asked once per page load (loading and key reports
// both need them).
let apiLanguages: Promise<string[]> | null = null;

function clubLanguages(): Promise<string[]> {
  apiLanguages ??= fetchLanguages()
    .then((locales) => (locales.length > 0 ? locales : KNOWN_LANGUAGES))
    .catch((err) => {
      apiLanguages = null;
      throw err;
    });
  return apiLanguages;
}

const savedLang = localStorage.getItem(STORAGE_KEY) ?? "de-CH";

i18n.use(initReactI18next).init({
  resources,
  lng: savedLang,
  fallbackLng: "en-GB",
  // React escapes rendered text, so i18next must not escape names a second time.
  interpolation: { escapeValue: false },
  returnNull: false,
  returnEmptyString: false,
});

// The API client reads the page language to translate error messages.
document.documentElement.lang = i18n.language;
i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

// ── Missing key tracking ──────────────────────────────────────────────────
const accessedKeys = new Map<string, string | undefined>();
let reportTimer: ReturnType<typeof setTimeout> | null = null;
const REPORT_DEBOUNCE_MS = 30_000;

function recordKey(key: string, defaultValue?: string) {
  if (!key) return;
  if (!accessedKeys.has(key) || (defaultValue && !accessedKeys.get(key))) {
    accessedKeys.set(key, defaultValue ?? accessedKeys.get(key));
  }
  if (!reportTimer) {
    reportTimer = setTimeout(flushAccessedKeys, REPORT_DEBOUNCE_MS);
  }
}

async function flushAccessedKeys() {
  if (reportTimer) {
    clearTimeout(reportTimer);
    reportTimer = null;
  }
  if (accessedKeys.size === 0) return;
  const keys = [...accessedKeys.entries()].map(([key, dv]) => ({
    key,
    default_value: dv ?? null,
  }));
  accessedKeys.clear();
  let locales = KNOWN_LANGUAGES;
  try {
    locales = await clubLanguages();
  } catch {
    // API unavailable — skip reporting
  }
  for (const locale of locales) {
    // Fire-and-forget — don't block the UI
    reportMissingKeys(locale, keys).catch(() => {});
  }
}

i18n.on("missingKey", (_lngs: string[], _ns: string, key: string) => {
  recordKey(key);
});

window.addEventListener("beforeunload", () => {
  flushAccessedKeys();
});

export async function loadAllTranslationsFromApi() {
  let locales = KNOWN_LANGUAGES;
  try {
    locales = await clubLanguages();
  } catch {
    // API unavailable — use static fallbacks only
  }
  await Promise.all(locales.map((loc) => loadTranslationsFromApi(loc)));
  // addResource is silent: re-render the screens that already showed keys.
  await i18n.changeLanguage(i18n.language);
  flushAccessedKeys();
}

export async function loadTranslationsFromApi(locale: string) {
  try {
    const data = await fetchTranslations(locale);
    // Parents before children: "a.b" after "a.b.c" would replace the
    // object that holds "a.b.c" with a string.
    for (const [key, value] of Object.entries(data).sort(([a], [b]) => (a < b ? -1 : 1))) {
      i18n.addResource(locale, "translation", key, value, { silent: true });
    }
  } catch {
    // API unavailable — keep static fallback
  }
}

export function setLanguage(lang: string) {
  flushAccessedKeys();
  localStorage.setItem(STORAGE_KEY, lang);
  i18n.changeLanguage(lang);
}

export function getCurrentLanguage(): string {
  return i18n.language;
}

export function useT() {
  const { t, i18n: i18nInstance, ready } = useTranslation();
  const wrappedT = useMemo(
    () =>
      ((...args: Parameters<typeof t>) => {
        const key =
          typeof args[0] === "string" ? args[0] : (args[0] as string[])?.[0];
        let defaultValue: string | undefined;
        if (args.length >= 2 && typeof args[1] === "string") {
          defaultValue = args[1];
        } else if (
          args.length >= 2 &&
          typeof args[1] === "object" &&
          args[1] !== null &&
          "defaultValue" in args[1]
        ) {
          const dv = (args[1] as { defaultValue?: unknown }).defaultValue;
          if (typeof dv === "string") defaultValue = dv;
        }
        if (key) recordKey(key, defaultValue);
        return t(...args);
      }) as typeof t,
    [t],
  );
  return { t: wrappedT, i18n: i18nInstance, ready };
}

/** A zod error message that is translated when validation runs. */
export function zmsg(key: string, defaultValue: string) {
  return { error: () => i18n.t(key, defaultValue) };
}

export default i18n;
