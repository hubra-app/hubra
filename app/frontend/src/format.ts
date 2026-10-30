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

const chfWholeFormatter = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  maximumFractionDigits: 0,
});

/** "CHF 1’250" – whole francs, for stat tiles. Pass `sign` for "+CHF 1’250". */
export function formatCHFWhole(amount: number, sign = false): string {
  const s = chfWholeFormatter.format(Math.abs(amount)).replace(/\u00a0/g, " ");
  if (amount < 0) return `−${s}`;
  return sign && amount > 0 ? `+${s}` : s;
}

export function formatCHFCompact(amount: number): string {
  return chfCompactFormatter.format(amount);
}

export function formatDateTime(iso: string | Date): string {
  return dateTimeFormatter.format(new Date(iso));
}

// The club's choice under Settings › Verein › Datumsformat.
let clubDateFormat = "DD.MM.YYYY";

export function setDateFormat(format: string | null | undefined): void {
  clubDateFormat = format || "DD.MM.YYYY";
}

/** A date in the club's format; a bare "YYYY-MM-DD" stays that calendar day. */
export function formatDate(iso: string | Date): string {
  let d: Date;
  if (typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [y, m, day] = iso.split("-").map(Number);
    d = new Date(y, m - 1, day);
  } else {
    d = new Date(iso);
  }
  if (Number.isNaN(d.getTime())) return typeof iso === "string" ? iso : "";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = String(d.getFullYear());
  switch (clubDateFormat) {
    case "YYYY-MM-DD":
      return `${yyyy}-${mm}-${dd}`;
    case "DD/MM/YYYY":
      return `${dd}/${mm}/${yyyy}`;
    case "MM/DD/YYYY":
      return `${mm}/${dd}/${yyyy}`;
    default:
      return `${dd}.${mm}.${yyyy}`;
  }
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
