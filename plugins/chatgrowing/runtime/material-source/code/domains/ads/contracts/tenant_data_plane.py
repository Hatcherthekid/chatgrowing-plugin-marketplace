from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TenantDataOutcomeState = Literal[
    "data_present",
    "confirmed_empty",
    "no_delivery",
    "mapping_incomplete",
    "stale",
    "partial",
    "query_failed",
    "artifact_failed",
]


@dataclass(frozen=True)
class TenantSyncCommit:
    source_version: str
    data_as_of: str


@dataclass(frozen=True)
class TenantDataLineage:
    organization_id: str
    data_plane_id: str
    source_connection_id: str
    source_asset_id: str
    external_account_id: str
    snapshot_id: str
    source_version: str
    schema_version: str
    data_as_of: str
    freshness_status: Literal["fresh", "stale"]


@dataclass(frozen=True)
class TenantDataOutcome:
    state: TenantDataOutcomeState
    lineage: TenantDataLineage | None
    reason_code: str | None = None
