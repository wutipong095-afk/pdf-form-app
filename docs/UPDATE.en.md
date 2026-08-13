# App update notices (offline-safe)

Thai: [UPDATE.md](UPDATE.md)

The app checks a vendor `latest.json` feed.  
If offline or no URL is configured — normal use continues with no error.

## What customers see

A blue bar under the header: new version → open Setup download link  
Dismissible (remembered per version in the browser)

## Vendor setup

1. Upload `PDFFormMarker-Setup-x.y.z.exe` to a public web/drive location
2. Upload `latest.json` (see `docs/latest.example.json`)
3. Point the app at the feed using one of:

| Method | Details |
|--------|---------|
| `update_feed.url` file | Next to `PDFFormMarker.exe` or under `%LOCALAPPDATA%\PDFFormMarker\` — one URL line |
| env `UPDATE_CHECK_URL` | For development / when env is available |

Example `update_feed.url`:

```text
https://your-site.com/releases/latest.json
```

## latest.json shape

```json
{
  "version": "0.2.0",
  "setup_url": "https://your-site.com/releases/PDFFormMarker-Setup-0.2.0.exe",
  "notes": "Short release note",
  "published_at": "2026-07-26"
}
```

- `version` must be newer than the app (numeric semver compare)
- `setup_url` opens in the browser for the customer to download and run Setup over the old install

## Technical behavior

- Feed fetch timeout ~3 seconds
- In-memory cache 6 hours
- `GET /api/update-check` · `?force=1` forces a fresh check
- No automatic download/install — the customer runs Setup (Setup already closes the old app during install)
