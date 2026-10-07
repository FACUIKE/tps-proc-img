"""
docscan: document scanning core.

Turns a photo of a document into a clean, straight scan. It must NOT import
FastAPI nor anything from `app`, so it can be used from the API, from the
command line (`python -m docscan`) or from any other Python program.

Given: image input/output (imageio.py) and the domain exceptions (exceptions.py).
TODO (team): detection, perspective correction, filters, the scanner that puts
them together and the command line (__main__.py).
"""

from docscan.exceptions import DocumentNotFound, InvalidImage, ScanError
from docscan.imageio import Photo, encode_png, from_pil, read_photo, to_pil

__all__ = [
    "DocumentNotFound", "InvalidImage", "Photo", "ScanError",
    "encode_png", "from_pil", "read_photo", "to_pil",
]
