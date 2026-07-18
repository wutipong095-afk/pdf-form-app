export function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element #${id}`);
  return el;
}

export function $el<T extends HTMLElement>(id: string): T {
  return $(id) as T;
}
