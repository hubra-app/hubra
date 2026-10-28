import { apiFetch, apiFetchRaw } from '@vollbuild/api-client';

export async function fetchTranslations(
  locale: string,
): Promise<Record<string, string>> {
  return apiFetch(`/i18n/${locale}`);
}

export async function fetchTranslationsList(
  locale: string,
): Promise<TranslationEntry[]> {
  return apiFetch(`/i18n/${locale}?list=1`);
}

export async function fetchLanguages(): Promise<string[]> {
  return apiFetch(`/i18n/languages`);
}

export async function patchTranslations(
  locale: string,
  entries: { key: string; value: string; alias_for?: string | null }[],
): Promise<{ upserted: number; locale: string }> {
  return apiFetch(`/i18n/${locale}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entries),
  });
}

export async function deleteTranslation(
  locale: string,
  key: string,
): Promise<{ deleted: boolean; count: number }> {
  return apiFetch(`/i18n/${locale}/${key}`, { method: "DELETE" });
}

export async function duplicateLocale(
  locale: string,
  source: string,
  copyValues: boolean,
): Promise<{
  locale: string;
  source: string;
  inserted: number;
  copy_values: boolean;
}> {
  return apiFetch(`/i18n/${locale}/duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, copy_values: copyValues }),
  });
}

export async function copyDefaults(
  locale: string,
): Promise<{ locale: string; filled: number }> {
  return apiFetch(`/i18n/${locale}/copy-defaults`, {
    method: "POST",
  });
}

export async function exportTranslations(
  locale: string,
  format: "json" | "csv" = "json",
): Promise<void> {
  const response = await apiFetchRaw(
    `/i18n/${locale}/export?format=${format}`,
  );
  const blob = await response.blob();
  const contentDisposition = response.headers.get("Content-Disposition");
  const filename = contentDisposition
    ? contentDisposition.split("filename=")[1]?.replace(/"/g, "")
    : `translations_${locale}.${format}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function importTranslations(
  locale: string,
  file: File,
  format: "json" | "csv",
): Promise<{ locale: string; imported: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetchRaw(
    `/i18n/${locale}/import?format=${format}`,
    {
      method: "POST",
      body: formData,
    },
  );
  return response.json();
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

export async function fetchFlaggedTranslations(
  locale: string,
): Promise<TranslationEntry[]> {
  return apiFetch(`/i18n/${locale}/flagged`);
}

export interface TranslationEntry {
  id: number;
  locale: string;
  key: string;
  value: string;
  default_value?: string | null;
  needs_attention?: boolean;
  is_missing?: boolean;
  is_stale?: boolean;
  last_used_at?: string | null;
  updated_at: string | null;
  alias_for?: string | null;
}
