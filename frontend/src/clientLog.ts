/** ส่ง error จากเบราว์เซอร์ไป server (rate-limit ฝั่งเซิร์ฟเวอร์) */

const MIN_INTERVAL_MS = 2500;
let lastSent = 0;
let suppressed = 0;

function eventId(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    "E-" +
    d.getFullYear() +
    pad(d.getMonth() + 1) +
    pad(d.getDate()) +
    "-" +
    pad(d.getHours()) +
    pad(d.getMinutes()) +
    pad(d.getSeconds())
  );
}

async function send(level: string, message: string, stack?: string, source = "ui"): Promise<void> {
  const now = Date.now();
  if (now - lastSent < MIN_INTERVAL_MS) {
    suppressed += 1;
    return;
  }
  lastSent = now;
  const eid = eventId();
  const body = {
    level,
    message: message.slice(0, 500),
    stack: (stack || "").slice(0, 2000),
    source,
    event_id: eid,
    suppressed,
  };
  suppressed = 0;
  try {
    await fetch("/api/client-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    });
  } catch {
    // เงียบ — อย่าวนลูป error จากตัวส่ง log เอง
  }
}

export function bindClientLog(): void {
  window.addEventListener("error", (ev) => {
    const msg = ev.message || String(ev.error || "window.error");
    const stack = ev.error && ev.error.stack ? String(ev.error.stack) : undefined;
    void send("error", msg, stack, "window.onerror");
  });
  window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev.reason;
    const msg =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "unhandledrejection";
    const stack = reason instanceof Error ? reason.stack : undefined;
    void send("error", msg, stack, "unhandledrejection");
  });
}
