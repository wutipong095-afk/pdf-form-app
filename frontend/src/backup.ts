/** สำรอง / กู้คืน / เทมเพลตเดี่ยว / แพ็กฟอร์ม */
import { $ } from "./dom";
import { api, apiJson } from "./api";
import { refreshDocs } from "./docs";

async function downloadBlob(res: Response, fallbackName: string): Promise<void> {
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error || "ดาวน์โหลดไม่สำเร็จ");
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename="?([^";]+)"?/i.exec(cd);
  const name = m?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

async function doBackup(): Promise<void> {
  const res = await api("/api/backup", { method: "POST" });
  await downloadBlob(res, "pdfmarker-backup.zip");
}

async function doRestore(
  file: File,
  mode: "merge" | "replace",
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  const data = await apiJson<{
    written?: number;
    skipped?: number;
    note_th?: string;
  }>("/api/restore?mode=" + encodeURIComponent(mode), {
    method: "POST",
    body: fd,
  });
  await refreshDocs(onMarkers, onRender);
  alert(
    `กู้คืนแล้ว (${mode})\nเขียน ${data.written ?? 0} ไฟล์ · ข้าม ${data.skipped ?? 0}\n` +
      (data.note_th || ""),
  );
}

async function exportTemplate(): Promise<void> {
  const name = ($("tplname") as HTMLInputElement).value.trim() || ($("tplsel") as HTMLSelectElement).value;
  if (!name) {
    alert("เลือกหรือตั้งชื่อเทมเพลตก่อน");
    return;
  }
  const res = await api("/api/template-export/" + encodeURIComponent(name));
  await downloadBlob(res, name + ".tpl.json");
}

async function importTemplate(
  file: File,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  const tryImport = async (overwrite: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    if (overwrite) fd.append("overwrite", "true");
    return apiJson<{ name?: string }>("/api/template-import", {
      method: "POST",
      body: fd,
    });
  };

  let data: { name?: string };
  try {
    data = await tryImport(false);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "นำเข้าไม่สำเร็จ";
    if (msg.includes("อยู่แล้ว") && confirm(msg + "\nทับไฟล์เดิมหรือไม่?")) {
      data = await tryImport(true);
    } else {
      throw e;
    }
  }
  await refreshDocs(onMarkers, onRender);
  if (data.name) ($("tplsel") as HTMLSelectElement).value = data.name;
  alert(`นำเข้าเทมเพลต "${data.name}" แล้ว`);
}

async function installFormpack(onMarkers: () => void, onRender: () => void): Promise<void> {
  const data = await apiJson<{ installed: string[]; skipped: string[] }>("/api/formpack/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: "v1", overwrite: false }),
  });
  await refreshDocs(onMarkers, onRender);
  alert(
    `ติดตั้งแพ็กฟอร์ม v1\nติดตั้ง: ${(data.installed || []).join(", ") || "—"}\nข้าม: ${(data.skipped || []).join(", ") || "—"}`,
  );
}

export function bindBackupUi(onMarkers: () => void, onRender: () => void): void {
  const backupBtn = document.getElementById("btn-backup");
  const restoreBtn = document.getElementById("btn-restore");
  const restoreFile = document.getElementById("restore-file") as HTMLInputElement | null;
  const exportBtn = document.getElementById("btn-tpl-export");
  const importBtn = document.getElementById("btn-tpl-import");
  const importFile = document.getElementById("tpl-import-file") as HTMLInputElement | null;
  const packBtn = document.getElementById("btn-formpack");

  if (backupBtn) {
    backupBtn.addEventListener("click", () => {
      void doBackup().catch((e) => alert(e instanceof Error ? e.message : "สำรองไม่สำเร็จ"));
    });
  }

  if (restoreBtn && restoreFile) {
    restoreBtn.addEventListener("click", () => restoreFile.click());
    restoreFile.addEventListener("change", () => {
      const file = restoreFile.files?.[0];
      restoreFile.value = "";
      if (!file) return;
      const merge = confirm(
        "กู้คืนจาก ZIP แบบรวมกับของเดิม?\n\nตกลง = รวม (ไม่ทับไฟล์ที่มี)\nยกเลิก = เลือกโหมดอื่น",
      );
      let mode: "merge" | "replace" = "merge";
      if (!merge) {
        if (!confirm("ใช้โหมดแทนที่?\nจะล้าง uploads / templates / output ของผู้ใช้แล้วแตกจาก ZIP")) {
          return;
        }
        mode = "replace";
      }
      void doRestore(file, mode, onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : "กู้คืนไม่สำเร็จ"),
      );
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      void exportTemplate().catch((e) => alert(e instanceof Error ? e.message : "ส่งออกไม่สำเร็จ"));
    });
  }

  if (importBtn && importFile) {
    importBtn.addEventListener("click", () => importFile.click());
    importFile.addEventListener("change", () => {
      const file = importFile.files?.[0];
      importFile.value = "";
      if (!file) return;
      void importTemplate(file, onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : "นำเข้าไม่สำเร็จ"),
      );
    });
  }

  if (packBtn) {
    packBtn.addEventListener("click", () => {
      if (!confirm("ติดตั้งแพ็กฟอร์มโรงเรียน v1 (ใบเบิก / จัดซื้อ / เดินทาง)?")) return;
      void installFormpack(onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : "ติดตั้งแพ็กไม่สำเร็จ"),
      );
    });
  }
}
