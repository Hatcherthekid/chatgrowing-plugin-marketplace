"""Public file manifest encoding and transfer limits shared with the server."""
import hashlib
import json
from typing import Any

CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNKS = 16384

class MaterialError(ValueError):
    def __init__(self, code: str, status: int = 409, *, retry_after: int = 0):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after

def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()

def bounded_text(value: Any, *, limit: int, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise MaterialError("material_text_invalid", 422)
    if required and not value.strip():
        raise MaterialError("material_text_required", 422)
    return value
