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
};

export function isOutDoc(doc: string | null | undefined): boolean {
  return (doc || "").startsWith("@out.");
}
