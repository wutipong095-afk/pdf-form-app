/** งานเก่า — ใบงานที่แก้ต่อได้ และ PDF ที่พิมพ์ไปแล้ว */
import { $ } from "./dom";
import { apiJson } from "./api";
import { state } from "./state";
import { loadDoc } from "./viewer";
import { clearChat } from "./chat";
import { clearActiveSheet, deleteSheet, duplicateSheet, openSheet } from "./sheets";
import { t } from "./i18n";
import type { HistoryFile, HistoryStatus } from "./types";

let historyOpen = false;
let selectedName = "";
let selectedKind: "sheet" | "pdf" | "" = "";
let searchTimer: ReturnType<typeof setTimeout> | null = null;

export function setHistoryOpen(open: boolean): void {
  historyOpen = open;
  const bar = $("histbar");
  bar.classList.toggle("open", open);
  bar.setAttribute("aria-hidden", open ? "false" : "true");
  const btn = $("btn-hist-toggle");
  btn.classList.toggle("active", open);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.textContent = open ? t("header.hideHistory") : t("header.history");
  if (open) {
    setStatus(t("hist.loading"));
    void refreshHistory().catch(() => setStatus(t("hist.loadFail")));
  }
}

export function notifyHistoryChanged(): void {
  if (historyOpen) void refreshHistory().catch(() => undefined);
}

function setStatus(msg: string): void {
  $("histstatus").textContent = msg;
}

function formatWhen(mtime: number): string {
  return new Date(mtime * 1000).toLocaleString();
}

function fileKind(f: HistoryFile): "sheet" | "pdf" {
  return f.kind === "sheet" ? "sheet" : "pdf";
}

function sheetMeta(f: HistoryFile): string {
  const bits = [t("hist.kindSheet"), formatWhen(f.mtime)];
  if (typeof f.filled === "number" && typeof f.pins === "number") {
    bits.push(`${f.filled}/${f.pins}`);
  }
  bits.push(f.printed ? t("hist.printedTag") : t("hist.draftTag"));
  return bits.join(" · ");
}

function actionButton(
  act: "dup" | "export" | "del",
  label: string,
  name: string,
): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "del";
  b.dataset.act = act;
  b.dataset.sheet = name;
  b.title = label;
  b.textContent = act === "del" ? "✕" : act === "dup" ? "⧉" : "⤓";
  return b;
}

function fillList(files: HistoryFile[]): void {
  const box = $("histlist");
  if (!files.length) {
    const empty = document.createElement("div");
    empty.className = "pick-empty";
    empty.textContent = t("hist.empty");
    box.replaceChildren(empty);
    return;
  }
  const groups = new Map<string, HistoryFile[]>();
  for (const f of files) {
    const key = f.group || t("hist.older");
    const arr = groups.get(key) || [];
    arr.push(f);
    groups.set(key, arr);
  }
  const frag = document.createDocumentFragment();
  for (const [group, items] of groups) {
    const h = document.createElement("div");
    h.className = "pick-group";
    h.textContent = `${group} (${items.length})`;
    frag.appendChild(h);
    for (const f of items) {
      const kind = fileKind(f);
      const row = document.createElement("div");
      row.className = "pick-row";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pick-item" + (f.name === selectedName ? " sel" : "");
      btn.dataset.name = f.name;
      btn.dataset.docId = f.doc_id;
      btn.dataset.kind = kind;
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent =
        kind === "sheet" ? sheetMeta(f) : `${t("hist.kindPdf")} · ${formatWhen(f.mtime)}`;
      btn.append(kind === "sheet" ? f.title || f.name : f.name, meta);
      row.appendChild(btn);
      if (kind === "sheet") {
        row.appendChild(actionButton("dup", t("hist.duplicate"), f.name));
        row.appendChild(actionButton("export", t("hist.export"), f.name));
        row.appendChild(actionButton("del", t("hist.delete"), f.name));
      }
      frag.appendChild(row);
    }
  }
  box.replaceChildren(frag);
}

export async function refreshHistory(q?: string): Promise<void> {
  const query = (q ?? ($("histsearch") as HTMLInputElement).value).trim();
  const url = query ? "/api/history?q=" + encodeURIComponent(query) : "/api/history";
  const st = await apiJson<HistoryStatus>(url);
  const openBtn = $("histopen") as HTMLButtonElement;
  const openFileBtn = $("histopenfile") as HTMLButtonElement;
  if (!st.open_folder_enabled) {
    openBtn.style.display = "none";
    openFileBtn.style.display = "none";
  }
  fillList(st.files || []);
  if (!st.count) {
    setStatus(t("hist.empty"));
    return;
  }
  if (query) {
    setStatus(t("hist.searchStatus", { q: query, n: st.count }));
    return;
  }
  setStatus(
    st.truncated ? t("hist.truncated", { count: st.count }) : t("hist.ready", { count: st.count }),
  );
}

async function openHistoryDoc(
  docId: string,
  name: string,
  kind: "sheet" | "pdf",
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  if (kind === "sheet") {
    await openSheet(name, onMarkers, onRender);
    return;
  }
  clearActiveSheet();
  await loadDoc(docId, onMarkers);
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  state.fields = [];
  state.selIdx = -1;
  state.chatIdx = -1;
  clearChat();
  onRender();
}

async function runSheetAction(
  act: string,
  name: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  if (act === "export") {
    window.location.href = "/api/sheets/" + encodeURIComponent(name) + "/export";
    return;
  }
  if (act === "dup") {
    await duplicateSheet(name, onMarkers, onRender);
    setStatus(t("hist.duplicated"));
    await refreshHistory();
    return;
  }
  if (!confirm(t("hist.deleteAsk", { name }))) return;
  await deleteSheet(name);
  if (selectedName === name) {
    selectedName = "";
    selectedKind = "";
  }
  setStatus(t("hist.deleted"));
  await refreshHistory();
}

export function bindHistory(onMarkers: () => void, onRender: () => void): void {
  $("btn-hist-toggle").onclick = () => setHistoryOpen(!historyOpen);
  $("histhide").onclick = () => setHistoryOpen(false);

  $("histopen").onclick = async () => {
    try {
      await apiJson("/api/history/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "", kind: "sheet" }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : t("hist.openFail"));
    }
  };

  $("histopenfile").onclick = async () => {
    if (!selectedName) {
      alert(t("hist.pickFirst"));
      return;
    }
    try {
      await apiJson("/api/history/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selectedName, kind: selectedKind || undefined }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : t("hist.openFail"));
    }
  };

  ($("histsearch") as HTMLInputElement).oninput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      void refreshHistory().catch(() => undefined);
    }, 250);
  };

  $("histlist").onclick = (e) => {
    const target = e.target as HTMLElement;
    const action = target.closest("button[data-act]") as HTMLButtonElement | null;
    if (action?.dataset.sheet) {
      void runSheetAction(action.dataset.act || "", action.dataset.sheet, onMarkers, onRender).catch(
        (err) => alert(err instanceof Error ? err.message : t("hist.deleteFail")),
      );
      return;
    }
    const btn = target.closest("button.pick-item") as HTMLButtonElement | null;
    if (!btn?.dataset.docId) return;
    selectedName = btn.dataset.name || "";
    selectedKind = btn.dataset.kind === "sheet" ? "sheet" : "pdf";
    $("histlist").querySelectorAll(".pick-item").forEach((el) => el.classList.remove("sel"));
    btn.classList.add("sel");
    void openHistoryDoc(btn.dataset.docId, selectedName, selectedKind, onMarkers, onRender).catch(
      (err) => {
        btn.classList.remove("sel");
        if (selectedName === btn.dataset.name) selectedName = "";
        alert(err instanceof Error ? err.message : t("hist.loadFail"));
      },
    );
  };
}
