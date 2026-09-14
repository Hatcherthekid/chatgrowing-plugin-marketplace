from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterable
from urllib.parse import unquote, urlparse


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SCHEMA_VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+$")
_ALLOWED_ENVIRONMENTS = frozenset({"development", "staging", "production"})
_ALLOWED_STATUSES = frozenset({"provisioning", "active", "suspended", "retired"})
_ALLOWED_STORE_SCHEMES = frozenset({"file", "s3"})


class DataPlaneContractError(ValueError):
    """A stable, non-secret reason why a data-plane contract is invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DataPlaneRoutingError(RuntimeError):
    """Fail-closed routing error safe for an application boundary to classify."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _required_identifier(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise DataPlaneContractError(
            "invalid_identifier",
            f"{name} must be a non-empty stable identifier",
        )
    return normalized


def _required_external_identifier(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or any(ord(character) < 32 for character in normalized):
        raise DataPlaneContractError(
            "invalid_source_identity",
            f"{name} must be a non-empty source identifier",
        )
    return normalized


@dataclass(frozen=True)
class _StoreLocation:
    scheme: str
    authority: str
    path: PurePosixPath


def _store_location(name: str, value: str, *, runtime: bool = False) -> _StoreLocation:
    reference = str(value or "").strip()
    if not reference:
        raise DataPlaneContractError("missing_store_ref", f"{name} is required")
    if "\n" in reference or "\r" in reference:
        raise DataPlaneContractError("invalid_store_ref", f"{name} contains control characters")

    if reference.startswith("/"):
        scheme = "file"
        authority = ""
        raw_path = reference
    else:
        parsed = urlparse(reference)
        scheme = parsed.scheme.lower()
        if scheme not in _ALLOWED_STORE_SCHEMES:
            raise DataPlaneContractError(
                "unsupported_store_ref",
                f"{name} must be an absolute path, file URI, or s3 URI",
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise DataPlaneContractError(
                "unsafe_store_ref",
                f"{name} must not contain credentials, query, or fragment",
            )
        if scheme == "file":
            if parsed.netloc not in {"", "localhost"}:
                raise DataPlaneContractError(
                    "invalid_store_ref",
                    f"{name} file URI must be local",
                )
            authority = ""
        else:
            if not parsed.netloc:
                raise DataPlaneContractError(
                    "invalid_store_ref",
                    f"{name} s3 URI must include a bucket",
                )
            authority = parsed.netloc.lower()
        raw_path = unquote(parsed.path)

    if runtime and scheme != "file":
        raise DataPlaneContractError(
            "invalid_runtime_store_ref",
            "runtime_store_ref must identify a local tenant runtime database",
        )
    if not raw_path.startswith("/"):
        raise DataPlaneContractError("invalid_store_ref", f"{name} path must be absolute")

    path = PurePosixPath(raw_path)
    if ".." in path.parts or path == PurePosixPath("/"):
        raise DataPlaneContractError(
            "unsafe_store_ref",
            f"{name} must identify a non-root namespace without parent traversal",
        )
    if scheme == "s3" and len(path.parts) < 2:
        raise DataPlaneContractError(
            "invalid_store_ref",
            f"{name} s3 URI must include a tenant-specific prefix",
        )
    return _StoreLocation(scheme=scheme, authority=authority, path=path)


def _locations_overlap(left: _StoreLocation, right: _StoreLocation) -> bool:
    if (left.scheme, left.authority) != (right.scheme, right.authority):
        return False
    return left.path == right.path or left.path in right.path.parents or right.path in left.path.parents


@dataclass(frozen=True)
class DataPlaneRef:
    data_plane_id: str
    organization_id: str
    environment: str
    runtime_store_ref: str
    snapshot_store_ref: str
    artifact_store_ref: str
    schema_version: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "data_plane_id",
            _required_identifier("data_plane_id", self.data_plane_id),
        )
        object.__setattr__(
            self,
            "organization_id",
            _required_identifier("organization_id", self.organization_id),
        )

        environment = str(self.environment or "").strip().lower()
        if environment not in _ALLOWED_ENVIRONMENTS:
            raise DataPlaneContractError(
                "invalid_environment",
                "environment must be development, staging, or production",
            )
        object.__setattr__(self, "environment", environment)

        status = str(self.status or "").strip().lower()
        if status not in _ALLOWED_STATUSES:
            raise DataPlaneContractError(
                "invalid_status",
                "status must be provisioning, active, suspended, or retired",
            )
        object.__setattr__(self, "status", status)

        schema_version = str(self.schema_version or "").strip()
        if not _SCHEMA_VERSION_PATTERN.fullmatch(schema_version):
            raise DataPlaneContractError(
                "invalid_schema_version",
                "schema_version must use major.minor format",
            )
        object.__setattr__(self, "schema_version", schema_version)

        locations = (
            _store_location("runtime_store_ref", self.runtime_store_ref, runtime=True),
            _store_location("snapshot_store_ref", self.snapshot_store_ref),
            _store_location("artifact_store_ref", self.artifact_store_ref),
        )
        for index, left in enumerate(locations):
            for right in locations[index + 1 :]:
                if _locations_overlap(left, right):
                    raise DataPlaneContractError(
                        "store_namespace_overlap",
                        "runtime, snapshot, and artifact stores must use disjoint namespaces",
                    )

    @property
    def store_locations(self) -> tuple[_StoreLocation, ...]:
        return (
            _store_location("runtime_store_ref", self.runtime_store_ref, runtime=True),
            _store_location("snapshot_store_ref", self.snapshot_store_ref),
            _store_location("artifact_store_ref", self.artifact_store_ref),
        )


@dataclass(frozen=True)
class TenantSourceRef:
    organization_id: str
    source_connection_id: str
    source_asset_id: str
    external_account_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_identifier("organization_id", self.organization_id),
        )
        object.__setattr__(
            self,
            "source_connection_id",
            _required_identifier("source_connection_id", self.source_connection_id),
        )
        object.__setattr__(
            self,
            "source_asset_id",
            _required_identifier("source_asset_id", self.source_asset_id),
        )
        object.__setattr__(
            self,
            "external_account_id",
            _required_external_identifier("external_account_id", self.external_account_id),
        )


@dataclass(frozen=True)
class TenantDataRoute:
    data_plane: DataPlaneRef
    source: TenantSourceRef


class TenantDataPlaneRouter:
    """Resolve one verified tenant/source pair without a global fallback."""

    def __init__(self, data_planes: Iterable[DataPlaneRef]) -> None:
        self._by_organization_environment: dict[tuple[str, str], DataPlaneRef] = {}
        self._by_data_plane_id: dict[str, DataPlaneRef] = {}

        for data_plane in data_planes:
            key = (data_plane.organization_id, data_plane.environment)
            if key in self._by_organization_environment:
                raise DataPlaneContractError(
                    "duplicate_organization_data_plane",
                    "an organization may have only one data plane per environment",
                )
            if data_plane.data_plane_id in self._by_data_plane_id:
                raise DataPlaneContractError(
                    "duplicate_data_plane_id",
                    "data_plane_id must be globally unique",
                )

            for existing in self._by_data_plane_id.values():
                if any(
                    _locations_overlap(candidate, occupied)
                    for candidate in data_plane.store_locations
                    for occupied in existing.store_locations
                ):
                    raise DataPlaneContractError(
                        "cross_tenant_store_collision",
                        "data planes must not share or nest storage namespaces",
                    )

            self._by_organization_environment[key] = data_plane
            self._by_data_plane_id[data_plane.data_plane_id] = data_plane

    def route(
        self,
        *,
        verified_organization_id: str,
        environment: str,
        source: TenantSourceRef,
    ) -> TenantDataRoute:
        try:
            organization_id = _required_identifier(
                "verified_organization_id",
                verified_organization_id,
            )
        except DataPlaneContractError as exc:
            raise DataPlaneRoutingError(
                "invalid_organization_context",
                "the verified organization context is invalid",
            ) from exc
        normalized_environment = str(environment or "").strip().lower()
        if normalized_environment not in _ALLOWED_ENVIRONMENTS:
            raise DataPlaneRoutingError(
                "invalid_environment",
                "the requested data-plane environment is invalid",
            )
        if organization_id != source.organization_id:
            raise DataPlaneRoutingError(
                "source_organization_mismatch",
                "the selected source does not belong to the verified organization",
            )

        data_plane = self._by_organization_environment.get(
            (organization_id, normalized_environment)
        )
        if data_plane is None:
            raise DataPlaneRoutingError(
                "data_plane_not_found",
                "no data plane is registered for the verified organization and environment",
            )
        if data_plane.status != "active":
            raise DataPlaneRoutingError(
                "data_plane_not_active",
                "the organization's data plane is not active",
            )
        return TenantDataRoute(data_plane=data_plane, source=source)
