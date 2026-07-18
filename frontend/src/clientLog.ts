/** ส่ง error จากเบราว์เซอร์ไป server (rate-limit ฝั่งเซิร์ฟเวอร์ + trailing flush) */

const MIN_INTERVAL_MS = 2500;
let lastSent = 0;
let suppressed = 0;
let pending: { level: string; message: string; stack?: string; source: string } | null = null;
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function eventId(): string {
  const d = new Date();
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return (
    "E-" +
    d.getFullYear() +
    pad(d.getMonth() + 1) +
    pad(d.getDate()) +
    "-" +
    pad(d.getHours()) +
    pad(d.getMinutes()) +
    pad(d.getSeconds()) +
    "-" +
    pad(d.getMilliseconds(), 3)
  );
}

async function postLog(
  level: string,
  message: string,
  stack: string | undefined,
  source: string,
  suppressedCount: number,
): Promise<void> {
  const eid = eventId();
  const body = {
    level,
    message: message.slice(0, 500),
    stack: (stack || "").slice(0, 2000),
    source,
    event_id: eid,
    suppressed: suppressedCount,
  };
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

function scheduleFlush(): void {
  if (flushTimer != null) return;
  const wait = Math.max(0, MIN_INTERVAL_MS - (Date.now() - lastSent));
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushPending();
  }, wait);
}

async function flushPending(): Promise<void> {
  if (!pending) return;
  const item = pending;
  pending = null;
  const count = suppressed;
  suppressed = 0;
  lastSent = Date.now();
  await postLog(item.level, item.message, item.stack, item.source, count);
}

async function send(level: string, message: string, stack?: string, source = "ui"): Promise<void> {
  const now = Date.now();
  if (now - lastSent < MIN_INTERVAL_MS) {
    suppressed += 1;
    pending = { level, message, stack, source };
    scheduleFlush();
    return;
  }
  if (flushTimer != null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  pending = null;
  const count = suppressed;
  suppressed = 0;
  lastSent = now;
  await postLog(level, message, stack, source, count);
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
