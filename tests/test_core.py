from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pdf2word_local.converter import ConversionError, _select_backend, _validate_paths


class CoreTests(unittest.TestCase):
    def test_rejects_non_pdf_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            source.write_text("not a pdf", encoding="utf-8")
            with self.assertRaisesRegex(ConversionError, "Input must be a PDF"):
                _validate_paths(source, Path(directory) / "output.docx", False)

    def test_rejects_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.pdf"
            output = Path(directory) / "output.docx"
            source.write_bytes(b"%PDF-1.4")
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(ConversionError, "already exists"):
                _validate_paths(source, output, False)

    def test_unknown_backend_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConversionError, "Unknown conversion backend"):
            _select_backend("unknown")


if __name__ == "__main__":
    unittest.main()
