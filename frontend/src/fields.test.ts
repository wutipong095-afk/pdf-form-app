import { beforeEach, expect, it } from 'vitest';
import { renderValues } from './fields';
import { state } from './state';

beforeEach(() => {
  document.body.innerHTML = '<div id="valuelist"></div>';
});

it('groups the value list by page without reindexing data-i', () => {
  state.fields = [
    { name: 'Later page first', page: 1, x: 0, y: 0, size: 12, value: 'b' },
    { name: 'Earlier page', page: 0, x: 0, y: 0, size: 12, value: 'a' },
    { name: 'Later page second', page: 1, x: 0, y: 0, size: 12, value: 'c' },
  ];
  renderValues();
  const headings = [...document.querySelectorAll('.field-group')].map(el => el.textContent);
  expect(headings).toEqual(['ข้อมูลหน้า 1', 'ข้อมูลหน้า 2']);
  const rows = [...document.querySelectorAll('#valuelist input')].map(el => ({
    i: (el as HTMLInputElement).dataset.i,
    id: el.id,
  }));
  expect(rows).toEqual([
    { i: '1', id: 'value-1' },
    { i: '0', id: 'value-0' },
    { i: '2', id: 'value-2' },
  ]);
  expect(document.querySelector('[data-goto="1"]')).not.toBeNull();
  expect(document.querySelector('[data-clear="0"]')).not.toBeNull();
  expect(document.querySelectorAll('.field-group')).toHaveLength(2);
});
