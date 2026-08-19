/** Shared types for Flask API responses */

export type LicenseStatus = {
  licensed: boolean;
  bypass: boolean;
  machine_id: string;
  expires: string | null;
  days_left: number | null;
  message: string;
  demo_only: boolean;
  demo_doc: string;
  demo_docs?: string[];
};

export type Field = {
  name: string;
  page: number;
  x: number;
  y: number;
  size: number;
  value?: string;
};

export type TemplatePayload = {
  doc?: string;
  fields: Field[];
};

export type DocsResponse = {
  pdfs: string[];
  templates: string[];
  font: string | null;
  user: string;
  auth_required?: boolean;
  license: LicenseStatus;
  font_ascender?: number;
  font_descender?: number;
};

export type FillResponse = {
  ok?: boolean;
  file?: string;
  archived?: string | null;
  error?: string;
  license_required?: boolean;
};

export type LicenseActivateResponse = LicenseStatus & {
  ok?: boolean;
  error?: string;
};

export type PageInfo = {
  pages: number;
  sizes: { w: number; h: number }[];
  zoom: number;
  font_ascender?: number;
  font_descender?: number;
};

export type LibraryDoc = {
  rel: string;
  name: string;
  filename: string;
  folder: string;
  has_template: boolean;
  tags?: string[];
  last_used?: number | null;
  doc_id: string;
};

export type LibraryStatus = {
  configured: boolean;
  root: string | null;
  suggested_root: string;
  count: number;
  scanned_at?: number;
  max_depth?: number;
  docs: LibraryDoc[];
  open_folder_enabled?: boolean;
};

/** Autofill book — reusable field name → value pairs, not tied to any PDF */
export type ProfileKind = "org" | "partner" | "person";

export type Profile = {
  id: string;
  name: string;
  kind: ProfileKind;
  values: Record<string, string>;
};

export type ProfilesResponse = {
  version: number;
  profiles: Profile[];
};

export type ProfileSaveResponse = {
  ok?: boolean;
  profile?: Profile;
  error?: string;
};

export type HistoryFile = {
  kind?: "sheet" | "pdf";
  title?: string;
  sheet?: string;
  printed?: boolean;
  filled?: number;
  pins?: number;
  name: string;
  stem: string;
  group: string;
  mtime: number;
  size: number;
  doc_id: string;
};

export type HistoryStatus = {
  count: number;
  truncated?: boolean;
  files: HistoryFile[];
  open_folder_enabled?: boolean;
};
