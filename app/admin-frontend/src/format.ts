const dateFormatter = new Intl.DateTimeFormat("de-CH", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const dateTimeFormatter = new Intl.DateTimeFormat("de-CH", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** 1.2 MB, 340 KB … (binary units, as the backups list shows them). */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "–";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** "vor 5 Min." / "5 min ago", "vor 3 Tagen" … from an ISO time. */
export function formatAgo(
  iso: string | null | undefined,
  tr: (de: string, en: string) => string,
): string {
  if (!iso) return tr("nie", "never");
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 1) return tr("gerade eben", "just now");
  if (min < 60) return tr(`vor ${min} Min.`, `${min} min ago`);
  const h = Math.round(min / 60);
  if (h < 24) return tr(`vor ${h} Std.`, `${h} h ago`);
  const d = Math.round(h / 24);
  if (d === 1) return tr("gestern", "yesterday");
  if (d < 60) return tr(`vor ${d} Tagen`, `${d} days ago`);
  return formatDate(iso);
}
