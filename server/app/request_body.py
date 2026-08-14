"""Bounded gzip/JSON request decoding."""

from __future__ import annotations

import gzip
import io
import json
from typing import Any

from fastapi import HTTPException, Request, status


def _decompress_gzip_bounded(body: bytes, maximum: int) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body), mode="rb") as compressed:
            expanded = compressed.read(maximum + 1)
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request body is not valid gzip data",
        ) from exc
    if len(expanded) > maximum:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="expanded request body exceeds configured limit",
        )
    return expanded


async def read_gzip_json(request: Request) -> Any:
    settings = request.app.state.settings
    encoding = request.headers.get("content-encoding", "").lower().strip()
    if encoding != "gzip":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Encoding must be gzip",
        )
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json",
        )
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > settings.max_compressed_batch_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="compressed request body exceeds configured limit",
            )
        chunks.append(chunk)
    body = b"".join(chunks)
    expanded = _decompress_gzip_bounded(body, settings.max_expanded_batch_bytes)
    try:
        return json.loads(expanded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expanded request body is not valid JSON",
        ) from exc
