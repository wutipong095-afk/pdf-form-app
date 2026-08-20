/**
 * ใบงานฝั่งเบราว์เซอร์ — คุมพฤติกรรมที่พังมาแล้วจริงในรีวิวสามรอบ
 *
 * ทุกเคสในไฟล์นี้มาจากบั๊กที่หลุดออกไปแล้วครั้งหนึ่ง ไม่ใช่เคสสมมติ
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  loadDoc: vi.fn(),
  closeDoc: vi.fn(),
  apiJson: vi.fn(),
  clearChat: vi.fn(),
}));

vi.mock("./viewer", () => ({ loadDoc: mocks.loadDoc, closeDoc: mocks.closeDoc }));
vi.mock("./api", () => ({ apiJson: mocks.apiJson }));
vi.mock("./chat", () => ({ clearChat: mocks.clearChat }));
vi.mock("./i18n", () => ({
  t: (key: string, vars?: Record<string, unknown>) =>
    vars ? `${key} ${Object.values(vars).join(" ")}` : key,
}));

type Sheets = typeof import("./sheets");
type State = typeof import("./state").state;

let sheets: Sheets;
let state: State;

const onMarkers = vi.fn();
const onRender = vi.fn();

function pin(value = "สมชาย") {
  return { name: "ผู้เบิก", page: 0, x: 10, y: 20, size: 14, value };
}

/** ส่วนของหน้าเว็บที่ sheets.ts แตะจริง */
function mountDom(): void {
  document.body.innerHTML = `
    <input id="tplname" value="ใบเบิก">
    <select id="docsel"></select>
    <select id="tplsel"></select>
    <div id="jobstatus"></div>
    <span id="savestate" class="idle"></span>
  `;
}

function sentBody(call = 0): Record<string, unknown> {
  const opts = mocks.apiJson.mock.calls[call][1] as RequestInit;
  return JSON.parse(String(opts.body));
}

beforeEach(async () => {
  vi.resetModules();
  vi.clearAllMocks();
  mountDom();
  mocks.loadDoc.mockResolvedValue(undefined);
  sheets = await import("./sheets");
  state = (await import("./state")).state;
});

describe("การเปิดใบงาน", () => {
  it("ไม่ผูก state.sheet ถ้าเปิดเอกสารไม่สำเร็จ", async () => {
    // ใบที่กำลังแก้อยู่บนจอ
    state.doc = "@form.aaa";
    state.sheet = "กำลังแก้.json";
    state.sourceDoc = "ใบเบิก.pdf";
    state.fields = [pin("ค่าที่ยังไม่ได้เซฟ")];

    mocks.apiJson.mockResolvedValue({ sheet: "เสีย.json", doc_id: "@form.bbb", fields: [] });
    mocks.loadDoc.mockRejectedValue(new Error("not found"));

    await expect(sheets.openSheet("เสีย.json", onMarkers, onRender)).rejects.toThrow();

    // ถ้าค้างเป็น "เสีย.json" ออโต้เซฟรอบถัดไปจะทับใบนั้นด้วยค่าของใบเดิม
    expect(state.sheet).toBeNull();
    expect(state.fields).toEqual([pin("ค่าที่ยังไม่ได้เซฟ")]);
  });

  it("ผูก state หลังเปิดเอกสารผ่านแล้วเท่านั้น", async () => {
    const order: string[] = [];
    mocks.loadDoc.mockImplementation(async () => {
      order.push(`loadDoc:sheet=${String(state.sheet)}`);
    });
    mocks.apiJson.mockResolvedValue({
      sheet: "ใบเบิก.json",
      doc_id: "@form.bbb",
      title: "ใบเบิก — สมชาย",
      source_doc: "ใบเบิก.pdf",
      template_name: "ใบเบิก",
      fields: [pin()],
    });

    await sheets.openSheet("ใบเบิก.json", onMarkers, onRender);

    expect(order).toEqual(["loadDoc:sheet=null"]);
    expect(state.sheet).toBe("ใบเบิก.json");
    expect(state.sourceDoc).toBe("ใบเบิก.pdf");
    expect(state.fields).toEqual([pin()]);
    expect(mocks.clearChat).toHaveBeenCalled();
  });
});

describe("ออโต้เซฟ", () => {
  it("ไม่ส่ง title ตอนอัปเดต — ช่องชื่อเทมเพลตต้องไม่กลายเป็นชื่อใบ", async () => {
    state.doc = "@form.aaa";
    state.sheet = "ใบเบิก.json";
    state.sourceDoc = "ใบเบิก.pdf";
    state.fields = [pin()];
    mocks.apiJson.mockResolvedValue({ sheet: "ใบเบิก.json", doc_id: "@form.aaa" });

    await sheets.saveSheetNow();

    const body = sentBody();
    expect(body.sheet).toBe("ใบเบิก.json");
    expect(body.template_name).toBe("ใบเบิก");
    expect(body).not.toHaveProperty("title");
  });

  it("ส่ง title กับ source_doc ตอนสร้างใบใหม่", async () => {
    state.doc = "ใบเบิก.pdf";
    state.sheet = null;
    state.sourceDoc = null;
    state.fields = [pin()];
    mocks.apiJson.mockResolvedValue({ sheet: "ใหม่.json", doc_id: "@form.aaa" });

    await sheets.saveSheetNow();

    const body = sentBody();
    expect(body.source_doc).toBe("ใบเบิก.pdf");
    expect(body.title).toBe("ใบเบิก");
    expect(body).not.toHaveProperty("sheet");
    expect(state.sheet).toBe("ใหม่.json");
  });

  it("ทิ้งคำตอบที่กลับมาช้ากว่าการสลับใบ", async () => {
    state.doc = "ใบเบิก.pdf";
    state.fields = [pin()];
    let finish: (v: unknown) => void = () => undefined;
    mocks.apiJson.mockReturnValue(new Promise((r) => {
      finish = r;
    }));

    const inFlight = sheets.saveSheetNow();
    // ผู้ใช้สลับไปเอกสารอื่นระหว่างรอ
    sheets.clearActiveSheet();
    finish({ sheet: "ของใบเก่า.json", doc_id: "@form.aaa", source_doc: "ใบเบิก.pdf" });
    await inFlight;

    expect(state.sheet).toBeNull();
    expect(state.sourceDoc).toBeNull();
  });

  it("ไม่ยิงคำขอเมื่อกำลังดู PDF ที่พิมพ์แล้ว", async () => {
    state.doc = "@out.ใบเบิก.pdf";
    state.fields = [pin()];
    expect(await sheets.saveSheetNow()).toBeNull();
    expect(mocks.apiJson).not.toHaveBeenCalled();
  });
});

describe("เริ่มใบใหม่ / ล้างใบ", () => {
  it("startNewSheet เก็บ sourceDoc ไว้ ใบใหม่จึงถูกสร้างได้", async () => {
    state.doc = "@form.aaa";
    state.sheet = "เก่า.json";
    state.sourceDoc = "ใบเบิก.pdf";
    state.fields = [pin("")];

    sheets.startNewSheet();
    expect(state.sheet).toBeNull();
    expect(state.sourceDoc).toBe("ใบเบิก.pdf");

    mocks.apiJson.mockResolvedValue({ sheet: "ใหม่.json", doc_id: "@form.aaa" });
    await sheets.saveSheetNow();
    expect(sentBody().source_doc).toBe("ใบเบิก.pdf");
  });

  it("clearActiveSheet ล้าง sourceDoc ด้วย — ใช้ตอนสลับเอกสาร", () => {
    state.sheet = "เก่า.json";
    state.sourceDoc = "ใบเบิก.pdf";
    sheets.clearActiveSheet();
    expect(state.sheet).toBeNull();
    expect(state.sourceDoc).toBeNull();
  });

  it("ยกเลิกออโต้เซฟที่ตั้งเวลาไว้ให้ใบเก่า", async () => {
    vi.useFakeTimers();
    try {
      state.doc = "ใบเบิก.pdf";
      state.fields = [pin()];
      sheets.scheduleSheetSave();
      sheets.clearActiveSheet();
      await vi.advanceTimersByTimeAsync(2000);
      expect(mocks.apiJson).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("ลบใบงาน", () => {
  beforeEach(() => {
    state.doc = "@form.aaa";
    state.sheet = "ใบเบิก.json";
    state.sourceDoc = "ใบเบิก.pdf";
    state.fields = [pin()];
    mocks.apiJson.mockResolvedValue({ ok: true });
  });

  it("ใบที่เปิดอยู่ → กลับไปที่ฟอร์มต้นฉบับ", async () => {
    mocks.loadDoc.mockImplementation(async (name: string) => {
      state.doc = name;
    });

    await sheets.deleteSheet("ใบเบิก.json", onMarkers, onRender);

    expect(mocks.loadDoc).toHaveBeenCalledWith("ใบเบิก.pdf", onMarkers);
    expect(state.doc).toBe("ใบเบิก.pdf");
    expect(state.sheet).toBeNull();
    // เปิดต้นฉบับได้แล้ว state.doc เป็นเอกสารจริง ไม่ใช่สแนปช็อต
    expect(state.sourceDoc).toBeNull();
    expect(mocks.closeDoc).not.toHaveBeenCalled();
  });

  it("เปิดต้นฉบับไม่ได้ → ปิดเอกสารทิ้ง ไม่ค้างที่สแนปช็อตที่ถูกเก็บกวาดไปแล้ว", async () => {
    mocks.loadDoc.mockRejectedValue(new Error("license"));

    await sheets.deleteSheet("ใบเบิก.json", onMarkers, onRender);

    expect(mocks.closeDoc).toHaveBeenCalled();
    expect(state.sheet).toBeNull();
    expect(state.fields).toEqual([]);
    expect(mocks.clearChat).toHaveBeenCalled();
  });

  it("ลบใบอื่นที่ไม่ได้เปิดอยู่ ไม่แตะจอ", async () => {
    await sheets.deleteSheet("ใบอื่น.json", onMarkers, onRender);

    expect(state.sheet).toBe("ใบเบิก.json");
    expect(state.doc).toBe("@form.aaa");
    expect(mocks.loadDoc).not.toHaveBeenCalled();
    expect(mocks.closeDoc).not.toHaveBeenCalled();
  });
});

describe("นำเข้า .fromdd", () => {
  it("ส่งไฟล์เป็น multipart แล้วเปิดใบที่ได้", async () => {
    mocks.apiJson.mockResolvedValue({
      sheet: "นำเข้า.json",
      doc_id: "@form.ccc",
      title: "ใบเบิก — สมชาย",
      source_doc: "ใบเบิก.pdf",
      fields: [pin()],
    });
    const file = new File([new Uint8Array([80, 75, 3, 4])], "ใบเบิก.fromdd");

    const r = await sheets.importSheet(file, onMarkers, onRender);

    const [url, opts] = mocks.apiJson.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/sheets/import");
    expect(opts.body).toBeInstanceOf(FormData);
    expect((opts.body as FormData).get("file")).toBe(file);
    expect(r.sheet).toBe("นำเข้า.json");
    expect(state.sheet).toBe("นำเข้า.json");
    expect(mocks.loadDoc).toHaveBeenCalledWith("@form.ccc", onMarkers);
  });
});

describe("ป้ายสถานะบันทึก", () => {
  function chip(): HTMLElement {
    return document.getElementById("savestate")!;
  }

  it("ขึ้น กำลังบันทึก… แล้วเป็น บันทึกแล้ว", async () => {
    state.doc = "ใบเบิก.pdf";
    state.fields = [pin()];
    let finish: (v: unknown) => void = () => undefined;
    mocks.apiJson.mockReturnValue(new Promise((r) => {
      finish = r;
    }));

    const inFlight = sheets.saveSheetNow();
    expect(chip().className).toBe("saving");

    finish({ sheet: "ก.json", doc_id: "@form.a", title: "ใบเบิก — สมชาย" });
    await inFlight;

    expect(chip().className).toBe("saved");
    expect(chip().textContent).toContain("save.saved");
    expect(chip().title).toContain("ใบเบิก — สมชาย");
  });

  it("บันทึกไม่สำเร็จต้องเห็นชัด ไม่ค้างที่ กำลังบันทึก…", async () => {
    state.doc = "ใบเบิก.pdf";
    state.fields = [pin()];
    mocks.apiJson.mockRejectedValue(new Error("disk full"));

    await sheets.saveSheetNow();

    expect(chip().className).toBe("failed");
    expect(chip().textContent).toContain("save.failed");
  });

  it("สลับเอกสารแล้วป้ายกลับเป็นว่าง", async () => {
    state.doc = "ใบเบิก.pdf";
    state.fields = [pin()];
    mocks.apiJson.mockResolvedValue({ sheet: "ก.json", doc_id: "@form.a", title: "ก" });
    await sheets.saveSheetNow();
    expect(chip().className).toBe("saved");

    sheets.clearActiveSheet();
    expect(chip().className).toBe("idle");
    expect(chip().textContent).toBe("save.idle");
  });

  it("เปิดใบเก่าขึ้นมาก็ถือว่าบันทึกแล้ว", async () => {
    mocks.apiJson.mockResolvedValue({
      sheet: "เก่า.json",
      doc_id: "@form.b",
      title: "ใบเบิก — สมหญิง",
      fields: [pin()],
    });
    await sheets.openSheet("เก่า.json", onMarkers, onRender);
    expect(chip().className).toBe("saved");
    expect(chip().title).toContain("ใบเบิก — สมหญิง");
  });
});
