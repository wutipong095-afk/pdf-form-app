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
  const browseBtn = $("libbrowse") as HTMLButtonElement;
  if (!st.open_folder_enabled) {
    openBtn.style.display = "none";
    openFileBtn.style.display = "none";
    browseBtn.style.display = "none";
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
  if (!st.count) {
    setStatus(
      "คลังยังว่าง — กดเปิดรากใน Explorer แล้วใส่ไฟล์ .pdf จากนั้นกดสแกนใหม่ หรือกดเลือกโฟลเดอร์… ที่มี PDF อยู่แล้ว",
    );
    return;
  }
  setStatus(
    `คลัง: ${st.count} ไฟล์` +
      (st.scanned_at ? ` · สแกนล่าสุด ${new Date(st.scanned_at * 1000).toLocaleString()}` : ""),
  );
}

function statusAfterScan(count: number, extra = "", seeded?: string | null): void {
  if (seeded) {
    setStatus(`ใส่ตัวอย่าง ${seeded} ให้แล้ว · ${count} ไฟล์ — เลือกจากรายการด้านขวาได้เลย${extra}`);
    return;
  }
  if (!count) {
    setStatus(
      "ยังไม่มีไฟล์ PDF ในโฟลเดอร์นี้ — กดเปิดรากใน Explorer คัดลอก .pdf เข้าไป แล้วกดสแกนใหม่" +
        extra,
    );
    return;
  }
  setStatus(`${count} ไฟล์ในคลัง — เลือกจากรายการเพื่อเปิด` + extra);
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

  $("libbrowse").onclick = async () => {
    const cur = ($("libroot") as HTMLInputElement).value.trim();
    try {
      const res = await apiJson<{ ok?: boolean; cancelled?: boolean; path?: string | null }>(
        "/api/library/browse",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ initial: cur }),
        },
      );
      if (res.cancelled || !res.path) {
        setStatus("ยกเลิกเลือกโฟลเดอร์");
        return;
      }
      ($("libroot") as HTMLInputElement).value = res.path;
      $("libset").click();
    } catch (e) {
      alert(e instanceof Error ? e.message : "เลือกโฟลเดอร์ไม่สำเร็จ");
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
          ? ` · สร้างโฟลเดอร์: ${res.scaffold_created.join(", ")}`
          : "";
      statusAfterScan(res.count, extra, res.seeded_demo);
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
