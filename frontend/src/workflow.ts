import { $ } from './dom';
import { api, apiJson } from './api';
import { state, isOutDoc } from './state';
import { t } from './i18n';
import { loadDoc } from './viewer';
import { leaveActiveSheet, flushSheetSave, hasPendingSheetSave, openSheet } from './sheets';
import { setHistoryOpen } from './history';
import { setProfilesOpen } from './profiles';
import { reviewFields } from './review';
import type { DocsResponse, TemplatePayload, HistoryStatus, PageInfo, LibraryStatus } from './types';

type View = 'home' | 'history' | 'settings' | 'edit' | 'fill' | 'test' | 'review' | 'done' | 'pdf';
type Hooks = { setTab: (tab: 'edit' | 'fill') => void; render: () => void; markers: () => void; newSheet: () => Promise<void> };
let hooks: Hooks;
let view: View = 'home';
let layoutDirty = false;
let catalog: { name: string; doc?: string }[] = [];
let previewUrl: string | null = null;
let previewPage = 0;
let previewSequence = 0;
let transition = false;
let reviewReturn: View = 'fill';
let previewReady = false;

export function flowError(error: unknown): void {
  const el = $('flow-message');
  el.textContent = error instanceof Error ? error.message : String(error);
  el.hidden = false;
}

export function markLayoutDirty(): void { layoutDirty = true; }
export function markLayoutSaved(): void { layoutDirty = false; void refreshCatalog(); }

export function syncWorkTitle(): void {
  const name = ($('tplname') as HTMLInputElement).value;
  $('active-title').textContent = state.sheet ? (state.sheetTitle || name) : name || t('flow.untitled');
  $('review-document').toggleAttribute('disabled', !state.doc || !state.fields.length || isOutDoc(state.doc));
  $('fill-progress').textContent = t('flow.progress', { filled: state.fields.filter(f => f.value?.trim()).length, total: state.fields.length });
}

function show(next: View): void {
  previewSequence++;
  view = next;
  document.body.dataset.view = next;
  for (const [id, visible] of Object.entries({
    'home-view': next === 'home', 'history-view': next === 'history', 'settings-view': next === 'settings',
    'prepare-view': next === 'edit' || next === 'test', 'work-heading': ['edit', 'fill', 'test', 'pdf'].includes(next),
    workspace: ['edit', 'fill', 'test', 'pdf'].includes(next), 'work-actions': ['edit', 'fill', 'test'].includes(next),
    'review-view': next === 'review', 'done-view': next === 'done',
  })) $(id).hidden = !visible;
  for (const [id, active] of Object.entries({ 'nav-forms': next === 'home', 'btn-hist-toggle': next === 'history', 'nav-prepare': next === 'edit' || next === 'test', 'nav-settings': next === 'settings' })) {
    if (active) $(id).setAttribute('aria-current', 'page'); else $(id).removeAttribute('aria-current');
  }
  $('review-document').textContent = next === 'edit' ? t('flow.testForm') : t('flow.reviewAction');
  $('review-document').toggleAttribute('disabled', !state.doc || !state.fields.length || isOutDoc(state.doc));
  if (['edit', 'fill', 'test'].includes(next)) hooks.setTab(next === 'edit' ? 'edit' : 'fill');
  setHistoryOpen(next === 'history');
  if (next !== 'settings') setProfilesOpen(false);
  syncWorkTitle();
  window.scrollTo(0, 0);
}

async function safeAction(action: () => Promise<void>): Promise<void> {
  if (transition) return;
  transition = true;
  $('flow-message').hidden = true;
  try { await action(); } catch (error) { flowError(error); } finally { transition = false; }
}

export async function beforeDocumentChange(): Promise<boolean> {
  await flushSheetSave();
  if (layoutDirty && !confirm(t('flow.discard'))) return false;
  layoutDirty = false;
  return true;
}

async function navigate(next: View): Promise<void> {
  if (!await beforeDocumentChange()) return;
  if (next === 'edit' && state.sheet) {
    const source = state.sourceDoc || state.doc;
    if (source) {
      await loadDoc(source, hooks.markers);
      ($("docsel") as HTMLSelectElement).value = source;
    }
    await leaveActiveSheet();
    state.fields = state.fields.map(field => ({ ...field, value: '' }));
    hooks.render();
  }
  show(next);
  if (next === 'home') await refreshCatalog();
}

function card(title: string, subtitle: string, label: string, action: () => Promise<void>): HTMLElement {
  const item = document.createElement('article'); item.className = 'form-card';
  const heading = document.createElement('h2'); heading.textContent = title;
  const desc = document.createElement('p'); desc.textContent = subtitle;
  const button = document.createElement('button'); button.className = 'primary'; button.textContent = label;
  button.onclick = () => void safeAction(action);
  item.append(heading, desc, button); return item;
}

async function useTemplate(name: string, libraryDoc?: string): Promise<void> {
  if (!await beforeDocumentChange()) return;
  const template = await apiJson<TemplatePayload>(libraryDoc ? '/api/library/template?doc=' + encodeURIComponent(libraryDoc) : '/api/template/' + encodeURIComponent(name));
  const source = libraryDoc || template.doc;
  if (!source) throw new Error(t('app.loadDocFail'));
  await leaveActiveSheet();
  await loadDoc(source, hooks.markers);
  state.fields = (template.fields || []).map(field => ({ ...field, value: '' }));
  state.selIdx = -1; state.chatIdx = -1;
  ($('tplname') as HTMLInputElement).value = name;
  ($('tplsel') as HTMLSelectElement).value = name;
  ($('docsel') as HTMLSelectElement).value = source;
  $('chatlog').replaceChildren(); $('result').replaceChildren();
  hooks.render(); show(state.fields.length ? 'fill' : 'edit');
}

function filterCatalog(): void {
  const q = ($('form-search') as HTMLInputElement).value.trim().toLocaleLowerCase();
  const cards = catalog.filter(form => form.name.toLocaleLowerCase().includes(q)).map(form => card(form.name, t(form.doc ? 'header.library' : 'flow.ready'), t('flow.use'), () => useTemplate(form.name, form.doc)));
  $('form-cards').replaceChildren(...cards);
  if (!cards.length) $('form-cards').textContent = t('flow.empty');
}

export async function refreshCatalog(): Promise<void> {
  try {
    const docs = await apiJson<DocsResponse>('/api/docs');
    catalog = docs.templates.map(name => ({ name }));
    if (docs.license?.licensed) {
      try {
        const library = await apiJson<LibraryStatus>('/api/library');
        catalog.push(...(library.docs || []).filter(doc => doc.has_template).map(doc => ({ name: doc.name, doc: doc.doc_id })));
      } catch { /* Local templates remain available if the shared library is offline. */ }
    }
    filterCatalog();
    $('catalog-retry').hidden = true;
    $('trial-status').hidden = !!docs.license?.licensed;
    try {
      const recent = await apiJson<HistoryStatus>('/api/history');
      $('recent-work').replaceChildren(...recent.files.filter(f => f.kind === 'sheet').slice(0, 4).map(f => card(f.title || f.name, t(f.printed ? 'hist.printedTag' : 'hist.draftTag'), t('flow.resume'), async () => {
        if (!await beforeDocumentChange()) return;
        await openSheet(f.name, hooks.markers, hooks.render);
      })));
      if (!$('recent-work').childElementCount) $('recent-work').textContent = t('hist.empty');
    } catch { $('recent-work').textContent = t('hist.loadFail'); }
  } catch { $('form-cards').textContent = t('flow.catalogError'); $('catalog-retry').hidden = false; }
}

async function loadPreview(): Promise<void> {
  const sequence = ++previewSequence;
  previewReady = false;
  ($('makepdf') as HTMLButtonElement).disabled = true;
  $('review-image').hidden = true; $('preview-retry').hidden = true;
  $('review-status').textContent = t('flow.loading');
  $('review-page').textContent = t('flow.page', { page: previewPage + 1, total: state.pages });
  ($('review-prev') as HTMLButtonElement).disabled = previewPage === 0;
  ($('review-next') as HTMLButtonElement).disabled = previewPage >= state.pages - 1;
  try {
    const response = await api('/api/fill-preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ doc: state.doc, fields: state.fields, page: previewPage }) });
    if (!response.ok) throw new Error((await response.json()).error || t('flow.previewFail'));
    const blob = await response.blob();
    if (sequence !== previewSequence || view !== 'review') return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    const img = $('review-image') as HTMLImageElement;
    img.src = previewUrl;
    await img.decode();
    if (sequence !== previewSequence || view !== 'review') return;
    img.hidden = false; $('review-status').textContent = '';
    previewReady = true;
    ($('makepdf') as HTMLButtonElement).disabled = !!$('review-issues').querySelector('.error');
  } catch (error) {
    if (sequence !== previewSequence) return;
    $('review-status').textContent = error instanceof Error ? error.message : t('flow.previewFail');
    $('preview-retry').hidden = false;
  }
}

async function beginReview(): Promise<void> {
  if (!state.doc || !state.fields.length) throw new Error(t('flow.noFields'));
  if (view === 'edit') { show('test'); hooks.render(); return; }
  try {
    await flushSheetSave();
  } catch {
    throw new Error(t('flow.saveFail'));
  }
  const info = await apiJson<PageInfo>('/api/pageinfo/' + encodeURIComponent(state.doc));
  if (document.fonts?.load) await document.fonts.load('16px FillPreview');
  const canvas = document.createElement('canvas'); const context = canvas.getContext('2d');
  const issues = reviewFields(state.fields, info.sizes, (text, size) => {
    if (!context) return 0;
    context.font = `${size}px FillPreview`; return context.measureText(text).width;
  });
  reviewReturn = view;
  $('review-issues').replaceChildren();
  for (const issue of issues) {
    const button = document.createElement('button');
    button.className = 'review-issue' + (issue.blocking ? ' error' : '');
    button.textContent = `${state.fields[issue.index].name}: ${t(issue.key)}`;
    button.onclick = () => { show(reviewReturn); const field = document.querySelector<HTMLInputElement>(`#valuelist input[data-i="${issue.index}"]`); field?.focus(); field?.scrollIntoView({ block: 'center' }); };
    $('review-issues').appendChild(button);
  }
  if (!issues.length) $('review-issues').textContent = t('flow.noIssues');
  const blank = state.fields.filter(f => !f.required && !f.value?.trim()).length;
  if (blank) { const p = document.createElement('p'); p.textContent = t('flow.optionalBlank', { count: blank }); $('review-issues').appendChild(p); }
  previewPage = 0; show('review'); await loadPreview();
}

export function canCreatePdf(): boolean { return view === 'review' && previewReady && !$('review-issues').querySelector('.error'); }
export function showPdfDone(): void { show('done'); }
export function isPreparing(): boolean { return ['edit', 'test'].includes(view) || (view === 'review' && reviewReturn === 'test'); }

export function initWorkflow(callbacks: Hooks): void {
  hooks = callbacks;
  $('nav-home').onclick = event => { event.preventDefault(); void safeAction(() => navigate('home')); };
  for (const [id, next] of Object.entries({ 'nav-forms': 'home', 'btn-hist-toggle': 'history', 'nav-settings': 'settings', 'nav-prepare': 'edit', 'back-to-forms': 'home' })) {
    $(id).onclick = () => void safeAction(() => navigate(next as View));
  }
  $('histhide').onclick = () => void safeAction(() => navigate('home'));
  $('form-search').oninput = filterCatalog;
  $('tplname').oninput = () => { markLayoutDirty(); syncWorkTitle(); };
  $('catalog-retry').onclick = () => void refreshCatalog();
  $('review-document').onclick = () => void safeAction(beginReview);
  $('review-back').onclick = () => show(reviewReturn);
  $('review-prev').onclick = () => { if (previewPage > 0) { previewPage--; void loadPreview(); } };
  $('review-next').onclick = () => { if (previewPage < state.pages - 1) { previewPage++; void loadPreview(); } };
  $('preview-retry').onclick = () => void loadPreview();
  $('result-edit').onclick = () => show(reviewReturn);
  $('result-new').onclick = () => void safeAction(async () => { await hooks.newSheet(); show('fill'); });
  $('result-folder').onclick = () => void safeAction(async () => { await apiJson('/api/open-folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ which: 'output' }) }); });
  $('tab-edit').onclick = () => void safeAction(async () => {
    if (state.sheet) await navigate('edit');
    else { show('edit'); hooks.render(); }
  });
  $('tab-fill').onclick = () => {
    show(view === 'edit' || view === 'test' || (view === 'review' && reviewReturn === 'test') ? 'test' : 'fill');
    hooks.render();
  };
  $('guided-fill').addEventListener('toggle', () => { if (($('guided-fill') as HTMLDetailsElement).open) window.dispatchEvent(new Event('workflow:guide')); });
  window.addEventListener('workflow:open', event => {
    const mode = (event as CustomEvent).detail;
    layoutDirty = false;
    show(mode === 'edit' ? 'edit' : mode === 'pdf' ? 'pdf' : 'fill');
    hooks.render();
  });
  window.addEventListener('beforeunload', event => { if (layoutDirty || hasPendingSheetSave()) { event.preventDefault(); event.returnValue = ''; } });
  show('home'); void refreshCatalog();
}
