/** คลังเอกสาร CP2 — เลือกโฟลเดอร์ราก, สแกน, ค้นหา, เปิดจากคลัง */
import { $ } from "./dom";
import { apiJson } from "./api";
import { state } from "./state";
import { loadDoc } from "./viewer";
import type { LibraryDoc, LibraryStatus, TemplatePayload } from "./types";

let selectedRel = "";

export function isLibDoc(doc: string | null | undefined): boolean {
  const d = doc || "";
  return d.startsWith("@lib.") || d.startsWith("@lib|") || d.startsWith("@lib/");
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function statusEl(): HTMLElement {
  return $("libstatus");
}

function setStatus(msg: string): void {
  statusEl().textContent = msg;
}

function fillResults(docs: LibraryDoc[]): void {
  const sel = $("libresults") as HTMLSelectElement;
  const prev = sel.value;
  sel.innerHTML =
    '<option value="">— เลือกจากคลัง (' +
    docs.length +
    ") —</option>" +
    docs
      .map((d) => {
        const label =
          (d.folder ? d.folder + " / " : "") + d.filename + (d.has_template ? " · มีเทมเพลต" : "");
        return (
          `<option value="${encodeURIComponent(d.doc_id)}"` +
          ` data-rel="${encodeURIComponent(d.rel)}"` +
          ` data-name="${encodeURIComponent(d.name)}">` +
          escapeHtml(label) +
          "</option>"
        );
      })
      .join("");
  if (prev) {
    for (const opt of Array.from(sel.options)) {
      if (opt.value === prev) {
        sel.value = prev;
        break;
      }
    }
  }
}

export async function refreshLibrary(q?: string): Promise<void> {
  const st = await apiJson<LibraryStatus>("/api/library");
  const rootInput = $("libroot") as HTMLInputElement;
  if (st.root) rootInput.value = st.root;
  else if (!rootInput.value && st.suggested_root) rootInput.placeholder = st.suggested_root;

  const openBtn = $("libopenroot") as HTMLButtonElement;
  const openFileBtn = $("libopenfile") as HTMLButtonElement;
  if (!st.open_folder_enabled) {
    openBtn.style.display = "none";
    openFileBtn.style.display = "none";
  }

  if (!st.configured) {
    setStatus("ยังไม่ได้ตั้งโฟลเดอร์ราก — ใส่ path แล้วกดตั้งราก หรือใช้ค่าแนะนำ");
    fillResults([]);
    return;
  }

  if (q !== undefined && q.trim()) {
    const res = await apiJson<{ docs: LibraryDoc[] }>(
      "/api/library/search?q=" + encodeURIComponent(q.trim()),
    );
    fillResults(res.docs || []);
    setStatus(`ค้นหา “${q.trim()}” — ${res.docs?.length || 0} รายการ (คลังมี ${st.count} ไฟล์)`);
    return;
  }

  fillResults(st.docs || []);
  setStatus(
    `คลัง: ${st.count} ไฟล์` +
      (st.scanned_at ? ` · สแกนล่าสุด ${new Date(st.scanned_at * 1000).toLocaleString()}` : ""),
  );
}

async function openLibraryDoc(
  docId: string,
  stemHint: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  await loadDoc(docId, onMarkers);
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  try {
    const t = await apiJson<TemplatePayload & { has_template?: boolean }>(
      "/api/library/template?doc=" + encodeURIComponent(docId),
    );
    ($("tplname") as HTMLInputElement).value = stemHint || "template";
    state.fields = t.fields || [];
  } catch {
    ($("tplname") as HTMLInputElement).value = stemHint || "";
    state.fields = [];
  }
  onRender();
}

export function bindLibrary(onMarkers: () => void, onRender: () => void): void {
  const search = $("libsearch") as HTMLInputElement;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  $("libset").onclick = async () => {
    const root = ($("libroot") as HTMLInputElement).value.trim();
    try {
      const res = await apiJson<{
        root: string;
        count: number;
        docs: LibraryDoc[];
        scaffold_created?: string[];
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
          ? ` · สร้างโฟลเดอร์: ${res.scaffold_created.join(", ")}`
          : "";
      setStatus(`ตั้งรากแล้ว · ${res.count} ไฟล์${extra}`);
      if (res.warning) alert(res.warning);
    } catch (e) {
      alert(e instanceof Error ? e.message : "ตั้งรากไม่สำเร็จ");
    }
  };

  $("libdefault").onclick = async () => {
    ($("libroot") as HTMLInputElement).value = "";
    $("libset").click();
  };

  $("libscan").onclick = async () => {
    try {
      const res = await apiJson<{ count: number; docs: LibraryDoc[]; warning?: string | null }>(
        "/api/library/scan",
        { method: "POST" },
      );
      fillResults(res.docs || []);
      setStatus(`สแกนใหม่ · ${res.count} ไฟล์`);
      search.value = "";
      if (res.warning) alert(res.warning);
    } catch (e) {
      alert(e instanceof Error ? e.message : "สแกนไม่สำเร็จ");
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
      alert(e instanceof Error ? e.message : "เปิด Explorer ไม่สำเร็จ");
    }
  };

  $("libopenfile").onclick = async () => {
    if (!selectedRel) {
      alert("เลือกไฟล์จากคลังก่อน");
      return;
    }
    try {
      await apiJson("/api/library/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rel: selectedRel }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : "เปิดไฟล์ไม่สำเร็จ");
    }
  };

  search.oninput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      void refreshLibrary(search.value).catch(() => undefined);
    }, 250);
  };

  ($("libresults") as HTMLSelectElement).onchange = (e) => {
    const sel = e.target as HTMLSelectElement;
    const opt = sel.selectedOptions[0];
    if (!sel.value || !opt) {
      selectedRel = "";
      return;
    }
    selectedRel = decodeURIComponent(opt.dataset.rel || "");
    const docId = decodeURIComponent(sel.value);
    const stem = decodeURIComponent(opt.dataset.name || "");
    void openLibraryDoc(docId, stem, onMarkers, onRender);
  };

  void refreshLibrary().catch(() => {
    setStatus("โหลดคลังไม่สำเร็จ");
  });
}
