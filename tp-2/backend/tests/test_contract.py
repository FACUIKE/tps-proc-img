"""
Acceptance tests: the assignment in executable form. DO NOT MODIFY.

If a test in this file fails, the implementation does not meet the assignment.
Run with:   cd backend && pytest tests/test_contract.py -v

The team's own tests (core unit tests, etc.) go in other files.
"""

import os
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from conftest import BACKEND_DIR, STORAGE_DIR

MB = 1024 * 1024

PAPER = (245, 245, 240)
TINTED_PAPER = (235, 212, 160)       # paper photographed under warm light
BACKGROUND = (45, 50, 58)            # dark table
INK = (25, 25, 25)
STRONG_RED = (225, 30, 40)           # e.g. a stamp or a highlighter

PORTRAIT = (300, 420)                # document size (width, height), A4-like ratio
LANDSCAPE = (420, 300)
CANVAS = (640, 640)                  # photo size (width, height)

DEFAULT_OPTIONS = {"color_mode": "color", "color_correction": True, "soften_colors": 0.0}
SCAN_FIELDS = {
    "id", "original_name", "url", "original_url", "width", "height",
    "size_bytes", "corners", "options", "created_at",
}

# Regions of the document, as fractions (x0, y0, x1, y1) of its width and height.
MARKER = (0.10, 0.08, 0.18, 0.14)        # inside the black square at the top-left
BLANK_TOP_RIGHT = (0.65, 0.06, 0.90, 0.18)
BLANK_BOTTOM_LEFT = (0.06, 0.70, 0.40, 0.92)
PATCH = (0.62, 0.75, 0.84, 0.86)         # inside the colored patch at the bottom-right


# ===========================================================================
# Synthetic photos
# ===========================================================================

def document(size=PORTRAIT, paper=PAPER, patch=None) -> np.ndarray:
    """
    An RGB page: a black square at the top-left (to tell where "up" is), some
    lines of "text" in the middle and, optionally, a colored patch at the
    bottom-right. The top-right and bottom-left corners are left blank.
    """
    w, h = size
    page = np.full((h, w, 3), paper, np.uint8)

    def box(x0, y0, x1, y1, color):
        page[round(y0 * h):round(y1 * h), round(x0 * w):round(x1 * w)] = color

    box(0.06, 0.05, 0.22, 0.17, INK)
    line_height = max(4 / h, 0.012)
    for i, y in enumerate(np.arange(0.28, 0.63, 0.05)):
        box(0.10, y, 0.90 - 0.08 * (i % 3), y + line_height, INK)
    if patch is not None:
        box(0.55, 0.70, 0.90, 0.90, patch)
    return page


def photo(page: np.ndarray, angle: float = 12.0, perspective: float = 0.0,
          scale: float = 1.0, canvas=CANVAS) -> tuple[np.ndarray, np.ndarray]:
    """
    Places the page on a dark, slightly noisy background: scaled, with the top
    edge narrowed by `perspective` (fraction of the width) and rotated `angle`
    degrees clockwise. Returns the RGB photo and the true corners of the page
    in the photo (top-left, top-right, bottom-right, bottom-left).
    """
    h, w = page.shape[:2]
    cw, ch = canvas
    hw, hh = w * scale / 2, h * scale / 2
    shape = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]], dtype=float)
    shape[0, 0] += perspective * 2 * hw
    shape[1, 0] -= perspective * 2 * hw
    a = np.deg2rad(angle)
    rotation = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    corners = shape @ rotation.T + [cw / 2, ch / 2]

    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    matrix = cv2.getPerspectiveTransform(src, corners.astype(np.float32))
    warped = cv2.warpPerspective(page, matrix, (cw, ch), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), matrix, (cw, ch))

    rng = np.random.default_rng(7)
    noise = rng.integers(-6, 7, size=(ch, cw, 1))
    background = np.clip(np.full((ch, cw, 3), BACKGROUND, dtype=int) + noise, 0, 255)
    result = np.where(mask[..., None] > 127, warped, background).astype(np.uint8)
    return result, corners


def no_document(kind: str) -> np.ndarray:
    """Photos where there is no document to find."""
    cw, ch = CANVAS
    if kind == "uniform":
        return np.full((ch, cw, 3), (128, 128, 128), np.uint8)
    if kind == "circles":
        img = np.full((ch, cw, 3), BACKGROUND, np.uint8)
        cv2.circle(img, (320, 320), 220, (230, 230, 230), -1)
        cv2.circle(img, (320, 320), 90, (200, 60, 60), -1)
        return img
    if kind == "tiny":  # the document is far too small (about 1 % of the photo)
        return photo(document(), angle=10, scale=0.2)[0]
    raise ValueError(kind)


def encode(rgb: np.ndarray | Image.Image, fmt: str = "PNG", **save_args) -> bytes:
    img = rgb if isinstance(rgb, Image.Image) else Image.fromarray(rgb)
    buf = BytesIO()
    img.save(buf, format=fmt, **save_args)
    return buf.getvalue()


MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "BMP": "image/bmp", "GIF": "image/gif"}


# ===========================================================================
# HTTP helpers
# ===========================================================================

def post_file(client, path: str, content: bytes, name: str = "photo.png",
              mime: str = "image/png", options: dict | None = None):
    data = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in (options or {}).items()}
    return client.post(path, files={"file": (name, content, mime)}, data=data)


def scan_ok(client, rgb: np.ndarray | None = None, options: dict | None = None,
            fmt: str = "PNG", name: str = "photo.png") -> dict:
    rgb = rgb if rgb is not None else photo(document())[0]
    r = post_file(client, "/api/scans", encode(rgb, fmt), name, MIME[fmt], options)
    assert r.status_code == 201, r.text
    return r.json()


def download(client, url: str) -> bytes:
    r = client.get(url)
    assert r.status_code == 200, f"Could not download {url}: {r.status_code}"
    return r.content


def download_image(client, url: str) -> Image.Image:
    img = Image.open(BytesIO(download(client, url)))
    img.load()
    return img


def assert_error(r, status: int, code: str):
    assert r.status_code == status, f"Expected {status}, got {r.status_code}: {r.text}"
    body = r.json()
    assert "detail" in body, f"The error must come in 'detail': {body}"
    detail = body["detail"]
    assert isinstance(detail, dict), f"'detail' must be a {{code, message}} object: {detail}"
    assert detail.get("code") == code, f"Expected code={code}: {detail}"
    assert isinstance(detail.get("message"), str) and detail["message"].strip(), "Missing 'message'"


def stored_files() -> set[str]:
    return {p.name for p in STORAGE_DIR.rglob("*") if p.is_file()} if STORAGE_DIR.exists() else set()


# ===========================================================================
# Pixel helpers
# ===========================================================================

def region(img: Image.Image, box) -> np.ndarray:
    a = np.asarray(img.convert("RGB"), dtype=float)
    h, w = a.shape[:2]
    x0, y0, x1, y1 = box
    return a[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].reshape(-1, 3)


def luminance(pixels: np.ndarray) -> float:
    return float((pixels @ [0.299, 0.587, 0.114]).mean())


def mean_color(pixels: np.ndarray) -> np.ndarray:
    return pixels.mean(axis=0)


def saturation(color: np.ndarray) -> float:
    return float((color.max() - color.min()) / max(color.max(), 1))


def border_luminance(img: Image.Image, band: float = 0.03) -> float:
    """Median luminance of a thin ring along the edges of the image."""
    g = np.asarray(img.convert("L"), dtype=float)
    h, w = g.shape
    bh, bw = max(1, int(h * band)), max(1, int(w * band))
    ring = np.concatenate([g[:bh].ravel(), g[-bh:].ravel(), g[:, :bw].ravel(), g[:, -bw:].ravel()])
    return float(np.median(ring))


def assert_upright_page(img: Image.Image, ratio: float, tolerance: float = 0.08):
    """The result is the page alone: right proportions, upright, not mirrored, cropped."""
    w, h = img.size
    assert abs((h / w) - ratio) / ratio <= tolerance, f"Height/width should be ≈{ratio:.2f}, got {h}x{w}"
    assert luminance(region(img, MARKER)) < 100, "The black square must stay at the top-left (is it rotated or mirrored?)"
    assert luminance(region(img, BLANK_TOP_RIGHT)) > 170, "The top-right corner of the page should be blank"
    assert luminance(region(img, BLANK_BOTTOM_LEFT)) > 170, "The bottom-left corner of the page should be blank"
    assert border_luminance(img) > 150, "The edges of the result should be paper, not the background of the photo"


def assert_corners(corners, expected: np.ndarray, tolerance: float = 0.02):
    assert isinstance(corners, list) and len(corners) == 4, f"'corners' must be a list of 4 points: {corners}"
    for point in corners:
        assert isinstance(point, list) and len(point) == 2, f"Each corner must be [x, y]: {point}"
        assert all(isinstance(v, (int, float)) for v in point), f"Coordinates must be numbers: {point}"
    max_distance = tolerance * float(np.hypot(*CANVAS))
    names = ["top-left", "top-right", "bottom-right", "bottom-left"]
    for name, got, want in zip(names, corners, expected):
        distance = float(np.hypot(got[0] - want[0], got[1] - want[1]))
        assert distance <= max_distance, f"{name} corner: expected ≈{want.round(1).tolist()}, got {got}"


# ===========================================================================
# System
# ===========================================================================

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ===========================================================================
# Upload validation (same rules for /api/detect and /api/scans)
# ===========================================================================

ENDPOINTS = ["/api/detect", "/api/scans"]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_file_too_large(client, path):
    content = encode(photo(document())[0]) + b"\0" * (10 * MB)
    assert_error(post_file(client, path, content), 413, "FILE_TOO_LARGE")


@pytest.mark.parametrize("path", ENDPOINTS)
@pytest.mark.parametrize("content", [b"", b"this is not an image", b"\x89PNG\r\n\x1a\n broken"],
                         ids=["empty", "text", "corrupt-png"])
def test_invalid_file(client, path, content):
    assert_error(post_file(client, path, content), 400, "INVALID_FILE")


@pytest.mark.parametrize("path", ENDPOINTS)
def test_unsupported_format(client, path):
    content = encode(photo(document())[0], "GIF")
    assert_error(post_file(client, path, content, "photo.gif", "image/gif"), 400, "UNSUPPORTED_FORMAT")


@pytest.mark.parametrize("path", ENDPOINTS)
def test_size_is_checked_before_format(client, path):
    content = b"not an image" * MB
    assert_error(post_file(client, path, content), 413, "FILE_TOO_LARGE")


@pytest.mark.parametrize("path", ENDPOINTS)
def test_missing_file_is_a_validation_error(client, path):
    assert client.post(path).status_code == 422


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "BMP"])
def test_accepted_formats(client, fmt):
    r = post_file(client, "/api/detect", encode(photo(document())[0], fmt), f"photo.{fmt.lower()}", MIME[fmt])
    assert r.status_code == 200, r.text


def test_format_is_detected_by_content(client):
    """A PNG named .jpg and sent as image/jpeg is still a valid photo."""
    r = post_file(client, "/api/detect", encode(photo(document())[0], "PNG"), "photo.jpg", "image/jpeg")
    assert r.status_code == 200, r.text


# ===========================================================================
# POST /api/detect
# ===========================================================================

def test_detect_response(client):
    rgb, corners = photo(document(), angle=12)
    r = post_file(client, "/api/detect", encode(rgb))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"width", "height", "corners"}, body
    assert (body["width"], body["height"]) == CANVAS
    assert_corners(body["corners"], corners)


@pytest.mark.parametrize("angle", [0, 12, -15, 25])
def test_detect_rotated(client, angle):
    rgb, corners = photo(document(), angle=angle)
    r = post_file(client, "/api/detect", encode(rgb))
    assert r.status_code == 200, r.text
    assert_corners(r.json()["corners"], corners)


def test_detect_with_perspective(client):
    rgb, corners = photo(document(), angle=6, perspective=0.12)
    r = post_file(client, "/api/detect", encode(rgb))
    assert r.status_code == 200, r.text
    assert_corners(r.json()["corners"], corners)


def test_detect_landscape_document(client):
    rgb, corners = photo(document(LANDSCAPE), angle=-10)
    r = post_file(client, "/api/detect", encode(rgb))
    assert r.status_code == 200, r.text
    assert_corners(r.json()["corners"], corners)


def test_detect_jpeg_photo(client):
    rgb, corners = photo(document(), angle=9)
    r = post_file(client, "/api/detect", encode(rgb, "JPEG", quality=80), "photo.jpg", "image/jpeg")
    assert r.status_code == 200, r.text
    assert_corners(r.json()["corners"], corners)


def exif_rotated_jpeg(angle: float = 8) -> tuple[bytes, np.ndarray]:
    """
    A phone photo: the pixels are stored rotated and the EXIF 'Orientation' tag
    (6 = rotate 90° clockwise to display) says how to show it upright.
    """
    rgb, corners = photo(document(), angle=angle, canvas=(640, 480))
    stored = Image.fromarray(rgb).transpose(Image.Transpose.ROTATE_90)  # 480x640 as stored
    exif = Image.Exif()
    exif[0x0112] = 6
    return encode(stored, "JPEG", quality=92, exif=exif), corners


def test_detect_respects_exif_orientation(client):
    content, corners = exif_rotated_jpeg()
    r = post_file(client, "/api/detect", content, "phone.jpg", "image/jpeg")
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["width"], body["height"]) == (640, 480), "Width and height are those of the photo as displayed"
    assert_corners(body["corners"], corners)


@pytest.mark.parametrize("kind", ["uniform", "circles", "tiny"])
def test_detect_document_not_found(client, kind):
    assert_error(post_file(client, "/api/detect", encode(no_document(kind))), 422, "DOCUMENT_NOT_FOUND")


def test_detect_stores_nothing(client):
    before = stored_files()
    listed = len(client.get("/api/scans").json())
    r = post_file(client, "/api/detect", encode(photo(document())[0]))
    assert r.status_code == 200, r.text
    assert stored_files() == before
    assert len(client.get("/api/scans").json()) == listed


# ===========================================================================
# POST /api/scans: response and storage
# ===========================================================================

def test_scan_response(client):
    rgb, corners = photo(document(), angle=12)
    r = post_file(client, "/api/scans", encode(rgb), "invoice.png")
    assert r.status_code == 201, r.text
    scan = r.json()
    assert set(scan) == SCAN_FIELDS, f"Unexpected fields: {set(scan) ^ SCAN_FIELDS}"
    assert isinstance(scan["id"], str) and scan["id"]
    assert scan["original_name"] == "invoice.png"
    assert scan["url"].startswith("/media/") and scan["url"].endswith(".png")
    assert scan["original_url"].startswith("/media/")
    assert scan["url"] != scan["original_url"]
    assert scan["options"] == DEFAULT_OPTIONS
    assert_corners(scan["corners"], corners)
    datetime.fromisoformat(scan["created_at"])


def test_scan_result_is_a_png_described_by_the_response(client):
    scan = scan_ok(client)
    content = download(client, scan["url"])
    img = Image.open(BytesIO(content))
    assert img.format == "PNG"
    assert img.size == (scan["width"], scan["height"])
    assert scan["size_bytes"] == len(content)


def test_scan_files_are_in_storage_dir(client):
    scan = scan_ok(client)
    for url in (scan["url"], scan["original_url"]):
        name = url.rsplit("/", 1)[-1]
        assert (STORAGE_DIR / name).is_file(), f"{name} must be saved in config.STORAGE_DIR"


def test_scan_keeps_the_original_photo_unchanged(client):
    content = encode(photo(document())[0], "JPEG", quality=85)
    r = post_file(client, "/api/scans", content, "receipt.jpeg", "image/jpeg")
    assert r.status_code == 201, r.text
    assert download(client, r.json()["original_url"]) == content


def test_scan_file_names_are_generated(client):
    scan = scan_ok(client, name="../../evil name.png")
    assert scan["original_name"] == "../../evil name.png"
    for url in (scan["url"], scan["original_url"]):
        assert "evil" not in url and ".." not in url


def test_scan_ids_are_unique(client):
    a, b = scan_ok(client), scan_ok(client)
    assert a["id"] != b["id"] and a["url"] != b["url"]


@pytest.mark.parametrize("kind", ["uniform", "circles", "tiny"])
def test_scan_document_not_found_stores_nothing(client, kind):
    before = stored_files()
    listed = len(client.get("/api/scans").json())
    assert_error(post_file(client, "/api/scans", encode(no_document(kind))), 422, "DOCUMENT_NOT_FOUND")
    assert stored_files() == before
    assert len(client.get("/api/scans").json()) == listed


# ===========================================================================
# POST /api/scans: geometry
# ===========================================================================

@pytest.mark.parametrize("angle", [0, 12, -15, 25])
def test_scan_is_straight_and_cropped(client, angle):
    scan = scan_ok(client, photo(document(), angle=angle)[0])
    assert_upright_page(download_image(client, scan["url"]), ratio=420 / 300)


def test_scan_corrects_perspective(client):
    scan = scan_ok(client, photo(document(), angle=6, perspective=0.12)[0])
    assert_upright_page(download_image(client, scan["url"]), ratio=420 / 300, tolerance=0.12)


def test_scan_landscape_document(client):
    scan = scan_ok(client, photo(document(LANDSCAPE), angle=-10)[0])
    assert_upright_page(download_image(client, scan["url"]), ratio=300 / 420)


def test_scan_respects_exif_orientation(client):
    content, _ = exif_rotated_jpeg()
    r = post_file(client, "/api/scans", content, "phone.jpg", "image/jpeg")
    assert r.status_code == 201, r.text
    assert_upright_page(download_image(client, r.json()["url"]), ratio=420 / 300)


def test_scan_keeps_a_readable_resolution(client):
    """The page is not shrunk: it keeps (at least) the size it has in the photo."""
    scan = scan_ok(client, photo(document(), angle=12)[0])
    assert scan["width"] >= 270 and scan["height"] >= 380, (scan["width"], scan["height"])


# ===========================================================================
# POST /api/scans: options
# ===========================================================================

def test_options_are_returned_with_defaults(client):
    scan = scan_ok(client, options={"color_mode": "grayscale"})
    assert scan["options"] == {**DEFAULT_OPTIONS, "color_mode": "grayscale"}


def test_options_are_returned(client):
    options = {"color_mode": "bw", "color_correction": False, "soften_colors": 0.25}
    assert scan_ok(client, options=options)["options"] == options


@pytest.mark.parametrize("options", [
    {"color_mode": "sepia"},
    {"color_mode": "Color"},
    {"soften_colors": 1.5},
    {"soften_colors": -0.1},
    {"soften_colors": "a lot"},
    {"color_correction": "maybe"},
])
def test_invalid_options(client, options):
    before = stored_files()
    r = post_file(client, "/api/scans", encode(photo(document())[0]), options=options)
    assert r.status_code == 422, r.text
    assert stored_files() == before


def test_color_mode_color(client):
    page = document(patch=STRONG_RED)
    scan = scan_ok(client, photo(page)[0], options={"color_mode": "color"})
    img = download_image(client, scan["url"])
    assert img.mode == "RGB"
    assert saturation(mean_color(region(img, PATCH))) > 0.5, "Colors are kept in color mode"


def test_color_mode_grayscale(client):
    scan = scan_ok(client, photo(document(patch=STRONG_RED))[0], options={"color_mode": "grayscale"})
    img = download_image(client, scan["url"])
    assert img.mode == "L", f"A grayscale scan must be saved with a single channel (mode L), got {img.mode}"
    assert_upright_page(img, ratio=420 / 300)


def test_color_mode_bw(client):
    scan = scan_ok(client, photo(document())[0], options={"color_mode": "bw"})
    img = download_image(client, scan["url"])
    assert img.mode == "L", f"A black and white scan is saved in mode L, got {img.mode}"
    values = np.asarray(img)
    assert set(np.unique(values).tolist()) <= {0, 255}, "Only pure black (0) and white (255) are allowed"
    white = float((values == 255).mean())
    assert 0.70 <= white <= 0.995, f"Mostly white paper with black ink expected, white = {white:.1%}"
    assert luminance(region(img, BLANK_TOP_RIGHT)) == 255, "Blank paper must be pure white"


def test_color_correction_whitens_tinted_paper(client):
    page = document(paper=TINTED_PAPER)
    scan = scan_ok(client, photo(page)[0], options={"color_correction": True})
    img = download_image(client, scan["url"])
    paper = mean_color(region(img, BLANK_TOP_RIGHT))
    assert paper.min() >= 225, f"The paper should look white, got {paper.round().tolist()}"
    assert paper.max() - paper.min() <= 15, f"The paper should be neutral (no color cast), got {paper.round().tolist()}"
    assert luminance(region(img, MARKER)) < 100, "Ink must stay dark"


def test_without_color_correction_the_tint_remains(client):
    page = document(paper=TINTED_PAPER)
    scan = scan_ok(client, photo(page)[0], options={"color_correction": False})
    paper = mean_color(region(download_image(client, scan["url"]), BLANK_TOP_RIGHT))
    assert paper.max() - paper.min() >= 50, f"Without correction the original color must remain, got {paper.round().tolist()}"


def test_color_correction_keeps_colors(client):
    page = document(paper=TINTED_PAPER, patch=STRONG_RED)
    scan = scan_ok(client, photo(page)[0], options={"color_correction": True})
    patch = mean_color(region(download_image(client, scan["url"]), PATCH))
    assert patch[0] > patch[1] + 80 and patch[0] > patch[2] + 80, f"The red patch must stay red, got {patch.round().tolist()}"


def _soften(client, amount: float) -> Image.Image:
    page = document(patch=STRONG_RED)
    options = {"color_correction": False, "soften_colors": amount}
    return download_image(client, scan_ok(client, photo(page)[0], options=options)["url"])


def test_soften_zero_leaves_colors_as_they_are(client):
    patch = mean_color(region(_soften(client, 0.0), PATCH))
    assert np.abs(patch - STRONG_RED).max() <= 25, f"Expected ≈{STRONG_RED}, got {patch.round().tolist()}"


def test_soften_colors_lightens_strong_colors(client):
    before = mean_color(region(_soften(client, 0.0), PATCH))
    after = mean_color(region(_soften(client, 1.0), PATCH))
    assert luminance(after[None]) >= luminance(before[None]) + 40, (
        f"A strong color must get lighter: {before.round().tolist()} → {after.round().tolist()}")
    assert saturation(after) <= 0.6 * saturation(before), (
        f"A strong color must get less saturated: {before.round().tolist()} → {after.round().tolist()}")
    assert after[0] >= after[1] and after[0] >= after[2], "It is lightened, not replaced: it must still be reddish"


def test_soften_colors_is_gradual(client):
    lums = [luminance(region(_soften(client, s), PATCH)) for s in (0.0, 0.5, 1.0)]
    assert lums[0] < lums[1] < lums[2], f"More soften_colors must lighten more: {lums}"


def test_soften_colors_does_not_touch_ink_or_paper(client):
    before, after = _soften(client, 0.0), _soften(client, 1.0)
    for box, name in [(MARKER, "black ink"), (BLANK_TOP_RIGHT, "white paper")]:
        a, b = mean_color(region(before, box)), mean_color(region(after, box))
        assert np.abs(a - b).max() <= 12, f"{name} must not change: {a.round().tolist()} → {b.round().tolist()}"


# ===========================================================================
# GET /api/scans, GET/DELETE /api/scans/{id}
# ===========================================================================

def test_get_scan(client):
    scan = scan_ok(client)
    r = client.get(f"/api/scans/{scan['id']}")
    assert r.status_code == 200, r.text
    assert r.json() == scan


def test_get_unknown_scan(client):
    assert_error(client.get("/api/scans/does-not-exist"), 404, "SCAN_NOT_FOUND")


def test_list_scans_newest_first(client):
    older = scan_ok(client)
    time.sleep(1.1)
    newer = scan_ok(client)
    r = client.get("/api/scans")
    assert r.status_code == 200, r.text
    ids = [s["id"] for s in r.json()]
    assert newer["id"] in ids and older["id"] in ids
    assert ids.index(newer["id"]) < ids.index(older["id"]), "The newest scan goes first"


def test_list_items_are_complete(client):
    scan = scan_ok(client)
    listed = {s["id"]: s for s in client.get("/api/scans").json()}
    assert listed[scan["id"]] == scan


def test_delete_scan(client):
    scan = scan_ok(client)
    r = client.delete(f"/api/scans/{scan['id']}")
    assert r.status_code == 204, r.text
    assert r.content == b""
    assert_error(client.get(f"/api/scans/{scan['id']}"), 404, "SCAN_NOT_FOUND")
    assert scan["id"] not in [s["id"] for s in client.get("/api/scans").json()]
    assert client.get(scan["url"]).status_code == 404
    assert client.get(scan["original_url"]).status_code == 404
    leftovers = [name for name in stored_files() if scan["id"] in name]
    assert not leftovers, f"Files of the deleted scan were left behind: {leftovers}"


def test_delete_unknown_scan(client):
    assert_error(client.delete("/api/scans/does-not-exist"), 404, "SCAN_NOT_FOUND")


def run_python(code: str, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)], cwd=BACKEND_DIR, capture_output=True,
        text=True, timeout=120, env={**os.environ, **env},
    )


def test_scans_survive_a_restart(client):
    """Scans are kept on disk: a new server process still finds them."""
    scan = scan_ok(client)
    result = run_python(f"""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            r = c.get("/api/scans/{scan['id']}")
            print(r.status_code)
            print(r.json().get("url"))
    """, TP_STORAGE_DIR=str(STORAGE_DIR))
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["200", scan["url"]], result.stdout + result.stderr


# ===========================================================================
# The core (docscan) is reusable without the API
# ===========================================================================

def test_core_does_not_depend_on_the_api():
    result = run_python("""
        import sys
        import docscan
        import docscan.__main__  # noqa: F401  (the command line entry point)
        loaded = [m for m in sys.modules if m.split(".")[0] in {"fastapi", "starlette", "app"}]
        print(loaded)
    """)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", f"docscan must not import the API: {result.stdout}"


def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "docscan", *map(str, args)], cwd=BACKEND_DIR,
        capture_output=True, text=True, timeout=120,
    )


def test_cli_scans_a_photo(tmp_path):
    source, target = tmp_path / "photo.jpg", tmp_path / "scan.png"
    source.write_bytes(encode(photo(document(), angle=-12)[0], "JPEG", quality=90))
    result = run_cli(source, target)
    assert result.returncode == 0, result.stderr
    img = Image.open(target)
    assert img.format == "PNG" and img.mode == "RGB"
    assert_upright_page(img, ratio=420 / 300)


def test_cli_options(tmp_path):
    source, target = tmp_path / "photo.png", tmp_path / "scan.png"
    source.write_bytes(encode(photo(document(paper=TINTED_PAPER, patch=STRONG_RED))[0]))
    result = run_cli(source, target, "--color-mode", "grayscale", "--no-color-correction", "--soften-colors", "0.5")
    assert result.returncode == 0, result.stderr
    img = Image.open(target)
    assert img.mode == "L"
    assert_upright_page(img, ratio=420 / 300)


def test_cli_document_not_found(tmp_path):
    source, target = tmp_path / "photo.png", tmp_path / "scan.png"
    source.write_bytes(encode(no_document("uniform")))
    result = run_cli(source, target)
    assert result.returncode != 0
    assert result.stderr.strip(), "The reason must be explained on stderr"
    assert not target.exists()
