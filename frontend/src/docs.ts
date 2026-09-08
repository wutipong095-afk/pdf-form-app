import { beforeDocumentChange } from "./workflow";
import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { renderLicense } from "./license";
import { loadDoc, applyFontMetrics } from "./viewer";
import { leaveActiveSheet } from "./sheets";
import { t } from "./i18n";
import type { DocsResponse, TemplatePayload } from "./types";

export async function refreshDocs(_onMarkers: () => void, _onRender: () => void): Promise<void> {
  const res = await api("/api/docs");
  const r = (await res.json()) as DocsResponse;
  if (r.license) renderLicense(r.license);

  const docsel = $("docsel") as HTMLSelectElement;
  const tplsel = $("tplsel") as HTMLSelectElement;
  const selectedDoc = docsel.value;
  const selectedTemplate = tplsel.value;
  docsel.replaceChildren(new Option(t("header.selectPdf"), ""));
  for (const name of r.pdfs) docsel.add(new Option(name, name));
  tplsel.replaceChildren(new Option(t("header.newTemplate"), ""));
  for (const name of r.templates) tplsel.add(new Option(name, name));
  docsel.value = selectedDoc; tplsel.value = selectedTemplate;

  const fontName = (r.font || "").split(/[/\\]/).pop();
  $("fonthint").textContent = r.font
    ? t("docs.fontOk", { name: fontName || "" })
    : t("docs.fontMissing");
  applyFontMetrics(r.font_ascender, r.font_descender);
  if (r.user) {
    $("who").textContent = r.auth_required === false ? t("header.thisMachine") : r.user;
  }


}

export function bindDocs(
  onMarkers: () => void,
  onRender: () => void,
): void {
  ($("upfile") as HTMLInputElement).onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file || !await beforeDocumentChange()) return;
    const fd = new FormData();
    fd.append("file", file);
    const res = await api("/api/upload", { method: "POST", body: fd });
    const r = (await res.json()) as { name: string; error?: string; license_required?: boolean };
    if (r.error) {
      alert(r.error);
      return;
    }
    await refreshDocs(onMarkers, onRender);
    ($("docsel") as HTMLSelectElement).value = r.name;
    try {
      await leaveActiveSheet();
      await loadDoc(r.name, onMarkers);
      state.fields = []; state.selIdx = -1;
      ($("tplname") as HTMLInputElement).value = r.name.replace(/\.pdf$/i, "");
      onRender();
      window.dispatchEvent(new CustomEvent("workflow:open", { detail: "edit" }));
    } catch (err) {
      alert(err instanceof Error ? err.message : t("app.loadDocFail"));
    }
  };

  ($("docsel") as HTMLSelectElement).onchange = async (e) => {
    const v = (e.target as HTMLSelectElement).value;
    if (v) {
      try {
        if (!await beforeDocumentChange()) return;
        await leaveActiveSheet();
        await loadDoc(v, onMarkers);
        state.fields = []; state.selIdx = -1;
        ($("tplname") as HTMLInputElement).value = v.replace(/\.pdf$/i, "");
        onRender();
        window.dispatchEvent(new CustomEvent("workflow:open", { detail: "edit" }));
      } catch (err) {
        alert(err instanceof Error ? err.message : t("app.loadDocFail"));
      }
    }
  };

  ($("tplsel") as HTMLSelectElement).onchange = async (e) => {
    const v = (e.target as HTMLSelectElement).value;
    try { if (!await beforeDocumentChange()) return; await leaveActiveSheet(); } catch (err) {
      alert(err instanceof Error ? err.message : t("save.failedTitle"));
      return;
    }
    if (!v) {
      state.fields = [];
      onRender();
      return;
    }
    const res = await api("/api/template/" + encodeURIComponent(v));
    const tpl = (await res.json()) as TemplatePayload;
    ($("tplname") as HTMLInputElement).value = v;
    state.fields = tpl.fields || [];
    if (tpl.doc && tpl.doc !== state.doc) {
      try {
        await loadDoc(tpl.doc, onMarkers);
        ($("docsel") as HTMLSelectElement).value = tpl.doc;
      } catch (err) {
        alert(err instanceof Error ? err.message : t("app.loadDocFail"));
      }
    }
    onRender();
    window.dispatchEvent(new CustomEvent("workflow:open", { detail: "edit" }));
  };
}
