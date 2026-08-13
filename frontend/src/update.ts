/** Update notice from latest.json — offline-safe */
import { apiJson } from "./api";
import { t } from "./i18n";

type UpdateCheck = {
  current?: string;
  update_available?: boolean;
  disabled?: boolean;
  offline?: boolean;
  latest?: string | null;
  setup_url?: string | null;
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
  const openBtn = document.getElementById("updopen") as HTMLButtonElement | null;
  if (!bar || !msg || !info.latest) return;

  const notes = info.notes ? ` — ${info.notes}` : "";
  msg.textContent = t("upd.msg", {
    latest: info.latest,
    current: info.current || "?",
    notes,
  });

  const url = (info.setup_url || "").trim();
  if (link) {
    if (url) {
      link.href = url;
      link.style.display = "";
      link.textContent = t("upd.downloadVer", { latest: info.latest });
    } else {
      link.style.display = "none";
    }
  }
  if (openBtn) {
    openBtn.style.display = url ? "" : "none";
    openBtn.onclick = () => {
      if (url) window.open(url, "_blank", "noopener");
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
