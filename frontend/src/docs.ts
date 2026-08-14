import { $ } from "./dom";
import { api } from "./api";
import { state } from "./state";
import { renderLicense } from "./license";
import { loadDoc } from "./viewer";
import { t } from "./i18n";
import type { DocsResponse, TemplatePayload } from "./types";

export async function refreshDocs(onMarkers: () => void, onRender: () => void): Promise<void> {
  const res = await api("/api/docs");
  const r = (await res.json()) as DocsResponse;
  if (r.license) renderLicense(r.license);

  const demoDoc = r.license?.demo_doc || "demo-form.pdf";
  const docsel = $("docsel") as HTMLSelectElement;
  const tplsel = $("tplsel") as HTMLSelectElement;
  docsel.replaceChildren(new Option(t("header.selectPdf"), ""));
  for (const name of r.pdfs) docsel.add(new Option(name, name));
  tplsel.replaceChildren(new Option(t("header.newTemplate"), ""));
  for (const name of r.templates) tplsel.add(new Option(name, name));

  const fontName = (r.font || "").split(/[/\\]/).pop();
  $("fonthint").textContent = r.font
    ? t("docs.fontOk", { name: fontName || "" })
    : t("docs.fontMissing");
  if (r.user) {
    $("who").textContent = r.auth_required === false ? t("header.thisMachine") : r.user;
  }

  if (!state.doc && r.pdfs.includes(demoDoc)) {
    docsel.value = demoDoc;
    await loadDoc(demoDoc, onMarkers);
    if (r.templates.includes("demo-ใบเบิก")) {
      tplsel.value = "demo-ใบเบิก";
      const tres = await api("/api/template/" + encodeURIComponent("demo-ใบเบิก"));
      const tpl = (await tres.json()) as TemplatePayload;
      ($("tplname") as HTMLInputElement).value = "demo-ใบเบิก";
      state.fields = tpl.fields || [];
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
    try {
      await loadDoc(r.name, onMarkers);
    } catch (err) {
      alert(err instanceof Error ? err.message : t("app.loadDocFail"));
    }
  };

  ($("docsel") as HTMLSelectElement).onchange = (e) => {
    const v = (e.target as HTMLSelectElement).value;
    if (v) {
      void loadDoc(v, onMarkers).catch((err) => {
        alert(err instanceof Error ? err.message : t("app.loadDocFail"));
      });
    }
  };

  ($("tplsel") as HTMLSelectElement).onchange = async (e) => {
    const v = (e.target as HTMLSelectElement).value;
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
  };
}
