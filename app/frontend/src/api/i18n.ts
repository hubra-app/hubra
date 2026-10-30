import { apiFetch } from '@hubra/api-client';

export async function fetchTranslations(
  locale: string,
): Promise<Record<string, string>> {
  return apiFetch(`/i18n/${locale}`);
}

export async function fetchLanguages(): Promise<string[]> {
  const locales: string[] = await apiFetch(`/i18n/languages`);
  // Older databases may also hold "de-ch" next to "de-CH": one language.
  return [...new Set(locales.map(canonicalLocale))];
}

/** BCP 47 casing ("de-ch" → "de-CH"), the code the app's texts are filed under. */
export function canonicalLocale(code: string): string {
  try {
    return Intl.getCanonicalLocales(code.replace(/_/g, "-"))[0] ?? code;
  } catch {
    return code;
  }
}

export async function reportMissingKeys(
  locale: string,
  keys: { key: string; default_value: string | null }[],
): Promise<{ flagged: number }> {
  return apiFetch(`/i18n/${locale}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keys }),
  });
}

/** A club's suggestion for a platform text (the platform admins decide). */
export interface TranslationSuggestion {
  id: number;
  locale: string;
  key: string;
  currentValue: string | null;
  proposedValue: string;
  note: string | null;
  status: "pending" | "accepted" | "rejected";
  decisionNote: string | null;
  decidedAt: string | null;
  createdAt: string | null;
}

export async function fetchSuggestions(): Promise<TranslationSuggestion[]> {
  return apiFetch(`/i18n/requests`);
}

export async function suggestTranslation(body: {
  locale: string;
  key: string;
  value: string;
  note?: string;
}): Promise<TranslationSuggestion> {
  return apiFetch(`/i18n/requests`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
