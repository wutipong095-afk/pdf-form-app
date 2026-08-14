/**
 * PDF Form Marker — TypeScript UI entry
 */
import { $ } from "./dom";
import { api } from "./api";
import { isOutDoc, state } from "./state";
import { bindLicenseUi } from "./license";
import { bindViewer, nudgeSelected, renderMarkers, showPage } from "./viewer";
import { bindValues, renderList, renderValues } from "./fields";
import { bindChat, bub, startChat } from "./chat";
import { bindDocs, refreshDocs } from "./docs";
import { bindClientLog } from "./clientLog";
import { bindSchoolUi } from "./school";
import { bindLibrary, isLibDoc, refreshLibrary } from "./library";
import { bindHistory, notifyHistoryChanged } from "./history";
import { bindBackupUi } from "./backup";
import { bindLangToggle, t } from "./i18n";
import type { FillResponse } from "./types";

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
  renderAll();
}

function renameField(i: number): void {
  const n = prompt(t("app.renamePrompt"), state.fields[i].name);
  if (n) {
    state.fields[i].name = n.trim();
    renderAll();
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
    const res = await api("/api/template/" + encodeURIComponent(name), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc: state.doc, fields: state.fields }),
    });
    const body = (await res.json().catch(() => ({}))) as { error?: string; library?: boolean };
    if (!res.ok) {
      alert(body.error || t("app.saveFail"));
      return;
    }
    if (isLibDoc(state.doc)) {
      await refreshLibrary().catch(() => undefined);
    } else {
      await refreshDocs(paintMarkers, renderAll);
      ($("tplsel") as HTMLSelectElement).value = name;
    }
    alert(t("app.saveOk", { name, count: state.fields.length }));
  };
}

function bindClearAndFill(): void {
  $("clearvals").onclick = () => {
    if (!confirm(t("app.clearConfirm"))) return;
    state.fields.forEach((f) => {
      f.value = "";
    });
    state.chatIdx = -1;
    $("chatlog").innerHTML = "";
    renderAll();
    startChat();
  };

  $("makepdf").onclick = async () => {
    if (!state.doc) return;
    if (isOutDoc(state.doc)) {
      $("result").textContent = t("app.fillFromHistory");
      return;
    }
    const demoDoc = state.lic?.demo_doc || "demo-form.pdf";
    if (
      state.lic &&
      !state.lic.licensed &&
      String(state.doc).toLowerCase() !== String(demoDoc).toLowerCase()
    ) {
      $("result").textContent = t("app.needLicense", { demo: demoDoc });
      return;
    }
    const outname = (($("tplname") as HTMLInputElement).value || "filled").trim() || "filled";
    const res = await api("/api/fill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc: state.doc, fields: state.fields, outname }),
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
  });
}

function bindMarking(): void {
  bindViewer(paintMarkers, (x, y) => {
    if (state.selIdx >= 0) {
      state.fields[state.selIdx].x = x;
      state.fields[state.selIdx].y = y;
      state.fields[state.selIdx].page = state.cur;
      state.selIdx = -1;
    } else {
      const name = prompt(t("app.markNamePrompt"));
      if (!name) return;
      const size = parseFloat(($("fsize") as HTMLInputElement).value) || 14;
      state.fields.push({ name, page: state.cur, x, y, size, value: "" });
    }
    renderAll();
  });
}

function init(): void {
  bindLangToggle();
  bindClientLog();
  bindSchoolUi();
  bindLicenseUi();
  bindLibrary(paintMarkers, renderAll);
  bindHistory(paintMarkers, renderAll);
  bindBackupUi(paintMarkers, renderAll);
  bindDocs(paintMarkers, renderAll);
  bindMarking();
  bindValues(
    (i, value) => {
      state.fields[i].value = value;
      paintMarkers();
      renderList(selField, renameField, delField);
    },
    (i) => {
      state.fields[i].value = "";
      renderAll();
    },
    gotoField,
  );
  bindTabs();
  bindChat(
    (page) => {
      state.cur = page;
      showPage(paintMarkers);
    },
    renderAll,
  );
  bindTemplateSave();
  bindClearAndFill();
  bindKeyboard();
  void refreshDocs(paintMarkers, renderAll);
}

init();
