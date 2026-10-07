from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from starlette.concurrency import run_in_threadpool

import docscan

from app import config
from app.repository import ScanRepository
from app.schemas import ColorMode, ErrorOut, ScanOptions, ScanOut

router = APIRouter(prefix="/api/scans", tags=["scans"])


def empty_scan(scan_id: str = "", original_name: str = "", options: ScanOptions | None = None) -> ScanOut:
    """Placeholder answer with the right shape. Delete it once the endpoints are implemented."""
    return ScanOut(
        id=scan_id, original_name=original_name, url="", original_url="",
        width=0, height=0, size_bytes=0, corners=[],
        options=options or ScanOptions(), created_at=datetime.now(),
    )


@router.post(
    "",
    response_model=ScanOut,
    status_code=status.HTTP_201_CREATED,
    summary="Scan a photo and save the result",
    responses={400: {"model": ErrorOut}, 413: {"model": ErrorOut}, 422: {"model": ErrorOut}},
)
async def create_scan(
    file: Annotated[UploadFile, File(description="Photo of a document")],
    color_mode: Annotated[ColorMode, Form()] = "color",
    color_correction: Annotated[bool, Form()] = True,
    soften_colors: Annotated[float, Form(ge=0, le=1)] = 0.0,
):
    options = ScanOptions(color_mode=color_mode, color_correction=color_correction, soften_colors=soften_colors)
    content = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise docscan.ScanError("FILE_TOO_LARGE", "El archivo supera el tamaño máximo permitido.")
    result = await run_in_threadpool(
        docscan.scan, content, allowed_formats=config.ALLOWED_FORMATS,
        **options.model_dump(),
    )
    return await run_in_threadpool(
        ScanRepository().save, content, file.filename or "", result, options,
    )


@router.get("", response_model=list[ScanOut], summary="List the scans, newest first")
def list_scans():
    # TODO (team): read the saved scans.
    return []


@router.get("/{scan_id}", response_model=ScanOut, summary="Get a scan", responses={404: {"model": ErrorOut}})
def get_scan(scan_id: str):
    # TODO (team): read the scan, or answer 404 SCAN_NOT_FOUND.
    return empty_scan(scan_id)


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scan and its files",
    responses={404: {"model": ErrorOut}},
)
def delete_scan(scan_id: str):
    # TODO (team): delete the files of the scan, or answer 404 SCAN_NOT_FOUND.
    return None
