import { describe, expect, it } from 'vitest';
import { reviewFields } from './review';
import type { Field } from './types';

const field: Field = { name: 'Name', x: 10, y: 30, page: 0, size: 14 };
const pages = [{ w: 300, h: 500 }];
const measure = (text: string) => text.length * 10;

describe('review before exporting', () => {
  it('does not block legacy optional blanks', () => {
    expect(reviewFields([field], pages, measure)).toEqual([]);
  });
  it('points to a required blank field', () => {
    expect(reviewFields([{ ...field, required: true }], pages, measure)).toEqual([{ index: 0, key: 'flow.missing', blocking: true }]);
  });
  it('blocks invalid numbers and impossible dates', () => {
    const input: Field[] = [{ ...field, input_type: 'number', value: 'one' }, { ...field, input_type: 'date', value: '2026-02-30' }];
    expect(reviewFields(input, pages, measure).map(issue => issue.key)).toEqual(['flow.badNumber', 'flow.badDate']);
  });
  it('allows signed decimals and leap day dates', () => {
    expect(reviewFields([{ ...field, input_type: 'number', value: '-1.25' }, { ...field, input_type: 'date', value: '2028-02-29' }], pages, measure)).toEqual([]);
  });
  it('warns for field or page overflow but allows review', () => {
    const issues = reviewFields([{ ...field, width: 20, value: 'long' }, { ...field, x: 295, value: 'x' }], pages, measure);
    expect(issues).toHaveLength(2);
    expect(issues.every(issue => issue.key === 'flow.overflow' && !issue.blocking)).toBe(true);
  });
  it('blocks a populated field on a missing page', () => {
    expect(reviewFields([{ ...field, page: 2, value: 'text' }], pages, measure)[0].key).toBe('flow.offPage');
  });
});
