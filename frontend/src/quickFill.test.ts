import { beforeEach, expect, it, vi } from 'vitest';
import { editQuickText, bindQuickObject, commitQuickInput } from './quickFill';
import { state } from './state';

beforeEach(() => {
  commitQuickInput();
  document.body.innerHTML = '<div id="pagewrap"><img id="pageimg"></div><input id="quick-size" value="14">';
  state.doc = 'test.pdf'; state.cur = 0; state.fields = []; state.selIdx = -1;
});

it('commits on Enter once and generates unique internal names', () => {
  const changed = vi.fn();
  state.fields = [{ name: 'quick_001', page: 0, x: 1, y: 1, size: 14 }];
  editQuickText(20, 30, changed);
  const input = document.querySelector<HTMLInputElement>('.quick-input')!;
  input.value = 'Example';
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
  commitQuickInput();
  expect(state.fields[1]).toMatchObject({ name: 'quick_002', value: 'Example', x: 20, y: 30 });
  expect(changed).toHaveBeenCalledTimes(1);
});

it('cancels edits with Escape and ignores Enter during composition', () => {
  state.fields = [{ name: 'quick_001', page: 0, x: 1, y: 1, size: 14, value: 'Original' }];
  editQuickText(1, 1, vi.fn(), 0);
  const input = document.querySelector<HTMLInputElement>('.quick-input')!;
  input.value = 'Changed';
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', isComposing: true }));
  expect(document.querySelector('.quick-input')).not.toBeNull();
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
  expect(state.fields[0].value).toBe('Original');
});

it('keeps the original page when navigation commits pending text', () => {
  editQuickText(20, 30, vi.fn());
  document.querySelector<HTMLInputElement>('.quick-input')!.value = 'Page one';
  state.cur = 1;
  commitQuickInput();
  expect(state.fields[0].page).toBe(0);
});

it('drags a field by the pointer delta, converted to document units', () => {
  const changed = vi.fn();
  state.zoom = 2; // scale() is 1 in jsdom (image unloaded), so ratio = scale()/zoom = 0.5
  state.fields = [{ name: 'quick_001', page: 0, x: 100, y: 100, size: 14 }];
  const img = document.getElementById('pageimg')!;
  Object.defineProperty(img, 'clientWidth', { value: 1000, configurable: true });
  Object.defineProperty(img, 'clientHeight', { value: 1000, configurable: true });
  const el = document.createElement('div');
  el.setPointerCapture = () => undefined;
  document.getElementById('pagewrap')!.appendChild(el);
  bindQuickObject(el, 0, changed);

  el.dispatchEvent(new MouseEvent('pointerdown', { button: 0, clientX: 200, clientY: 200 }));
  el.dispatchEvent(new MouseEvent('pointermove', { clientX: 260, clientY: 200 }));
  el.dispatchEvent(new MouseEvent('pointerup'));

  expect(state.fields[0].x).toBe(130); // 100 + 60 * 0.5
  expect(state.fields[0].y).toBe(100); // no vertical movement
  expect(state.selIdx).toBe(0);
  expect(changed).toHaveBeenCalled();
  expect(document.querySelector('.quick-input')).toBeNull(); // a drag never opens the editor
});

it('preserves newlines in an existing multi-line value', () => {
  state.fields = [{ name: 'quick_001', page: 0, x: 1, y: 1, size: 14, value: 'First line\nSecond line' }];
  editQuickText(1, 1, vi.fn(), 0);
  const input = document.querySelector<HTMLTextAreaElement>('.quick-input')!;
  expect(input.value).toBe('First line\nSecond line'); // a single-line <input> would strip the \n on open
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
  commitQuickInput();
  expect(state.fields[0].value).toBe('First line\nSecond line');
});

it('commits a pending edit on drag-start without dropping the drag target', () => {
  state.zoom = 2;
  state.fields = [
    { name: 'quick_001', page: 0, x: 100, y: 100, size: 14 },
    { name: 'quick_002', page: 0, x: 200, y: 200, size: 14 },
  ];
  const img = document.getElementById('pageimg')!;
  Object.defineProperty(img, 'clientWidth', { value: 1000, configurable: true });
  Object.defineProperty(img, 'clientHeight', { value: 1000, configurable: true });
  const el = document.createElement('div');
  el.setPointerCapture = () => undefined;
  document.getElementById('pagewrap')!.appendChild(el);
  // The open editor's re-render would remove the drag target; the fix suppresses it.
  const pendingRerender = vi.fn(() => el.remove());
  editQuickText(1, 1, pendingRerender, 0);
  document.querySelector<HTMLTextAreaElement>('.quick-input')!.value = 'typed';
  bindQuickObject(el, 1, vi.fn());

  el.dispatchEvent(new MouseEvent('pointerdown', { button: 0, clientX: 300, clientY: 300 }));
  expect(state.fields[0].value).toBe('typed'); // pending text committed to state
  expect(pendingRerender).not.toHaveBeenCalled(); // but its re-render was suppressed
  expect(el.isConnected).toBe(true); // so the drag target survives

  el.dispatchEvent(new MouseEvent('pointermove', { clientX: 360, clientY: 300 }));
  el.dispatchEvent(new MouseEvent('pointerup'));
  expect(state.fields[1].x).toBe(230); // 200 + 60 * 0.5 — the drag actually ran
});
