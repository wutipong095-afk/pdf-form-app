/**
 * PDF Form Marker — TypeScript UI entry (เต็มหน้า)
 */
import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { bindLicenseUi } from "./license";
import { bindViewer, nudgeSelected, renderMarkers, showPage } from "./viewer";
import { bindValues, renderList, renderValues } from "./fields";
import { bindChat, bub, startChat } from "./chat";
import { bindDocs, refreshDocs } from "./docs";
import type { FillResponse } from "./types";

function setTab(t: "edit" | "fill"): void {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  $("tab-" + t).classList.add("active");
  $("panel-" + t).classList.add("active");
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
  if (!confirm(`ลบจุด "${state.fields[i].name}" ทิ้ง?`)) return;
  state.fields.splice(i, 1);
  state.selIdx = -1;
  renderAll();
}

function renameField(i: number): void {
  const n = prompt("ชื่อใหม่ของฟิลด์:", state.fields[i].name);
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
      alert("เลือก PDF และตั้งชื่อเทมเพลตก่อน");
      return;
    }
    await api("/api/template/" + encodeURIComponent(name), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc: state.doc, fields: state.fields }),
    });
    await refreshDocs(paintMarkers, renderAll);
    ($("tplsel") as HTMLSelectElement).value = name;
    alert(`บันทึกเทมเพลต "${name}" แล้ว (${state.fields.length} จุด)`);
  };
}

function bindClearAndFill(): void {
  $("clearvals").onclick = () => {
    if (!confirm("ล้างค่าที่กรอกไว้ทั้งหมด เพื่อเริ่มกรอกรอบใหม่? (จุดที่มาร์คไว้ยังอยู่ครบ)")) return;
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
    const demoDoc = state.lic?.demo_doc || "demo-form.pdf";
    if (
      state.lic &&
      !state.lic.licensed &&
      String(state.doc).toLowerCase() !== String(demoDoc).toLowerCase()
    ) {
      $("result").textContent =
        "❌ ยังไม่มีไลเซนต์ — ส่งรหัสเครื่องด้านบนให้ผู้ขาย หรือทดลองกับ " + demoDoc;
      return;
    }
    const outname =
      (($("tplname") as HTMLInputElement).value || "filled") +
      "-" +
      new Date().toISOString().slice(0, 10);
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
    $("result").innerHTML = `✅ <a href="/download/${encodeURIComponent(r.file!)}" target="_blank">เปิด ${r.file}</a>`;
    bub("สร้างไฟล์ " + r.file + " เรียบร้อย 🎉", "bot");
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
      const name = prompt("ชื่อข้อมูลของจุดนี้ (เช่น ชื่อผู้เบิก):");
      if (!name) return;
      const size = parseFloat(($("fsize") as HTMLInputElement).value) || 14;
      state.fields.push({ name, page: state.cur, x, y, size, value: "" });
    }
    renderAll();
  });
}

function init(): void {
  bindLicenseUi();
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
