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
};
