/** ปุ่มโหมดโรงเรียน: เปิดโฟลเดอร์ / สร้างรายงานปัญหา */
import { api } from "./api";

async function openFolder(which: string): Promise<void> {
  const res = await api("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ which }),
  });
  const data = (await res.json()) as { error?: string };
  if (!res.ok) {
    alert(data.error || "เปิดโฟลเดอร์ไม่สำเร็จ");
  }
}

async function downloadSupportReport(): Promise<void> {
  const res = await api("/api/support-report", { method: "POST" });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { error?: string };
    alert(data.error || "สร้างรายงานไม่สำเร็จ");
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
  const dataBtn = document.getElementById("btn-open-data");
  const outBtn = document.getElementById("btn-open-output");
  const reportBtn = document.getElementById("btn-support-report");
  if (dataBtn) dataBtn.addEventListener("click", () => void openFolder("data"));
  if (outBtn) outBtn.addEventListener("click", () => void openFolder("output"));
  if (reportBtn) reportBtn.addEventListener("click", () => void downloadSupportReport());

  // ซ่อนปุ่มออกจากระบบเมื่อโหมดโรงเรียน (ไม่มี login)
  const logoutForm = document.getElementById("logout-form");
  const who = document.getElementById("who");
  void api("/api/me")
    .then((r) => r.json())
    .then(
      (me: {
        auth_required?: boolean;
        open_folder_enabled?: boolean;
        user?: string;
        version?: string;
      }) => {
        if (!me.auth_required && logoutForm) {
          logoutForm.style.display = "none";
        }
        if (!me.open_folder_enabled) {
          if (dataBtn) dataBtn.style.display = "none";
          if (outBtn) outBtn.style.display = "none";
        }
        if (who && me.user) {
          who.textContent = me.auth_required ? me.user : "เครื่องนี้";
        }
        const ver = document.getElementById("appver");
        if (ver && me.version) ver.textContent = "v" + me.version;
      },
    )
    .catch(() => {
      /* ignore */
    });
}
