"""素材库的窄领域输入；身份必须由 BFF 的当前授权上下文构造。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any
from uuid import uuid4


class MaterialError(ValueError):
    def __init__(self, code: str, status: int = 409, *, retry_after: int = 0):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class MaterialActor:
    organization_id: str
    membership_id: str
    capabilities: frozenset[str]

    def require(self, capability: str) -> None:
        if not self.organization_id or not self.membership_id or capability not in self.capabilities:
            raise MaterialError("material_access_denied", 403)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


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


def youtube_session_operation_id(organization_id: str, distribution_id: str) -> str:
    """Stable Vault write identity for an already-persisted upload intent."""
    return digest({"youtube_session": distribution_id, "organization_id": organization_id})


def youtube_upload_binding_verified(video: dict, *, video_id: str, channel_id: str, entry: dict) -> bool:
    """Binding can survive an omitted synthetic flag; its value remains unknown.

    All other requested metadata, identity and processing evidence must match.
    An explicitly returned synthetic flag must also match the reviewed request.
    """
    from .youtube_publication import verification
    checks = verification(video, entry)
    return (bool(video_id) and video.get('id') == video_id
        and video.get('snippet', {}).get('channelId') == channel_id
        and not checks['mismatch'] and set(checks['missing']) <= {'status.containsSyntheticMedia'}
        and video.get('status', {}).get('uploadStatus') == 'processed'
        and video.get('processingDetails', {}).get('processingStatus') == 'succeeded')
