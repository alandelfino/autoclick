"""Paths for resources and native tools shipped with the application."""
import os
from pathlib import Path
import sys


def resource_path(*parts):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return str(root.joinpath(*parts))


def configure_native_tools():
    tesseract = resource_path('tesseract', 'tesseract.exe')
    if os.path.isfile(tesseract):
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = tesseract
        os.environ['TESSDATA_PREFIX'] = resource_path('tesseract', 'tessdata')


def node_command():
    bundled = resource_path('node', 'node.exe')
    return bundled if os.path.isfile(bundled) else 'node'
