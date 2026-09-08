import { $ } from "./dom";
import { state } from "./state";
import { t } from "./i18n";

export function renderList(onGoto: (i: number) => void, onRename: (i: number) => void, onDel: (i: number) => void): void {
  $("fieldlist").innerHTML = state.fields
    .map((f, i) => {
      const val = f.value ? ` = <b>${escapeHtml(f.value)}</b>` : "";
      const meta = t("fields.pageSize", { page: f.page + 1, size: f.size });
      return `<li class="${i === state.selIdx ? "sel" : ""}" data-i="${i}">
        <span class="fname" data-act="goto">📍 ${escapeHtml(f.name)} <small>${escapeHtml(meta)}</small>${val}</span>
        <button class="del" style="color:#0077ff" data-act="rename" title="${escapeAttr(t("fields.renameTitle"))}">✏️</button>
        <button class="del" data-act="del" title="${escapeAttr(t("fields.deleteTitle"))}">✕</button>
      </li>`;
    })
    .join("");

  $("fieldlist").onclick = (e) => {
    const target = e.target as HTMLElement;
    const li = target.closest("li[data-i]") as HTMLElement | null;
    if (!li) return;
    const i = Number(li.dataset.i);
    const act = (target.closest("[data-act]") as HTMLElement | null)?.dataset.act;
    if (act === "rename") onRename(i);
    else if (act === "del") onDel(i);
    else onGoto(i);
  };
}

export function renderValues(): void {
  const el = $("valuelist");
  let lastPage = -1;
  el.innerHTML = state.fields
    .map((f, i) => ({ f, i }))
    .sort((a, b) => a.f.page - b.f.page || a.i - b.i)
    .map(({ f, i }) => {
      const heading = f.page !== lastPage ? `<h3 class="field-group">${escapeHtml(t("flow.pageGroup", { page: f.page + 1 }))}</h3>` : "";
      lastPage = f.page;
      const type = f.input_type === "date" ? "date" : "text";
      return `${heading}<div class="vrow">
      <label for="value-${i}" data-goto="${i}">${escapeHtml(f.name)}${f.required ? " *" : ""}</label>
      <input id="value-${i}" data-i="${i}" type="${type}" ${f.input_type === "number" ? 'inputmode="decimal"' : ""} ${f.required ? 'required aria-required="true"' : ""} value="${escapeAttr(f.value || "")}" placeholder="${escapeAttr(t("fields.emptyPlaceholder"))}">
      <button data-clear="${i}" aria-label="${escapeAttr(t("fields.clearTitle") + ": " + f.name)}">✕</button>
    </div>`;
    }).join("");
}

export function bindValues(
  onChange: (i: number, value: string) => void,
  onClear: (i: number) => void,
  onGoto: (i: number) => void,
): void {
  const el = $("valuelist");
  el.addEventListener("input", (e) => {
    const target = e.target as HTMLInputElement;
    const i = target.dataset.i;
    if (i === undefined) return;
    onChange(Number(i), target.value.trim());
  });
  el.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    if (target.dataset.clear !== undefined) {
      onClear(Number(target.dataset.clear));
      return;
    }
    if (target.dataset.goto !== undefined) onGoto(Number(target.dataset.goto));
  });
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
