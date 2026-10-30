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

// i18next keeps working on the objects above, so the API texts end up in
// them; this copy stays as shipped.
const BUILT_IN: Record<string, unknown> = JSON.parse(
  JSON.stringify({ "en-GB": en, "de-CH": deCH }),
);

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
// Keys the API has a value for, per locale; only the others are missing.
const apiKeys = new Map<string, Set<string>>();
// The report also marks keys as used (the stale flag on the translations
// page, 30 days by default), so every used key goes out once a day. In
// between, only keys this browser has not reported yet since then.
const REPORTED_KEY = "cms_i18n_reported";
const FULL_REPORT_MS = 24 * 60 * 60 * 1000;
// Off for a day once the API says no (members without i18n write
// permission).
const DENIED_KEY = "cms_i18n_report_denied";

function reportingDenied(): boolean {
  try {
    return Date.now() - Number(localStorage.getItem(DENIED_KEY)) < FULL_REPORT_MS;
  } catch {
    return false;
  }
}

interface Reported {
  at: number;
  keys: string[];
}

function loadReported(locale: string): Reported | null {
  try {
    const raw = localStorage.getItem(`${REPORTED_KEY}:${locale}`);
    const rec = raw ? (JSON.parse(raw) as Reported) : null;
    if (!rec || !Array.isArray(rec.keys) || Date.now() - rec.at > FULL_REPORT_MS) return null;
    return rec;
  } catch {
    return null;
  }
}

function saveReported(locale: string, rec: Reported) {
  try {
    localStorage.setItem(`${REPORTED_KEY}:${locale}`, JSON.stringify(rec));
  } catch {
    // Storage blocked: report again next time
  }
}

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
  if (reportingDenied()) {
    accessedKeys.clear();
    return;
  }
  const keys = [...accessedKeys.entries()].map(([key, dv]) => ({
    key,
    default_value: dv ?? null,
  }));
  accessedKeys.clear();
  let locales: string[];
  try {
    locales = await clubLanguages();
  } catch {
    // API unavailable — skip reporting
    return;
  }
  for (const locale of locales) {
    const known = apiKeys.get(locale);
    // Translations not loaded: nothing to compare against.
    if (!known) continue;
    const reported = loadReported(locale);
    const done = new Set(reported?.keys);
    const batch = reported
      ? keys.filter((k) => !known.has(k.key) && !done.has(k.key))
      : keys;
    if (batch.length === 0) continue;
    // Remember only the missing ones: the others are filtered by `known`.
    // Saved before sending: a report on page unload never sees its answer.
    const sent = batch.map((k) => k.key).filter((key) => !known.has(key));
    saveReported(
      locale,
      reported ? { at: reported.at, keys: [...done, ...sent] } : { at: Date.now(), keys: sent },
    );
    // Fire-and-forget — don't block the UI
    reportMissingKeys(locale, batch).catch((err: { status?: number }) => {
      if (err?.status !== 403) return;
      try {
        localStorage.setItem(DENIED_KEY, String(Date.now()));
      } catch {
        // Storage blocked: ask again next time
      }
    });
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

/** The built-in text at a dotted key: a string, an object of texts, or undefined. */
function builtIn(locale: string, key: string): unknown {
  let node: unknown = BUILT_IN[locale];
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return node;
}

/**
 * Whether a text from the API may go over the built-in ones. A row whose text
 * is its own key would show that key, and a row that clashes with the
 * built-in tree would hide a whole group of texts: "a.b" over the object
 * "a.b.*" drops every child, and "a.b.c" under the text "a.b" drops "a.b".
 * Old databases still hold such rows from earlier releases.
 */
function usableApiText(locale: string, key: string, value: unknown): boolean {
  if (typeof value !== "string" || !value.trim() || value.trim() === key) return false;
  if (typeof builtIn(locale, key) === "object") return false;
  const parts = key.split(".");
  for (let i = 1; i < parts.length; i++) {
    if (typeof builtIn(locale, parts.slice(0, i).join(".")) === "string") return false;
  }
  return true;
}

export async function loadTranslationsFromApi(locale: string) {
  try {
    const data = await fetchTranslations(locale);
    apiKeys.set(
      locale,
      new Set(Object.keys(data).filter((key) => data[key]?.trim())),
    );
    // Parents before children: "a.b" after "a.b.c" would replace the
    // object that holds "a.b.c" with a string.
    for (const [key, value] of Object.entries(data).sort(([a], [b]) => (a < b ? -1 : 1))) {
      if (!usableApiText(locale, key, value)) continue;
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
