"""
Input/output schemas of the API: the contract with the frontend and the tests.

The field names and types must not change. You can add validators or new
schemas for the extras.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ColorMode = Literal["color", "grayscale", "bw"]
Point = list[float]  # [x, y] in pixels of the photo


class ScanOptions(BaseModel):
    color_mode: ColorMode = "color"
    color_correction: bool = True
    soften_colors: float = Field(0.0, ge=0, le=1)


class DetectionOut(BaseModel):
    width: int = Field(description="Width of the photo (after applying the EXIF orientation)")
    height: int = Field(description="Height of the photo (after applying the EXIF orientation)")
    corners: list[Point] = Field(description="Top-left, top-right, bottom-right, bottom-left")

    model_config = {"json_schema_extra": {"example": {
        "width": 4032, "height": 3024,
        "corners": [[812.4, 403.0], [3120.9, 512.7], [2988.1, 2804.2], [701.5, 2650.3]],
    }}}


class ScanOut(BaseModel):
    id: str
    original_name: str
    url: str = Field(description="Public URL of the scan (PNG)")
    original_url: str = Field(description="Public URL of the photo, as it was received")
    width: int
    height: int
    size_bytes: int
    corners: list[Point]
    options: ScanOptions
    created_at: datetime

    model_config = {"json_schema_extra": {"example": {
        "id": "0b6f1c2e9a4d4e0f8c1f3b7a2d9e6c41",
        "original_name": "invoice.jpg",
        "url": "/media/0b6f1c2e9a4d4e0f8c1f3b7a2d9e6c41.png",
        "original_url": "/media/0b6f1c2e9a4d4e0f8c1f3b7a2d9e6c41-original.jpg",
        "width": 2310, "height": 3264, "size_bytes": 1843301,
        "corners": [[812.4, 403.0], [3120.9, 512.7], [2988.1, 2804.2], [701.5, 2650.3]],
        "options": {"color_mode": "grayscale", "color_correction": True, "soften_colors": 0.5},
        "created_at": "2026-10-07T15:42:10",
    }}}


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    detail: ErrorDetail

    model_config = {"json_schema_extra": {"example": {
        "detail": {"code": "DOCUMENT_NOT_FOUND", "message": "No se encontró un documento en la foto."},
    }}}
