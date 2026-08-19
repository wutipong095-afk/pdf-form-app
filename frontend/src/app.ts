/**
 * PDF Form Marker — TypeScript UI entry
 */
import { $ } from "./dom";
import { api } from "./api";
import { isJobDoc, isOutDoc, state } from "./state";
import { bindLicenseUi } from "./license";
import { bindViewer, nudgeSelected, renderMarkers, showPage, ensureFillFont } from "./viewer";
import { bindValues, renderList, renderValues } from "./fields";
import { ask, bindChat, bub, startChat } from "./chat";
import { bindDocs, refreshDocs } from "./docs";
import { bindClientLog } from "./clientLog";
import { bindSchoolUi } from "./school";
import { bindLibrary, isLibDoc, refreshLibrary } from "./library";
import { bindHistory, notifyHistoryChanged } from "./history";
import { bindJobSaved, saveJobNow, scheduleJobSave, startNewSheet } from "./jobs";
import { bindBackupUi } from "./backup";
import { askFieldName, bindProfiles } from "./profiles";
import { bindLangToggle, t } from "./i18n";
import type { FillResponse } from "./types";

function setTab(tab: "edit" | "fill"): void {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  $("tab-" + tab).classList.add("active");
  $("panel-" + tab).classList.add("active");
  $("pagewrap").classList.toggle("marking", tab === "edit" && !isOutDoc(state.doc));
  paintMarkers();
  if (tab === "fill") void saveJobNow();
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
  renderAll();
  if (state.job) scheduleJobSave();
}

function renameField(i: number): void {
  const n = prompt(t("app.renamePrompt"), state.fields[i].name);
  if (n) {
    state.fields[i].name = n.trim();
    renderAll();
    if (state.job) scheduleJobSave();
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
      scheduleJobSave();
    },
  );
}

function renderAll(): void {
  renderList(selField, renameField, delField);
  renderValues();
  paintMarkers();
}

function bindTabs(): void {
  $("tab-edit").onclick = () => setTab("edit");
  $("tab-fill").onclick = () => {
    setTab("fill");
    renderValues();
    startChat();
  };
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
      body: JSON.stringify({ doc: tplDoc, fields: state.fields }),
    });
    const body = (await res.json().catch(() => ({}))) as { error?: string; library?: boolean };
    if (!res.ok) {
      alert(body.error || t("app.saveFail"));
      return;
    }
    if (isLibDoc(tplDoc)) {
      await refreshLibrary().catch(() => undefined);
    } else if (!isJobDoc(state.doc)) {
      await refreshDocs(paintMarkers, renderAll);
      ($("tplsel") as HTMLSelectElement).value = name;
    }
    alert(t("app.saveOk", { name, count: state.fields.length }));
  };
}

function bindClearAndFill(): void {
  $("clearvals").onclick = () => {
    if (!confirm(t("app.clearConfirm"))) return;
    startNewSheet();
    state.fields.forEach((f) => {
      f.value = "";
    });
    state.chatIdx = -1;
    $("chatlog").innerHTML = "";
    renderAll();
    startChat();
    scheduleJobSave();
  };

  $("makepdf").onclick = async () => {
    if (!state.doc) return;
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
      return;
    }
    await saveJobNow();
    const outname = (($("tplname") as HTMLInputElement).value || "filled").trim() || "filled";
    // ใบใหม่หลังกดล้างค่ายังไม่ได้เปลี่ยน state.doc — สร้าง PDF จากใบที่กำลังแก้จริง
    const fillDoc = state.job ? "@job." + state.job : state.doc;
    const res = await api("/api/fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc: fillDoc, fields: state.fields, outname }),
    });
    const r = (await res.json()) as FillResponse;
    if (r.error) {
      $("result").textContent = "❌ " + r.error;
      return;
    }
    const result = $("result");
    result.replaceChildren(t("app.donePrefix"));
    const link = document.createElement("a");
    link.href = "/download/" + encodeURIComponent(r.file!);
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = t("app.openFile", { file: r.file! });
    result.appendChild(link);
    bub(t("app.created", { file: r.file! }), "bot");
    notifyHistoryChanged();
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
    paintMarkers();
    if (state.job) scheduleJobSave();
  });
}

function bindMarking(): void {
  bindViewer(paintMarkers, (x, y) => {
    if (state.selIdx >= 0) {
      state.fields[state.selIdx].x = x;
      state.fields[state.selIdx].y = y;
      state.fields[state.selIdx].page = state.cur;
      state.selIdx = -1;
      renderAll();
      if (state.job) scheduleJobSave();
      return;
    }
    // Naming is async — the dialog offers field names already in the autofill book
    const page = state.cur;
    const size = parseFloat(($("fsize") as HTMLInputElement).value) || 14;
    void askFieldName().then((name) => {
      if (!name) return;
      state.fields.push({ name: name.trim(), page, x, y, size, value: "" });
      renderAll();
      if (state.job) scheduleJobSave();
    });
  });
}

/**
 * After autofill: repaint values/markers, and move the chat on only if the box it is
 * currently asking about got filled — otherwise the same question is asked twice.
 */
function afterProfileApply(): void {
  renderAll();
  scheduleJobSave();
  if (state.chatIdx < 0) return;
  const asking = state.fields[state.chatIdx];
  if (asking && (asking.value || "").trim()) ask();
}

function init(): void {
  bindLangToggle();
  bindClientLog();
  bindSchoolUi();
  bindLicenseUi(() => {
    void refreshDocs(paintMarkers, renderAll);
  });
  bindLibrary(paintMarkers, renderAll);
  bindHistory(paintMarkers, renderAll);
  bindJobSaved(() => notifyHistoryChanged());
  bindBackupUi(paintMarkers, renderAll);
  bindProfiles(afterProfileApply);
  bindDocs(paintMarkers, renderAll);
  bindMarking();
  bindValues(
    (i, value) => {
      state.fields[i].value = value;
      paintMarkers();
      renderList(selField, renameField, delField);
      scheduleJobSave();
    },
    (i) => {
      state.fields[i].value = "";
      renderAll();
      scheduleJobSave();
    },
    gotoField,
  );
  bindTabs();
  bindChat(
    (page) => {
      state.cur = page;
      showPage(paintMarkers);
    },
    () => {
      renderAll();
      scheduleJobSave();
    },
  );
  bindTemplateSave();
  bindClearAndFill();
  bindKeyboard();
  ensureFillFont(paintMarkers);
  void refreshDocs(paintMarkers, renderAll);
}

init();
