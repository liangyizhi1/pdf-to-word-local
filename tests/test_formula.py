from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from pdf2word_local.formula import (
    enrich_docx_with_formulae,
    is_formula_image_block,
    looks_like_formula,
    normalize_ocr_result,
)


class FormulaUnitTests(unittest.TestCase):
    def test_formula_image_filter_accepts_compact_region(self) -> None:
        block = {"type": 1, "bbox": (100, 200, 360, 250), "image": b"image"}
        self.assertTrue(
            is_formula_image_block(block, page_width=600, page_height=800)
        )

    def test_formula_image_filter_rejects_tiny_and_page_scan(self) -> None:
        tiny = {"type": 1, "bbox": (10, 10, 20, 18), "image": b"image"}
        scan = {"type": 1, "bbox": (0, 0, 600, 800), "image": b"image"}
        self.assertFalse(is_formula_image_block(tiny, page_width=600, page_height=800))
        self.assertFalse(is_formula_image_block(scan, page_width=600, page_height=800))

    def test_normalize_ocr_result_supports_common_shapes(self) -> None:
        latex, confidence = normalize_ocr_result(
            ({"latex": "$x^2=y$", "confidence": 1.2}, {"elapsed": 0.1})
        )
        self.assertEqual(latex, "x^2=y")
        self.assertEqual(confidence, 1.0)

    def test_formula_likelihood_rejects_plain_logo_text(self) -> None:
        self.assertTrue(looks_like_formula(r"\frac{x}{y}=2"))
        self.assertFalse(looks_like_formula("OpenAI"))


HAS_INTEGRATION_DEPS = all(
    importlib.util.find_spec(name) is not None
    for name in ("pymupdf", "PIL", "docx")
)


@unittest.skipUnless(HAS_INTEGRATION_DEPS, "formula integration dependencies are unavailable")
class FormulaIntegrationTests(unittest.TestCase):
    def test_image_formula_is_reported_and_added_to_word(self) -> None:
        import pymupdf
        from docx import Document
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_buffer = io.BytesIO()
            image = Image.new("RGB", (500, 100), "white")
            ImageDraw.Draw(image).text((20, 25), "x / y = 2", fill="black")
            image.save(image_buffer, format="PNG")

            pdf_path = root / "formula.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page(width=600, height=800)
            page.insert_image(
                pymupdf.Rect(80, 120, 480, 200),
                stream=image_buffer.getvalue(),
            )
            pdf.save(pdf_path)
            pdf.close()

            docx_path = root / "formula.docx"
            Document().save(docx_path)
            summary = enrich_docx_with_formulae(
                pdf_path,
                docx_path,
                recognizer=lambda _: {"latex": r"\frac{x}{y}=2", "confidence": 0.94},
            )

            self.assertEqual(summary.candidate_count, 1)
            self.assertEqual(summary.recognized_count, 1)
            self.assertTrue(summary.appendix_added)
            self.assertEqual(summary.results[0].page, 1)
            self.assertEqual(summary.results[0].bbox, [80.0, 120.0, 480.0, 200.0])
            json.dumps(summary.to_dict())
            self.assertTrue(docx_path.stat().st_size > 0)

    def test_text_only_pdf_reports_no_image_candidates(self) -> None:
        import pymupdf
        from docx import Document

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "text.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_text((72, 72), "x + y = 2")
            pdf.save(pdf_path)
            pdf.close()
            docx_path = root / "text.docx"
            Document().save(docx_path)

            summary = enrich_docx_with_formulae(
                pdf_path,
                docx_path,
                recognizer=lambda _: r"x+y=2",
            )
            self.assertEqual(summary.status, "no_candidates")
            self.assertEqual(summary.candidate_count, 0)


if __name__ == "__main__":
    unittest.main()
