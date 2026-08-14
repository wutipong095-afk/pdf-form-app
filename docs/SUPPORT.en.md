# FromDD license and support policy

Thai: [SUPPORT.md](SUPPORT.md)  
Sales plan: [SALES_LICENSE_PLAN.md](SALES_LICENSE_PLAN.md)  
Key-issue email templates: [LICENSE_EMAIL.md](LICENSE_EMAIL.md)

## Product model

**One Setup** for trial and full use.  
No key: official sample forms only.  
With a key: the customer’s own PDFs. No reinstall.

## Price (on the sales pages, not in the app)

| Channel | Price | Key term |
|---------|-------|----------|
| Thailand | ~THB 490 / computer | ~5 years |
| International | US$69 / computer (PPP US$49) | ~10 years |

Sold per computer. Volume discount when an organization buys several.  
Site: [website/pricing.html](../website/pricing.html) · [website/pricing.en.html](../website/pricing.en.html)

## Moving to a new PC

- Allowed when the old PC is retired
- **2 replacements per license per year**
- A new PC gets a new machine ID — backup ZIP excludes `machine_id` / `license.json`; see [BACKUP.en.md](BACKUP.en.md)
- For now the vendor issues a new key by hand

## Issuing keys (temporary)

Customer emails the 16-character machine ID to **fromdd@xambrain.com**.  
Vendor: `python scripts/gen_license.py <id>`  
- Thailand: `--days 1825`
- International: `--days 3650`

Do not promise instant keys on the website until the Activate page exists.

## What support covers

- Install / activate / PC replacement within quota
- Sample forms and a short guide
- Setup update notices when `latest.json` is published

Not in scope: per-print billing, site licenses, monthly subscriptions, hosting customer PDFs.
