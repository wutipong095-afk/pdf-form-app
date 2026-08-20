/** โฟลเดอร์เก็บงาน — ให้ผู้ใช้เลือกเองว่าใบงานจะไปอยู่ที่ไหน */
import { $ } from "./dom";
import { apiJson } from "./api";
import { t } from "./i18n";

export type WorkDirStatus = {
  path: string;
  default_path: string;
  custom: boolean;
  unavailable: boolean;
  configured_path?: string;
  moved?: number;
};

type BrowseJob = { job_id?: string; pending?: boolean; cancelled?: boolean; path?: string };

let current: WorkDirStatus | null = null;

function render(st: WorkDirStatus): void {
  current = st;
  const label = $("workdirlabel");
  label.textContent = st.custom ? t("work.label", { path: st.path }) : t("work.default");
  label.classList.toggle("warn", st.unavailable);
  if (st.unavailable) {
    label.textContent = t("work.unavailable", { path: st.path });
  }
  label.title = st.path;
  ($("workdirreset") as HTMLButtonElement).hidden = !st.custom;
}

export async function refreshWorkDir(): Promise<void> {
  try {
    render(await apiJson<WorkDirStatus>("/api/workdir"));
  } catch {
    // แถบนี้ไม่ใช่ของจำเป็นต่อการใช้งาน — เงียบไว้ดีกว่าขึ้น error กวน
  }
}

/** เปิดกล่องเลือกโฟลเดอร์ของ Windows แล้วรอผล */
async function pickFolder(initial: string): Promise<string | null> {
  const start = await apiJson<BrowseJob>("/api/workdir/browse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initial }),
  });
  if (!start.job_id) return null;
  for (let i = 0; i < 600; i++) {
    await new Promise((r) => setTimeout(r, 500));
    const st = await apiJson<BrowseJob>("/api/workdir/browse/" + encodeURIComponent(start.job_id));
    if (st.pending) continue;
    return st.cancelled ? null : st.path || null;
  }
  return null;
}

async function apply(body: Record<string, unknown>): Promise<void> {
  const st = await apiJson<WorkDirStatus>("/api/workdir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  render(st);
  alert(t("work.movedOk", { path: st.path, moved: st.moved ?? 0 }));
}

export function bindWorkDir(onMoved: () => void): void {
  const pick = $("workdirpick") as HTMLButtonElement;
  const reset = $("workdirreset") as HTMLButtonElement;
  const open = $("workdiropen") as HTMLButtonElement;

  pick.onclick = async () => {
    const was = pick.textContent;
    pick.disabled = true;
    pick.textContent = t("work.picking");
    try {
      const chosen = await pickFolder(current?.path || "");
      if (chosen) {
        await apply({ path: chosen });
        onMoved();
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : t("work.fail"));
    } finally {
      pick.disabled = false;
      pick.textContent = was;
    }
  };

  reset.onclick = async () => {
    if (!confirm(t("work.resetAsk"))) return;
    try {
      await apply({ reset: true });
      onMoved();
    } catch (e) {
      alert(e instanceof Error ? e.message : t("work.fail"));
    }
  };

  open.onclick = async () => {
    try {
      await apiJson("/api/open-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ which: "work" }),
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : t("work.fail"));
    }
  };

  void refreshWorkDir();
}
