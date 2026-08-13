/** School-mode buttons: open folders / support report */
import { api, apiJson } from "./api";
import { bindUpdateCheck } from "./update";
import { t } from "./i18n";

type MeResponse = {
  auth_required?: boolean;
  open_folder_enabled?: boolean;
  user?: string;
  version?: string;
};

async function openFolder(which: string): Promise<void> {
  try {
    await apiJson<{ ok?: boolean }>("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ which }),
    });
  } catch (e) {
    alert(e instanceof Error ? e.message : t("school.openFolderFail"));
  }
}

async function downloadSupportReport(): Promise<void> {
  const res = await api("/api/support-report", { method: "POST" });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { error?: string };
    alert(data.error || t("school.reportFail"));
    return;
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename="?([^";]+)"?/i.exec(cd);
  const name = m?.[1] || "report.zip";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function bindSchoolUi(): void {
  const outBtn = document.getElementById("btn-open-output");
  const reportBtn = document.getElementById("btn-support-report");
  if (outBtn) outBtn.addEventListener("click", () => void openFolder("output"));
  if (reportBtn) reportBtn.addEventListener("click", () => void downloadSupportReport());

  const logoutForm = document.getElementById("logout-form");
  const who = document.getElementById("who");
  void apiJson<MeResponse>("/api/me")
    .then((me) => {
      if (!me.auth_required && logoutForm) {
        logoutForm.style.display = "none";
      }
      if (!me.open_folder_enabled && outBtn) {
        outBtn.style.display = "none";
      }
      if (who && me.user) {
        who.textContent = me.auth_required ? me.user : t("header.thisMachine");
      }
      const ver = document.getElementById("appver");
      if (ver && me.version) ver.textContent = "v" + me.version;
    })
    .catch(() => {
      /* ignore */
    });

  bindUpdateCheck();
}
