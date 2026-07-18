import { $ } from "./dom";
import { state } from "./state";

export function renderList(onGoto: (i: number) => void, onRename: (i: number) => void, onDel: (i: number) => void): void {
  $("fieldlist").innerHTML = state.fields
    .map((f, i) => {
      const val = f.value ? ` = <b>${escapeHtml(f.value)}</b>` : "";
      return `<li class="${i === state.selIdx ? "sel" : ""}" data-i="${i}">
        <span class="fname" data-act="goto">📍 ${escapeHtml(f.name)} <small>(หน้า ${f.page + 1}, ${f.size}pt)</small>${val}</span>
        <button class="del" style="color:#0077ff" data-act="rename" title="เปลี่ยนชื่อฟิลด์">✏️</button>
        <button class="del" data-act="del" title="ลบจุดนี้ทิ้ง">✕</button>
      </li>`;
    })
    .join("");

  $("fieldlist").onclick = (e) => {
    const t = e.target as HTMLElement;
    const li = t.closest("li[data-i]") as HTMLElement | null;
    if (!li) return;
    const i = Number(li.dataset.i);
    const act = (t.closest("[data-act]") as HTMLElement | null)?.dataset.act;
    if (act === "rename") onRename(i);
    else if (act === "del") onDel(i);
    else onGoto(i);
  };
}

export function renderValues(): void {
  const el = $("valuelist");
  el.innerHTML = state.fields
    .map(
      (f, i) =>
        `<div class="vrow">
          <span class="vname" data-goto="${i}" title="${escapeAttr(f.name)} (หน้า ${f.page + 1})">📍 ${escapeHtml(f.name)}</span>
          <input data-i="${i}" value="${escapeAttr(f.value || "")}" placeholder="— ว่าง —">
          <button class="del" data-clear="${i}" title="ล้างค่าช่องนี้">✕</button>
        </div>`,
    )
    .join("");
}

export function bindValues(
  onChange: (i: number, value: string) => void,
  onClear: (i: number) => void,
  onGoto: (i: number) => void,
): void {
  const el = $("valuelist");
  el.addEventListener("input", (e) => {
    const t = e.target as HTMLInputElement;
    const i = t.dataset.i;
    if (i === undefined) return;
    onChange(Number(i), t.value.trim());
  });
  el.addEventListener("click", (e) => {
    const t = e.target as HTMLElement;
    if (t.dataset.clear !== undefined) {
      onClear(Number(t.dataset.clear));
      return;
    }
    if (t.dataset.goto !== undefined) onGoto(Number(t.dataset.goto));
  });
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(s: string): string {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
