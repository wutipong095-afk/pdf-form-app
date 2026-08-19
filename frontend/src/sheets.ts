/** ใบงาน — ค่าที่กรอกถูกบันทึกอัตโนมัติเป็น JSON เล็ก ๆ เปิดแก้ต่อได้ */
import { $ } from "./dom";
import { apiJson } from "./api";
import { isFormDoc, isOutDoc, state } from "./state";
import { loadDoc } from "./viewer";
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
  template_name?: string;
  fields?: Field[];
  printed?: string[];
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

export function clearActiveSheet(): void {
  newEpoch();
  state.sheet = null;
  state.sourceDoc = null;
  setSheetStatus("");
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
  try {
    const body: Record<string, unknown> = {
      fields: state.fields,
      title: titleFromUi() || "sheet",
      template_name: titleFromUi(),
    };
    if (state.sheet) body.sheet = state.sheet;
    else body.source_doc = source;
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
    onSaved?.();
    return r;
  } catch {
    if (sent === epoch) setSheetStatus(t("hist.saveFail"));
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

export async function deleteSheet(name: string): Promise<void> {
  await apiJson("/api/sheets/" + encodeURIComponent(name), { method: "DELETE" });
  if (state.sheet === name) clearActiveSheet();
}
