from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import ConversionError, ConversionOptions, convert_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2word",
        description="Convert one or more PDF files to Word locally.",
    )
    parser.add_argument("pdf", nargs="+", type=Path, help="PDF file(s) to convert")
    parser.add_argument("-o", "--output-dir", type=Path, help="Directory for Word files")
    parser.add_argument("--start-page", type=int, default=1, help="First page, starting at 1")
    parser.add_argument("--end-page", type=int, help="Last page, inclusive")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing Word files")
    parser.add_argument("--no-report", action="store_true", help="Do not write JSON reports")
    parser.add_argument(
        "--backend",
        choices=("auto", "word", "pdf2docx"),
        default="auto",
        help="Conversion engine (default: auto)",
    )
    parser.add_argument(
        "--formula-ocr",
        action="store_true",
        help="Recognize image-based formulae and add an experimental Word appendix",
    )
    parser.add_argument(
        "--max-formulae-per-page",
        type=int,
        default=20,
        metavar="N",
        help="Maximum image regions sent to formula OCR per page (default: 20)",
    )
    parser.add_argument(
        "--split-images",
        action="store_true",
        help="Extract PDF images and split composite images along whitespace bands",
    )
    parser.add_argument(
        "--max-images-per-page",
        type=int,
        default=50,
        metavar="N",
        help="Maximum PDF image regions exported per page (default: 50)",
    )
    parser.add_argument(
        "--max-pieces-per-image",
        type=int,
        default=16,
        metavar="N",
        help="Maximum generated pieces for one PDF image (default: 16)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for source in args.pdf:
        output = (output_dir / f"{source.stem}.docx") if output_dir else None
        try:
            report = convert_pdf(
                source,
                output,
                options=ConversionOptions(
                    start_page=args.start_page,
                    end_page=args.end_page,
                    overwrite=args.overwrite,
                    write_report=not args.no_report,
                    backend=args.backend,
                    recognize_formulas=args.formula_ocr,
                    max_formulas_per_page=args.max_formulae_per_page,
                    segment_images=args.split_images,
                    max_images_per_page=args.max_images_per_page,
                    max_pieces_per_image=args.max_pieces_per_image,
                ),
            )
            print(f"[OK] {report.output} ({report.backend})")
            if report.formula_recognition is not None:
                formulae = report.formula_recognition
                print(
                    f"[FORMULAE] {formulae.recognized_count}/{formulae.candidate_count} recognized; "
                    f"{formulae.native_equation_count} native Word equations"
                )
            if report.image_segmentation is not None:
                images = report.image_segmentation
                print(
                    f"[IMAGES] {images.image_count} extracted; "
                    f"{images.split_image_count} split into {images.piece_count} pieces"
                )
            for warning in report.warnings:
                print(f"[WARNING] {warning}")
        except ConversionError as exc:
            failures += 1
            print(f"[ERROR] {source}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
