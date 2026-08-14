from __future__ import annotations

import gzip

import pytest
from fastapi import HTTPException

from app.request_body import _decompress_gzip_bounded


def test_bounded_gzip_decode() -> None:
    assert _decompress_gzip_bounded(gzip.compress(b"payload"), 7) == b"payload"


def test_rejects_expansion_over_limit() -> None:
    with pytest.raises(HTTPException) as error:
        _decompress_gzip_bounded(gzip.compress(b"12345678"), 7)
    assert error.value.status_code == 413


def test_rejects_invalid_gzip() -> None:
    with pytest.raises(HTTPException) as error:
        _decompress_gzip_bounded(b"not gzip", 100)
    assert error.value.status_code == 400
