/** ผลของการสร้าง PDF ที่แสดงใต้ปุ่ม — ลิงก์ไฟล์ และคำเตือนถ้ามีหมุดตกขอบ */
import { $ } from "./dom";
import { t } from "./i18n";
import type { FillResponse } from "./types";

export function renderFillResult(r: FillResponse): void {
  const box = $("result");
  box.replaceChildren(t("app.donePrefix"));

  const link = document.createElement("a");
  link.href = "/download/" + encodeURIComponent(r.file || "");
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = t("app.openFile", { file: r.file || "" });
  box.appendChild(link);

  if (r.orphan_pins) {
    // ฟอร์มมีหน้าน้อยกว่าตอนที่มาร์คจุดไว้ — ค่าบางช่องไม่ได้ลงใน PDF
    // ครูต้องรู้ก่อนเอาไปเสนอเซ็น ไม่ใช่มารู้ตอนถูกตีกลับ
    const warn = document.createElement("div");
    warn.className = "fillwarn";
    warn.textContent = t("hist.orphanPins", { count: r.orphan_pins });
    box.appendChild(warn);
  }
}
