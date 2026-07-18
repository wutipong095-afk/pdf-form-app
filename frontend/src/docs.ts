import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { renderLicense } from "./license";
import { loadDoc } from "./viewer";
import type { DocsResponse, TemplatePayload } from "./types";

export async function refreshDocs(onMarkers: () => void, onRender: () => void): Promise<void> {
  const res = await api("/api/docs");
  const r = (await res.json()) as DocsResponse;
  if (r.license) renderLicense(r.license);

  const demoDoc = r.license?.demo_doc || "demo-form.pdf";
  const docsel = $("docsel") as HTMLSelectElement;
  const tplsel = $("tplsel") as HTMLSelectElement;
  docsel.innerHTML =
    '<option value="">— เลือก PDF —</option>' + r.pdfs.map((p) => `<option>${p}</option>`).join("");
  tplsel.innerHTML =
    '<option value="">— เทมเพลตใหม่ —</option>' +
    r.templates.map((t) => `<option>${t}</option>`).join("");

  const fontName = (r.font || "").split(/[/\\]/).pop();
  $("fonthint").textContent = r.font ? "ฟอนต์ทับ: " + fontName : "⚠️ ไม่พบฟอนต์ไทย";
  if (r.user) $("who").textContent = r.user;

  if (!state.doc && r.pdfs.includes(demoDoc)) {
    docsel.value = demoDoc;
    await loadDoc(demoDoc, onMarkers);
    if (r.templates.includes("demo-ใบเบิก")) {
      tplsel.value = "demo-ใบเบิก";
      const tres = await api("/api/template/" + encodeURIComponent("demo-ใบเบิก"));
      const t = (await tres.json()) as TemplatePayload;
      ($("tplname") as HTMLInputElement).value = "demo-ใบเบิก";
      state.fields = t.fields || [];
      onRender();
    }
  }
}

export function bindDocs(
  onMarkers: () => void,
  onRender: () => void,
): void {
  ($("upfile") as HTMLInputElement).onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const res = await api("/api/upload", { method: "POST", body: fd });
    const r = (await res.json()) as { name: string; error?: string };
    if (r.error) {
      alert(r.error);
      return;
    }
    await refreshDocs(onMarkers, onRender);
    ($("docsel") as HTMLSelectElement).value = r.name;
    await loadDoc(r.name, onMarkers);
  };

  ($("docsel") as HTMLSelectElement).onchange = (e) => {
    const v = (e.target as HTMLSelectElement).value;
    if (v) void loadDoc(v, onMarkers);
  };

  ($("tplsel") as HTMLSelectElement).onchange = async (e) => {
    const v = (e.target as HTMLSelectElement).value;
    if (!v) {
      state.fields = [];
      onRender();
      return;
    }
    const res = await api("/api/template/" + encodeURIComponent(v));
    const t = (await res.json()) as TemplatePayload;
    ($("tplname") as HTMLInputElement).value = v;
    state.fields = t.fields || [];
    if (t.doc && t.doc !== state.doc) {
      await loadDoc(t.doc, onMarkers);
      ($("docsel") as HTMLSelectElement).value = t.doc;
    }
    onRender();
  };
}
