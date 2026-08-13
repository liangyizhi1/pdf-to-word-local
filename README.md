# PDF to Word Local

A private, offline PDF-to-Word converter with a desktop interface, batch conversion, optional formula OCR, image extraction and splitting, and machine-readable quality reports.

> Status: early alpha. Version 0.3 works best with searchable PDFs. Formula OCR and image splitting are optional, review-oriented features.

## Why this project

- **Private by default:** files stay on your computer.
- **Simple desktop workflow:** select PDFs, choose a folder, and convert.
- **Optional formula OCR:** image-based equations can be recognized as LaTeX and appended to Word for verification.
- **Optional image splitting:** embedded composite images can be exported as separate PNG pieces when clear whitespace separators exist.
- **Honest quality signals:** missing text and uncertain results are reported instead of silently treated as successful.
- **Recoverable writes:** completed files replace temporary output only after conversion succeeds.

## Windows quick start

1. Install Python 3.10 or newer.
2. Double-click `install_windows.bat` once.
3. Double-click `run_app.bat` to use the desktop application.

No PDF or Word file is uploaded. The default `pdf2docx` engine runs locally.

## Formula OCR

Formula recognition is optional because its OCR model is substantially larger than the base converter.

1. Double-click `install_formula_ocr.bat` once.
2. Enable **Recognize formula images (experimental)** in the desktop application.
3. Verify the generated equation appendix against the source PDF.

On Windows with Microsoft Office and `latex2mathml`, recognized LaTeX is transformed through Office's `MML2OMML.XSL` into editable Word equations. When native conversion is unavailable, the appendix contains editable LaTeX text instead. Every candidate includes page number, bounding box, OCR status, confidence when available, and rendering mode in `.conversion.json`.

Current formula scope:

- recognizes compact image regions that appear to contain formulae;
- rejects plain OCR output without mathematical patterns;
- caps candidates per page to avoid sending full-page scans and illustrations to the formula model;
- does not yet recognize equations drawn with PDF fonts or vector paths;
- appends a review section rather than claiming reliable original-position replacement.

## Image extraction and splitting

Enable **Extract and split PDF images** in the desktop application, or pass `--split-images` on the command line. Extracted PNG files are written to `<document-name>_images` beside the DOCX. This export does not change the images or layout already placed in the Word file.

The splitter looks for clear horizontal and vertical whitespace bands inside embedded raster images. It works well for simple multi-panel figures, contact sheets, and grid-like composites. If no reliable separator exists, it preserves the complete image instead of making an arbitrary crop. Tiny image regions and likely full-page scans are skipped.

The `.conversion.json` report records each source page, PDF bounding box, pixel crop bounding box, output dimensions, split axis, status, warnings, and filenames. Output names such as `page-0001_image-001_piece-01.png` keep every piece traceable to its source.

Important limits:

- touching or overlapping panels may not split;
- panels on a shared nonuniform background may not split;
- vector artwork is not rasterized into separate objects;
- an existing nonempty image output folder is protected unless overwrite is enabled.

## Command line

```powershell
python -m pip install --no-build-isolation -e ".[portable]"
pdf2word document.pdf
pdf2word document.pdf --formula-ocr
pdf2word document.pdf --formula-ocr --max-formulae-per-page 12
pdf2word document.pdf --split-images
pdf2word document.pdf --split-images --max-images-per-page 50 --max-pieces-per-image 16
pdf2word a.pdf b.pdf --output-dir converted
```

Each conversion writes a DOCX and a `.conversion.json` report containing the engine, page count, editable-text volume, image count, formula results, image segmentation results, warnings, and duration.

## Engines

- `pdf2docx` is the default, cross-platform open-source engine.
- `word` automates a licensed local copy of Microsoft Word on Windows. Some Office installations show a first-use PDF import confirmation, so this engine is opt-in with `--backend word`.

## Current limitations

- Password-protected files are not supported.
- General page OCR is not bundled; scanned prose may produce incomplete editable text.
- Pixel-perfect reconstruction is not guaranteed.
- Complex tables, vector formulae, and unusual fonts may need manual correction.
- OCR-generated equations and segmented images must be checked before scientific or production use.

## Development

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m ruff check .
```

Roadmap: vector/text formula detection, local Chinese/English page OCR, table diagnostics, visual regression samples, signed Windows builds, and a Chinese desktop interface.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. MIT licensed. Chinese documentation: [README.zh-CN.md](README.zh-CN.md).
