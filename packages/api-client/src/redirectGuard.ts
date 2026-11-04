/**
 * Every automatic redirect between the portals goes through `redirectTo`.
 *
 * It notes the hop in a short-lived cookie on the shared parent domain
 * (.hubra.club), so the club app, SSO and manage all see the same chain for
 * this browser. When too many hops pile up in a few seconds (redirectLoop.ts)
 * the page stops instead of redirecting again: it shows an error page with
 * a way out (try again, or sign out and in), and reports the chain to the
 * API, which writes it to the platform event log with the sign-in session.
 *
 * Only host and path are kept, never the query or the hash.
 */
import { BASE, SSO_URL, clearTokens, getCookie } from "./client";
import {
  WINDOW_MS,
  addHop,
  describeChain,
  isLoop,
  parseHops,
  safeTarget,
  serializeHops,
  stripUrl,
  type Hop,
} from "./redirectLoop";

const COOKIE = "hubra_redirects";

/** Set once this page has shown the loop page: no more redirects. */
let stopped = false;
/** Whether this page load already recorded a hop: a second redirect from the
 * same page (two effects racing) replaces it instead of counting twice. */
let recordedThisPage = false;

function cookieAttrs(maxAge: number): string {
  // The parent of the portal hosts, as the API sets its cookies; host-only
  // on localhost and bare domains.
  const labels = window.location.hostname.split(".");
  const parent = labels.length > 2 ? `; domain=.${labels.slice(1).join(".")}` : "";
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  return `; Max-Age=${maxAge}; path=/; SameSite=Lax${parent}${secure}`;
}

function writeHops(hops: Hop[]): void {
  try {
    document.cookie = `${COOKIE}=${serializeHops(hops)}${cookieAttrs(Math.ceil(WINDOW_MS / 1000))}`;
  } catch {
    // No cookies: no loop detection either, the redirect still happens.
  }
}

function clearHops(): void {
  try {
    document.cookie = `${COOKIE}=${cookieAttrs(0)}`;
    document.cookie = `${COOKIE}=; Max-Age=0; path=/`;
  } catch {
    // As above.
  }
}

/** The hops of this browser in the last few seconds (for diagnostics). */
export function recentRedirects(): Hop[] {
  return parseHops(getCookie(COOKIE));
}

/**
 * Go to `url` because of `why` (a short code: "anon", "no-club",
 * "email-unverified", …). Returns false, and shows the loop page instead,
 * when this would be one redirect too many.
 */
export function redirectTo(url: string, why: string): boolean {
  if (stopped) return false;
  // Only places of this install: a caller passing on a ?redirect= it did not
  // check must not be able to send people elsewhere (or run javascript:).
  const target = safeTarget(url, window.location.href, [SSO_URL]);
  if (target === null) {
    console.warn("redirect refused: not a Hubra address");
    return false;
  }
  const now = Date.now();
  const hop: Hop = {
    t: now,
    from: stripUrl(window.location.href),
    to: stripUrl(target),
    why: why.slice(0, 40),
  };
  let hops = parseHops(getCookie(COOKIE));
  if (recordedThisPage && hops.length > 0) hops = hops.slice(0, -1);
  hops = addHop(hops, hop, now);
  recordedThisPage = true;

  if (isLoop(hops, now)) {
    stopped = true;
    clearHops();
    reportLoop(hops);
    showLoopPage(hops);
    return false;
  }
  writeHops(hops);
  window.location.assign(target);
  return true;
}

function reportLoop(hops: Hop[]): void {
  const start = hops[0]?.t ?? Date.now();
  try {
    fetch(`${BASE}/global/auth/redirect-loop`, {
      method: "POST",
      credentials: "include",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": getCookie("csrf_access_token"),
      },
      body: JSON.stringify({
        page: stripUrl(window.location.href),
        hops: hops.map((h) => ({
          ms: h.t - start,
          from: h.from,
          to: h.to,
          why: h.why,
        })),
      }),
    }).catch(() => {});
  } catch {
    // Reporting is best effort.
  }
}

function german(): boolean {
  const lang = document.documentElement.lang || navigator.language || "";
  return lang.toLowerCase().startsWith("de");
}

function dark(): boolean {
  const choice = getCookie("hubra_theme");
  if (choice === "dark") return true;
  if (choice === "light") return false;
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  style: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.style.cssText = style;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** A plain page over the app (no React: it must work in every portal). */
function showLoopPage(hops: Hop[]): void {
  const de = german();
  const t = (deText: string, enText: string) => (de ? deText : enText);
  const isDark = dark();
  const fg = isDark ? "#e6e3ef" : "#1a1625";
  const muted = isDark ? "#b7b0c9" : "#5b5470";
  const bg = isDark ? "#1a1625" : "#f4f2f9";
  const card = isDark ? "#2e2940" : "#ffffff";
  const primary = isDark ? "#9f7cf8" : "#7441e0";

  const overlay = el(
    "div",
    `position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:16px;background:${bg};color:${fg};font-family:'Hanken Grotesk',system-ui,sans-serif;overflow:auto`,
  );
  overlay.setAttribute("role", "alertdialog");
  overlay.setAttribute("aria-labelledby", "hubra-loop-title");
  const box = el(
    "div",
    `max-width:460px;width:100%;background:${card};border-radius:12px;padding:24px;box-shadow:0 4px 24px rgba(0,0,0,.12)`,
  );
  const title = el(
    "h1",
    "margin:0 0 8px;font-size:20px;font-weight:700;font-family:'Bricolage Grotesque',system-ui,sans-serif",
    t("Diese Seite leitet immer wieder weiter", "This page keeps redirecting"),
  );
  title.id = "hubra-loop-title";
  const text = el(
    "p",
    `margin:0 0 16px;font-size:14px;line-height:1.5;color:${muted}`,
    t(
      "Die Anmeldung und die App haben sich gegenseitig hin- und hergeschickt. Wir haben angehalten und den Fehler gemeldet. Meist hilft es, sich neu anzumelden.",
      "Sign-in and the app kept sending you back and forth. We stopped and reported the problem. Signing in again usually fixes it.",
    ),
  );
  const buttons = el("div", "display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px");
  const btn = "border:0;border-radius:8px;padding:8px 14px;font-size:14px;font-weight:600;cursor:pointer";
  const relogin = el(
    "button",
    `${btn};background:${primary};color:#fff`,
    t("Abmelden und neu anmelden", "Sign out and sign in again"),
  );
  relogin.type = "button";
  relogin.onclick = () => {
    clearTokens();
    // Give the sign-out request a moment before leaving the page.
    setTimeout(() => window.location.assign(`${SSO_URL}/login`), 300);
  };
  const retry = el(
    "button",
    `${btn};background:transparent;color:${primary};border:1px solid ${primary}`,
    t("Erneut versuchen", "Try again"),
  );
  retry.type = "button";
  retry.onclick = () => window.location.reload();
  buttons.append(relogin, retry);

  const details = el("details", `font-size:12px;color:${muted}`);
  details.append(el("summary", "cursor:pointer", t("Details für den Support", "Details for support")));
  const pre = el(
    "pre",
    "white-space:pre-wrap;word-break:break-all;margin:8px 0 0;font-size:12px",
    `${new Date().toISOString()}\n${describeChain(hops).split(" → ").join("\n→ ")}`,
  );
  details.append(pre);

  box.append(title, text, buttons, details);
  overlay.append(box);
  document.body.append(overlay);
  relogin.focus();
}
