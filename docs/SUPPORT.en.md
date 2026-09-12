# FormDD license and support policy

Thai: [SUPPORT.md](SUPPORT.md)  
Sales plan: [SALES_LICENSE_PLAN.md](SALES_LICENSE_PLAN.md)  
Key-issue email templates: [LICENSE_EMAIL.md](LICENSE_EMAIL.md)

## Product model

**One Setup** for trial and full use.  
No key: the 6-file trial pack in `demo/` only — both templates and Quick Fill.  
With a key: the customer’s own PDFs in both modes. No reinstall. Quick Fill is not sold separately.

## Price (on the sales pages, not in the app)

| Channel | What we sell | Notes |
|---------|--------------|-------|
| International store (English pages) | US$19 per computer for 10 years. More computers: US$19 × count, no volume discount | All paid seats: 10 years (3,650 days from issuance), not lifetime. Updates while the key is valid (expiry on the license bar). Do not promise a 5-year feature cutoff until the update feed can be gated. |
| Thailand store (Thai pages only) | see [SUPPORT.md](SUPPORT.md) | Do not publish baht prices on English pages. |

English site: US$19 per computer is the only paid price. Teams email a count. No cheaper School/Org packs.  
Thai quotes default to **lifetime + major updates for 3 years** if the buyer does not pick a plan. Thai prices are per PC, multiplied by the number of PCs, with no automatic volume discount.  
Site: [website/pricing.en.html](../website/pricing.en.html) · [website/pricing.html](../website/pricing.html) (Thai)

## Moving to a new PC

- Allowed when the old PC is retired
- **2 replacements per license per year**
- A new PC gets a new machine ID — backup ZIP excludes `machine_id` / `license.json`; see [BACKUP.en.md](BACKUP.en.md)
- For now the vendor issues a new key by hand

## Issuing keys (temporary)

Customer emails the 16-character machine ID to **formdd@xambrain.com**.  
Vendor: `python scripts/gen_license.py <id> --term 1` or `--days 36500` for a new Thai lifetime license.  
- Thailand: `--term 1` for one year; `--days 36500` for LT or LT with major updates for 3 years. Record the purchased plan separately; the key does not encode update entitlement.
- International: `--term 10` (public term: 10 years / 3,650 days from issuance; expiry on the license bar)
- PC replacement carrying leftover days: `--days N` (N = days left on the old key; use `0` on the UTC expiry calendar day). Do not use `--term` here, or the new key gets a full sold period.
- The script has no silent 5-year default — every invocation must pass either `--term` or `--days`.

Log every issued key in [LICENSE_REGISTRY.md](LICENSE_REGISTRY.md) or the quota for PC replacement cannot be enforced.

Do not promise instant keys on the website until the Activate page exists.

## What support covers

- Install / activate / PC replacement within quota
- Sample forms and a short guide
- Setup update notices when `latest.json` is published (same feed for every valid key)

Not in scope: per-print billing, site licenses, monthly subscriptions, hosting customer PDFs.
