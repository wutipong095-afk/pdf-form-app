# Backup and restore

Thai: [BACKUP.md](BACKUP.md)

## Backup

In the app, click **Backup** to get `pdfmarker-backup-….zip` containing:

- Uploaded original PDFs (`uploads/`)
- Templates (`templates_json/`)
- Filled PDFs (`output/`)
- Autofill book (`profiles.json`)
- Document library settings (`library.json` + `.pdfmarker` if present)

**Not included:** `machine_id` / `license.json` / `secret_key` / log files

## Restore

1. Click **Restore…** and pick a ZIP
2. Choose a mode:
   - **Merge** — do not overwrite existing files
   - **Replace** — clear the user’s uploads/templates/output and autofill book (`profiles.json`), then extract from the ZIP

## Moving to a new PC

1. Back up on the old PC
2. Restore on the new PC
3. **Request a new license key** from the vendor with the new machine ID — do not copy `machine_id` / `license.json` from the old PC

## Single template

- **Export template** — download JSON for the selected template
- **Import template…** — upload a `.json` / `.tpl.json` file

## Form pack v1

Install requisition / purchasing / travel templates from the in-app button, then tune pin positions to match your school’s real forms.
