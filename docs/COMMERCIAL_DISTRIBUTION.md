# Commercial distribution review — 2026-09-08

## 0.4.0 engine change

The shipped application uses pdf_engine.py (pypdf, ReportLab/HarfBuzz,
PDFium). Runtime requirements no longer include PyMuPDF; packaging
explicitly excludes fitz/pymupdf and ReportLab's unused DarkGarden fonts
(GPL). PyMuPDF remains only in development requirements for test fixtures
and independent coordinate checks. Existing 0.3.2 and older installers
are unchanged and still use PyMuPDF.

Exact installed PDF dependency notices are copied under third_party_licenses
and included in the package. This is not a complete distribution legal
clearance: provenance/redistribution notices for the existing fonts
(including TH Sarabun) and all other application dependencies still
require review before a public release. No website feed or public
release was updated.

## Historical finding (before this change)

FormDD imported PyMuPDF (`fitz`) in app.py for rendering and writing PDFs,
and requirements.txt included PyMuPDF. Packaging the Python application
in an EXE does not remove dependency license obligations. Upstream offered
GNU AGPL v3 or a separate commercial license.

## Decision recorded here

The runtime PDF engine was replaced so the desktop product does not
ship PyMuPDF. AGPL obligations from that library therefore no longer
apply to the 0.4.0 application binary. This does not by itself complete
commercial compliance for every remaining dependency.

No public release has been published. The owner should still obtain
legal review of the combined notices, fonts, and installer contents
before selling copies.
