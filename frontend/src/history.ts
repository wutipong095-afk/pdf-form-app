/** Completed work — filled PDFs in the user output folder */
import { $ } from "./dom";
import { apiJson } from "./api";
import { state } from "./state";
import { loadDoc } from "./viewer";
import { clearChat } from "./chat";
import { t } from "./i18n";
import type { HistoryFile, HistoryStatus } from "./types";

let historyOpen = false;
let selectedName = "";
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
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pick-item" + (f.name === selectedName ? " sel" : "");
      btn.dataset.name = f.name;
      btn.dataset.docId = f.doc_id;
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = formatWhen(f.mtime);
      btn.append(f.name, meta);
      frag.appendChild(btn);
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
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  await loadDoc(docId, onMarkers);
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  state.fields = [];
  state.selIdx = -1;
  state.chatIdx = -1;
  clearChat();
  onRender();
}

export function bindHistory(onMarkers: () => void, onRender: () => void): void {
  $("btn-hist-toggle").onclick = () => setHistoryOpen(!historyOpen);
  $("histhide").onclick = () => setHistoryOpen(false);

  $("histopen").onclick = async () => {
    try {
      await apiJson("/api/history/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "" }),
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
        body: JSON.stringify({ name: selectedName }),
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
    const btn = (e.target as HTMLElement).closest("button.pick-item") as HTMLButtonElement | null;
    if (!btn?.dataset.docId) return;
    selectedName = btn.dataset.name || "";
    $("histlist").querySelectorAll(".pick-item").forEach((el) => el.classList.remove("sel"));
    btn.classList.add("sel");
    void openHistoryDoc(btn.dataset.docId, onMarkers, onRender).catch((err) => {
      btn.classList.remove("sel");
      if (selectedName === btn.dataset.name) selectedName = "";
      alert(err instanceof Error ? err.message : t("hist.loadFail"));
    });
  };
}
