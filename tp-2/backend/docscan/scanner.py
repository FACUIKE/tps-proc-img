"""Image decoding, document detection, perspective correction and filters."""

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class ScanError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ScanResult:
    png: bytes
    original_format: str
    width: int
    height: int
    corners: list[list[float]]


@dataclass
class DocumentDetector:
    max_dimension: int = 1200
    min_area_ratio: float = 0.05
    approximation_ratio: float = 0.02

    def detect(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        scale = min(1.0, self.max_dimension / max(height, width))
        small = cv2.resize(image, (round(width * scale), round(height * scale)))
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(contour)
            if area < self.min_area_ratio * small.shape[0] * small.shape[1]:
                break
            polygon = cv2.approxPolyDP(
                contour, self.approximation_ratio * cv2.arcLength(contour, True), True,
            )
            if len(polygon) != 4 or not cv2.isContourConvex(polygon):
                continue
            points = polygon.reshape(4, 2).astype(np.float32)
            if (points[:, 0].min() <= 1 and points[:, 1].min() <= 1
                    and points[:, 0].max() >= small.shape[1] - 2
                    and points[:, 1].max() >= small.shape[0] - 2):
                continue
            points /= np.array([small.shape[1] / width, small.shape[0] / height])
            center = points.mean(axis=0)
            angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
            points = points[np.argsort(angles)]
            return np.roll(points, -np.argmin(points.sum(axis=1)), axis=0)
        raise ScanError("DOCUMENT_NOT_FOUND", "No se encontró un documento en la foto.")


class PerspectiveCorrector:
    def apply(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        tl, tr, br, bl = corners
        width = max(2, round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
        height = max(2, round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
        target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        matrix = cv2.getPerspectiveTransform(corners, target)
        return cv2.warpPerspective(image, matrix, (width, height))


class ColorCorrection:
    def apply(self, image: np.ndarray) -> np.ndarray:
        white = np.percentile(image, 90, axis=(0, 1))
        return np.clip(image.astype(np.float32) * (255 / np.maximum(white, 1)), 0, 255).astype(np.uint8)


@dataclass
class SoftenColors:
    amount: float

    def apply(self, image: np.ndarray) -> np.ndarray:
        pixels = image.astype(np.float32)
        saturation = (pixels.max(axis=2) - pixels.min(axis=2)) / np.maximum(pixels.max(axis=2), 1)
        strength = (self.amount * saturation * 0.8)[..., None]
        return np.round(pixels + (255 - pixels) * strength).astype(np.uint8)


class Grayscale:
    def apply(self, image: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


class BlackAndWhite:
    def apply(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def scan(
    content: bytes, *, allowed_formats: set[str], color_mode: str = "color",
    color_correction: bool = True, soften_colors: float = 0.0,
) -> ScanResult:
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            original_format = source.format
            if original_format not in allowed_formats:
                raise ScanError("UNSUPPORTED_FORMAT", "El formato de la imagen no está permitido.")
            image = np.array(ImageOps.exif_transpose(source).convert("RGB"))
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ScanError("INVALID_FILE", "El archivo no se puede abrir como imagen.") from exc

    corners = DocumentDetector().detect(image)
    result = PerspectiveCorrector().apply(image, corners)
    filters = []
    if color_correction:
        filters.append(ColorCorrection())
    if soften_colors:
        filters.append(SoftenColors(soften_colors))
    if color_mode == "grayscale":
        filters.append(Grayscale())
    elif color_mode == "bw":
        filters.append(BlackAndWhite())
    for image_filter in filters:
        result = image_filter.apply(result)
    output = BytesIO()
    Image.fromarray(result).save(output, format="PNG")
    height, width = result.shape[:2]
    return ScanResult(output.getvalue(), original_format, width, height, corners.tolist())
