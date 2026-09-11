/**
 * PDF Form Marker — TypeScript UI entry
 */
import { $ } from "./dom";
import { api } from "./api";
import { isFormDoc, isOutDoc, state } from "./state";
import { bindLicenseUi } from "./license";
import { bindViewer, nudgeSelected, renderMarkers, showPage, ensureFillFont } from "./viewer";
import { bindValues, renderList, renderValues } from "./fields";
import { ask, bindChat, bub, startChat } from "./chat";
import { bindDocs, refreshDocs } from "./docs";
import { bindClientLog } from "./clientLog";
import { bindSchoolUi } from "./school";
import { bindLibrary, isLibDoc, refreshLibrary } from "./library";
import { bindHistory, notifyHistoryChanged } from "./history";
import { bindSheetSaved, flushSheetSave, scheduleSheetSave, startNewSheet } from "./sheets";
import { bindBackupUi } from "./backup";
import { bindWorkDir } from "./workdir";
import { renderFillResult } from "./fillResult";
import { askFieldName, bindProfiles } from "./profiles";
import { bindLangToggle, t } from "./i18n";
import { initWorkflow, syncWorkTitle, markLayoutDirty, markLayoutSaved, flowError, canCreatePdf, showPdfDone, isPreparing, beforeDocumentChange } from "./workflow";
import type { FillResponse } from "./types";
import { isQuickFill, editQuickText, commitQuickInput } from './quickFill';

function quickChanged(): void { markLayoutDirty(); renderAll(); }

function setTab(tab: "edit" | "fill"): void {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  $("tab-" + tab).classList.add("active");
  $("panel-" + tab).classList.add("active");
  $("pagewrap").classList.toggle("marking", tab === "edit" && !isOutDoc(state.doc));
  paintMarkers();

}

function gotoField(i: number): void {
  if (state.fields[i].page !== state.cur) {
    state.cur = state.fields[i].page;
    showPage(paintMarkers);
  }
}

function selField(i: number): void {
  state.selIdx = state.selIdx === i ? -1 : i;
  gotoField(i);
  renderAll();
}

function delField(i: number): void {
  if (!confirm(t("app.deleteConfirm", { name: state.fields[i].name }))) return;
  state.fields.splice(i, 1);
  state.selIdx = -1;
  markLayoutDirty();
  renderAll();
  if (state.sheet) scheduleSheetSave();
}

function renameField(i: number): void {
  const n = prompt(t("app.renamePrompt"), state.fields[i].name);
  if (n) {
    state.fields[i].name = n.trim();
    markLayoutDirty();
    renderAll();
    if (state.sheet) scheduleSheetSave();
  }
}

function paintMarkers(): void {
  renderMarkers(
    (i) => {
      state.selIdx = state.selIdx === i ? -1 : i;
      renderAll();
    },
    (i, value) => {
      state.fields[i].value = value;
      renderAll();
      scheduleSheetSave();
    },
    quickChanged,
  );
}

function renderAll(): void {
  renderList(selField, renameField, delField);
  renderValues();
  paintMarkers();
  syncWorkTitle();
  renderFieldOptions();
}

function bindTemplateSave(): void {
  $("savetpl").onclick = async () => {
    const name = ($("tplname") as HTMLInputElement).value.trim();
    if (!state.doc || !name) {
      alert(t("app.needPdfAndName"));
      return;
    }
    if (isOutDoc(state.doc)) {
      alert(t("app.fillFromHistory"));
      return;
    }
    const tplDoc = state.sourceDoc || state.doc;
    const res = await api("/api/template/" + encodeURIComponent(name), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc: tplDoc, fields: state.fields.map((f) => ({ ...f, value: "" })) }),
    });
    const body = (await res.json().catch(() => ({}))) as { error?: string; library?: boolean };
    if (!res.ok) {
      alert(body.error || t("app.saveFail"));
      return;
    }
    if (isLibDoc(tplDoc)) {
      await refreshLibrary().catch(() => undefined);
    } else if (!isFormDoc(state.doc)) {
      await refreshDocs(paintMarkers, renderAll);
      ($("tplsel") as HTMLSelectElement).value = name;
    }
    markLayoutSaved();
    syncWorkTitle();
    const listed = [...($("tplsel") as HTMLSelectElement).options].some(option => option.value === name);
    alert(t(!state.lic?.licensed && !listed ? "flow.savedTrial" : "flow.setupSaved"));
  };
}

async function newSheet(): Promise<void> {
  await flushSheetSave();
  startNewSheet();
  state.fields = state.fields.map(field => ({ ...field, value: "" }));
  state.chatIdx = -1;
  $("chatlog").replaceChildren();
  $("result").replaceChildren();
  renderAll();
}

function renderFieldOptions(): void {
  const field = state.fields[state.selIdx];
  $("field-options").hidden = !field;
  if (!field) return;
  $("field-option-name").textContent = field.name;
  const required = $("field-required") as HTMLInputElement;
  const kind = $("field-type") as HTMLSelectElement;
  const width = $("field-width") as HTMLInputElement;
  const size = $("field-size") as HTMLInputElement;
  required.checked = !!field.required; kind.value = field.input_type || "text";
  width.value = field.width == null ? "" : String(field.width); size.value = String(field.size);
  const update = () => {
    if (!width.checkValidity() || !size.checkValidity()) return;
    field.required = required.checked;
    field.input_type = kind.value as "text" | "number" | "date";
    if (width.value) field.width = Number(width.value); else delete field.width;
    if (size.value) field.size = Number(size.value);
    markLayoutDirty();
    paintMarkers();
  };
  required.onchange = update; kind.onchange = update; width.onchange = update; size.onchange = update;
}

function bindClearAndFill(): void {
  $("clearvals").onclick = () => { void newSheet().catch(flowError); };

  $("makepdf").onclick = async () => {
    commitQuickInput();
    if (!state.doc || !canCreatePdf()) return;
    if (isOutDoc(state.doc)) {
      $("result").textContent = t("app.fillFromHistory");
      return;
    }
    const demoDocs = (state.lic?.demo_docs || [state.lic?.demo_doc || "demo-form.pdf"]).map((n) =>
      String(n).toLowerCase(),
    );
    const fillKey = String(state.sourceDoc || state.doc).toLowerCase();
    const docName = fillKey.split(/[/\\|]/).pop() || fillKey;
    if (state.lic && !state.lic.licensed && !demoDocs.includes(docName) && !demoDocs.includes(fillKey)) {
      $("result").textContent = t("app.needLicense");
      if (isQuickFill()) flowError(t('app.needLicense'));
      return;
    }
    const button = $("makepdf") as HTMLButtonElement;
    button.disabled = true;
    ($('quick-export') as HTMLButtonElement).disabled = true;
    button.textContent = t("flow.creating");
    try {
    if (!isPreparing()) {
      try { await flushSheetSave(); }
      catch { throw new Error(t("flow.saveFail")); }
    }
    const outname = state.sheetTitle || (($("tplname") as HTMLInputElement).value || "filled").trim() || "filled";
    const res = await api("/api/fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // ส่ง sheet ไปด้วยเพื่อให้ฝั่งเซิร์ฟเวอร์จำได้ว่า PDF นี้พิมพ์จากใบไหน
      body: JSON.stringify({ doc: state.doc, fields: state.fields, outname, sheet: state.sheet }),
    });
    const r = (await res.json()) as FillResponse;
    if (r.error) {
      throw new Error(r.error);
    }
    renderFillResult(r);
    bub(t("app.created", { file: r.file! }), "bot");
    notifyHistoryChanged();
    showPdfDone();
    } catch (error) { flowError(error); }
    finally { button.disabled = false; ($('quick-export') as HTMLButtonElement).disabled = false; button.textContent = t("flow.create"); }
  };
}

function bindKeyboard(): void {
  window.addEventListener("resize", paintMarkers);
  window.addEventListener("keydown", (e) => {
    if (state.selIdx < 0 || !$("panel-edit").classList.contains("active")) return;
    if (document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
    const step = e.shiftKey ? 5 : 0.5;
    if (e.key === "ArrowUp") nudgeSelected(0, -step);
    else if (e.key === "ArrowDown") nudgeSelected(0, step);
    else if (e.key === "ArrowLeft") nudgeSelected(-step, 0);
    else if (e.key === "ArrowRight") nudgeSelected(step, 0);
    else if (e.key === "Escape") {
      state.selIdx = -1;
      renderAll();
      return;
    } else return;
    e.preventDefault();
    markLayoutDirty();
    paintMarkers();
    if (state.sheet) scheduleSheetSave();
  });
}

function bindMarking(): void {
  bindViewer(paintMarkers, (x, y) => {
    if (isQuickFill()) { editQuickText(x, y, quickChanged); return; }
    if (state.selIdx >= 0) {
      state.fields[state.selIdx].x = x;
      state.fields[state.selIdx].y = y;
      state.fields[state.selIdx].page = state.cur;
      markLayoutDirty();
      state.selIdx = -1;
      renderAll();
      if (state.sheet) scheduleSheetSave();
      return;
    }
    // Naming is async — the dialog offers field names already in the autofill book
    const page = state.cur;
    const size = parseFloat(($("fsize") as HTMLInputElement).value) || 14;
    void askFieldName().then((name) => {
      if (!name) return;
      markLayoutDirty();
      state.fields.push({ name: name.trim(), page, x, y, size, value: "" });
      renderAll();
      if (state.sheet) scheduleSheetSave();
    });
  });
}

/**
 * After autofill: repaint values/markers, and move the chat on only if the box it is
 * currently asking about got filled — otherwise the same question is asked twice.
 */
function afterProfileApply(): void {
  renderAll();
  scheduleSheetSave();
  if (state.chatIdx < 0) return;
  const asking = state.fields[state.chatIdx];
  if (asking && (asking.value || "").trim()) ask();
}

function init(): void {
  bindLangToggle(beforeDocumentChange);
  bindClientLog();
  bindSchoolUi();
  bindLicenseUi(() => {
    void refreshDocs(paintMarkers, renderAll);
  });
  bindLibrary(paintMarkers, renderAll);
  bindHistory(paintMarkers, renderAll);
  bindSheetSaved(() => { notifyHistoryChanged(); syncWorkTitle(); });
  bindBackupUi(paintMarkers, renderAll);
  bindWorkDir(() => notifyHistoryChanged());
  bindProfiles(afterProfileApply);
  bindDocs(paintMarkers, renderAll);
  bindMarking();
  bindValues(
    (i, value) => {
      state.fields[i].value = value;
      paintMarkers();
      renderList(selField, renameField, delField);
      scheduleSheetSave();
      syncWorkTitle();
    },
    (i) => {
      state.fields[i].value = "";
      renderAll();
      scheduleSheetSave();
    },
    gotoField,
  );
  window.addEventListener("workflow:guide", startChat);
  bindChat(
    (page) => {
      state.cur = page;
      showPage(paintMarkers);
    },
    () => {
      renderAll();
      scheduleSheetSave();
    },
  );
  bindTemplateSave();
  bindClearAndFill();
  bindKeyboard();
  $('quick-export').onclick = () => { commitQuickInput(); $('makepdf').click(); };
  $('quick-size').onchange = () => {
    const input = $('quick-size') as HTMLInputElement;
    if (!input.value || !input.checkValidity()) return;
    const field = state.fields[state.selIdx];
    if (field) { field.size = Number(input.value); quickChanged(); }
  };
  $('quick-delete').onclick = () => {
    commitQuickInput();
    if (state.selIdx < 0) return;
    state.fields.splice(state.selIdx, 1); state.selIdx = -1; quickChanged();
  };
  ensureFillFont(paintMarkers);
  initWorkflow({ setTab, render: renderAll, markers: paintMarkers, newSheet });
  void refreshDocs(paintMarkers, renderAll).catch(flowError);
}

init();
