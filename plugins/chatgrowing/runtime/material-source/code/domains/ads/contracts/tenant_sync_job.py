from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .data_plane import TenantSourceRef
from .tenant_provider_sync import TenantProviderSyncRequest


TenantSyncJobStage = Literal["start", "commit"]


class TenantSyncJobAuthorizationError(PermissionError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TenantSyncJobGrant:
    """Non-secret authority returned to one organization-scoped worker."""

    request: TenantProviderSyncRequest
    source: TenantSourceRef
    job_id: str
    expires_at: int
