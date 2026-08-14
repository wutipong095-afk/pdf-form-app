/** Document library — root folder, scan, search, open */
import { $ } from "./dom";
import { apiJson } from "./api";
import { state } from "./state";
import { loadDoc } from "./viewer";
import { t } from "./i18n";
import type { LibraryDoc, LibraryStatus, TemplatePayload } from "./types";

let selectedRel = "";
let libraryOpen = false;
let browseBusy = false;

export function isLibDoc(doc: string | null | undefined): boolean {
  const d = doc || "";
  return d.startsWith("@lib.") || d.startsWith("@lib|") || d.startsWith("@lib/");
}

export function setLibraryOpen(open: boolean): void {
  libraryOpen = open;
  const bar = $("libbar");
  bar.classList.toggle("open", open);
  bar.setAttribute("aria-hidden", open ? "false" : "true");
  const btn = $("btn-lib-toggle");
  btn.classList.toggle("active", open);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.textContent = open ? t("header.hideLibrary") : t("header.library");
  if (open) {
    setStatus(t("lib.loading"));
    void refreshLibrary().catch(() => setStatus(t("lib.loadFail")));
  }
}

function statusEl(): HTMLElement {
  return $("libstatus");
}

function setStatus(msg: string): void {
  statusEl().textContent = msg;
}

function setBrowseBusy(busy: boolean): void {
  browseBusy = busy;
  const btn = $("libbrowse") as HTMLButtonElement;
  btn.disabled = busy;
  btn.textContent = busy ? t("lib.browsing") : t("lib.browse");
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function browseFolderAsync(initial: string): Promise<string | null> {
  const started = await apiJson<{ job_id?: string; error?: string }>("/api/library/browse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initial }),
  });
  const jobId = started.job_id;
  if (!jobId) throw new Error(started.error || t("lib.browseStartFail"));

  const deadline = Date.now() + 10 * 60 * 1000;
  while (Date.now() < deadline) {
    await sleep(400);
    const st = await apiJson<{
      pending?: boolean;
      cancelled?: boolean;
      path?: string | null;
      error?: string;
    }>("/api/library/browse/" + encodeURIComponent(jobId));
    if (st.pending) continue;
    if (st.error) throw new Error(st.error);
    if (st.cancelled || !st.path) return null;
    return st.path;
  }
  throw new Error(t("lib.browseTimeout"));
}

function fillResults(docs: LibraryDoc[]): void {
  const box = $("libresults");
  if (!docs.length) {
    const empty = document.createElement("div");
    empty.className = "pick-empty";
    empty.textContent = t("lib.selectFrom");
    box.replaceChildren(empty);
    return;
  }
  const groups = new Map<string, LibraryDoc[]>();
  for (const d of docs) {
    const key = d.folder || t("lib.rootFolder");
    const arr = groups.get(key) || [];
    arr.push(d);
    groups.set(key, arr);
  }
  const frag = document.createDocumentFragment();
  for (const [folder, items] of groups) {
    const h = document.createElement("div");
    h.className = "pick-group";
    h.textContent = `${folder} (${items.length})`;
    frag.appendChild(h);
    for (const d of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pick-item" + (d.rel === selectedRel ? " sel" : "");
      btn.dataset.docId = d.doc_id;
      btn.dataset.rel = d.rel;
      btn.dataset.name = d.name;
      btn.textContent = d.filename + (d.has_template ? t("lib.hasTemplate") : "");
      frag.appendChild(btn);
    }
  }
  box.replaceChildren(frag);
}

export async function refreshLibrary(q?: string): Promise<void> {
  const st = await apiJson<LibraryStatus>("/api/library");
  const rootInput = $("libroot") as HTMLInputElement;
  if (st.root) rootInput.value = st.root;
  else if (!rootInput.value && st.suggested_root) rootInput.placeholder = st.suggested_root;

  const openBtn = $("libopenroot") as HTMLButtonElement;
  const openFileBtn = $("libopenfile") as HTMLButtonElement;
  const browseBtn = $("libbrowse") as HTMLButtonElement;
  if (!st.open_folder_enabled) {
    openBtn.style.display = "none";
    openFileBtn.style.display = "none";
    browseBtn.style.display = "none";
  }

  if (!st.configured) {
    setStatus(t("lib.notConfigured"));
    fillResults([]);
    return;
  }

  if (q !== undefined && q.trim()) {
    const res = await apiJson<{ docs: LibraryDoc[] }>(
      "/api/library/search?q=" + encodeURIComponent(q.trim()),
    );
    fillResults(res.docs || []);
    setStatus(
      t("lib.searchStatus", {
        q: q.trim(),
        n: res.docs?.length || 0,
        total: st.count,
      }),
    );
    return;
  }

  fillResults(st.docs || []);
  if (!st.count) {
    setStatus(t("lib.empty"));
    return;
  }
  setStatus(
    t("lib.statusCount", { count: st.count }) +
      (st.scanned_at
        ? t("lib.lastScan", { when: new Date(st.scanned_at * 1000).toLocaleString() })
        : ""),
  );
}

function statusAfterScan(count: number, extra = "", seeded?: string | null): void {
  if (seeded) {
    setStatus(t("lib.seeded", { seeded, count, extra }));
    return;
  }
  if (!count) {
    setStatus(t("lib.noPdf", { extra }));
    return;
  }
  setStatus(t("lib.ready", { count, extra }));
}

async function openLibraryDoc(
  docId: string,
  stemHint: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  try {
    await loadDoc(docId, onMarkers);
  } catch (e) {
    alert(e instanceof Error ? e.message : t("lib.loadFail"));
    return;
  }
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  try {
    const tpl = await apiJson<TemplatePayload & { has_template?: boolean }>(
      "/api/library/template?doc=" + encodeURIComponent(docId),
    );
    ($("tplname") as HTMLInputElement).value = stemHint || "template";
    state.fields = tpl.fields || [];
  } catch {
    ($("tplname") as HTMLInputElement).value = stemHint || "";
    state.fields = [];
  }
  onRender();
}

export function bindLibrary(onMarkers: () => void, onRender: () => void): void {
  const search = $("libsearch") as HTMLInputElement;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  $("btn-lib-toggle").onclick = () => setLibraryOpen(!libraryOpen);
  $("libhide").onclick = () => setLibraryOpen(false);

  $("libbrowse").onclick = async () => {
    if (browseBusy) return;
    const cur = ($("libroot") as HTMLInputElement).value.trim();
    setBrowseBusy(true);
    setStatus(t("lib.browseOpen"));
    try {
      const path = await browseFolderAsync(cur);
      if (!path) {
        setStatus(t("lib.browseCancel"));
        return;
      }
      ($("libroot") as HTMLInputElement).value = path;
      $("libset").click();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lib.browseFail"));
    } finally {
      setBrowseBusy(false);
    }
  };

  $("libset").onclick = async () => {
    const root = ($("libroot") as HTMLInputElement).value.trim();
    try {
      const res = await apiJson<{
        root: string;
        count: number;
        docs: LibraryDoc[];
        scaffold_created?: string[];
        seeded_demo?: string | null;
        warning?: string | null;
      }>("/api/library/root", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root: root || "default", scaffold: true }),
      });
      ($("libroot") as HTMLInputElement).value = res.root;
      fillResults(res.docs || []);
      const extra =
        res.scaffold_created && res.scaffold_created.length
          ? t("lib.scaffold", { folders: res.scaffold_created.join(", ") })
          : "";
      statusAfterScan(res.count, extra, res.seeded_demo);
      if (res.warning) alert(res.warning);
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lib.setRootFail"));
    }
  };

  $("libdefault").onclick = async () => {
    ($("libroot") as HTMLInputElement).value = "";
    $("libset").click();
  };

  $("libscan").onclick = async () => {
    try {
      const res = await apiJson<{
        count: number;
        docs: LibraryDoc[];
        seeded_demo?: string | null;
        warning?: string | null;
      }>("/api/library/scan", { method: "POST" });
      fillResults(res.docs || []);
      statusAfterScan(res.count, "", res.seeded_demo);
      search.value = "";
      if (res.warning) alert(res.warning);
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lib.scanFail"));
    }
  };

  $("libopenroot").onclick = async () => {
    try {
      await apiJson("/api/library/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rel: "" }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lib.openExplorerFail"));
    }
  };

  $("libopenfile").onclick = async () => {
    if (!selectedRel) {
      alert(t("lib.pickFileFirst"));
      return;
    }
    try {
      await apiJson("/api/library/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rel: selectedRel }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lib.openFileFail"));
    }
  };

  search.oninput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      void refreshLibrary(search.value).catch(() => undefined);
    }, 250);
  };

  $("libresults").onclick = (e) => {
    const btn = (e.target as HTMLElement).closest("button.pick-item") as HTMLButtonElement | null;
    if (!btn?.dataset.docId) {
      return;
    }
    selectedRel = btn.dataset.rel || "";
    $("libresults").querySelectorAll(".pick-item").forEach((el) => el.classList.remove("sel"));
    btn.classList.add("sel");
    const stem = btn.dataset.name || "";
    void openLibraryDoc(btn.dataset.docId, stem, onMarkers, onRender);
  };
}
