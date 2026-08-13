from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .formula import FormulaSummary, enrich_docx_with_formulae
from .images import ImageSegmentationSummary, segment_pdf_images

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from pdf2docx import Converter
except ImportError:
    Converter = None


class ConversionError(RuntimeError):
    """Raised when an input cannot be converted safely."""


@dataclass(frozen=True)
class ConversionOptions:
    start_page: int = 1
    end_page: int | None = None
    overwrite: bool = False
    write_report: bool = True
    backend: str = "auto"
    recognize_formulas: bool = False
    max_formulas_per_page: int = 20
    segment_images: bool = False
    max_images_per_page: int = 50
    max_pieces_per_image: int = 16


@dataclass(frozen=True)
class PdfInspection:
    page_count: int
    selected_page_count: int
    text_characters: int
    image_count: int
    low_text_pages: list[int] = field(default_factory=list)

    @property
    def likely_scanned(self) -> bool:
        return bool(self.low_text_pages) and len(self.low_text_pages) == self.selected_page_count


@dataclass
class ConversionReport:
    source: str
    output: str
    status: str
    backend: str
    duration_seconds: float
    inspection: PdfInspection
    warnings: list[str] = field(default_factory=list)
    formula_recognition: FormulaSummary | None = None
    image_segmentation: ImageSegmentationSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path | None = None) -> Path:
        report_path = path or Path(self.output).with_suffix(".conversion.json")
        report_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report_path


def _validate_paths(source: Path, output: Path, overwrite: bool) -> None:
    if not source.is_file():
        raise ConversionError(f"PDF file does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        raise ConversionError(f"Input must be a PDF file: {source}")
    if output.suffix.lower() != ".docx":
        raise ConversionError(f"Output must use the .docx extension: {output}")
    if source.resolve() == output.resolve():
        raise ConversionError("Input and output paths must be different.")
    if output.exists() and not overwrite:
        raise ConversionError(f"Output already exists: {output}")


def _word_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return True


def available_backends() -> list[str]:
    backends: list[str] = []
    if Converter is not None and fitz is not None:
        backends.append("pdf2docx")
    if _word_available():
        backends.append("word")
    return backends


def _select_backend(requested: str) -> str:
    choices = available_backends()
    if requested == "auto" and choices:
        return choices[0]
    if requested in choices:
        return requested
    if requested not in {"auto", "word", "pdf2docx"}:
        raise ConversionError(f"Unknown conversion backend: {requested}")
    if requested == "word":
        raise ConversionError("The Microsoft Word backend is not available on this computer.")
    if requested == "pdf2docx":
        raise ConversionError(
            "The portable backend is not installed. Run install_windows.bat or install .[portable]."
        )
    raise ConversionError(
        "No conversion engine is available. Run install_windows.bat, or install the portable "
        "engine with: python -m pip install -e .[portable]"
    )


def _warnings_for(inspection: PdfInspection) -> list[str]:
    if inspection.likely_scanned:
        return [
            (
                "All selected pages contain very little editable text. The PDF may be scanned; "
                "review the Word result carefully."
            )
        ]
    if inspection.low_text_pages:
        pages = ", ".join(str(page) for page in inspection.low_text_pages[:12])
        suffix = "..." if len(inspection.low_text_pages) > 12 else ""
        return [f"Pages with little editable text: {pages}{suffix}"]
    return []


def _convert_with_word(source: Path, output: Path) -> PdfInspection:
    try:
        import win32com.client
    except ImportError as exc:
        raise ConversionError("The Microsoft Word automation package is not available.") from exc
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(source), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False
        )
        page_count = max(1, int(document.ComputeStatistics(2)))
        text = "".join(str(document.Content.Text).split())
        image_count = int(document.InlineShapes.Count) + int(document.Shapes.Count)
        document.SaveAs2(str(output), FileFormat=16, AddToRecentFiles=False)
        low_text_pages = list(range(1, page_count + 1)) if len(text) < page_count * 30 else []
        return PdfInspection(
            page_count=page_count,
            selected_page_count=page_count,
            text_characters=len(text),
            image_count=image_count,
            low_text_pages=low_text_pages,
        )
    except Exception as exc:
        raise ConversionError(f"Microsoft Word could not convert this PDF: {exc}") from exc
    finally:
        if document is not None:
            with suppress(Exception):
                document.Close(False)
        if word is not None:
            with suppress(Exception):
                word.Quit()


def _inspect_with_pymupdf(source: Path, start_page: int, end_page: int | None) -> PdfInspection:
    if fitz is None:
        raise ConversionError("PyMuPDF is not installed.")
    try:
        document = fitz.open(source)
    except Exception as exc:
        raise ConversionError(f"Unable to open PDF: {exc}") from exc
    try:
        if document.needs_pass:
            raise ConversionError("Password-protected PDFs are not supported yet.")
        page_count = document.page_count
        if page_count == 0:
            raise ConversionError("The PDF has no pages.")
        if start_page < 1 or start_page > page_count:
            raise ConversionError(f"Start page must be between 1 and {page_count}.")
        final_page = page_count if end_page is None else end_page
        if final_page < start_page or final_page > page_count:
            raise ConversionError(f"End page must be between {start_page} and {page_count}.")
        text_characters = 0
        image_count = 0
        low_text_pages: list[int] = []
        for page_number in range(start_page - 1, final_page):
            page = document.load_page(page_number)
            page_text = "".join(page.get_text("text").split())
            text_characters += len(page_text)
            image_count += len(page.get_images(full=True))
            if len(page_text) < 30:
                low_text_pages.append(page_number + 1)
        return PdfInspection(
            page_count=page_count,
            selected_page_count=final_page - start_page + 1,
            text_characters=text_characters,
            image_count=image_count,
            low_text_pages=low_text_pages,
        )
    finally:
        document.close()


def _convert_with_pdf2docx(
    source: Path, output: Path, settings: ConversionOptions
) -> PdfInspection:
    if Converter is None:
        raise ConversionError("The optional portable conversion engine is not installed.")
    inspection = _inspect_with_pymupdf(source, settings.start_page, settings.end_page)
    converter = None
    try:
        converter = Converter(str(source))
        converter.convert(str(output), start=settings.start_page - 1, end=settings.end_page)
        return inspection
    finally:
        if converter is not None:
            converter.close()


def convert_pdf(
    source: str | Path,
    output: str | Path | None = None,
    *,
    options: ConversionOptions | None = None,
) -> ConversionReport:
    settings = options or ConversionOptions()
    if not 1 <= settings.max_formulas_per_page <= 100:
        raise ConversionError("max_formulas_per_page must be between 1 and 100.")
    if not 1 <= settings.max_images_per_page <= 200:
        raise ConversionError("max_images_per_page must be between 1 and 200.")
    if not 1 <= settings.max_pieces_per_image <= 64:
        raise ConversionError("max_pieces_per_image must be between 1 and 64.")
    source_path = Path(source).expanduser().resolve()
    output_path = (
        Path(output).expanduser().resolve()
        if output is not None
        else source_path.with_suffix(".docx")
    )
    _validate_paths(source_path, output_path, settings.overwrite)
    backend = _select_backend(settings.backend)
    if backend == "word" and (settings.start_page != 1 or settings.end_page is not None):
        raise ConversionError(
            "Selected page ranges require the portable engine. Use the full document or "
            "run install_windows.bat."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-", suffix=".docx", dir=output_path.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    temporary_path.unlink(missing_ok=True)
    formula_summary: FormulaSummary | None = None
    image_summary: ImageSegmentationSummary | None = None
    try:
        if backend == "word":
            inspection = _convert_with_word(source_path, temporary_path)
        else:
            inspection = _convert_with_pdf2docx(source_path, temporary_path, settings)
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise ConversionError("The converter did not produce a valid Word file.")
        if settings.recognize_formulas:
            try:
                formula_summary = enrich_docx_with_formulae(
                    source_path,
                    temporary_path,
                    start_page=settings.start_page,
                    end_page=settings.end_page,
                    max_per_page=settings.max_formulas_per_page,
                )
            except Exception as exc:  # noqa: BLE001 - optional enrichment boundary.
                formula_summary = FormulaSummary(
                    status="failed",
                    warnings=[f"Formula recognition failed: {exc}"],
                )
        if settings.segment_images:
            image_directory = output_path.with_name(f"{output_path.stem}_images")
            try:
                image_summary = segment_pdf_images(
                    source_path,
                    image_directory,
                    start_page=settings.start_page,
                    end_page=settings.end_page,
                    max_per_page=settings.max_images_per_page,
                    max_pieces_per_image=settings.max_pieces_per_image,
                    overwrite=settings.overwrite,
                )
            except Exception as exc:  # noqa: BLE001 - optional enrichment boundary.
                image_summary = ImageSegmentationSummary(
                    status="failed",
                    output_directory=str(image_directory),
                    warnings=[f"Image segmentation failed: {exc}"],
                )
        os.replace(temporary_path, output_path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        if isinstance(exc, ConversionError):
            raise
        raise ConversionError(f"Conversion failed: {exc}") from exc
    warnings = _warnings_for(inspection)
    if formula_summary is not None:
        warnings.extend(formula_summary.warnings)
    if image_summary is not None:
        warnings.extend(image_summary.warnings)
    report = ConversionReport(
        source=str(source_path),
        output=str(output_path),
        status="completed_with_warnings" if warnings else "completed",
        backend=backend,
        duration_seconds=round(time.perf_counter() - started, 3),
        inspection=inspection,
        warnings=warnings,
        formula_recognition=formula_summary,
        image_segmentation=image_summary,
    )
    if settings.write_report:
        report.write_json()
    return report
