from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class TenantProviderSyncContractError(ValueError):
    """A stable, non-secret reason why a provider sync request is invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_provider_channel(value: str) -> str:
    channel = str(value or "").strip().lower()
    if not _IDENTIFIER_PATTERN.fullmatch(channel):
        raise TenantProviderSyncContractError(
            "invalid_provider_channel",
            "provider channel must be a non-empty stable identifier",
        )
    return channel


def _required_identifier(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise TenantProviderSyncContractError(
            "invalid_provider_sync_identity",
            f"{name} must be a non-empty stable identifier",
        )
    return normalized


def _required_external_identifier(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or any(ord(character) < 32 for character in normalized):
        raise TenantProviderSyncContractError(
            "invalid_provider_sync_identity",
            f"{name} must be a non-empty source identifier",
        )
    return normalized


@dataclass(frozen=True)
class TenantProviderSyncRequest:
    """Server-owned provider request containing identifiers but never credentials."""

    organization_id: str
    environment: str
    channel: str
    connection_id: str
    resource_id: str
    external_account_id: str
    target_date: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_identifier("organization_id", self.organization_id),
        )
        environment = str(self.environment or "").strip().lower()
        if environment not in {"development", "staging", "production"}:
            raise TenantProviderSyncContractError(
                "invalid_provider_sync_environment",
                "environment must be development, staging, or production",
            )
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "channel", normalize_provider_channel(self.channel))
        object.__setattr__(
            self,
            "connection_id",
            _required_identifier("connection_id", self.connection_id),
        )
        object.__setattr__(
            self,
            "resource_id",
            _required_identifier("resource_id", self.resource_id),
        )
        object.__setattr__(
            self,
            "external_account_id",
            _required_external_identifier(
                "external_account_id",
                self.external_account_id,
            ),
        )
        if self.target_date is not None:
            if type(self.target_date) is not str:
                raise TenantProviderSyncContractError(
                    "invalid_provider_sync_target_date",
                    "target_date must be an ISO calendar date",
                )
            try:
                normalized_target_date = date.fromisoformat(self.target_date).isoformat()
            except ValueError:
                raise TenantProviderSyncContractError(
                    "invalid_provider_sync_target_date",
                    "target_date must be an ISO calendar date",
                ) from None
            if normalized_target_date != self.target_date:
                raise TenantProviderSyncContractError(
                    "invalid_provider_sync_target_date",
                    "target_date must be an ISO calendar date",
                )
