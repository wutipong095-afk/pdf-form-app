"""จุดเข้า Windows desktop — Waitress + หน้าต่างสถานะ + เปิดเบราว์เซอร์

ปิดหน้าต่างสถานะ = หยุดเซิร์ฟเวอร์
ไม่รวมใน Docker / พัฒนาปกติ (ใช้ python app.py)
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from typing import NoReturn, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ค่าเริ่มต้นโหมดโรงเรียน ก่อน import app
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "5000")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

# ห้าม bypass ไลเซนต์ใน build ปล่อยจริง
if getattr(sys, "frozen", False):
    os.environ.pop("LICENSE_BYPASS", None)

SERVER_IDENT = "PDFFormMarker"
_DEFAULT_PORT = 5000

# ผลจาก thread เซิร์ฟเวอร์ (ว่าง = ยังรันปกติ)
_server_error: list[BaseException] = []


def _fatal(message: str) -> NoReturn:
    """แสดง error ให้เห็นแม้ console=False แล้วออก"""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("PDF Form Marker", message)
        root.destroy()
    except Exception:
        pass
    raise SystemExit(1)


def _resolve_port() -> int:
    raw = os.environ.get("PORT", str(_DEFAULT_PORT))
    if raw is None or str(raw).strip() == "":
        return _DEFAULT_PORT
    try:
        port = int(str(raw).strip())
    except ValueError:
        _fatal(
            f"ค่า PORT ไม่ถูกต้อง: {raw!r}\n"
            f"ต้องเป็นตัวเลข 1–65535 (ค่าเริ่มต้น {_DEFAULT_PORT})"
        )
    if not (1 <= port <= 65535):
        _fatal(f"ค่า PORT นอกช่วง: {port}\nต้องอยู่ระหว่าง 1–65535")
    return port


def _tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _looks_like_ours(server: str, body: str) -> bool:
    """ระบุแอปเรา: header Waitress ident หรือ JSON license ที่มี demo_doc เฉพาะ"""
    if SERVER_IDENT in (server or ""):
        return True
    # กัน false positive จาก API อื่นที่มีแค่ "licensed" / "machine_id"
    return (
        '"demo_doc"' in body
        and "demo-form.pdf" in body
        and '"machine_id"' in body
    )


def _probe_app(host: str, port: int) -> str:
    """ตรวจพอร์ต — คืน 'ours' | 'foreign' | 'closed' | 'unknown'

    unknown = TCP เปิดแต่ยังตอบ HTTP ไม่ได้ (timeout / อุ่นเครื่อง) → ให้ retry
    foreign = ได้ HTTP response แล้วแต่ไม่ใช่เรา
    """
    if not _tcp_open(host, port):
        return "closed"
    try:
        # cold start: get_machine_id รอได้ ~1s + waitress/ed25519 บนเครื่องช้า
        req = Request(f"http://{host}:{port}/api/license", method="GET")
        with urlopen(req, timeout=2.0) as resp:
            server = resp.headers.get("Server") or ""
            body = resp.read(4096).decode("utf-8", errors="ignore")
        return "ours" if _looks_like_ours(server, body) else "foreign"
    except HTTPError as e:
        # ได้ response จริง (เช่น 401) — ตัดสินจาก header/body ได้
        server = (e.headers.get("Server") if e.headers else None) or ""
        body = ""
        try:
            body = e.read(4096).decode("utf-8", errors="ignore")
        except Exception:
            pass
        return "ours" if _looks_like_ours(server, body) else "foreign"
    except (URLError, OSError, TimeoutError, ValueError):
        # ยังไม่พร้อม / timeout — อย่าตีเป็น foreign
        return "unknown"


def _serve(host: str, port: int) -> None:
    try:
        from waitress import serve

        from app import app

        serve(app, host=host, port=port, threads=8, ident=SERVER_IDENT)
    except BaseException as exc:  # noqa: BLE001 — ต้องโชว์ทุกอย่างที่ทำให้เซิร์ฟเวอร์ตาย
        _server_error.append(exc)


def _format_server_error(exc: BaseException) -> str:
    if isinstance(exc, OSError):
        return (
            f"เปิดเซิร์ฟเวอร์ไม่สำเร็จ\n\n{exc}\n\n"
            "พอร์ตอาจถูกใช้งาน หรือสิทธิ์เครื่องไม่อนุญาต"
        )
    return f"เซิร์ฟเวอร์หยุดทำงาน\n\n{type(exc).__name__}: {exc}"


def _run_status_ui(
    url: str,
    *,
    already_running: bool,
    server_thread: Optional[threading.Thread] = None,
) -> None:
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("PDF Form Marker")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))

    frame = ttk.Frame(root, padding=16)
    frame.grid(row=0, column=0)

    title_var = tk.StringVar(
        value="กำลังทำงานอยู่แล้ว" if already_running else "PDF Form Marker กำลังทำงาน"
    )
    detail_var = tk.StringVar(value=url)

    title_lbl = ttk.Label(frame, textvariable=title_var, font=("Segoe UI", 11, "bold"))
    title_lbl.grid(row=0, column=0, columnspan=2, sticky="w")
    detail_lbl = ttk.Label(frame, textvariable=detail_var, wraplength=340)
    detail_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 12))

    dead = {"shown": False}

    def open_browser() -> None:
        webbrowser.open(url)

    def stop_app() -> None:
        root.destroy()
        os._exit(0)

    btn_open = ttk.Button(frame, text="เปิดเบราว์เซอร์", command=open_browser)
    btn_open.grid(row=2, column=0, padx=(0, 8), sticky="ew")

    if already_running:
        ttk.Button(frame, text="ปิดหน้าต่างนี้", command=root.destroy).grid(
            row=2, column=1, sticky="ew"
        )
    else:
        btn_stop = ttk.Button(frame, text="หยุดโปรแกรม", command=stop_app)
        btn_stop.grid(row=2, column=1, sticky="ew")
        root.protocol("WM_DELETE_WINDOW", stop_app)

        def watch_server() -> None:
            if dead["shown"]:
                return
            exc = _server_error[0] if _server_error else None
            died = exc is not None or (
                server_thread is not None and not server_thread.is_alive()
            )
            if not died:
                root.after(500, watch_server)
                return
            dead["shown"] = True
            title_var.set("เซิร์ฟเวอร์หยุดทำงาน")
            if exc is not None:
                detail_var.set(_format_server_error(exc))
            else:
                detail_var.set(
                    "เซิร์ฟเวอร์ปิดตัวโดยไม่ทราบสาเหตุ\n"
                    "ดู log ที่ %LOCALAPPDATA%\\PDFFormMarker\\logs\\"
                )
            btn_open.state(["disabled"])
            btn_stop.configure(text="ปิด")

        root.after(500, watch_server)

    root.mainloop()


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _resolve_port()
    url = f"http://{host}:{port}/"

    # pre-start: retry ถ้า unknown (instance เก่าอุ่นเครื่อง) — อย่าเพิ่ง bind ทับ
    probe = "closed"
    for _ in range(8):
        probe = _probe_app(host, port)
        if probe in ("ours", "foreign", "closed"):
            break
        time.sleep(0.25)

    if probe == "ours":
        webbrowser.open(url)
        _run_status_ui(url, already_running=True)
        return
    if probe == "foreign":
        _fatal(
            f"พอร์ต {port} ถูกใช้โดยโปรแกรมอื่นอยู่แล้ว\n\n"
            f"ปิดโปรแกรมนั้น หรือตั้ง PORT เป็นพอร์ตว่างแล้วเปิดใหม่\n"
            f"(ตอนนี้ไม่เปิดเบราว์เซอร์ไปที่บริการอื่น)"
        )
    if probe == "unknown":
        # TCP เปิดแต่ไม่ตอบเป็นแอปเราภายในเวลา — อย่า bind ทับ
        _fatal(
            f"พอร์ต {port} มีโปรแกรมอื่นเปิดอยู่ แต่ตอบไม่ทันหรือไม่ใช่ PDF Form Marker\n\n"
            "ปิดโปรแกรมนั้น หรือเปลี่ยน PORT แล้วเปิดใหม่"
        )

    # import app → create_app() สร้าง DATA_DIR / SECRET_KEY / seed demo
    try:
        import app as _app  # noqa: F401
    except BaseException as exc:  # noqa: BLE001
        _fatal(f"เริ่มแอปไม่สำเร็จ\n\n{type(exc).__name__}: {exc}")

    server = threading.Thread(target=_serve, args=(host, port), daemon=True)
    server.start()

    ready = False
    # ~50 × (sleep 0.1 + probe สูงสุด ~2s) — พอสำหรับ cold start เครื่องช้า
    for _ in range(50):
        if _server_error:
            _fatal(_format_server_error(_server_error[0]))
        status = _probe_app(host, port)
        if status == "ours":
            ready = True
            break
        if status == "foreign":
            _fatal(
                f"พอร์ต {port} ถูกโปรแกรมอื่นใช้งานระหว่างเริ่มต้น\n\n"
                "ปิดโปรแกรมนั้น หรือเปลี่ยน PORT แล้วเปิดใหม่"
            )
        # closed / unknown → รอต่อ (unknown = อุ่นเครื่อง / timeout)
        if not server.is_alive() and not _server_error:
            _fatal(
                "เซิร์ฟเวอร์ปิดตัวก่อนพร้อมใช้งาน\n"
                "ดู log ที่ %LOCALAPPDATA%\\PDFFormMarker\\logs\\"
            )
        time.sleep(0.1)

    if not ready:
        if _server_error:
            _fatal(_format_server_error(_server_error[0]))
        _fatal(
            f"เซิร์ฟเวอร์ไม่พร้อมภายในเวลาที่กำหนด\n"
            f"ลองเปิดใหม่ หรือเปลี่ยน PORT (ปัจจุบัน {port})"
        )

    webbrowser.open(url)
    _run_status_ui(url, already_running=False, server_thread=server)


if __name__ == "__main__":
    main()
