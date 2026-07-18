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
};

export type FillResponse = {
  ok?: boolean;
  file?: string;
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
};
