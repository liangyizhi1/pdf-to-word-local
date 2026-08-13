from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from pdf2word_local.images import (
    is_exportable_image_block,
    segment_pdf_images,
    split_image,
)


def _composite_image(columns: int, rows: int, *, dark_background: bool = False):
    from PIL import Image, ImageDraw

    panel_width = 120
    panel_height = 90
    gap = 30
    background = "black" if dark_background else "white"
    foreground = "white" if dark_background else "black"
    width = columns * panel_width + (columns - 1) * gap
    height = rows * panel_height + (rows - 1) * gap
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    for row in range(rows):
        for column in range(columns):
            left = column * (panel_width + gap) + 10
            top = row * (panel_height + gap) + 10
            right = left + panel_width - 20
            bottom = top + panel_height - 20
            draw.rectangle((left, top, right, bottom), fill=foreground)
    return image


class ImageSegmentationUnitTests(unittest.TestCase):
    def test_image_filter_skips_tiny_and_page_scan_blocks(self) -> None:
        tiny = {"type": 1, "bbox": (10, 10, 20, 20), "image": b"image"}
        scan = {"type": 1, "bbox": (0, 0, 600, 800), "image": b"image"}
        figure = {"type": 1, "bbox": (80, 120, 480, 360), "image": b"image"}
        self.assertFalse(is_exportable_image_block(tiny, page_width=600, page_height=800))
        self.assertFalse(is_exportable_image_block(scan, page_width=600, page_height=800))
        self.assertTrue(is_exportable_image_block(figure, page_width=600, page_height=800))

    def test_vertical_whitespace_splits_two_panels(self) -> None:
        pieces = split_image(_composite_image(2, 1))
        self.assertEqual(len(pieces), 2)
        self.assertLess(pieces[0][0][2], pieces[1][0][0])

    def test_horizontal_whitespace_splits_two_panels(self) -> None:
        pieces = split_image(_composite_image(1, 2))
        self.assertEqual(len(pieces), 2)
        self.assertLess(pieces[0][0][3], pieces[1][0][1])

    def test_mixed_grid_splits_four_panels(self) -> None:
        pieces = split_image(_composite_image(2, 2))
        self.assertEqual(len(pieces), 4)

    def test_dark_background_is_supported(self) -> None:
        pieces = split_image(_composite_image(2, 1, dark_background=True))
        self.assertEqual(len(pieces), 2)

    def test_single_panel_keeps_original_dimensions(self) -> None:
        image = _composite_image(1, 1)
        pieces = split_image(image)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0][0], (0, 0, image.width, image.height))


class ImageSegmentationIntegrationTests(unittest.TestCase):
    def test_pdf_composite_image_exports_four_pieces(self) -> None:
        import pymupdf

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            buffer = io.BytesIO()
            _composite_image(2, 2).save(buffer, format="PNG")
            pdf_path = root / "composite.pdf"
            document = pymupdf.open()
            page = document.new_page(width=600, height=800)
            page.insert_image(
                pymupdf.Rect(80, 120, 480, 440),
                stream=buffer.getvalue(),
            )
            document.save(pdf_path)
            document.close()

            output = root / "composite_images"
            summary = segment_pdf_images(pdf_path, output)

            self.assertEqual(summary.status, "completed")
            self.assertEqual(summary.image_count, 1)
            self.assertEqual(summary.split_image_count, 1)
            self.assertEqual(summary.piece_count, 4)
            pdf_bbox = summary.results[0].pdf_bbox
            self.assertEqual(pdf_bbox[0], 80.0)
            self.assertEqual(pdf_bbox[2], 480.0)
            self.assertGreaterEqual(pdf_bbox[1], 120.0)
            self.assertLessEqual(pdf_bbox[3], 440.0)
            self.assertEqual(summary.results[0].split_axis, "mixed")
            self.assertEqual(len(list(output.glob("*.png"))), 4)
            json.dumps(summary.to_dict())

    def test_nonempty_output_requires_overwrite(self) -> None:
        import pymupdf

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "empty.pdf"
            document = pymupdf.open()
            document.new_page()
            document.save(pdf_path)
            document.close()
            output = root / "images"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "not empty"):
                segment_pdf_images(pdf_path, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
