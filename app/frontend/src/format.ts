const chfFormatter = new Intl.NumberFormat("de-CH", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const chfCompactFormatter = new Intl.NumberFormat("de-CH", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const dateTimeFormatter = new Intl.DateTimeFormat("de-CH", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const relativeFormatter = new Intl.RelativeTimeFormat("de-CH", {
  style: "short",
});

export function formatCHF(amount: number): string {
  return chfFormatter.format(amount);
}

export function formatCHFCompact(amount: number): string {
  return chfCompactFormatter.format(amount);
}

export function formatDateTime(iso: string | Date): string {
  return dateTimeFormatter.format(new Date(iso));
}

export function formatRelative(iso: string | Date): string {
  const diff = new Date(iso).getTime() - Date.now();
  const sec = Math.round(diff / 1000);
  const min = Math.round(sec / 60);
  const hr = Math.round(min / 60);
  const day = Math.round(hr / 24);
  if (Math.abs(sec) < 60) return relativeFormatter.format(sec, "second");
  if (Math.abs(min) < 60) return relativeFormatter.format(min, "minute");
  if (Math.abs(hr) < 24) return relativeFormatter.format(hr, "hour");
  if (Math.abs(day) < 30) return relativeFormatter.format(day, "day");
  const mo = Math.round(day / 30);
  if (Math.abs(mo) < 12) return relativeFormatter.format(mo, "month");
  return relativeFormatter.format(Math.round(mo / 12), "year");
}
