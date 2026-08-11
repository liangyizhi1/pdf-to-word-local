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
                ),
            )
            print(f"[OK] {report.output} ({report.backend})")
            for warning in report.warnings:
                print(f"[WARNING] {warning}")
        except ConversionError as exc:
            failures += 1
            print(f"[ERROR] {source}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
