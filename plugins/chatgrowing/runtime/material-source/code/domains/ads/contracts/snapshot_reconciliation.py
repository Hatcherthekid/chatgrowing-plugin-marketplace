from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Literal


SNAPSHOT_SOURCE_EVIDENCE_VERSION = 2
SNAPSHOT_RECONCILIATION_VERSION = 2


@dataclass(frozen=True)
class GovernedTableCount:
    table_name: str
    row_count: int


@dataclass(frozen=True)
class SnapshotSourceEvidence:
    evidence_version: int
    organization_id: str
    data_plane_id: str
    source_connection_id: str
    source_asset_id: str
    external_account_id: str
    runtime_store_ref_digest: str
    source_version: str
    schema_version: str
    data_as_of: str
    captured_at: str
    sqlite_user_version: int
    schema_digest: str
    source_backup_digest: str
    governed_table_counts: tuple[GovernedTableCount, ...]
    integrity_status: Literal["ok"]
    evidence_checksum: str

    def checksum_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("evidence_checksum")
        return payload


@dataclass(frozen=True)
class SnapshotReconciliation:
    reconciliation_version: int
    snapshot_id: str
    organization_id: str
    data_plane_id: str
    source_connection_id: str
    source_asset_id: str
    external_account_id: str
    source_evidence_checksum: str
    source_version: str
    schema_version: str
    data_as_of: str
    checked_at: str
    snapshot_sqlite_user_version: int
    snapshot_schema_digest: str
    snapshot_backup_digest: str
    snapshot_table_counts: tuple[GovernedTableCount, ...]
    status: Literal["exact_match"]


def snapshot_source_evidence_checksum(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
