"""Offline PDF to Word conversion tools."""

from .converter import ConversionOptions, ConversionReport, convert_pdf
from .formula import FormulaResult, FormulaSummary

__all__ = [
    "ConversionOptions",
    "ConversionReport",
    "FormulaResult",
    "FormulaSummary",
    "convert_pdf",
]
__version__ = "0.2.0"
