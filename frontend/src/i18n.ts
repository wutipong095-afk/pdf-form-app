/** UI locale — catalogs from repo locales/*.json */
import th from "../../locales/th.json";
import en from "../../locales/en.json";
import { api } from "./api";

export type Locale = "th" | "en";

const CATALOGS: Record<Locale, Record<string, unknown>> = { th, en };
const STORAGE_KEY = "ui_lang";
const COOKIE_NAME = "ui_lang";

function normalize(raw: string | null | undefined): Locale {
  if (!raw) return "th";
  const v = raw.trim().toLowerCase();
  if (v.startsWith("en")) return "en";
  return "th";
}

function readCookie(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)ui_lang=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function writeCookie(lang: Locale): void {
  document.cookie = `${COOKIE_NAME}=${lang};path=/;max-age=31536000;SameSite=Lax`;
}

function lookup(catalog: Record<string, unknown>, key: string): string | null {
  let cur: unknown = catalog;
  for (const part of key.split(".")) {
    if (!cur || typeof cur !== "object" || !(part in (cur as object))) return null;
    cur = (cur as Record<string, unknown>)[part];
  }
  return typeof cur === "string" ? cur : null;
}

/** Match server first paint: <html lang> → cookie → th (never prefer stale localStorage). */
function resolveInitialLocale(): Locale {
  const htmlLang = document.documentElement.getAttribute("lang");
  if (htmlLang) return normalize(htmlLang);
  const cookie = readCookie();
  if (cookie) return normalize(cookie);
  return "th";
}

let current: Locale = resolveInitialLocale();

export function getLocale(): Locale {
  return current;
}

export function t(key: string, vars?: Record<string, string | number>): string {
  let text = lookup(CATALOGS[current], key);
  if (text == null && current !== "th") text = lookup(CATALOGS.th, key);
  if (text == null) text = key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.split(`{${k}}`).join(String(v));
    }
  }
  return text;
}

/** Apply data-i18n / data-i18n-placeholder / data-i18n-title / data-i18n-html */
export function applyDomI18n(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) el.textContent = t(key);
  });
  root.querySelectorAll<HTMLElement>("[data-i18n-html]").forEach((el) => {
    const key = el.getAttribute("data-i18n-html");
    if (key) el.innerHTML = t(key);
  });
  root.querySelectorAll<HTMLElement>("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (key && "placeholder" in el) (el as HTMLInputElement).placeholder = t(key);
  });
  root.querySelectorAll<HTMLElement>("[data-i18n-title]").forEach((el) => {
    const key = el.getAttribute("data-i18n-title");
    if (key) el.title = t(key);
  });
  document.documentElement.lang = current;
}

export async function setLocale(lang: Locale): Promise<void> {
  const next = normalize(lang);
  current = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    /* ignore */
  }
  writeCookie(next);
  try {
    await api("/api/ui-lang", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lang: next }),
    });
  } catch {
    /* still reload with cookie */
  }
  location.reload();
}

export function bindLangToggle(): void {
  const sel = document.getElementById("ui-lang") as HTMLSelectElement | null;
  if (!sel) return;

  // Keep JS locale aligned with server-rendered select / <html lang>
  current = normalize(sel.value || document.documentElement.lang || current);
  sel.value = current;

  sel.onchange = () => {
    const v = normalize(sel.value);
    if (v !== current) void setLocale(v);
  };

  // Mirror server locale into cookie / localStorage / launcher file
  writeCookie(current);
  try {
    localStorage.setItem(STORAGE_KEY, current);
  } catch {
    /* ignore */
  }
  void api("/api/ui-lang", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lang: current }),
  }).catch(() => undefined);
}
