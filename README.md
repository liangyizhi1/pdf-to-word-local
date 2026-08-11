# PDF to Word Local

A private, offline PDF-to-Word converter with a desktop interface, batch conversion, basic layout preservation, and a machine-readable quality report.

> Status: early alpha. Version 0.1 works best with searchable, text-based PDFs. Scanned PDFs and complex tables still need careful review.

## Why this project

- **Private by default:** files stay on your computer.
- **Simple desktop workflow:** select PDFs, choose a folder, and convert.
- **Honest quality signals:** low-text documents are reported instead of silently treated as successful.
- **Automation-friendly:** the same converter is available from the command line.
- **Recoverable writes:** completed files replace temporary output only after conversion succeeds.

## Windows quick start

1. Install Python 3.10 or newer.
2. Double-click `install_windows.bat` once.
3. Double-click `run_app.bat` to use the desktop application.

No PDF or Word file is uploaded. The default `pdf2docx` engine runs locally.

## Command line

```powershell
python -m pip install --no-build-isolation -e ".[portable]"
pdf2word document.pdf
pdf2word a.pdf b.pdf --output-dir converted
pdf2word document.pdf --start-page 2 --end-page 8
```

Each conversion writes a DOCX and a `.conversion.json` report containing the engine, page count, editable-text volume, image count, warnings, and duration.

## Engines

- `pdf2docx` is the default, cross-platform open-source engine.
- `word` automates a licensed local copy of Microsoft Word on Windows. Some Office installations show a first-use PDF import confirmation, so this engine is opt-in with `--backend word`.

## Current limitations

- Password-protected files are not supported.
- OCR is not bundled yet; scanned PDFs may produce incomplete editable text.
- Pixel-perfect reconstruction is not guaranteed.
- Complex tables, formulas, and unusual fonts may need manual correction.

## Development

```powershell
set PYTHONPATH=src
python -m unittest discover -s tests
python -m compileall -q src tests
```

Roadmap: local Chinese/English OCR, table diagnostics, visual regression samples, signed Windows builds, and a Chinese desktop interface.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. MIT licensed.
