import { beforeEach, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ apiJson: vi.fn(), flush: vi.fn(), leave: vi.fn(), load: vi.fn(), open: vi.fn() }));
vi.mock('./api', () => ({ api: vi.fn(), apiJson: mocks.apiJson }));
vi.mock('./sheets', () => ({ flushSheetSave: mocks.flush, leaveActiveSheet: mocks.leave, openSheet: mocks.open, saveSheetNow: vi.fn(), hasPendingSheetSave: vi.fn(() => false) }));
vi.mock('./history', () => ({ setHistoryOpen: vi.fn() }));
vi.mock('./profiles', () => ({ setProfilesOpen: vi.fn() }));
vi.mock('./viewer', () => ({ loadDoc: mocks.load }));
vi.mock('./i18n', () => ({ t: (key: string) => key }));

beforeEach(() => {
  vi.resetModules(); vi.clearAllMocks();
  vi.stubGlobal('scrollTo', vi.fn());
  const ids = ['flow-message','active-title','fill-progress','home-view','history-view','settings-view','prepare-view','work-heading','workspace','work-actions','review-view','done-view','form-cards','recent-work','trial-status','chatlog','result','guided-fill','jobstatus'];
  const buttons = ['nav-home','nav-forms','btn-hist-toggle','nav-settings','nav-prepare','back-to-forms','review-document','histhide','catalog-retry','review-back','review-prev','review-next','preview-retry','result-edit','result-new','result-folder','tab-edit','tab-fill'];
  document.body.innerHTML = ids.map(id => `<div id="${id}"></div>`).join('') + buttons.map(id => `<button id="${id}"></button>`).join('') + '<input id="tplname"><input id="form-search"><select id="tplsel"></select><select id="docsel"></select>';
  document.body.insertAdjacentHTML('beforeend', '<div id="pagewrap"></div>');
  mocks.flush.mockResolvedValue(undefined); mocks.leave.mockResolvedValue(undefined); mocks.load.mockResolvedValue(undefined);
  mocks.apiJson.mockImplementation(async (url: string) => {
    if (url === '/api/docs') return { templates: ['Leave'], license: { licensed: true } };
    if (url === '/api/history') return { files: [] };
    return { doc: 'leave.pdf', fields: [{ name: 'Name', page: 0, x: 10, y: 20, size: 14, value: 'old value' }] };
  });
});

it('opens a chosen template straight into fill, without carrying values into the new sheet', async () => {
  const { initWorkflow } = await import('./workflow');
  const { state } = await import('./state');
  const setTab = vi.fn();
  initWorkflow({ setTab, render: vi.fn(), markers: vi.fn(), newSheet: vi.fn() });
  await vi.waitFor(() => expect(document.querySelector('#form-cards button')).not.toBeNull());
  (document.querySelector('#form-cards button') as HTMLButtonElement).click();
  await vi.waitFor(() => expect(document.body.dataset.view).toBe('fill'));
  expect(state.fields[0].value).toBe('');
  expect(mocks.load).toHaveBeenCalledWith('leave.pdf', expect.any(Function));
  expect(setTab).toHaveBeenLastCalledWith('fill');
});

it('keeps the current screen when autosave fails during navigation', async () => {
  const { initWorkflow } = await import('./workflow');
  initWorkflow({ setTab: vi.fn(), render: vi.fn(), markers: vi.fn(), newSheet: vi.fn() });
  mocks.flush.mockRejectedValue(new Error('Disk full'));
  document.getElementById('nav-settings')!.click();
  await vi.waitFor(() => expect(document.getElementById('flow-message')!.textContent).toBe('Disk full'));
  expect(document.body.dataset.view).toBe('home');
});


it('stays on fill when the fill tab is clicked during a live sheet', async () => {
  const { initWorkflow } = await import('./workflow');
  const { state } = await import('./state');
  const setTab = vi.fn();
  initWorkflow({ setTab, render: vi.fn(), markers: vi.fn(), newSheet: vi.fn() });
  await vi.waitFor(() => expect(document.querySelector('#form-cards button')).not.toBeNull());
  (document.querySelector('#form-cards button') as HTMLButtonElement).click();
  await vi.waitFor(() => expect(document.body.dataset.view).toBe('fill'));
  state.sheet = 'leave.json';
  document.getElementById('tab-fill')!.click();
  expect(document.body.dataset.view).toBe('fill');
  expect(setTab).toHaveBeenLastCalledWith('fill');
});

it('offers ready library forms from the same home screen', async () => {
  mocks.apiJson.mockImplementation(async (url: string) => {
    if (url === '/api/docs') return { templates: [], license: { licensed: true } };
    if (url === '/api/library') return { docs: [{ name: 'Library form', doc_id: '@lib.example', has_template: true }] };
    if (url === '/api/history') return { files: [] };
    return { fields: [{ name: 'Name', page: 0, x: 10, y: 20, size: 14, value: '' }] };
  });
  const { initWorkflow } = await import('./workflow');
  initWorkflow({ setTab: vi.fn(), render: vi.fn(), markers: vi.fn(), newSheet: vi.fn() });
  await vi.waitFor(() => expect(document.querySelector('#form-cards button')).not.toBeNull());
  (document.querySelector('#form-cards button') as HTMLButtonElement).click();
  await vi.waitFor(() => expect(document.body.dataset.view).toBe('fill'));
  expect(mocks.load).toHaveBeenCalledWith('@lib.example', expect.any(Function));
});
