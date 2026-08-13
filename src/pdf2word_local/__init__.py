"""Offline PDF to Word conversion tools."""

from .converter import ConversionOptions, ConversionReport, convert_pdf
from .formula import FormulaResult, FormulaSummary
from .images import ImageResult, ImageSegmentationSummary

__all__ = [
    "ConversionOptions",
    "ConversionReport",
    "FormulaResult",
    "FormulaSummary",
    "ImageResult",
    "ImageSegmentationSummary",
    "convert_pdf",
]
__version__ = "0.3.0"
