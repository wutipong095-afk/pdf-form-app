import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
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

export function showPage(onMarkers: () => void): void {
  if (!state.doc) return;
  const el = img();
  el.src = `/page/${encodeURIComponent(state.doc)}/${state.cur}.png?${Date.now()}`;
  $("pglabel").textContent = `หน้า ${state.cur + 1} / ${state.pages}`;
  el.onload = onMarkers;
}

export async function loadDoc(name: string, onMarkers: () => void): Promise<void> {
  state.doc = name;
  const res = await api(`/api/pageinfo/${encodeURIComponent(name)}`);
  const info = (await res.json()) as { pages: number; zoom: number };
  state.pages = info.pages;
  state.zoom = info.zoom;
  state.cur = 0;
  showPage(onMarkers);
}

export function renderMarkers(
  onSelect: (i: number) => void,
  onEditValue: (i: number, value: string) => void,
): void {
  const w = wrap();
  w.querySelectorAll(".marker,.mlabel,.mvalue").forEach((n) => n.remove());
  const s = scale();
  const fillActive = $("panel-fill").classList.contains("active");

  state.fields.forEach((f, i) => {
    if (f.page !== state.cur) return;
    const px = (f.x * state.zoom) / s;
    const py = (f.y * state.zoom) / s;
    const m = document.createElement("div");
    m.className = "marker" + (i === state.selIdx ? " sel" : "");
    m.style.left = `${px}px`;
    m.style.top = `${py}px`;
    m.title = f.name + (f.value ? ` = ${f.value}` : "");
    m.onclick = (ev) => {
      ev.stopPropagation();
      if (fillActive) {
        const nv = prompt(`ค่าของ "${f.name}":`, f.value || "");
        if (nv !== null) onEditValue(i, nv.trim());
        return;
      }
      onSelect(i);
    };
    w.appendChild(m);
    if (f.value) {
      const v = document.createElement("div");
      v.className = "mvalue";
      v.textContent = f.value;
      v.style.left = `${px}px`;
      v.style.top = `${py}px`;
      v.style.fontSize = `${(f.size * state.zoom) / s}px`;
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
    if (!state.doc || !$("panel-edit").classList.contains("active")) return;
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
