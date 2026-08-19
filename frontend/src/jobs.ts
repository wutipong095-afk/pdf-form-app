/** ไฟล์งาน .fromdd — บันทึกอัตโนมัติตอนกรอก เปิดแก้ต่อได้ */
import { $ } from "./dom";
import { apiJson } from "./api";
import { isJobDoc, isOutDoc, state } from "./state";
import { loadDoc } from "./viewer";
import { t } from "./i18n";
import type { Field } from "./types";

export type JobPayload = {
  ok?: boolean;
  file: string;
  doc_id: string;
  title?: string;
  source_doc?: string;
  template_name?: string;
  fields?: Field[];
  error?: string;
};

let timer: ReturnType<typeof setTimeout> | null = null;
let saving = false;
let pending = false;
let onSaved: (() => void) | null = null;

export function bindJobSaved(cb: () => void): void {
  onSaved = cb;
}

export function setJobStatus(msg: string): void {
  const el = document.getElementById("jobstatus");
  if (el) el.textContent = msg;
}

export function clearActiveJob(): void {
  state.job = null;
  state.sourceDoc = null;
  setJobStatus("");
}

/** เริ่มใบใหม่จากฟอร์มเดิม — เก็บ sourceDoc ไว้ให้ออโต้เซฟสร้าง .fromdd ใหม่ */
export function startNewSheet(): void {
  state.job = null;
  setJobStatus("");
}

function titleFromUi(): string {
  return (($("tplname") as HTMLInputElement).value || "").trim();
}

function sourceDocForSave(): string | null {
  if (isOutDoc(state.doc)) return null;
  if (isJobDoc(state.doc)) return state.sourceDoc;
  return state.doc;
}

export function scheduleJobSave(): void {
  if (isOutDoc(state.doc)) return;
  if (!state.doc || !state.fields.length) return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    void saveJobNow();
  }, 800);
}

export async function saveJobNow(): Promise<JobPayload | null> {
  if (isOutDoc(state.doc)) return null;
  if (!state.doc || !state.fields.length) return null;
  const source = sourceDocForSave();
  if (!state.job && !source) return null;
  if (saving) {
    pending = true;
    return null;
  }
  saving = true;
  try {
    const body: Record<string, unknown> = {
      fields: state.fields,
      title: titleFromUi() || "job",
      template_name: titleFromUi(),
    };
    if (state.job) body.job = state.job;
    else body.source_doc = source;
    const r = await apiJson<JobPayload>("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.job = r.file;
    if (r.source_doc) state.sourceDoc = r.source_doc;
    setJobStatus(t("hist.saved", { file: r.file }));
    onSaved?.();
    return r;
  } catch {
    setJobStatus(t("hist.saveFail"));
    return null;
  } finally {
    saving = false;
    if (pending) {
      pending = false;
      scheduleJobSave();
    }
  }
}

export async function openJob(
  name: string,
  onMarkers: () => void,
  onRender: () => void,
): Promise<void> {
  const r = await apiJson<JobPayload>("/api/jobs/" + encodeURIComponent(name));
  state.job = r.file;
  state.sourceDoc = r.source_doc || null;
  if (r.template_name) ($("tplname") as HTMLInputElement).value = r.template_name;
  await loadDoc(r.doc_id, onMarkers);
  ($("docsel") as HTMLSelectElement).value = "";
  ($("tplsel") as HTMLSelectElement).value = "";
  state.fields = r.fields || [];
  state.selIdx = -1;
  state.chatIdx = -1;
  onRender();
  setJobStatus(t("hist.saved", { file: r.file }));
}
