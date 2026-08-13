/** Backup / restore / single template / form pack */
import { $ } from "./dom";
import { api, apiJson } from "./api";
import { refreshDocs } from "./docs";
import { t } from "./i18n";

async function downloadBlob(res: Response, fallbackName: string): Promise<void> {
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error || t("bak.downloadFail"));
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
    note?: string;
    note_th?: string;
  }>("/api/restore?mode=" + encodeURIComponent(mode), {
    method: "POST",
    body: fd,
  });
  await refreshDocs(onMarkers, onRender);
  alert(
    t("bak.restoreOk", {
      mode,
      written: data.written ?? 0,
      skipped: data.skipped ?? 0,
      note: data.note || data.note_th || "",
    }),
  );
}

async function exportTemplate(): Promise<void> {
  const name = ($("tplname") as HTMLInputElement).value.trim() || ($("tplsel") as HTMLSelectElement).value;
  if (!name) {
    alert(t("bak.needTplName"));
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
    const msg = e instanceof Error ? e.message : t("bak.importFail");
    const conflict = /อยู่แล้ว|already exists/i.test(msg);
    if (conflict && confirm(t("bak.importOverwriteAsk", { msg }))) {
      data = await tryImport(true);
    } else {
      throw e;
    }
  }
  await refreshDocs(onMarkers, onRender);
  if (data.name) ($("tplsel") as HTMLSelectElement).value = data.name;
  alert(t("bak.importOk", { name: data.name || "" }));
}

async function installFormpack(onMarkers: () => void, onRender: () => void): Promise<void> {
  const data = await apiJson<{ installed: string[]; skipped: string[] }>("/api/formpack/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: "v1", overwrite: false }),
  });
  await refreshDocs(onMarkers, onRender);
  alert(
    t("bak.formpackOk", {
      installed: (data.installed || []).join(", ") || "—",
      skipped: (data.skipped || []).join(", ") || "—",
    }),
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
      void doBackup().catch((e) => alert(e instanceof Error ? e.message : t("bak.backupFail")));
    });
  }

  if (restoreBtn && restoreFile) {
    restoreBtn.addEventListener("click", () => restoreFile.click());
    restoreFile.addEventListener("change", () => {
      const file = restoreFile.files?.[0];
      restoreFile.value = "";
      if (!file) return;
      const merge = confirm(t("bak.restoreMergeAsk"));
      let mode: "merge" | "replace" = "merge";
      if (!merge) {
        if (!confirm(t("bak.restoreReplaceAsk"))) {
          return;
        }
        mode = "replace";
      }
      void doRestore(file, mode, onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : t("bak.restoreFail")),
      );
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      void exportTemplate().catch((e) => alert(e instanceof Error ? e.message : t("bak.exportFail")));
    });
  }

  if (importBtn && importFile) {
    importBtn.addEventListener("click", () => importFile.click());
    importFile.addEventListener("change", () => {
      const file = importFile.files?.[0];
      importFile.value = "";
      if (!file) return;
      void importTemplate(file, onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : t("bak.importFail")),
      );
    });
  }

  if (packBtn) {
    packBtn.addEventListener("click", () => {
      if (!confirm(t("bak.formpackAsk"))) return;
      void installFormpack(onMarkers, onRender).catch((e) =>
        alert(e instanceof Error ? e.message : t("bak.formpackFail")),
      );
    });
  }
}
