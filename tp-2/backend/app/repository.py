"""Disk persistence for scans and their original uploads."""

from datetime import datetime, timezone
from uuid import uuid4

from docscan import ScanResult

from app import config
from app.schemas import ScanOptions, ScanOut


class ScanRepository:
    def save(self, original: bytes, original_name: str, result: ScanResult, options: ScanOptions) -> ScanOut:
        scan_id = uuid4().hex
        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "BMP": "bmp"}[result.original_format]
        result_name = f"{scan_id}.png"
        original_file = f"{scan_id}-original.{extension}"
        scan = ScanOut(
            id=scan_id, original_name=original_name,
            url=f"{config.MEDIA_URL}/{result_name}",
            original_url=f"{config.MEDIA_URL}/{original_file}",
            width=result.width, height=result.height, size_bytes=len(result.png),
            corners=result.corners, options=options, created_at=datetime.now(timezone.utc),
        )
        files = {
            result_name: result.png,
            original_file: original,
            f"{scan_id}.json": scan.model_dump_json().encode("utf-8"),
        }
        config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        written = []
        try:
            for name, content in files.items():
                path = config.STORAGE_DIR / name
                with path.open("xb") as output:
                    written.append(path)
                    output.write(content)
        except OSError:
            for path in written:
                path.unlink(missing_ok=True)
            raise
        return scan
