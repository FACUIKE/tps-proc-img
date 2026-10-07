from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.schemas import DetectionOut, ErrorOut
from app.uploads import read_upload

router = APIRouter(prefix="/api", tags=["detection"])


@router.post(
    "/detect",
    response_model=DetectionOut,
    summary="Detect the document in a photo",
    responses={400: {"model": ErrorOut}, 413: {"model": ErrorOut}, 422: {"model": ErrorOut}},
)
async def detect(file: Annotated[UploadFile, File(description="Photo of a document")]):
    upload = await read_upload(file)  # given: 413 FILE_TOO_LARGE / 400 INVALID_FILE / 400 UNSUPPORTED_FORMAT
    # TODO (team): find the document in upload.photo.image with docscan and return its corners.
    return DetectionOut(width=upload.photo.width, height=upload.photo.height, corners=[])
