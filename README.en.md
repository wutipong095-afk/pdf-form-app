# PDF Form Marker

Mark fields on a PDF, then overlay Thai (or any) text as a layer (PyMuPDF + Flask).  
Built for **schools** — install on a PC, works offline, license bound to the machine.

Separate from the `school-reports` vault — a general government/school form filler.

Roadmap: [ROADMAP.md](ROADMAP.md) · Backlog: [docs/BACKLOG.md](docs/BACKLOG.md)  
Thai README: [README.md](README.md)

---

## School mode (default)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Set SESSION_COOKIE_SECURE=false in .env for local runs
python app.py
```

Open http://localhost:5000 — **no login required**

| What the app provides | Location (Windows) |
|-----------------------|--------------------|
| Data / license | `%LOCALAPPDATA%\PDFFormMarker\data` |
| Sheets (the filled values) | Pick your own folder from the backup bar · default `%LOCALAPPDATA%\PDFFormMarker\data\users\<user>\sheets` |
| Form snapshots (blank PDFs, one copy per form) | `%LOCALAPPDATA%\PDFFormMarker\data\users\<user>\forms` |
| Logs | `%LOCALAPPDATA%\PDFFormMarker\logs` |
| Bind | `127.0.0.1` only |

In the app: **PDF output** · **Support report** · **Backup / restore**  
(System folder `%LOCALAPPDATA%\PDFFormMarker\data` stays internal — not exposed as a UI button)

On first launch you get **demo-form.pdf** + template **demo-ใบเบิก** to try immediately.

UI language: choose **Thai / English** in the header (remembered via cookie + local file).

Backup/restore: [docs/BACKUP.en.md](docs/BACKUP.en.md) — ZIP has no `machine_id`/license (a new PC needs a new key)

Windows installer: [docs/INSTALLER.en.md](docs/INSTALLER.en.md) — `.\scripts\build_windows.ps1`  
Linux / macOS packages: [docs/PACKAGING.en.md](docs/PACKAGING.en.md) — `./scripts/build_linux.sh` · `./scripts/build_macos.sh`  
Update notices (`latest.json`): [docs/UPDATE.en.md](docs/UPDATE.en.md)

If you already have project `./data`, the app **keeps using that folder**  
(or set `DATA_DIR=./data` in `.env`)

A fresh machine without `./data` stores under `%LOCALAPPDATA%\PDFFormMarker\` (Windows)

---

## Frontend (TypeScript)

UI lives in [`frontend/`](frontend/) — builds into `static/` for Flask

```bash
cd frontend
npm install
npm run build    # → static/js/app.js
npm run dev      # UI on :5173 (run python app.py alongside)
```

Locale catalogs: [`locales/th.json`](locales/th.json), [`locales/en.json`](locales/en.json)

## CI / CD

GitHub Actions runs `pytest`, frontend tests/build, and a Docker smoke test on every PR and every push to `master`.  
To ship: tag `v0.3.2` (must match `APP_VERSION`). That builds `FormDD-Setup-*.exe` and opens a GitHub Release as a copy — the primary host stays `formdd.xambrain.com` ([docs/UPDATE.en.md](docs/UPDATE.en.md)).

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

---

## Developer / multi-user mode

Require login:

```env
AUTH_REQUIRED=true
ADMIN_USER=admin
ADMIN_PASSWORD=changeme
SESSION_COOKIE_SECURE=false
```

Docker + Caddy deploy (advanced — **not** the main school path): see [DEPLOY.md](DEPLOY.md)

```bash
cp .env.example .env   # set SECRET_KEY, passwords, DOMAIN — never ship default passwords on the network
docker compose up -d --build
```

---

## Document library (CP2)

In-app **Document library** bar: set a root folder → auto scaffold `01-การเงิน` / `02-พัสดุ` / `03-บุคคล` → scan/search PDFs → open to fill

- Index: `<root>/.pdfmarker/index.json`
- Sidecar template: `name.pdf` + `name.tpl.json` in the same folder
- Chosen root path stored in `DATA_DIR/library.json` (PDFs stay in the library)
- Library docs use ids like `@lib.` + base64url of the relative path

## Layout

| path | Role |
|------|------|
| `app.py` | API + PDF + logging |
| `i18n_core.py` | UI locale helper |
| `locales/` | `th.json` / `en.json` string catalogs |
| `library_core.py` | Library scan/index |
| `logging_setup.py` | Rotating log files |
| `templates/` | HTML (login + app) |
| `frontend/` | TypeScript UI (Vite) |
| `fonts/` | Thai civil-service fonts (TH Sarabun = Arabic digits; IT๙ = Thai digits if `FONT_PATH` set) |
| `demo/` | Sample PDF + template (committed) |
| `data/users/<user>/` | Used when `DATA_DIR=./data` (not in git) |

---

## License (1 machine; term is in the key)

- Verified with **Ed25519**: the app ships only `license_public.pem` — customers cannot mint keys
- Machine ID persisted in `DATA_DIR/machine_id`
- Without a key: PDF creation only for the official **contents** of `demo-form.pdf`
- With a key: any document until expiry (UTC)

Issue keys (vendor machine with private key only):

```bash
python scripts/gen_keypair.py          # first time only
python scripts/gen_license.py <16-char-machine-id>
```

Do not commit / do not put in Docker: `keys/ed25519_private.pem`

Local development only (never on customer PCs):

```env
LICENSE_BYPASS=true
```
