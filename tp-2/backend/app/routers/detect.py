from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.schemas import DetectionOut, ErrorOut

router = APIRouter(prefix="/api", tags=["detection"])


@router.post(
    "/detect",
    response_model=DetectionOut,
    summary="Detect the document in a photo",
    responses={400: {"model": ErrorOut}, 413: {"model": ErrorOut}, 422: {"model": ErrorOut}},
)
async def detect(file: Annotated[UploadFile, File(description="Photo of a document")]):
    # TODO (team): validate the file, find the document with docscan and return its corners.
    return DetectionOut(width=0, height=0, corners=[])
