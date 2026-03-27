from .base import ParseResult, BaseParser
from .pymupdf_parser import PyMuPDFParser
from .pymupdf4llm_parser import PyMuPDF4LLMParser
from .pdfplumber_parser import PDFPlumberParser
from .unstructured_parser import UnstructuredParser
from .marker_parser import MarkerParser
from .llamaparse_parser import LlamaParseParser
from .ocr_tesseract_parser import TesseractOCRParser

PARSER_REGISTRY = {
    "pymupdf": PyMuPDFParser,
    "pymupdf4llm": PyMuPDF4LLMParser,
    "pdfplumber": PDFPlumberParser,
    "unstructured": UnstructuredParser,
    "marker": MarkerParser,
    "llamaparse": LlamaParseParser,
    "ocr_tesseract": TesseractOCRParser,
}
