import { $ } from "./dom";
import { state } from "./state";

export function bub(text: string, who: "bot" | "user"): void {
  const d = document.createElement("div");
  d.className = "bub " + who;
  d.textContent = text;
  const log = $("chatlog");
  log.appendChild(d);
  log.scrollTop = 1e9;
}

export function ask(): void {
  while (state.chatIdx < state.fields.length && state.fields[state.chatIdx].value) {
    state.chatIdx++;
  }
  if (state.chatIdx < state.fields.length) {
    bub(`กรอก: ${state.fields[state.chatIdx].name}`, "bot");
  } else {
    bub('ครบทุกช่องแล้ว ✅ กด "สร้าง PDF" ได้เลย หรือพิมพ์ แก้ [ชื่อฟิลด์] เพื่อแก้ค่า', "bot");
  }
}

export function startChat(): void {
  if (!state.fields.length) {
    bub("ยังไม่มีจุดที่มาร์คไว้ — กลับไปแท็บ ① ก่อนครับ", "bot");
    return;
  }
  if (state.chatIdx === -1) {
    state.chatIdx = 0;
    bub(`มี ${state.fields.length} ช่องให้กรอก เริ่มเลย!`, "bot");
    ask();
  }
}

export function handleChat(
  onNeedPage: (page: number) => void,
  onRender: () => void,
): void {
  const input = $("chatinput") as HTMLInputElement;
  const v = input.value.trim();
  if (!v) return;
  input.value = "";
  bub(v, "user");

  const m = v.match(/^แก้\s*(.*)$/);
  if (m) {
    const q = m[1].trim();
    let i = q ? state.fields.findIndex((f) => f.name === q) : -1;
    if (i < 0 && q) i = state.fields.findIndex((f) => f.name.includes(q));
    if (i < 0) {
      bub(
        `ไม่พบฟิลด์ "${q}" — พิมพ์แค่บางส่วนของชื่อก็ได้ หรือแก้ในตารางด้านบน/คลิกจุดบนเอกสารได้เลย`,
        "bot",
      );
      return;
    }
    state.fields[i].value = "";
    state.chatIdx = i;
    onRender();
    ask();
    return;
  }

  if (state.chatIdx >= 0 && state.chatIdx < state.fields.length) {
    state.fields[state.chatIdx].value = v === "-" ? "" : v;
    if (state.fields[state.chatIdx].page !== state.cur) {
      onNeedPage(state.fields[state.chatIdx].page);
    }
    onRender();
    state.chatIdx++;
    ask();
  }
}

export function bindChat(
  onNeedPage: (page: number) => void,
  onRender: () => void,
): void {
  $("chatsend").onclick = () => handleChat(onNeedPage, onRender);
  $("chatinput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleChat(onNeedPage, onRender);
  });
}
