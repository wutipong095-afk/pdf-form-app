import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { t } from "./i18n";
import type { LicenseActivateResponse, LicenseStatus } from "./types";

export function renderLicense(st: LicenseStatus | null | undefined): void {
  const lic = st || ({} as LicenseStatus);
  state.lic = lic;
  const bar = $("licbar");
  const form = $("licform");
  $("licmid").textContent = lic.machine_id || "—";
  $("licmsg").textContent = lic.message || "";
  if (lic.licensed) {
    bar.className = "ok";
    form.style.display = "none";
  } else {
    bar.className = "warn";
    form.style.display = "flex";
  }
}

export async function activateLicense(key: string): Promise<LicenseActivateResponse> {
  const res = await api("/api/license", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  const data = (await res.json()) as LicenseActivateResponse;
  if (!res.ok || !data.licensed) {
    throw new Error(data.error || data.message || t("lic.activateFail"));
  }
  return data;
}

export function bindLicenseUi(): void {
  $("licactivate").onclick = async () => {
    const key = ($("lickey") as HTMLInputElement).value.trim();
    if (!key) {
      alert(t("lic.needKey"));
      return;
    }
    try {
      const r = await activateLicense(key);
      renderLicense(r);
      alert(t("lic.activateOk"));
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lic.activateFail"));
    }
  };
}
