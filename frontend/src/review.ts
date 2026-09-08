import type { Field } from './types';

export type ReviewIssue = { index: number; key: string; blocking: boolean };

/** Empty optional fields are valid. Width checks are warnings, not proof of clipping. */
export function reviewFields(fields: Field[], sizes: { w: number; h: number }[], measure: (text: string, size: number) => number): ReviewIssue[] {
  const issues: ReviewIssue[] = [];
  fields.forEach((field, index) => {
    const value = (field.value || '').trim();
    if (field.required && !value) issues.push({ index, key: 'flow.missing', blocking: true });
    if (!value) return;
    if (field.input_type === 'number' && (!Number.isFinite(Number(value)) || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value))) {
      issues.push({ index, key: 'flow.badNumber', blocking: true });
    }
    if (field.input_type === 'date') {
      const parsed = new Date(value + 'T00:00:00Z');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) {
        issues.push({ index, key: 'flow.badDate', blocking: true });
      }
    }
    const page = sizes[field.page];
    if (!page || field.x < 0 || field.y < 0 || field.x >= page.w || field.y > page.h) {
      issues.push({ index, key: 'flow.offPage', blocking: true });
    } else if (measure(value, field.size) > Math.min(field.width ?? Infinity, page.w - field.x)) {
      issues.push({ index, key: 'flow.overflow', blocking: false });
    }
  });
  return issues;
}
