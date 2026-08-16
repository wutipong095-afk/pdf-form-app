/** Autofill book — reusable field name → value pairs, matched by exact field name */
import { $ } from "./dom";
import { apiJson } from "./api";
import { state } from "./state";
import { t } from "./i18n";
import type { Profile, ProfileKind, ProfileSaveResponse, ProfilesResponse } from "./types";

const KINDS: ProfileKind[] = ["org", "partner", "person"];

let profilesOpen = false;
let profiles: Profile[] = [];
let selectedId = "";
let dirty = false;
/** Non-empty while the server says profiles.json cannot be read */
let loadError = "";
/** Draft rows in the editor — kept as an array so blank/duplicate keys can exist while typing */
let rows: { key: string; value: string }[] = [];

export function setProfilesOpen(open: boolean): void {
  profilesOpen = open;
  const bar = $("profbar");
  bar.classList.toggle("open", open);
  bar.setAttribute("aria-hidden", open ? "false" : "true");
  const btn = $("btn-prof-toggle");
  btn.classList.toggle("active", open);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.textContent = open ? t("header.hideProfiles") : t("header.profiles");
  if (open) {
    setStatus(loadError || t("prof.loading"));
    void refreshProfiles().catch((err) => setStatus(loadErrorText(err)));
  }
}

/** A damaged book must say so — never look like an empty one, or the user will just add over it */
function loadErrorText(err: unknown): string {
  loadError = err instanceof Error && err.message ? err.message : t("prof.loadFail");
  return loadError;
}

function setStatus(msg: string): void {
  $("profstatus").textContent = msg;
}

function kindLabel(kind: ProfileKind): string {
  return t("prof.kind" + kind.charAt(0).toUpperCase() + kind.slice(1));
}

/** Every field name known to the book — feeds the pin-name datalist */
export function knownKeys(): string[] {
  const set = new Set<string>();
  for (const p of profiles) {
    for (const k of Object.keys(p.values)) set.add(k);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

function suggestedKeys(): string[] {
  return t("prof.suggestedKeys")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export async function refreshProfiles(): Promise<void> {
  const data = await apiJson<ProfilesResponse>("/api/profiles");
  loadError = "";
  profiles = data.profiles || [];
  if (selectedId && !profiles.some((p) => p.id === selectedId)) {
    selectedId = "";
    dirty = false;
  }
  renderProfilesUi();
  setStatus(profiles.length ? t("prof.ready", { count: profiles.length }) : t("prof.empty"));
}

function current(): Profile | null {
  return profiles.find((p) => p.id === selectedId) || null;
}

function loadRowsFrom(p: Profile | null): void {
  rows = p ? Object.entries(p.values).map(([key, value]) => ({ key, value })) : [];
  dirty = false;
}

function renderProfilesUi(): void {
  renderList();
  renderEditor();
  renderApplySelect();
  syncMarkDatalist();
}

function renderList(): void {
  const box = $("proflist");
  if (!profiles.length) {
    const empty = document.createElement("div");
    empty.className = "pick-empty";
    empty.textContent = t("prof.empty");
    box.replaceChildren(empty);
    return;
  }
  const frag = document.createDocumentFragment();
  for (const p of profiles) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pick-item" + (p.id === selectedId ? " sel" : "");
    btn.dataset.id = p.id;
    const meta = document.createElement("span");
    meta.className = "meta";
    const n = Object.keys(p.values).length;
    meta.textContent = `${kindLabel(p.kind)} · ${n}`;
    btn.append(p.name, meta);
    frag.appendChild(btn);
  }
  box.replaceChildren(frag);
}

function renderEditor(): void {
  const p = current();
  const editor = $("profedit");
  editor.hidden = !p;
  if (!p) return;

  ($("profname") as HTMLInputElement).value = p.name;
  const kindSel = $("profkind") as HTMLSelectElement;
  kindSel.replaceChildren(...KINDS.map((k) => new Option(kindLabel(k), k)));
  kindSel.value = p.kind;

  const pairs = $("profpairs");
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "pick-empty";
    empty.textContent = t("prof.noRows");
    pairs.replaceChildren(empty);
  } else {
    const frag = document.createDocumentFragment();
    rows.forEach((row, i) => {
      const line = document.createElement("div");
      line.className = "prow";

      const key = document.createElement("input");
      key.type = "text";
      key.className = "pkey";
      key.dataset.i = String(i);
      key.dataset.part = "key";
      key.value = row.key;
      key.placeholder = t("prof.keyPlaceholder");
      key.maxLength = 80;

      const val = document.createElement("input");
      val.type = "text";
      val.className = "pval";
      val.dataset.i = String(i);
      val.dataset.part = "value";
      val.value = row.value;
      val.placeholder = t("prof.valuePlaceholder");
      val.maxLength = 500;

      const del = document.createElement("button");
      del.type = "button";
      del.className = "prowdel";
      del.dataset.del = String(i);
      del.title = t("prof.removeRow");
      del.textContent = "✕";

      line.append(key, val, del);
      frag.appendChild(line);
    });
    pairs.replaceChildren(frag);
  }

  const sugg = $("profsuggest");
  const frag = document.createDocumentFragment();
  const label = document.createElement("span");
  label.className = "sugglabel";
  label.textContent = t("prof.suggested");
  frag.appendChild(label);
  const used = new Set(rows.map((r) => r.key.trim()));
  for (const key of suggestedKeys()) {
    if (used.has(key)) continue;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "suggchip";
    chip.dataset.key = key;
    chip.textContent = "+ " + key;
    frag.appendChild(chip);
  }
  sugg.replaceChildren(frag);
}

/** Keeps the pin-name <datalist> in sync so marking can reuse existing names */
function syncMarkDatalist(): void {
  const list = document.getElementById("profkeys") as HTMLDataListElement | null;
  if (!list) return;
  list.replaceChildren(...knownKeys().map((k) => new Option(k, k)));
}

function renderApplySelect(): void {
  const sel = $("profapplysel") as HTMLSelectElement;
  const keep = sel.value;
  sel.replaceChildren(new Option(t("prof.applySelect"), ""));
  for (const p of profiles) sel.add(new Option(p.name, p.id));
  sel.value = profiles.some((p) => p.id === keep) ? keep : "";
  const has = profiles.length > 0;
  $("profapplyrow").hidden = !has;
}

/** Collapsing two rows with the same name would silently drop one — report it instead */
function duplicateKey(): string | null {
  const seen = new Set<string>();
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    if (seen.has(key)) return key;
    seen.add(key);
  }
  return null;
}

function collectValues(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (key) out[key] = row.value.trim();
  }
  return out;
}

function selectProfile(id: string): void {
  // Already open — reloading would silently throw the draft away on a misclick
  if (id === selectedId) return;
  if (dirty && !confirm(t("prof.unsavedAsk"))) return;
  selectedId = id;
  loadRowsFrom(current());
  renderProfilesUi();
}

async function createProfile(name: string, kind: ProfileKind, values: Record<string, string>): Promise<void> {
  const res = await apiJson<ProfileSaveResponse>("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, kind, values }),
  });
  if (!res.profile) throw new Error(res.error || t("prof.saveFail"));
  profiles.push(res.profile);
  selectedId = res.profile.id;
  loadRowsFrom(res.profile);
  renderProfilesUi();
  setStatus(t("prof.ready", { count: profiles.length }));
}

async function saveCurrent(): Promise<void> {
  const p = current();
  if (!p) {
    alert(t("prof.pickFirst"));
    return;
  }
  const name = ($("profname") as HTMLInputElement).value.trim();
  if (!name) {
    alert(t("prof.needName"));
    return;
  }
  const dup = duplicateKey();
  if (dup) {
    alert(t("prof.duplicateRow", { name: dup }));
    return;
  }
  const kind = ($("profkind") as HTMLSelectElement).value as ProfileKind;
  const values = collectValues();
  const res = await apiJson<ProfileSaveResponse>("/api/profiles/" + encodeURIComponent(p.id), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, kind, values }),
  });
  if (!res.profile) throw new Error(res.error || t("prof.saveFail"));
  const i = profiles.findIndex((x) => x.id === p.id);
  if (i >= 0) profiles[i] = res.profile;
  loadRowsFrom(res.profile);
  renderProfilesUi();
  setStatus(t("prof.saved", { name: res.profile.name, count: Object.keys(res.profile.values).length }));
}

/**
 * Fills fields whose name matches a profile key exactly.
 * replaceAll=false leaves anything the user already typed untouched.
 */
export function applyProfile(profile: Profile, replaceAll: boolean): { filled: number; missed: number } {
  const keys = new Map<string, string>();
  for (const [k, v] of Object.entries(profile.values)) keys.set(k.trim(), v);
  let filled = 0;
  let missed = 0;
  for (const f of state.fields) {
    const hit = keys.get(f.name.trim());
    if (hit === undefined) {
      missed++;
      continue;
    }
    if (!replaceAll && (f.value || "").trim()) continue;
    f.value = hit;
    filled++;
  }
  return { filled, missed };
}

function bindBar(): void {
  $("btn-prof-toggle").onclick = () => setProfilesOpen(!profilesOpen);
  $("profhide").onclick = () => setProfilesOpen(false);

  $("proflist").onclick = (e) => {
    const btn = (e.target as HTMLElement).closest("button.pick-item") as HTMLButtonElement | null;
    if (btn?.dataset.id) selectProfile(btn.dataset.id);
  };

  $("profnew").onclick = () => {
    if (dirty && !confirm(t("prof.unsavedAsk"))) return;
    void createProfile(t("prof.newName"), "org", {}).catch((err) =>
      alert(err instanceof Error ? err.message : t("prof.saveFail")),
    );
  };

  $("profpairs").addEventListener("input", (e) => {
    const el = e.target as HTMLInputElement;
    const i = el.dataset.i;
    if (i === undefined || !el.dataset.part) return;
    const row = rows[Number(i)];
    if (!row) return;
    if (el.dataset.part === "key") row.key = el.value;
    else row.value = el.value;
    dirty = true;
  });

  $("profpairs").addEventListener("click", (e) => {
    const del = (e.target as HTMLElement).closest("[data-del]") as HTMLElement | null;
    if (!del) return;
    rows.splice(Number(del.dataset.del), 1);
    dirty = true;
    renderEditor();
  });

  $("profaddrow").onclick = () => {
    rows.push({ key: "", value: "" });
    dirty = true;
    renderEditor();
    const inputs = $("profpairs").querySelectorAll<HTMLInputElement>("input.pkey");
    inputs[inputs.length - 1]?.focus();
  };

  $("profsuggest").addEventListener("click", (e) => {
    const chip = (e.target as HTMLElement).closest("[data-key]") as HTMLElement | null;
    if (!chip?.dataset.key) return;
    rows.push({ key: chip.dataset.key, value: "" });
    dirty = true;
    renderEditor();
  });

  for (const id of ["profname", "profkind"]) {
    $(id).addEventListener("input", () => {
      dirty = true;
    });
  }

  $("profsave").onclick = () => {
    void saveCurrent().catch((err) => alert(err instanceof Error ? err.message : t("prof.saveFail")));
  };

  $("profdup").onclick = () => {
    const p = current();
    if (!p) {
      alert(t("prof.pickFirst"));
      return;
    }
    const dup = duplicateKey();
    if (dup) {
      alert(t("prof.duplicateRow", { name: dup }));
      return;
    }
    const name = ($("profname") as HTMLInputElement).value.trim() || p.name;
    const kind = ($("profkind") as HTMLSelectElement).value as ProfileKind;
    void createProfile(t("prof.duplicateSuffix", { name }), kind, collectValues()).catch((err) =>
      alert(err instanceof Error ? err.message : t("prof.saveFail")),
    );
  };

  $("profdel").onclick = () => {
    const p = current();
    if (!p) {
      alert(t("prof.pickFirst"));
      return;
    }
    if (!confirm(t("prof.deleteConfirm", { name: p.name }))) return;
    void apiJson("/api/profiles/" + encodeURIComponent(p.id), { method: "DELETE" })
      .then(() => {
        profiles = profiles.filter((x) => x.id !== p.id);
        selectedId = "";
        loadRowsFrom(null);
        renderProfilesUi();
        setStatus(profiles.length ? t("prof.ready", { count: profiles.length }) : t("prof.empty"));
      })
      .catch((err) => alert(err instanceof Error ? err.message : t("prof.deleteFail")));
  };
}

function bindApply(onApplied: () => void): void {
  const run = (replaceAll: boolean) => {
    const sel = $("profapplysel") as HTMLSelectElement;
    const p = profiles.find((x) => x.id === sel.value);
    if (!p) {
      $("profapplystatus").textContent = t("prof.applyPick");
      return;
    }
    if (!state.fields.length) {
      $("profapplystatus").textContent = t("prof.applyNoFields");
      return;
    }
    if (replaceAll && !confirm(t("prof.replaceAllConfirm", { name: p.name }))) return;
    const { filled, missed } = applyProfile(p, replaceAll);
    $("profapplystatus").textContent = filled
      ? t("prof.applyResult", { filled, missed })
      : t("prof.applyNone");
    onApplied();
  };
  $("profapply").onclick = () => run(false);
  $("profreplace").onclick = () => run(true);
}

export function bindProfiles(onApplied: () => void): void {
  bindBar();
  bindApply(onApplied);
  // Load quietly so the fill tab and the pin-name datalist work without opening the bar.
  // A failure is remembered, not swallowed — the bar shows it when opened.
  void refreshProfiles().catch((err) => loadErrorText(err));
}

/**
 * Pin naming with the book's field names offered as a datalist.
 * Falls back to prompt() where <dialog> is unavailable.
 */
export function askFieldName(): Promise<string | null> {
  const dlg = document.getElementById("markdlg") as HTMLDialogElement | null;
  const input = document.getElementById("markname") as HTMLInputElement | null;
  const ok = document.getElementById("markok");
  const cancel = document.getElementById("markcancel");
  // Missing dialog (older cached HTML, no <dialog> support) must never block marking
  if (!dlg || typeof dlg.showModal !== "function" || !input || !ok || !cancel) {
    return Promise.resolve(prompt(t("app.markNamePrompt")));
  }
  syncMarkDatalist();
  input.value = "";
  return new Promise((resolve) => {
    // Close the dialog ourselves rather than leaning on <form method="dialog">
    let settled = false;
    const finish = (value: string | null) => {
      if (settled) return;
      settled = true;
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      input.removeEventListener("keydown", onKey);
      dlg.removeEventListener("close", onCancel);
      if (dlg.open) dlg.close();
      resolve(value);
    };
    const onOk = () => finish(input.value.trim() || null);
    const onCancel = () => finish(null);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onOk();
      }
    };
    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
    input.addEventListener("keydown", onKey);
    dlg.addEventListener("close", onCancel); // Esc
    dlg.showModal();
    input.focus();
  });
}
