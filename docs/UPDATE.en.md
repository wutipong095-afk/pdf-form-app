# App update notices (offline-safe)

Thai: [UPDATE.md](UPDATE.md)

The app checks a vendor `latest.json` feed.  
If offline or no URL is configured — normal use continues with no error.

FromDD primary host: `https://fromdd.xambrain.com/releases/latest.json`  
The installer ships `update_feed.url` automatically.

## What customers see

A blue bar under the header: new version → **Install** (download, verify SHA-256, then launch Setup).  
A browser link remains as fallback.  
Dismissible (remembered per version in the browser).

## Vendor setup

1. A build produces under `dist/installer/`:
   - `FromDD-Setup-x.y.z.exe` (never a generic `FromDD-Setup.exe` that gets overwritten)
   - `latest.json` (includes `sha256` / `size`)
   - `SHA256SUMS.txt`
2. Upload the **new** `.exe` to `/var/www/fromdd/releases/` — **do not overwrite** an older `FromDD-Setup-x.y.z.exe`
3. Upload `latest.json` (this file may be overwritten; it is the pointer)
4. Create a GitHub Release every time as a backup — see below

## latest.json shape

```json
{
  "version": "0.3.1",
  "setup_url": "https://fromdd.xambrain.com/releases/FromDD-Setup-0.3.1.exe",
  "sha256": "abcdef....64 hex....",
  "size": 34603008,
  "published_at": "2026-08-13",
  "notes": "Short release note"
}
```

- `version` must be newer than the app (numeric semver compare)
- `setup_url` must be HTTPS and the filename must match the version, e.g. `FromDD-Setup-0.3.1.exe`
- `sha256` is required for the in-app Install button (verified before running)
- `size` is recommended — when present, the app also checks the byte length
- Full examples: `docs/latest.example.json` / `website/releases/latest.example.json`

After Inno, `scripts/build_windows.ps1` runs `scripts/write_release_meta.py`.

## Versioned files are immutable

Correct:

```text
FromDD-Setup-0.3.0.exe
FromDD-Setup-0.3.1.exe
FromDD-Setup-0.4.0.exe
```

Incorrect: `FromDD-Setup.exe` or `PDFFormMarker-Setup.exe` overwritten on every release.

If a customer reports “0.3.0 is broken”, you must still be able to inspect that installer.  
Only `latest.json` retargets to the new file.

Internal repo / install folder names may stay `PDFFormMarker` (`PDFFormMarker.exe`, `%LOCALAPPDATA%\PDFFormMarker`). The customer-facing download is **FromDD**.

## Caddy (caching)

```text
/releases/latest.json
Cache-Control: no-cache

/releases/FromDD-Setup-0.3.0.exe
Cache-Control: public, max-age=31536000, immutable
```

`latest.json` changes often; a versioned `.exe` must never change.  
Example config: `website/Caddyfile.fromdd`

The app fetches the feed with `Cache-Control: no-cache` and a ~3s timeout.

## GitHub Releases (every time — backup, not primary host)

The marketing/update host remains `fromdd.xambrain.com`.  
Still create a GitHub Release for every version, e.g. tag `v0.3.1` titled **FromDD v0.3.1**.

Assets:

- `FromDD-Setup-0.3.1.exe`
- `SHA256SUMS.txt`

This gives history, tags, notes, a backup binary, proof that version shipped, and a download fallback if the VPS is down.

Example:

```powershell
gh release create v0.3.1 `
  dist/installer/FromDD-Setup-0.3.1.exe `
  dist/installer/SHA256SUMS.txt `
  --title "FromDD v0.3.1" `
  --notes-file CHANGELOG.md
```

Do not point `latest.json` at GitHub by default — keep `fromdd.xambrain.com`.

## Secrets must not live on the public site

`/var/www/fromdd` may contain: HTML, CSS, JS, installer, `latest.json`.

Never place: `private.key`, `license-master.key`, `gen_license.py`, `.env`, a customer database.

A future online Activate belongs on `api.fromdd.xambrain.com` (or `/api` via reverse proxy).  
The private signing key stays in backend environment/secrets only.

## Technical behavior

- Feed fetch timeout ~3 seconds · Setup download timeout ~180 seconds
- In-memory cache 6 hours
- `GET /api/update-check` · `?force=1` forces a fresh check
- `POST /api/update-install` — downloads to `%LOCALAPPDATA%\PDFFormMarker\data\updates\`, verifies SHA-256, then launches Setup (localhost only, after a click)
- If the feed has no `sha256`, the app will not run the file — browser link only
