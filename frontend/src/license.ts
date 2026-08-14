import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { t } from "./i18n";
import type { LicenseActivateResponse, LicenseStatus } from "./types";

function setDisplay(id: string, show: boolean): void {
  const el = document.getElementById(id);
  if (el) el.style.display = show ? "" : "none";
}

function closeLibraryBar(): void {
  const bar = document.getElementById("libbar");
  const btn = document.getElementById("btn-lib-toggle");
  if (bar) {
    bar.classList.remove("open");
    bar.setAttribute("aria-hidden", "true");
  }
  if (btn) {
    btn.classList.remove("active");
    btn.setAttribute("aria-expanded", "false");
    btn.textContent = t("header.library");
  }
}

function applyTrialLock(lic: LicenseStatus): void {
  const locked = !lic.licensed;
  setDisplay("upfile", !locked);
  setDisplay("btn-lib-toggle", !locked);
  setDisplay("btn-formpack", !locked);
  const hint = document.getElementById("lictrial");
  if (hint) hint.hidden = !locked;
  if (locked) closeLibraryBar();
}

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
  applyTrialLock(lic);
}

async function copyMachineId(): Promise<void> {
  const mid = ($("licmid").textContent || "").trim();
  if (!mid || mid === "—") return;
  try {
    await navigator.clipboard.writeText(mid);
    alert(t("lic.copied"));
  } catch {
    alert(t("lic.copyFail"));
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

export function bindLicenseUi(onActivated?: () => void): void {
  $("licactivate").onclick = async () => {
    const key = ($("lickey") as HTMLInputElement).value.trim();
    if (!key) {
      alert(t("lic.needKey"));
      return;
    }
    try {
      const r = await activateLicense(key);
      renderLicense(r);
      onActivated?.();
      alert(t("lic.activateOk"));
    } catch (e) {
      alert(e instanceof Error ? e.message : t("lic.activateFail"));
    }
  };
  const copyBtn = document.getElementById("liccopy");
  if (copyBtn) copyBtn.addEventListener("click", () => void copyMachineId());
}
