import { $ } from "./dom";
import { ApiError, api } from "./api";
import { isOutDoc, state } from "./state";
import { t } from "./i18n";
import type { Field } from "./types";

function img(): HTMLImageElement {
  return $("pageimg") as HTMLImageElement;
}

function wrap(): HTMLElement {
  return $("pagewrap");
}

export function scale(): number {
  const el = img();
  return el.naturalWidth ? el.naturalWidth / el.clientWidth : 1;
}

/** Overlay CSS px for one PDF point — same mapping as pin x/y */
function pdfPtToCss(pt: number): number {
  return (pt * state.zoom) / scale();
}

export function applyFontMetrics(asc?: number, desc?: number): void {
  if (typeof asc === "number" && Number.isFinite(asc) && asc > 0) state.fontAsc = asc;
  if (typeof desc === "number" && Number.isFinite(desc) && desc < 0) state.fontDesc = desc;
}

/** Load the fill TTF so overlay glyphs match the printed PDF, then repaint. */
export function ensureFillFont(onReady: () => void): void {
  const fonts = document.fonts;
  if (!fonts?.load) return;
  void fonts
    .load("16px FillPreview")
    .then(() => onReady())
    .catch(() => undefined);
}

export function showPage(onMarkers: () => void): void {
  if (!state.doc) return;
  const el = img();
  el.src = `/page/${encodeURIComponent(state.doc)}/${state.cur}.png?${Date.now()}`;
  $("pglabel").textContent = t("viewer.page", { cur: state.cur + 1, pages: state.pages });
  el.onload = onMarkers;
}

export async function loadDoc(name: string, onMarkers: () => void): Promise<void> {
  const res = await api(`/api/pageinfo/${encodeURIComponent(name)}`);
  const info = (await res.json().catch(() => ({}))) as {
    pages?: number;
    zoom?: number;
    error?: string;
    font_ascender?: number;
    font_descender?: number;
  };
  if (!res.ok || info.pages == null) {
    throw new ApiError(info.error || t("app.loadDocFail"), res.status);
  }
  state.doc = name;
  state.pages = info.pages;
  state.zoom = info.zoom ?? 2;
  applyFontMetrics(info.font_ascender, info.font_descender);
  state.cur = 0;
  syncHistoryChrome();
  showPage(onMarkers);
}

function syncHistoryChrome(): void {
  const hist = isOutDoc(state.doc);
  const notice = document.getElementById("histnotice");
  if (notice) notice.hidden = !hist;
  const make = document.getElementById("makepdf") as HTMLButtonElement | null;
  if (make) make.disabled = hist;
  const save = document.getElementById("savetpl") as HTMLButtonElement | null;
  if (save) save.disabled = hist;
  const wrapEl = document.getElementById("pagewrap");
  if (wrapEl) {
    const editActive = document.getElementById("panel-edit")?.classList.contains("active");
    wrapEl.classList.toggle("marking", !!editActive && !hist);
  }
}

export function renderMarkers(
  onSelect: (i: number) => void,
  onEditValue: (i: number, value: string) => void,
): void {
  const w = wrap();
  w.querySelectorAll(".marker,.mlabel,.mvalue").forEach((n) => n.remove());
  const fillActive = $("panel-fill").classList.contains("active");

  state.fields.forEach((f, i) => {
    if (f.page !== state.cur) return;
    const px = pdfPtToCss(f.x);
    const py = pdfPtToCss(f.y);
    const m = document.createElement("div");
    m.className = "marker" + (i === state.selIdx ? " sel" : "");
    m.style.left = `${px}px`;
    m.style.top = `${py}px`;
    m.title = f.name + (f.value ? ` = ${f.value}` : "");
    m.onclick = (ev) => {
      ev.stopPropagation();
      if (fillActive) {
        const nv = prompt(t("viewer.valuePrompt", { name: f.name }), f.value || "");
        if (nv !== null) onEditValue(i, nv.trim());
        return;
      }
      onSelect(i);
    };
    w.appendChild(m);
    if (f.value) {
      const em = pdfPtToCss(f.size);
      const v = document.createElement("div");
      v.className = "mvalue";
      v.textContent = f.value;
      v.style.left = `${px}px`;
      // ตรงกับ insert_thai_text: top = y - ascender * fontsize
      v.style.top = `${py - state.fontAsc * em}px`;
      v.style.fontSize = `${em}px`;
      v.style.lineHeight = String(state.fontAsc - state.fontDesc);
      w.appendChild(v);
    } else {
      const l = document.createElement("div");
      l.className = "mlabel";
      l.textContent = f.name;
      l.style.left = `${px}px`;
      l.style.top = `${py - 6}px`;
      w.appendChild(l);
    }
  });
}

export function bindViewer(
  onMarkers: () => void,
  onPlaceOrMove: (x: number, y: number) => void,
): void {
  $("prev").onclick = () => {
    if (state.cur > 0) {
      state.cur--;
      showPage(onMarkers);
    }
  };
  $("next").onclick = () => {
    if (state.cur < state.pages - 1) {
      state.cur++;
      showPage(onMarkers);
    }
  };
  img().onclick = (e) => {
    if (!state.doc || isOutDoc(state.doc) || !$("panel-edit").classList.contains("active")) return;
    const rect = img().getBoundingClientRect();
    const x = ((e.clientX - rect.left) * scale()) / state.zoom;
    const y = ((e.clientY - rect.top) * scale()) / state.zoom;
    onPlaceOrMove(x, y);
  };
}

export function nudgeSelected(dx: number, dy: number): Field | null {
  if (state.selIdx < 0) return null;
  const f = state.fields[state.selIdx];
  f.x += dx;
  f.y += dy;
  return f;
}
