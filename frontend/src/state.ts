import type { Field, LicenseStatus } from "./types";

export type AppState = {
  zoom: number;
  doc: string | null;
  pages: number;
  cur: number;
  fields: Field[];
  selIdx: number;
  chatIdx: number;
  lic: LicenseStatus | null;
  /** Fill-font ascender / descender — overlay must match insert_thai_text */
  fontAsc: number;
  fontDesc: number;
  /** ชื่อไฟล์งาน .fromdd ที่กำลังแก้ (ไม่มีนามสกุลใน doc_id) */
  job: string | null;
  /** เอกสารต้นฉบับเมื่อ state.doc เป็น @job.… */
  sourceDoc: string | null;
};

export const state: AppState = {
  zoom: 2,
  doc: null,
  pages: 0,
  cur: 0,
  fields: [],
  selIdx: -1,
  chatIdx: -1,
  lic: null,
  fontAsc: 0.85,
  fontDesc: -0.25,
  job: null,
  sourceDoc: null,
};

export function isOutDoc(doc: string | null | undefined): boolean {
  return (doc || "").startsWith("@out.");
}

export function isJobDoc(doc: string | null | undefined): boolean {
  return (doc || "").startsWith("@job.");
}
