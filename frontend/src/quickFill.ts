import { $ } from './dom';
import { state, isOutDoc } from './state';
import { scale } from './viewer';
import { t } from './i18n';

export function isQuickFill(): boolean { return document.body.dataset.quick === 'true'; }

let finish: (() => void) | null = null;
export function commitQuickInput(): void { finish?.(); }

export function editQuickText(x: number, y: number, changed: () => void, index?: number): void {
  commitQuickInput();
  if (!state.doc || isOutDoc(state.doc)) return;
  const doc = state.doc, page = state.cur;
  const field = index === undefined ? undefined : state.fields[index];
  const size = field?.size || Number(($('quick-size') as HTMLInputElement).value) || 14;
  const ratio = state.zoom / scale();
  const input = document.createElement('input');
  input.className = 'quick-input';
  input.setAttribute('aria-label', t('quick.text'));
  input.value = field?.value || '';
  input.style.left = `${Math.min(x * ratio, Math.max(0, $('pagewrap').clientWidth - 180))}px`;
  input.style.top = `${Math.max(0, (y - state.fontAsc * size) * ratio)}px`;
  let closed = false;
  const close = (save: boolean) => {
    if (closed) return;
    closed = true; finish = null;
    const value = input.value.trim();
    input.remove();
    if (!save || state.doc !== doc) return;
    if (field) field.value = value;
    else if (value) {
      let n = 1;
      while (state.fields.some(f => f.name === `quick_${String(n).padStart(3, '0')}`)) n++;
      state.fields.push({ name: `quick_${String(n).padStart(3, '0')}`, page, x, y, size, value });
      state.selIdx = state.fields.length - 1;
    }
    if (field || value) changed();
  };
  finish = () => close(true);
  input.onblur = () => close(true);
  input.onkeydown = event => {
    event.stopPropagation();
    if (event.isComposing) return;
    if (event.key === 'Enter' || event.key === 'Escape') {
      event.preventDefault(); close(event.key === 'Enter');
    }
  };
  $('pagewrap').appendChild(input); input.focus();
}

export function bindQuickObject(el: HTMLElement, index: number, changed: () => void): void {
  const field = state.fields[index];
  el.style.pointerEvents = 'auto';
  el.style.touchAction = 'none';
  el.style.cursor = 'move';
  el.title = field.value || t('quick.text');
  el.onpointerdown = event => {
    if (event.button !== 0) return;
    event.preventDefault(); event.stopPropagation();
    commitQuickInput();
    const startX = event.clientX, startY = event.clientY, x = field.x, y = field.y;
    let moved = false;
    el.setPointerCapture(event.pointerId);
    el.onpointermove = move => {
      const dx = move.clientX - startX, dy = move.clientY - startY;
      if (Math.hypot(dx, dy) < 3 && !moved) return;
      moved = true;
      const ratio = scale() / state.zoom;
      field.x = Math.max(0, Math.min($('pageimg').clientWidth * ratio, x + dx * ratio));
      field.y = Math.max(0, Math.min($('pageimg').clientHeight * ratio, y + dy * ratio));
      el.style.transform = `translate(${(field.x - x) / ratio}px, ${(field.y - y) / ratio}px)`;
    };
    el.onpointerup = () => {
      el.onpointermove = null; el.onpointerup = null;
      state.selIdx = index;
      ($('quick-size') as HTMLInputElement).value = String(field.size);
      changed();
      if (!moved) editQuickText(field.x, field.y, changed, index);
    };
    el.onpointercancel = () => { el.onpointermove = null; changed(); };
  };
  el.onclick = event => event.stopPropagation();
}
