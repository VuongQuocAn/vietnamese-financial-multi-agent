"""Xử lý tài liệu, contracts và runtime path resolution giữ vị trí nguồn."""

from .ocr_loader import LoadedOCRPage, OCRLoadError, load_ocr_page
from .path_resolver import resolve_path

__all__ = ["resolve_path", "load_ocr_page", "LoadedOCRPage", "OCRLoadError"]
