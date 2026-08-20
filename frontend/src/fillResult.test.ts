/** ผลหลังกดสร้าง PDF — ถ้ามีช่องที่พิมพ์ไม่ลง ต้องบอก ไม่ใช่ยื่นลิงก์เฉย ๆ */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./i18n", () => ({
  t: (key: string, vars?: Record<string, unknown>) =>
    vars ? `${key} ${Object.values(vars).join(" ")}` : key,
}));

type FillResult = typeof import("./fillResult");
let mod: FillResult;

beforeEach(async () => {
  vi.resetModules();
  document.body.innerHTML = '<div id="result"></div>';
  mod = await import("./fillResult");
});

function box(): HTMLElement {
  return document.getElementById("result")!;
}

describe("ผลการสร้าง PDF", () => {
  it("ปกติ — มีลิงก์ดาวน์โหลด ไม่มีคำเตือน", () => {
    mod.renderFillResult({ ok: true, file: "ใบลา-20260820.pdf" });

    const link = box().querySelector("a")!;
    expect(link.getAttribute("href")).toBe("/download/" + encodeURIComponent("ใบลา-20260820.pdf"));
    expect(link.target).toBe("_blank");
    expect(box().querySelector(".fillwarn")).toBeNull();
  });

  it("มีหมุดตกขอบ — เตือนข้างลิงก์ พร้อมจำนวนจุด", () => {
    mod.renderFillResult({ ok: true, file: "ใบเบิก.pdf", orphan_pins: 2 });

    const warn = box().querySelector(".fillwarn");
    expect(warn).not.toBeNull();
    // ใช้ข้อความเดียวกับตอนย้ายฟอร์ม จะได้ไม่ต้องเรียนสองแบบ
    expect(warn!.textContent).toContain("hist.orphanPins");
    expect(warn!.textContent).toContain("2");
    // ลิงก์ต้องยังอยู่ — PDF สร้างสำเร็จ แค่ขาดบางช่อง
    expect(box().querySelector("a")).not.toBeNull();
  });

  it("orphan_pins = 0 ถือว่าไม่มีปัญหา", () => {
    mod.renderFillResult({ ok: true, file: "ก.pdf", orphan_pins: 0 });
    expect(box().querySelector(".fillwarn")).toBeNull();
  });

  it("สร้างใหม่แล้วคำเตือนเก่าต้องหายไป", () => {
    mod.renderFillResult({ ok: true, file: "ก.pdf", orphan_pins: 3 });
    expect(box().querySelector(".fillwarn")).not.toBeNull();

    mod.renderFillResult({ ok: true, file: "ข.pdf" });
    expect(box().querySelector(".fillwarn")).toBeNull();
    expect(box().querySelectorAll("a").length).toBe(1);
  });
});
