/** Update notice from latest.json — offline-safe; verify SHA-256 before running Setup */
import { ApiError, apiJson } from "./api";
import { t } from "./i18n";

type UpdateCheck = {
  current?: string;
  update_available?: boolean;
  disabled?: boolean;
  offline?: boolean;
  latest?: string | null;
  setup_url?: string | null;
  sha256?: string | null;
  size?: number | null;
  notes?: string | null;
};

const DISMISS_PREFIX = "pdfmarker_dismiss_update_";

function dismissedKey(latest: string): string {
  return DISMISS_PREFIX + latest;
}

function isDismissed(latest: string): boolean {
  try {
    return localStorage.getItem(dismissedKey(latest)) === "1";
  } catch {
    return false;
  }
}

function setDismissed(latest: string): void {
  try {
    localStorage.setItem(dismissedKey(latest), "1");
  } catch {
    /* ignore */
  }
}

function hideBar(): void {
  const bar = document.getElementById("updbar");
  if (bar) bar.classList.remove("show");
}

function showBar(info: UpdateCheck): void {
  const bar = document.getElementById("updbar");
  const msg = document.getElementById("updmsg");
  const link = document.getElementById("updlink") as HTMLAnchorElement | null;
  const installBtn = document.getElementById("updinstall") as HTMLButtonElement | null;
  if (!bar || !msg || !info.latest) return;

  const notes = info.notes ? ` — ${info.notes}` : "";
  msg.textContent = t("upd.msg", {
    latest: info.latest,
    current: info.current || "?",
    notes,
  });

  const url = (info.setup_url || "").trim();
  const canVerify = Boolean(url && info.sha256);
  if (link) {
    if (url) {
      link.href = url;
      link.style.display = "";
      link.textContent = t("upd.downloadVer", { latest: info.latest });
    } else {
      link.style.display = "none";
    }
  }
  if (installBtn) {
    installBtn.style.display = canVerify ? "" : "none";
    installBtn.disabled = false;
    installBtn.textContent = t("upd.installVer", { latest: info.latest });
    installBtn.onclick = () => {
      void runVerifiedInstall(installBtn, msg);
    };
  }

  const dismiss = document.getElementById("upddismiss");
  if (dismiss) {
    dismiss.onclick = () => {
      setDismissed(info.latest!);
      hideBar();
    };
  }

  bar.classList.add("show");
}

async function runVerifiedInstall(
  btn: HTMLButtonElement,
  msg: HTMLElement,
): Promise<void> {
  btn.disabled = true;
  const prev = btn.textContent;
  btn.textContent = t("upd.downloading");
  try {
    await apiJson("/api/update-install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    msg.textContent = t("upd.installOk");
    btn.textContent = t("upd.installOk");
  } catch (err) {
    btn.disabled = false;
    btn.textContent = prev || t("upd.install");
    const text = err instanceof ApiError ? err.message : t("api.updateDownloadFail");
    msg.textContent = text;
  }
}

export function bindUpdateCheck(): void {
  void apiJson<UpdateCheck>("/api/update-check")
    .then((info) => {
      if (!info.update_available || !info.latest) return;
      if (isDismissed(info.latest)) return;
      showBar(info);
    })
    .catch(() => {
      /* offline / no feed — silent */
    });
}
