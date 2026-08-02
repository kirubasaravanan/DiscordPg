"""Only mounted when settings.storage_backend == "local" (see app/main.py).

These routes are what LocalFilesystemStorageBackend's "presigned" URLs
actually point to — the local analog of hitting a real R2/S3 bucket
directly. Security is the same idea as a real presigned URL: the token in
the query string is a signed, time-limited credential scoped to one key and
one action (upload or download); there is no user-auth check here at all,
by design, exactly like a real presigned URL needs none.
"""

from fastapi import APIRouter, Query, Request, Response

from app.api.errors import not_found, unauthorized
from app.security.jwt import StorageTokenAction, TokenError, decode_storage_token
from app.storage.local import LocalFilesystemStorageBackend

router = APIRouter()
_backend = LocalFilesystemStorageBackend()


def _verify(storage_key: str, token: str, action: StorageTokenAction) -> None:
    try:
        token_key = decode_storage_token(token, action)
    except TokenError as exc:
        raise unauthorized(f"Invalid or expired storage token: {exc}")
    if token_key != storage_key:
        raise unauthorized("Storage token does not match this key.")


@router.put("/{storage_key:path}")
async def upload(storage_key: str, request: Request, token: str = Query(...)) -> Response:
    _verify(storage_key, token, StorageTokenAction.UPLOAD)
    body = await request.body()
    _backend.write(storage_key, body)
    return Response(status_code=204)


@router.get("/{storage_key:path}")
def download(storage_key: str, token: str = Query(...)) -> Response:
    _verify(storage_key, token, StorageTokenAction.DOWNLOAD)
    if not _backend.object_exists(storage_key):
        raise not_found("Nothing has been uploaded to this storage key yet.")
    return Response(content=_backend.read(storage_key), media_type="application/octet-stream")
