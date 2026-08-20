/** แถบงานเก่า — สิ่งที่ผู้ใช้เห็นและกดได้ในลิสต์ */
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiJson: vi.fn(),
  loadDoc: vi.fn(),
  clearChat: vi.fn(),
  openSheet: vi.fn(),
  duplicateSheet: vi.fn(),
  deleteSheet: vi.fn(),
  relinkSheet: vi.fn(),
  renameSheet: vi.fn(),
  importSheet: vi.fn(),
  clearActiveSheet: vi.fn(),
}));

vi.mock("./api", () => ({ apiJson: mocks.apiJson }));
vi.mock("./viewer", () => ({ loadDoc: mocks.loadDoc }));
vi.mock("./chat", () => ({ clearChat: mocks.clearChat }));
vi.mock("./sheets", () => ({
  openSheet: mocks.openSheet,
  duplicateSheet: mocks.duplicateSheet,
  deleteSheet: mocks.deleteSheet,
  relinkSheet: mocks.relinkSheet,
  renameSheet: mocks.renameSheet,
  importSheet: mocks.importSheet,
  clearActiveSheet: mocks.clearActiveSheet,
}));
vi.mock("./i18n", () => ({
  t: (key: string, vars?: Record<string, unknown>) =>
    vars ? `${key} ${Object.values(vars).join(" ")}` : key,
}));

type History = typeof import("./history");
let history: History;

const onMarkers = vi.fn();
const onRender = vi.fn();

function sheetRow(over: Record<string, unknown> = {}) {
  return {
    kind: "sheet",
    name: "ใบเบิก-20260819.json",
    sheet: "ใบเบิก-20260819.json",
    stem: "ใบเบิก-20260819",
    title: "ใบเบิก — สมชาย",
    group: "ใบเบิก",
    mtime: 1_760_000_000,
    size: 900,
    doc_id: "@form.aaa",
    printed: false,
    filled: 2,
    pins: 3,
    source_name: "ใบเบิก.pdf",
    source_present: true,
    source_changed: false,
    ...over,
  };
}

function pdfRow() {
  return {
    kind: "pdf",
    name: "ใบเบิก-20260819.pdf",
    stem: "ใบเบิก-20260819",
    group: "ใบเบิก",
    mtime: 1_760_000_000,
    size: 90_000,
    doc_id: "@out.ใบเบิก-20260819.pdf",
  };
}

function mountDom(): void {
  document.body.innerHTML = `
    <div id="histbar"></div>
    <button id="btn-hist-toggle"></button>
    <button id="histhide"></button>
    <button id="histopen"></button>
    <button id="histopenfile"></button>
    <button id="histimport"></button>
    <input type="file" id="histimportfile">
    <input type="text" id="histsearch" value="">
    <span id="histstatus"></span>
    <div id="histlist"></div>
    <select id="docsel"></select>
    <select id="tplsel"></select>
  `;
}

async function showRows(rows: unknown[]): Promise<void> {
  mocks.apiJson.mockResolvedValue({
    count: rows.length,
    truncated: false,
    files: rows,
    open_folder_enabled: true,
  });
  await history.refreshHistory();
}

function rowFor(title: string): HTMLElement {
  const el = [...document.querySelectorAll<HTMLElement>(".pick-row")].find((r) =>
    (r.textContent || "").includes(title),
  );
  if (!el) throw new Error(`ไม่พบแถว ${title}`);
  return el;
}

function actions(row: HTMLElement): string[] {
  return [...row.querySelectorAll<HTMLButtonElement>("button[data-act]")].map(
    (b) => b.dataset.act || "",
  );
}

beforeEach(async () => {
  vi.resetModules();
  vi.clearAllMocks();
  mountDom();
  history = await import("./history");
  history.bindHistory(onMarkers, onRender);
  // ตัวจัดการคลิกกลืน error ลง alert — ทำให้มันดังขึ้นมา ไม่งั้นเทสผ่านทั้งที่พัง
  vi.stubGlobal("alert", (m: string) => {
    throw new Error("UNEXPECTED_ALERT: " + m);
  });
});

describe("ลิสต์งานเก่า", () => {
  it("บอกว่าใบงานมาจากฟอร์มไหน", async () => {
    await showRows([sheetRow()]);
    const row = rowFor("ใบเบิก — สมชาย");
    expect(row.textContent).toContain("hist.fromForm ใบเบิก.pdf");
    expect(row.textContent).toContain("2/3");
    expect(row.textContent).toContain("hist.draftTag");
  });

  it("ปุ่มทุกปุ่มมีข้อความกำกับ ไม่ใช่สัญลักษณ์ล้วน", async () => {
    await showRows([sheetRow({ source_changed: true })]);
    const buttons = [
      ...rowFor("ใบเบิก — สมชาย").querySelectorAll<HTMLButtonElement>("button[data-act]"),
    ];
    expect(buttons.length).toBe(5);
    for (const b of buttons) {
      const label = b.querySelector(".lbl");
      // ⧉ ⤓ ⟳ เดาไม่ออกถ้าไม่มีคำกำกับ และบนแท็บเล็ตจ่อเมาส์ดู title ไม่ได้
      expect(label, `ปุ่ม ${b.dataset.act} ไม่มีข้อความ`).not.toBeNull();
      expect((label!.textContent || "").length).toBeGreaterThan(0);
      expect(b.title.length).toBeGreaterThan(0);
    }
  });

  it("ฟอร์มต้นฉบับเปลี่ยน → เตือนและมีปุ่มให้ย้าย", async () => {
    await showRows([sheetRow({ source_changed: true })]);
    const row = rowFor("ใบเบิก — สมชาย");
    expect(row.textContent).toContain("hist.formChanged");
    expect(actions(row)).toEqual(["relink", "rename", "dup", "export", "del"]);
  });

  it("ฟอร์มไม่เปลี่ยน → ไม่มีปุ่มย้าย", async () => {
    await showRows([sheetRow()]);
    expect(actions(rowFor("ใบเบิก — สมชาย"))).toEqual(["rename", "dup", "export", "del"]);
  });

  it("ฟอร์มต้นฉบับหายไป → บอกไว้ แต่ยังไม่ชวนให้ย้าย", async () => {
    await showRows([sheetRow({ source_present: false })]);
    const row = rowFor("ใบเบิก — สมชาย");
    expect(row.textContent).toContain("hist.sourceGone");
    expect(actions(row)).not.toContain("relink");
  });

  it("PDF ที่พิมพ์แล้วดูได้อย่างเดียว ไม่มีปุ่มจัดการใบงาน", async () => {
    await showRows([pdfRow()]);
    expect(actions(rowFor("ใบเบิก-20260819.pdf"))).toEqual([]);
  });
});

describe("ปุ่มในแถว", () => {
  it("ถามก่อนลบ และไม่ลบถ้าผู้ใช้ยกเลิก", async () => {
    const confirmSpy = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirmSpy);
    await showRows([sheetRow()]);

    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>('[data-act="del"]')!.click();
    await vi.waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    expect(mocks.deleteSheet).not.toHaveBeenCalled();
  });

  it("ย้ายไปฟอร์มใหม่เมื่อผู้ใช้ยืนยัน", async () => {
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    mocks.relinkSheet.mockResolvedValue({ sheet: "ใบเบิก-20260819.json" });
    await showRows([sheetRow({ source_changed: true })]);

    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>('[data-act="relink"]')!.click();
    await vi.waitFor(() =>
      expect(mocks.relinkSheet).toHaveBeenCalledWith(
        "ใบเบิก-20260819.json",
        onMarkers,
        onRender,
      ),
    );
  });

  it("คลิกแถวใบงาน → เปิดใบนั้น", async () => {
    mocks.openSheet.mockResolvedValue(undefined);
    await showRows([sheetRow()]);

    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>(".pick-item")!.click();
    await vi.waitFor(() =>
      expect(mocks.openSheet).toHaveBeenCalledWith("ใบเบิก-20260819.json", onMarkers, onRender),
    );
    expect(mocks.loadDoc).not.toHaveBeenCalled();
  });

  it("คลิกแถว PDF → เปิดเป็นเอกสารและล้างจอ ไม่ใช่เปิดเป็นใบงาน", async () => {
    const { state } = await import("./state");
    state.fields = [{ name: "ก", page: 0, x: 1, y: 2, size: 14, value: "ค่าเก่า" }];
    await showRows([pdfRow()]);

    rowFor("ใบเบิก-20260819.pdf").querySelector<HTMLButtonElement>(".pick-item")!.click();
    await vi.waitFor(() =>
      expect(mocks.loadDoc).toHaveBeenCalledWith("@out.ใบเบิก-20260819.pdf", onMarkers),
    );
    // ส่วนที่เคยพังเงียบ ๆ เพราะ error ถูกกลืนลง alert
    expect(mocks.clearActiveSheet).toHaveBeenCalled();
    expect(mocks.clearChat).toHaveBeenCalled();
    expect(state.fields).toEqual([]);
    expect(onRender).toHaveBeenCalled();
    expect(mocks.openSheet).not.toHaveBeenCalled();
  });

  it("เปลี่ยนชื่อใบงาน — เติมชื่อเดิมไว้ให้แก้", async () => {
    const promptSpy = vi.fn().mockReturnValue("ใบเบิก ส่งเขต");
    vi.stubGlobal("prompt", promptSpy);
    mocks.renameSheet.mockResolvedValue({ sheet: "ใบเบิก-20260819.json" });
    await showRows([sheetRow()]);

    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>('[data-act="rename"]')!.click();
    await vi.waitFor(() =>
      expect(mocks.renameSheet).toHaveBeenCalledWith("ใบเบิก-20260819.json", "ใบเบิก ส่งเขต"),
    );
    expect(promptSpy.mock.calls[0][1]).toBe("ใบเบิก — สมชาย");
  });

  it("ยกเลิกหรือใส่ชื่อว่าง แล้วไม่เปลี่ยนอะไร", async () => {
    vi.stubGlobal("prompt", vi.fn().mockReturnValue(null));
    await showRows([sheetRow()]);
    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>('[data-act="rename"]')!.click();

    vi.stubGlobal("prompt", vi.fn().mockReturnValue("   "));
    rowFor("ใบเบิก — สมชาย").querySelector<HTMLButtonElement>('[data-act="rename"]')!.click();

    await new Promise((r) => setTimeout(r, 10));
    expect(mocks.renameSheet).not.toHaveBeenCalled();
  });
});


describe("นำเข้า .formdd", () => {
  function choose(name: string): void {
    const input = document.getElementById("histimportfile") as HTMLInputElement;
    // jsdom ไม่มี DataTransfer — วาง FileList จำลองลงไปตรง ๆ
    const file = new File([new Uint8Array([80, 75])], name);
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change"));
  }

  it("ปุ่มนำเข้าเปิดหน้าต่างเลือกไฟล์", () => {
    const input = document.getElementById("histimportfile") as HTMLInputElement;
    const click = vi.spyOn(input, "click").mockImplementation(() => undefined);
    (document.getElementById("histimport") as HTMLButtonElement).click();
    expect(click).toHaveBeenCalled();
  });

  it("ไฟล์ที่ไม่ใช่ .formdd ถูกปฏิเสธตั้งแต่ฝั่งเบราว์เซอร์", async () => {
    const alertSpy = vi.fn();
    vi.stubGlobal("alert", alertSpy);
    choose("ใบเบิก.pdf");
    await vi.waitFor(() => expect(alertSpy).toHaveBeenCalledWith("hist.importWrongType"));
    expect(mocks.importSheet).not.toHaveBeenCalled();
  });

  it("ไฟล์ .formdd ถูกส่งไปนำเข้า", async () => {
    mocks.importSheet.mockResolvedValue({ sheet: "ใหม่.json", title: "ใบเบิก — สมชาย" });
    mocks.apiJson.mockResolvedValue({ count: 0, truncated: false, files: [], open_folder_enabled: true });
    choose("ใบเบิก.formdd");
    await vi.waitFor(() => expect(mocks.importSheet).toHaveBeenCalled());
    expect((mocks.importSheet.mock.calls[0][0] as File).name).toBe("ใบเบิก.formdd");
  });

  it("ไฟล์ .fromdd ของรุ่นก่อนเปลี่ยนชื่อยังนำเข้าได้", async () => {
    mocks.importSheet.mockResolvedValue({ sheet: "ใหม่.json", title: "ใบเบิก" });
    mocks.apiJson.mockResolvedValue({ count: 0, truncated: false, files: [], open_folder_enabled: true });
    choose("ใบเบิก.fromdd");
    await vi.waitFor(() => expect(mocks.importSheet).toHaveBeenCalled());
    expect((mocks.importSheet.mock.calls[0][0] as File).name).toBe("ใบเบิก.fromdd");
  });
});
