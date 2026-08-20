/** ใบงาน — ค่าที่กรอกถูกบันทึกอัตโนมัติเป็น JSON เล็ก ๆ เปิดแก้ต่อได้ */
import { $ } from "./dom";
import { apiJson } from "./api";
import { isFormDoc, isOutDoc, state } from "./state";
import { closeDoc, loadDoc } from "./viewer";
import { clearChat } from "./chat";
import { t } from "./i18n";
import type { Field } from "./types";

export type SheetPayload = {
  ok?: boolean;
  sheet: string;
  doc_id: string;
  title?: string;
  form_sha?: string;
  source_doc?: string;
  source_name?: string;
  source_present?: boolean;
  source_changed?: boolean;
  template_name?: string;
  fields?: Field[];
  printed?: string[];
  orphan_pins?: number;
  error?: string;
};

let timer: ReturnType<typeof setTimeout> | null = null;
let saving = false;
let pending = false;
let onSaved: (() => void) | null = null;
/** เพิ่มทุกครั้งที่สลับใบ — คำตอบออโต้เซฟที่ออกก่อนหน้าถือว่าหมดอายุ */
let epoch = 0;

function newEpoch(): void {
  epoch++;
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  pending = false;
}

export function bindSheetSaved(cb: () => void): void {
  onSaved = cb;
}

export function setSheetStatus(msg: string): void {
  const el = document.getElementById("jobstatus");
  if (el) el.textContent = msg;
}

type SaveState = "idle" | "saving" | "saved" | "failed";

/** ป้ายสถานะบนหัวเว็บ — ผู้ใช้ต้องเห็นว่างานถูกบันทึกแล้วโดยไม่ต้องเดา */
function setSaveState(kind: SaveState, name = ""): void {
  const el = document.getElementById("savestate");
  if (!el) return;
  el.className = kind;
  if (kind === "saved") {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    el.textContent = t("save.saved", { time });
    el.title = t("save.savedTitle", { name });
    return;
  }
  if (kind === "failed") {
    el.textContent = t("save.failed");
    el.title = t("save.failedTitle");
    return;
  }
  el.textContent = kind === "saving" ? t("save.saving") : t("save.idle");
  el.title = "";
}

export function clearActiveSheet(): void {
  newEpoch();
  state.sheet = null;
  state.sourceDoc = null;
  setSheetStatus("");
  setSaveState("idle");
}

/** เริ่มใบใหม่จากฟอร์มเดิม — เก็บ sourceDoc ไว้ให้ออโต้เซฟสร้างใบใหม่ */
export function startNewSheet(): void {
  newEpoch();
  state.sheet = null;
  setSheetStatus("");
}

function titleFromUi(): string {
  return (($("tplname") as HTMLInputElement).value || "").trim();
}

function sourceDocForSave(): string | null {
  if (isOutDoc(state.doc)) return null;
  if (isFormDoc(state.doc)) return state.sourceDoc;
  return state.doc;
}

export function scheduleSheetSave(): void {
  if (isOutDoc(state.doc)) return;
  if (!state.doc || !state.fields.length) return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    void saveSheetNow();
  }, 800);
}

export async function saveSheetNow(): Promise<SheetPayload | null> {
  if (isOutDoc(state.doc)) return null;
  if (!state.doc || !state.fields.length) return null;
  const source = sourceDocForSave();
  if (!state.sheet && !source) return null;
  if (saving) {
    pending = true;
    return null;
  }
  saving = true;
  const sent = epoch;
  setSaveState("saving");
  try {
    const body: Record<string, unknown> = {
      fields: state.fields,
      template_name: titleFromUi(),
    };
    if (state.sheet) {
      // ไม่ส่ง title ตอนอัปเดต — ชื่อใบตั้งจากค่าที่กรอก ฝั่งเซิร์ฟเวอร์คิดให้เอง
      body.sheet = state.sheet;
    } else {
      body.source_doc = source;
      body.title = titleFromUi() || "sheet";
    }
    const r = await apiJson<SheetPayload>("/api/sheets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    // ผู้ใช้สลับใบระหว่างรอ — ไฟล์ฝั่งเซิร์ฟเวอร์ถูกต้องแล้ว แต่ห้ามผูกกลับมาที่ใบใหม่
    if (sent !== epoch) return null;
    state.sheet = r.sheet;
    if (r.source_doc) state.sourceDoc = r.source_doc;
    setSheetStatus(t("hist.saved", { file: r.title || r.sheet }));
    setSaveState("saved", r.title || r.sheet);
    onSaved?.();
    return r;
  } catch {
    if (sent === epoch) {
      setSheetStatus(t("hist.saveFail"));
      setSaveState("failed");
    }
    return null;
  } finally {
    saving = false;
    if (pending) {
      pending = false;
      scheduleSheetSave();
    }
  }
}

function applySheet(r: SheetPayload, onRender: () => void): void {
  setSaveState("saved", r.title || r.sheet);
  state.sheet = r.sheet;
  state.sourceDoc = r.source_doc || null;
  if (r.template_name) ($("tplname") as HTMLInputElement).value = r.template_name;
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  state.fields = r.fields || [];
  state.selIdx = -1;
  state.chatIdx = -1;
  clearChat();
  onRender();
  setSheetStatus(t("hist.saved", { file: r.title || r.sheet }));
}

export async function openSheet(
  name: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  const r = await apiJson<SheetPayload>("/api/sheets/" + encodeURIComponent(name));
  // เปิดเอกสารให้ผ่านก่อน — ถ้าล้ม state.sheet ต้องไม่ค้างชี้ใบที่เปิดไม่ขึ้น
  // ไม่งั้นค่าของใบที่ยังอยู่บนจอจะถูกออโต้เซฟทับลงใบนั้น
  clearActiveSheet();
  await loadDoc(r.doc_id, onMarkers);
  applySheet(r, onRender);
}

export async function duplicateSheet(
  name: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<SheetPayload> {
  const r = await apiJson<SheetPayload>(
    "/api/sheets/" + encodeURIComponent(name) + "/duplicate",
    { method: "POST" },
  );
  clearActiveSheet();
  await loadDoc(r.doc_id, onMarkers);
  applySheet(r, onRender);
  return r;
}

/**
 * ลบใบงาน — ถ้าเป็นใบที่เปิดอยู่ ต้องพาจอกลับไปที่ฟอร์มต้นฉบับ
 * เพราะ @form.{sha} บนจออาจถูกเก็บกวาดไปพร้อมใบสุดท้ายที่อ้างถึงมัน
 */
/** นำเข้าไฟล์ .fromdd จากเครื่องอื่น แล้วเปิดใบที่ได้ขึ้นมาแก้ต่อ */
export async function importSheet(
  file: File,
  onMarkers: () => void,
  onRender: () => void,
): Promise<SheetPayload> {
  const form = new FormData();
  form.append("file", file);
  const r = await apiJson<SheetPayload>("/api/sheets/import", { method: "POST", body: form });
  clearActiveSheet();
  await loadDoc(r.doc_id, onMarkers);
  applySheet(r, onRender);
  return r;
}

/** ตั้งชื่อใบงานเอง — ชื่อนี้ใช้ทั้งในลิสต์ ตอนค้นหา และเป็นชื่อไฟล์ตอนส่งออก */
export async function renameSheet(name: string, title: string): Promise<SheetPayload> {
  const r = await apiJson<SheetPayload>(
    "/api/sheets/" + encodeURIComponent(name) + "/rename",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    },
  );
  if (state.sheet === name) setSaveState("saved", r.title || r.sheet);
  return r;
}

/** ย้ายใบงานไปใช้ฟอร์มต้นฉบับเวอร์ชันปัจจุบัน แล้วโหลดสแนปช็อตใหม่ขึ้นจอ */
export async function relinkSheet(
  name: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<SheetPayload> {
  const r = await apiJson<SheetPayload>(
    "/api/sheets/" + encodeURIComponent(name) + "/relink",
    { method: "POST" },
  );
  clearActiveSheet();
  await loadDoc(r.doc_id, onMarkers);
  applySheet(r, onRender);
  return r;
}

export async function deleteSheet(
  name: string,
  onMarkers?: () => void,
  onRender?: () => void,
): Promise<void> {
  const wasOpen = state.sheet === name;
  const source = state.sourceDoc;
  await apiJson("/api/sheets/" + encodeURIComponent(name), { method: "DELETE" });
  if (!wasOpen) return;

  startNewSheet();
  if (source && onMarkers) {
    try {
      await loadDoc(source, onMarkers);
      // เปิดต้นฉบับได้แล้ว — state.doc เป็นเอกสารจริง ไม่ใช่สแนปช็อตอีกต่อไป
      state.sourceDoc = null;
      onRender?.();
      return;
    } catch {
      // ต้นฉบับถูกลบ ย้าย หรือไลเซนต์ไม่ผ่าน — ล้างจอดีกว่าปล่อยให้ค้างที่ไฟล์ที่หายไป
    }
  }
  // สแนปช็อตอาจถูกเก็บกวาดไปพร้อมใบสุดท้ายแล้ว — ตัด state.doc ทิ้งด้วย
  // ไม่งั้นพรีวิวยังขอ /page/@form.{sha} ที่ 404
  closeDoc();
  clearActiveSheet();
  state.fields = [];
  state.selIdx = -1;
  state.chatIdx = -1;
  clearChat();
  onRender?.();
}
