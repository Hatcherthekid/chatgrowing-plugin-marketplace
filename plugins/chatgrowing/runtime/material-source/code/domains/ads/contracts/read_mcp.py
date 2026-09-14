"""Host-neutral public DTOs for the read-only Ads MCP capability surface."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PrivateAttr, field_validator, model_validator

from .fact_semantics import validate_fact_date_semantics_pair

PUBLIC_TOOL_NAMES = (
    "ads_catalog_search",
    "ads_catalog_describe",
    "ads_capability_context",
    "ads_data_health",
    "ads_data_query",
    "ads_workspace_analyze",
    "ads_knowledge_search",
    "ads_context_lookup",
    "ads_report_generate",
)
PublicToolName = Literal[
    "ads_catalog_search",
    "ads_catalog_describe",
    "ads_capability_context",
    "ads_data_health",
    "ads_data_query",
    "ads_workspace_analyze",
    "ads_knowledge_search",
    "ads_context_lookup",
    "ads_report_generate",
]
KnowledgeSourceQuality = Literal[
    "internal_governed_method",
    "organization_reviewed",
    "platform_official",
    "public_reference",
]
CatalogSourceKind = Literal["data_product", "config_source", "artifact"]
FactSemantics = Literal["cohort", "actual"]
CountingSemantics = Literal["total_events", "unique_users"]
DateSemantics = Literal["install_cohort_date", "actual_event_date"]
EvidenceFactSemantics = Literal["cohort", "actual", "mixed"]
EvidenceDateSemantics = Literal["install_cohort_date", "actual_event_date", "mixed"]
CatalogCapability = Literal[
    "query",
    "describe",
    "aggregate",
    "detail",
    "config",
    "status",
    "trend",
    "ranking",
    "report_followup",
    "asset_analysis",
    "placement_analysis",
]

PUBLIC_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
MAX_PUBLIC_MODEL_BYTES = 128_000
MAX_PUBLIC_TOOL_DISCLOSURE_BYTES = 112_000
MAX_PREVIEW_ROWS = 200
PRIVATE_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:file://[^\s\"'<>]*|"
    r"/(?:root|Users|private|home|tmp|etc|opt|srv|mnt|Volumes|var)/[^\s\"'<>]*|"
    r"(?:\.\./)+[^\s\"'<>]*|[A-Za-z]:\\[^\s\"'<>]*)",
    re.IGNORECASE,
)

PublicIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=PUBLIC_IDENTIFIER_PATTERN),
]
FieldName = Annotated[str, Field(min_length=1, max_length=128)]
ShortLabel = Annotated[str, Field(min_length=1, max_length=240)]
ShortText = Annotated[str, Field(min_length=1, max_length=2_000)]
JsonScalar = Union[str, int, float, bool, None]


class PublicContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_serialized_budget(self) -> "PublicContractModel":
        try:
            payload = json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("public contract must serialize as standards-compliant JSON") from exc
        if len(payload) > MAX_PUBLIC_MODEL_BYTES:
            raise ValueError(
                f"public contract exceeds compact output budget of {MAX_PUBLIC_MODEL_BYTES} bytes"
            )
        return self


def _unique_non_empty(values: list[str], field_name: str) -> list[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if len(cleaned) != len(values):
        raise ValueError(f"{field_name} must not contain blank values")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} must not contain duplicates")
    return cleaned


def _reject_private_references(value: Any) -> None:
    if isinstance(value, str):
        if PRIVATE_REFERENCE_PATTERN.search(value):
            raise ValueError("public response must not expose private filesystem references")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_private_references(key)
            _reject_private_references(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_references(item)


class DateRange(PublicContractModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> "DateRange":
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class FilterPredicate(PublicContractModel):
    field: FieldName
    operator: FilterOperator = FilterOperator.EQ
    value: Union[JsonScalar, list[JsonScalar]] = None

    @model_validator(mode="after")
    def validate_value_shape(self) -> "FilterPredicate":
        if self.operator in {FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL}:
            if self.value is not None:
                raise ValueError(f"{self.operator.value} does not accept value")
            return self
        if self.value is None:
            raise ValueError(f"{self.operator.value} requires value")
        if self.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.operator.value} requires a non-empty list")
        elif isinstance(self.value, list):
            raise ValueError(f"{self.operator.value} accepts one scalar value")
        return self


class SortSpec(PublicContractModel):
    field: FieldName
    direction: Literal["asc", "desc"] = "asc"
    nulls: Literal["first", "last"] = "last"


class QuerySpec(PublicContractModel):
    source_id: PublicIdentifier
    fact_semantics: Optional[FactSemantics] = None
    counting_semantics: Optional[CountingSemantics] = None
    date_range: DateRange
    dimensions: list[FieldName] = Field(default_factory=list, max_length=40)
    metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    filters: list[FilterPredicate] = Field(default_factory=list, max_length=60)
    cohort_window: Optional[PublicIdentifier] = None
    order_by: list[SortSpec] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=500, ge=1, le=10_000)
    scope: "QueryScopeSelector" = Field(default_factory=lambda: QueryScopeSelector())

    @field_validator("dimensions", "metrics")
    @classmethod
    def validate_unique_fields(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> "QuerySpec":
        if not self.dimensions and not self.metrics:
            raise ValueError("at least one dimension or metric is required")
        return self


class QueryScopeSelector(PublicContractModel):
    """User intent may only narrow the current principal's server-owned scope."""

    mode: Literal["current_authorized"] = "current_authorized"
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    app_refs: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    resource_refs: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    resource_cursor: Optional[Annotated[str, Field(pattern=r"^c[0-9]+$")]] = None
    resource_limit: int = Field(default=20, ge=1, le=20)

    @field_validator("channels", "app_refs", "resource_refs")
    @classmethod
    def validate_scope_terms(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class CatalogSearchRequest(PublicContractModel):
    query: Optional[ShortText] = None
    fact_semantics: Optional[FactSemantics] = None
    counting_semantics: Optional[CountingSemantics] = None
    metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    dimensions: list[FieldName] = Field(default_factory=list, max_length=40)
    channel: Optional[PublicIdentifier] = None
    source_kinds: list[CatalogSourceKind] = Field(default_factory=list, max_length=3)
    capabilities: list[CatalogCapability] = Field(default_factory=list, max_length=11)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("metrics", "dimensions", "source_kinds", "capabilities")
    @classmethod
    def validate_unique_terms(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)

    @model_validator(mode="after")
    def validate_search_signal(self) -> "CatalogSearchRequest":
        if self.fact_semantics:
            opposite = "cohort" if self.fact_semantics == "actual" else "actual"
            if any(metric.startswith(f"{opposite}_") for metric in self.metrics):
                raise ValueError("catalog metric prefix conflicts with fact_semantics")
        if not any(
            (
                self.query,
                self.fact_semantics,
                self.metrics,
                self.dimensions,
                self.channel,
                self.source_kinds,
                self.capabilities,
            )
        ):
            raise ValueError("catalog search requires at least one search signal")
        return self


class CatalogDescribeRequest(PublicContractModel):
    source_id: PublicIdentifier
    requested_fields: list[FieldName] = Field(default_factory=list, max_length=80)

    @field_validator("requested_fields")
    @classmethod
    def validate_requested_fields(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "requested_fields")


class DataHealthRequest(PublicContractModel):
    source_ids: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    resource_refs: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    apps: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    requested_date_range: Optional[DateRange] = None

    @field_validator("source_ids", "resource_refs", "channels", "apps")
    @classmethod
    def validate_health_scope(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class KnowledgeSearchRequest(PublicContractModel):
    query: Optional[ShortText] = None
    topics: list[ShortLabel] = Field(default_factory=list, max_length=30)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    source_qualities: list[KnowledgeSourceQuality] = Field(default_factory=list, max_length=4)
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("topics", "channels", "source_qualities")
    @classmethod
    def validate_search_terms(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)

    @model_validator(mode="after")
    def validate_search_signal(self) -> "KnowledgeSearchRequest":
        if not any((self.query, self.topics, self.channels, self.source_qualities)):
            raise ValueError("knowledge search requires at least one search signal")
        return self


ContextKind = Literal["organization_pack", "user_rules", "candidate_policy"]
ContextSourceQuality = Literal["organization_reviewed", "user_preference", "governance_policy"]
ContextRuleType = Literal[
    "business_goal",
    "analysis_preference",
    "sop",
    "approval_preference",
    "account_structure",
    "industry_context",
]
CandidateType = Literal[
    "lesson",
    "knowledge_patch",
    "skill_patch",
    "source_policy_issue",
    "metric_issue",
]


class ContextLookupRequest(PublicContractModel):
    query: Optional[ShortText] = None
    organization_ids: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    apps: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    topics: list[ShortLabel] = Field(default_factory=list, max_length=40)
    context_kinds: list[ContextKind] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("organization_ids", "apps", "channels", "topics", "context_kinds")
    @classmethod
    def validate_context_terms(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)

    @model_validator(mode="after")
    def validate_lookup_signal(self) -> "ContextLookupRequest":
        if not any(
            (
                self.query,
                self.organization_ids,
                self.apps,
                self.channels,
                self.topics,
                self.context_kinds,
            )
        ):
            raise ValueError("context lookup requires at least one search signal")
        return self


class QueryEntityKey(PublicContractModel):
    values: dict[FieldName, PublicIdentifier] = Field(min_length=1, max_length=6)


class QueryExecutionReceiptRef(PublicContractModel):
    receipt_id: PublicIdentifier
    schema_version: Literal["QueryExecutionReceipt.v1"] = "QueryExecutionReceipt.v1"
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("query receipt timestamps must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "QueryExecutionReceiptRef":
        if self.expires_at <= self.created_at:
            raise ValueError("query receipt expires_at must be after created_at")
        return self


class QueryReplayProvenance(PublicContractModel):
    original_receipt_id: PublicIdentifier
    original_created_at: datetime
    original_expires_at: datetime
    replayed_at: datetime
    replay_policy: Literal["explicit_exact_query_spec"] = "explicit_exact_query_spec"
    authorization_rechecked: Literal[True] = True

    @field_validator("original_created_at", "original_expires_at", "replayed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("query replay timestamps must include timezone information")
        return value


class EphemeralResultHandle(PublicContractModel):
    result_handle_id: PublicIdentifier
    schema_version: Literal["EphemeralResultHandle.v1"] = "EphemeralResultHandle.v1"
    row_count: int = Field(ge=0)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("result handle expires_at must include timezone information")
        return value


class PublishedEvidenceSetRef(PublicContractModel):
    evidence_set_id: PublicIdentifier
    schema_version: Literal["PublishedEvidenceSet.v1"] = "PublishedEvidenceSet.v1"
    content_format: Literal["rows_v1", "json_utf8_chunks_v1"] = "rows_v1"
    row_count: int = Field(ge=1)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_lineage_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_contract_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_window_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    coverage_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    grain: list[FieldName] = Field(default_factory=list, max_length=40)
    fact_semantics: Optional[EvidenceFactSemantics] = None
    date_semantics: Optional[EvidenceDateSemantics] = None
    expires_at: datetime

    @field_validator("evidence_set_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not value.startswith("pes_"):
            raise ValueError("published evidence set id must use pes_ prefix")
        return value

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("published evidence set expires_at must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_semantics(self) -> "PublishedEvidenceSetRef":
        validate_fact_date_semantics_pair(self.fact_semantics, self.date_semantics)
        return self


class RenderedAssetRef(PublicContractModel):
    rendered_asset_id: PublicIdentifier
    report_run_id: PublicIdentifier
    schema_version: Literal["RenderedAsset.v1"] = "RenderedAsset.v1"
    media_type: Literal["image/png", "application/pdf", "text/markdown"]
    byte_size: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    renderer_ref: PublicIdentifier
    created_at: datetime
    expires_at: datetime

    @field_validator("rendered_asset_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not value.startswith("ra_"):
            raise ValueError("rendered asset id must use ra_ prefix")
        return value

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("rendered asset timestamps must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "RenderedAssetRef":
        if self.expires_at <= self.created_at:
            raise ValueError("rendered asset expires_at must be after created_at")
        return self


class ReportRunRef(PublicContractModel):
    report_run_ref_id: PublicIdentifier
    report_run_id: PublicIdentifier
    schema_version: Literal["ReportRun.v1"] = "ReportRun.v1"
    status: Literal["ready"] = "ready"
    evidence_set_refs: list[PublishedEvidenceSetRef] = Field(min_length=1, max_length=20)
    rendered_asset_refs: list[RenderedAssetRef] = Field(default_factory=list, max_length=10)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    expires_at: datetime

    @field_validator("report_run_ref_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not value.startswith("rr_"):
            raise ValueError("report run ref id must use rr_ prefix")
        return value

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("report run timestamps must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "ReportRunRef":
        if self.expires_at <= self.created_at:
            raise ValueError("report run expires_at must be after created_at")
        return self


class QueryContinuationContextRef(PublicContractModel):
    receipt: QueryExecutionReceiptRef
    result_handle: EphemeralResultHandle


ContinuationOperation = Literal["expand_relation", "breakdown", "switch_profile"]
ContinuationCompatibility = Literal["ready", "partial", "unknown"]


class QueryContinuationOption(PublicContractModel):
    transition_ref: PublicIdentifier
    input_refs: list["ArtifactInputRef"] = Field(default_factory=list, max_length=20)
    continuation_contexts: list[QueryContinuationContextRef] = Field(default_factory=list, max_length=20)
    operation: ContinuationOperation
    label: ShortLabel
    source_id: PublicIdentifier
    target_source_id: PublicIdentifier
    structure_model: PublicIdentifier
    report_profile: Optional[PublicIdentifier] = None
    target_object_type: Optional[PublicIdentifier] = None
    target_dimensions: list[FieldName] = Field(default_factory=list, max_length=20)
    parent_key_fields: list[FieldName] = Field(default_factory=list, max_length=6)
    preserved_metrics: list[FieldName] = Field(default_factory=list, max_length=100)
    available_metrics: list[FieldName] = Field(default_factory=list, max_length=300)
    dropped_metrics: list[FieldName] = Field(default_factory=list, max_length=100)
    compatible_parent_count: int = Field(default=0, ge=0)
    total_parent_count: int = Field(default=0, ge=0)
    compatibility: ContinuationCompatibility = "ready"
    limitations: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator(
        "target_dimensions",
        "parent_key_fields",
        "preserved_metrics",
        "available_metrics",
        "dropped_metrics",
    )
    @classmethod
    def validate_option_fields(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class QueryRefinementRequest(PublicContractModel):
    """Continue one governed query from its evidence artifacts.

    The caller selects one opaque, server-planned continuation capability.
    Source, time window, compatible dimensions, parent keys and physical scope
    remain server-owned, so the Host does not reconstruct provider hierarchies.
    """

    input_refs: list["ArtifactInputRef"] = Field(default_factory=list, max_length=20)
    continuation_contexts: list[QueryContinuationContextRef] = Field(default_factory=list, max_length=20)
    transition_ref: PublicIdentifier
    selected_parent_keys: list[QueryEntityKey] = Field(default_factory=list, max_length=100)
    metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    counting_semantics: Optional[CountingSemantics] = None

    @field_validator("input_refs", mode="before")
    @classmethod
    def compact_input_refs(cls, values: Any) -> Any:
        if not isinstance(values, list):
            return values
        compacted = []
        for value in values:
            payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
            if isinstance(payload, dict):
                compacted.append(
                    {
                        "artifact_id": payload.get("artifact_id"),
                        "inspect_token": payload.get("inspect_token"),
                    }
                )
            else:
                compacted.append(payload)
        return compacted

    @model_validator(mode="after")
    def validate_context_family(self) -> "QueryRefinementRequest":
        if bool(self.input_refs) == bool(self.continuation_contexts):
            raise ValueError("provide exactly one of input_refs or continuation_contexts")
        return self

    @field_validator("metrics")
    @classmethod
    def validate_refinement_metrics(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "metrics")


class DataQueryRequest(PublicContractModel):
    query_spec: Optional[QuerySpec] = None
    refinement: Optional[QueryRefinementRequest] = None
    replay_receipt: Optional[QueryExecutionReceiptRef] = None
    preview_limit: int = Field(default=100, ge=1, le=MAX_PREVIEW_ROWS)

    @model_validator(mode="after")
    def validate_query_mode(self) -> "DataQueryRequest":
        modes = sum(
            value is not None
            for value in (self.query_spec, self.refinement, self.replay_receipt)
        )
        if modes != 1:
            raise ValueError("provide exactly one of query_spec, refinement, or replay_receipt")
        return self


class CapabilityContextRequest(PublicContractModel):
    _client_bootstrap_contract_version: str = PrivateAttr(default="ChatGrowingBootstrapContract.v1")
    resource_kinds: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    capability_kinds: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    cursor: Optional[PublicIdentifier] = None
    limit: int = Field(default=50, ge=1, le=100)

    def __init__(self, **data: Any) -> None:
        # Host/runtime compatibility context must not change the frozen public
        # bootstrap Tool input. Accept it only as an internal construction hint.
        client_version = str(data.pop("client_bootstrap_contract_version", "ChatGrowingBootstrapContract.v1") or "").strip()
        if not re.fullmatch(PUBLIC_IDENTIFIER_PATTERN, client_version):
            raise ValueError("client bootstrap contract version is invalid")
        super().__init__(**data)
        self._client_bootstrap_contract_version = client_version

    @property
    def client_bootstrap_contract_version(self) -> str:
        return self._client_bootstrap_contract_version

    @field_validator(
        "resource_kinds",
        "channels",
        "capability_kinds",
    )
    @classmethod
    def validate_context_filters(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class ReportConfig(PublicContractModel):
    primary_window: DateRange

    @model_validator(mode="after")
    def validate_window_size(self) -> "ReportConfig":
        if self.primary_window.end_date - self.primary_window.start_date > timedelta(days=91):
            raise ValueError("ReportConfig primary_window cannot exceed 92 days")
        return self


class ReportGenerateRequest(PublicContractModel):
    report_id: Optional[PublicIdentifier] = None
    report_date: Optional[date] = None
    report_config: Optional[ReportConfig] = None
    # Compact server-extensible envelope. The internal UserDefinedReportSpec
    # validates its nested ``spec`` before any artifact is read.
    composition: Optional[dict[str, Any]] = None
    include_png_long_image: bool = False
    resource_ref: Optional[PublicIdentifier] = None
    app_ref: Optional[PublicIdentifier] = None

    _authorized_account_id: str = PrivateAttr(default="")
    _authorized_app: str = PrivateAttr(default="")
    _authorized_resource_ref: str = PrivateAttr(default="")

    def __init__(self, **data: Any) -> None:
        # Access-layer execution hints never enter the public schema or model
        # dump.  The Remote facade derives them from principal-owned opaque
        # refs after authorizing the request.
        account_id = str(data.pop("_authorized_account_id", "") or "").strip()
        app = str(data.pop("_authorized_app", "") or "").strip()
        resource_ref = str(data.pop("_authorized_resource_ref", "") or "").strip()
        composition = data.get("composition")
        if isinstance(composition, dict) and isinstance(composition.get("input_refs"), list):
            compacted = dict(composition)
            compact_refs = []
            for item in composition["input_refs"]:
                payload = item.model_dump(mode="python") if isinstance(item, BaseModel) else item
                if isinstance(payload, dict):
                    compact_refs.append(
                        {
                            "artifact_id": payload.get("artifact_id"),
                            "inspect_token": payload.get("inspect_token"),
                        }
                    )
                else:
                    compact_refs.append(payload)
            compacted["input_refs"] = compact_refs
            data["composition"] = compacted
            composition = compacted
        if isinstance(composition, dict) and isinstance(composition.get("evidence_set_refs"), list):
            compacted = dict(composition)
            compacted["evidence_set_refs"] = [
                item.model_dump(mode="python") if isinstance(item, BaseModel) else item
                for item in composition["evidence_set_refs"]
            ]
            data["composition"] = compacted
        super().__init__(**data)
        self._authorized_account_id = account_id
        self._authorized_app = app
        self._authorized_resource_ref = resource_ref

    @model_validator(mode="after")
    def validate_report_window(self) -> "ReportGenerateRequest":
        if (
            self.report_config is not None
            and self.report_date is not None
            and self.report_config.primary_window.end_date != self.report_date
        ):
            raise ValueError("report_date must match report_config.primary_window.end_date")
        if self.composition is not None:
            allowed = {
                "mode",
                "primary_window",
                "spec",
                "input_refs",
                "evidence_set_refs",
                "feishu_projection",
            }
            unknown = sorted(set(self.composition) - allowed)
            if unknown:
                raise ValueError(f"composition has unknown fields: {', '.join(unknown)}")
            if self.composition.get("mode", "generate") not in {"preview", "generate"}:
                raise ValueError("composition.mode must be preview or generate")
            composition_window = self.composition.get("primary_window")
            if composition_window is not None:
                try:
                    validated_window = DateRange.model_validate(composition_window)
                except ValidationError as exc:
                    raise ValueError("composition.primary_window must be a valid date range") from exc
                if validated_window.end_date - validated_window.start_date > timedelta(days=91):
                    raise ValueError("composition.primary_window cannot exceed 92 days")
                if self.report_config is not None and validated_window != self.report_config.primary_window:
                    raise ValueError(
                        "composition.primary_window must match report_config.primary_window when both are provided"
                    )
                if self.report_date is not None and validated_window.end_date != self.report_date:
                    raise ValueError(
                        "report_date must match composition.primary_window.end_date when both are provided"
                    )
                self.composition["primary_window"] = validated_window.model_dump(mode="json")
            if not isinstance(self.composition.get("spec"), dict):
                raise ValueError("composition.spec must be a report specification")
            refs = self.composition.get("input_refs")
            evidence_refs = self.composition.get("evidence_set_refs")
            if bool(refs) == bool(evidence_refs):
                raise ValueError(
                    "composition requires exactly one of input_refs or evidence_set_refs"
                )
            if refs:
                if not isinstance(refs, list) or not 1 <= len(refs) <= 20:
                    raise ValueError("composition.input_refs requires 1-20 evidence artifacts")
                for ref in refs:
                    if isinstance(ref, BaseModel):
                        ref = ref.model_dump(mode="python")
                    if not isinstance(ref, dict) or set(ref) != {"artifact_id", "inspect_token"}:
                        raise ValueError("composition input refs require artifact_id and inspect_token")
                    ArtifactInputRef.model_validate(ref)
            else:
                if not isinstance(evidence_refs, list) or not 1 <= len(evidence_refs) <= 20:
                    raise ValueError("composition.evidence_set_refs requires 1-20 published evidence sets")
                for ref in evidence_refs:
                    PublishedEvidenceSetRef.model_validate(ref)
            if self.composition.get("mode", "generate") == "generate" and not evidence_refs:
                raise ValueError(
                    "composition.mode=generate requires published evidence_set_refs; "
                    "legacy input_refs are preview-only"
                )
            if self.include_feishu_projection and not self.include_png_long_image:
                raise ValueError("Feishu projection requires png_long_image generation")
            if composition_window is None and self.report_config is None and self.report_date is None:
                raise ValueError("user-defined reports require composition.primary_window")
        else:
            if self.report_id is None:
                raise ValueError("registered reports require report_id")
            if self.report_config is None and self.report_date is None:
                raise ValueError("registered reports require report_date or report_config")
        return self

    @property
    def generation_mode(self) -> Literal["preview", "generate"]:
        return str((self.composition or {}).get("mode") or "generate")  # type: ignore[return-value]

    @property
    def report_spec(self) -> Optional[dict[str, Any]]:
        value = (self.composition or {}).get("spec")
        return dict(value) if isinstance(value, dict) else None

    @property
    def input_refs(self) -> list["ArtifactInputRef"]:
        return [
            ArtifactInputRef.model_validate(
                item.model_dump(mode="python") if isinstance(item, BaseModel) else item
            )
            for item in (self.composition or {}).get("input_refs") or []
        ]

    @property
    def evidence_set_refs(self) -> list["PublishedEvidenceSetRef"]:
        return [
            PublishedEvidenceSetRef.model_validate(
                item.model_dump(mode="python") if isinstance(item, BaseModel) else item
            )
            for item in (self.composition or {}).get("evidence_set_refs") or []
        ]

    @property
    def include_feishu_projection(self) -> bool:
        return bool((self.composition or {}).get("feishu_projection", False))

    @property
    def resolved_report_id(self) -> str:
        if self.report_id:
            return self.report_id
        payload = json.dumps(self.report_spec or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "user_report_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def resolved_primary_window(self) -> DateRange:
        composition_window = (self.composition or {}).get("primary_window")
        if isinstance(composition_window, dict):
            return DateRange.model_validate(composition_window)
        if self.report_config is not None:
            return self.report_config.primary_window
        assert self.report_date is not None
        return DateRange(
            start_date=self.report_date - timedelta(days=6),
            end_date=self.report_date,
        )

    @property
    def authorized_account_id(self) -> str:
        return self._authorized_account_id

    @property
    def authorized_app(self) -> str:
        return self._authorized_app

    @property
    def authorized_resource_ref(self) -> str:
        return self._authorized_resource_ref


class AggregateFunction(str, Enum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"


class AggregateExpression(PublicContractModel):
    field: FieldName
    function: AggregateFunction
    output_field: FieldName


class FilterOperation(PublicContractModel):
    operation: Literal["filter"] = "filter"
    predicates: list[FilterPredicate] = Field(min_length=1, max_length=60)


class AggregateOperation(PublicContractModel):
    operation: Literal["aggregate"] = "aggregate"
    group_by: list[FieldName] = Field(default_factory=list, max_length=40)
    aggregations: list[AggregateExpression] = Field(min_length=1, max_length=80)


class RatioOperation(PublicContractModel):
    operation: Literal["ratio"] = "ratio"
    numerator_field: FieldName
    denominator_field: FieldName
    output_field: FieldName
    scale: float = Field(default=1.0, gt=0)


class SortOperation(PublicContractModel):
    operation: Literal["sort"] = "sort"
    order_by: list[SortSpec] = Field(min_length=1, max_length=10)


class RankOperation(PublicContractModel):
    operation: Literal["rank"] = "rank"
    order_by: list[SortSpec] = Field(min_length=1, max_length=10)
    partition_by: list[FieldName] = Field(default_factory=list, max_length=20)
    output_field: FieldName = "rank"


class DeltaOperation(PublicContractModel):
    operation: Literal["delta"] = "delta"
    field: FieldName
    order_field: FieldName
    partition_by: list[FieldName] = Field(default_factory=list, max_length=20)
    output_field: FieldName


class PctChangeOperation(PublicContractModel):
    operation: Literal["pct_change"] = "pct_change"
    field: FieldName
    order_field: FieldName
    partition_by: list[FieldName] = Field(default_factory=list, max_length=20)
    periods: int = Field(default=1, ge=1, le=365)
    output_field: FieldName


class PivotOperation(PublicContractModel):
    operation: Literal["pivot"] = "pivot"
    index: list[FieldName] = Field(min_length=1, max_length=20)
    columns: list[FieldName] = Field(min_length=1, max_length=10)
    values: FieldName
    aggregation: AggregateFunction


WorkspaceOperation = Annotated[
    Union[
        FilterOperation,
        AggregateOperation,
        RatioOperation,
        SortOperation,
        RankOperation,
        DeltaOperation,
        PctChangeOperation,
        PivotOperation,
    ],
    Field(discriminator="operation"),
]


class ArtifactInputRef(PublicContractModel):
    """Minimal capability pointer accepted by workspace analysis."""

    artifact_id: PublicIdentifier
    inspect_token: PublicIdentifier


class WorkspaceAnalyzeRequest(PublicContractModel):
    input_refs: list[ArtifactInputRef] = Field(default_factory=list, max_length=20)
    result_handles: list[EphemeralResultHandle] = Field(default_factory=list, max_length=20)
    evidence_set_refs: list[PublishedEvidenceSetRef] = Field(default_factory=list, max_length=20)
    mode: Literal["sql", "operations", "python"]
    sql: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    python: Optional[str] = Field(default=None, min_length=1, max_length=50_000)
    operations: list[WorkspaceOperation] = Field(default_factory=list, max_length=50)
    output_name: Optional[ShortLabel] = None
    output_lifecycle: Literal["session", "published"] = "session"
    preview_limit: int = Field(default=100, ge=1, le=MAX_PREVIEW_ROWS)

    @field_validator("input_refs", mode="before")
    @classmethod
    def compact_input_refs(cls, values: Any) -> Any:
        if not isinstance(values, list):
            return values
        compacted = []
        for value in values:
            payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
            if isinstance(payload, dict):
                compacted.append(
                    {
                        "artifact_id": payload.get("artifact_id"),
                        "inspect_token": payload.get("inspect_token"),
                    }
                )
            else:
                compacted.append(payload)
        return compacted

    @model_validator(mode="after")
    def validate_analysis_candidate(self) -> "WorkspaceAnalyzeRequest":
        input_families = sum(
            bool(value)
            for value in (self.input_refs, self.result_handles, self.evidence_set_refs)
        )
        if input_families != 1:
            raise ValueError(
                "provide exactly one of input_refs, result_handles, or evidence_set_refs"
            )
        if self.mode == "sql":
            if not self.sql:
                raise ValueError("sql mode requires sql")
            if self.operations or self.python:
                raise ValueError("sql mode does not accept operations or python")
        elif self.mode == "operations":
            if self.sql or self.python:
                raise ValueError("operations mode does not accept sql or python")
            if not self.operations:
                raise ValueError("operations mode requires at least one operation")
        else:
            if not self.python:
                raise ValueError("python mode requires python")
            if self.sql or self.operations:
                raise ValueError("python mode does not accept sql or operations")
        return self


class ArtifactRef(PublicContractModel):
    artifact_id: PublicIdentifier
    namespace: PublicIdentifier
    kind: PublicIdentifier
    lineage: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    read_scope: Literal["preview", "full"] = "preview"
    inspect_token: PublicIdentifier
    lifecycle: Literal[
        "run",
        "session",
        "durable",
        "session_evidence",
        "published_analysis",
        "scheduled_snapshot",
    ]
    expires_at: Optional[datetime] = None

    @field_validator("lineage")
    @classmethod
    def validate_lineage(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "lineage")

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "ArtifactRef":
        if self.lifecycle not in {"durable", "published_analysis", "scheduled_snapshot"} and self.expires_at is None:
            raise ValueError("ephemeral artifacts require expires_at")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("artifact expires_at must include timezone information")
        return self


class MetricComparisonContract(PublicContractModel):
    status: Literal["not_applicable", "requires_event_binding", "comparable"]
    target_event_fields: list[FieldName] = Field(default_factory=list, max_length=20)
    event_metric_bindings: dict[str, FieldName] = Field(default_factory=dict)
    denominator_bindings: dict[str, FieldName] = Field(default_factory=dict)
    forbidden_metric_ids: list[FieldName] = Field(default_factory=list, max_length=40)
    notes: list[ShortText] = Field(default_factory=list, max_length=20)


class MetricBinding(PublicContractModel):
    metric_id: FieldName
    formula_ref: PublicIdentifier
    formula: Optional[ShortText] = None
    numerator_field: Optional[Union[FieldName, list[FieldName]]] = None
    denominator_field: Optional[Union[FieldName, list[FieldName]]] = None
    unit: ShortLabel
    cohort_window: Optional[PublicIdentifier] = None
    source_authority: PublicIdentifier
    comparison_contract: Optional[MetricComparisonContract] = None


class ExecutedScope(PublicContractModel):
    date_range: Optional[DateRange] = None
    fact_semantics: Optional[EvidenceFactSemantics] = None
    date_semantics: Optional[EvidenceDateSemantics] = None
    dimensions: list[FieldName] = Field(default_factory=list, max_length=40)
    metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    filters: list[FilterPredicate] = Field(default_factory=list, max_length=60)
    cohort_window: Optional[PublicIdentifier] = None
    order_by: list[SortSpec] = Field(default_factory=list, max_length=10)
    limit: Optional[int] = Field(default=None, ge=1, le=10_000)

    @field_validator("dimensions", "metrics")
    @classmethod
    def validate_unique_fields(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)

    @model_validator(mode="after")
    def validate_fact_date_semantics(self) -> "ExecutedScope":
        validate_fact_date_semantics_pair(
            self.fact_semantics,
            self.date_semantics,
            allow_mixed=True,
        )
        return self


class DataWindow(PublicContractModel):
    requested: Optional[DateRange] = None
    observed: Optional[DateRange] = None
    as_of_date: Optional[date] = None
    timezone: Optional[ShortLabel] = None


class CoverageState(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"
    MAPPING_INCOMPLETE = "mapping_incomplete"
    UNKNOWN = "unknown"


class Coverage(PublicContractModel):
    state: CoverageState = CoverageState.UNKNOWN
    observed_sources: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    missing_sources: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    mapping_status: Optional[ShortLabel] = None
    notes: list[ShortText] = Field(default_factory=list, max_length=50)

    @field_validator("observed_sources", "missing_sources")
    @classmethod
    def validate_source_ids(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class FreshnessState(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    UNKNOWN = "unknown"


class Freshness(PublicContractModel):
    state: FreshnessState = FreshnessState.UNKNOWN
    basis: Literal["source_runtime", "returned_evidence", "not_evaluated"] = "not_evaluated"
    latest_available_date: Optional[date] = None
    as_of_date: Optional[date] = None
    lag_days: Optional[int] = Field(default=None, ge=0)
    timezone: Optional[ShortLabel] = None


class AdsToolError(PublicContractModel):
    code: PublicIdentifier
    message: ShortText
    retryable: bool = False
    repairable: bool = False
    invalid_fields: list[FieldName] = Field(default_factory=list, max_length=100)
    available_fields: list[FieldName] = Field(default_factory=list, max_length=500)
    available_filters: list[FieldName] = Field(default_factory=list, max_length=200)
    candidate_sources: list[PublicIdentifier] = Field(default_factory=list, max_length=100)
    repair_hints: list[ShortText] = Field(default_factory=list, max_length=50)
    trace_id: PublicIdentifier

    @field_validator("invalid_fields", "available_fields", "available_filters", "candidate_sources")
    @classmethod
    def validate_unique_values(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class EvidenceStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"
    ERROR = "error"


class AdsEvidenceEnvelope(PublicContractModel):
    status: EvidenceStatus
    tool_name: PublicToolName
    coverage: Coverage = Field(default_factory=Coverage)
    freshness: Freshness = Field(default_factory=Freshness)
    limitations: list[ShortText] = Field(default_factory=list, max_length=100)
    error: Optional[AdsToolError] = None
    trace_id: PublicIdentifier

    @model_validator(mode="after")
    def validate_status_contract(self) -> "AdsEvidenceEnvelope":
        if self.status == EvidenceStatus.ERROR:
            if self.error is None:
                raise ValueError("error status requires a typed error")
            if self.error.trace_id != self.trace_id:
                raise ValueError("error trace_id must match envelope trace_id")
        elif self.error is not None:
            raise ValueError("non-error status must not include an error")
        if self.status in {EvidenceStatus.PARTIAL, EvidenceStatus.EMPTY} and not self.limitations:
            raise ValueError(f"{self.status.value} status requires an observation limitation")
        _reject_private_references(self.model_dump(mode="json"))
        return self


class CatalogSourceCard(PublicContractModel):
    source_id: PublicIdentifier
    display_name: Optional[ShortLabel] = None
    source_kind: CatalogSourceKind
    authority: PublicIdentifier
    fact_semantics: Optional[FactSemantics] = None
    date_semantics: Optional[DateSemantics] = None
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    grain: list[FieldName] = Field(default_factory=list, max_length=40)
    supported_dimensions: list[FieldName] = Field(default_factory=list, max_length=200)
    supported_metrics: list[FieldName] = Field(default_factory=list, max_length=300)
    supported_filters: list[FieldName] = Field(default_factory=list, max_length=200)
    capabilities: list[CatalogCapability] = Field(default_factory=list, max_length=11)
    matched_capabilities: list[CatalogCapability] = Field(default_factory=list, max_length=11)
    missing_capabilities: list[CatalogCapability] = Field(default_factory=list, max_length=11)
    matched_dimensions: list[FieldName] = Field(default_factory=list, max_length=40)
    matched_metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    missing_dimensions: list[FieldName] = Field(default_factory=list, max_length=40)
    missing_metrics: list[FieldName] = Field(default_factory=list, max_length=40)
    known_gaps: list[ShortText] = Field(default_factory=list, max_length=50)
    structure_models: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    report_profiles: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    continuation_operations: list[ContinuationOperation] = Field(default_factory=list, max_length=3)
    contract_refs: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness: Optional[Freshness] = None

    @model_validator(mode="after")
    def validate_fact_date_semantics(self) -> "CatalogSourceCard":
        validate_fact_date_semantics_pair(self.fact_semantics, self.date_semantics)
        return self


class FieldDescriptor(PublicContractModel):
    field_id: FieldName
    aliases: list[ShortLabel] = Field(default_factory=list, max_length=50)
    data_type: Optional[PublicIdentifier] = None
    description: Optional[ShortText] = None
    required: bool = False


class MetricDescriptor(PublicContractModel):
    metric_id: FieldName
    aliases: list[ShortLabel] = Field(default_factory=list, max_length=50)
    description: Optional[ShortText] = None
    formula_ref: Optional[PublicIdentifier] = None
    formula: Optional[ShortText] = None
    numerator_field: Optional[Union[FieldName, list[FieldName]]] = None
    denominator_field: Optional[Union[FieldName, list[FieldName]]] = None
    unit: ShortLabel
    cohort_window: Optional[PublicIdentifier] = None
    source_authority: PublicIdentifier
    comparison_contract: Optional[MetricComparisonContract] = None
    definition_status: Optional[Literal["published"]] = None
    definition_effective_from: Optional[date] = None
    definition_effective_to: Optional[date] = None
    registry_revision: Optional[PublicIdentifier] = None
    definition_digest: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    definition_source_refs: list[ShortText] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_definition_evidence(self) -> "MetricDescriptor":
        evidence = {
            "definition_effective_from": self.definition_effective_from,
            "registry_revision": self.registry_revision,
            "definition_digest": self.definition_digest,
            "definition_source_refs": self.definition_source_refs,
        }
        if self.definition_status == "published":
            missing = [name for name, value in evidence.items() if value is None or value == []]
            if missing:
                raise ValueError(
                    "published metric definition missing evidence: " + ", ".join(missing)
                )
            if (
                self.definition_effective_to is not None
                and self.definition_effective_to < self.definition_effective_from
            ):
                raise ValueError("metric definition effective_to must not precede effective_from")
        elif any(value is not None and value != [] for value in evidence.values()) or self.definition_effective_to is not None:
            raise ValueError("metric definition evidence requires published status")
        return self


class FreshnessPolicy(PublicContractModel):
    max_lag_days: Optional[int] = Field(default=None, ge=0)
    stale_policy: PublicIdentifier
    timezone: Optional[ShortLabel] = None


class CatalogSourceDescription(PublicContractModel):
    source_id: PublicIdentifier
    display_name: Optional[ShortLabel] = None
    source_kind: CatalogSourceKind
    authority: PublicIdentifier
    fact_semantics: Optional[FactSemantics] = None
    date_semantics: Optional[DateSemantics] = None
    grain: list[FieldName] = Field(default_factory=list, max_length=40)
    primary_key: list[FieldName] = Field(default_factory=list, max_length=40)
    join_semantics: list[ShortText] = Field(default_factory=list, max_length=50)
    dimensions: list[FieldDescriptor] = Field(default_factory=list, max_length=200)
    metrics: list[MetricDescriptor] = Field(default_factory=list, max_length=300)
    filters: list[FieldDescriptor] = Field(default_factory=list, max_length=200)
    supported_date_windows: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    supported_cohort_windows: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    freshness_policy: Optional[FreshnessPolicy] = None
    mapping_semantics: list[ShortText] = Field(default_factory=list, max_length=50)
    known_gaps: list[ShortText] = Field(default_factory=list, max_length=50)
    cannot_derive_conditions: list[ShortText] = Field(default_factory=list, max_length=50)
    capabilities: list[CatalogCapability] = Field(default_factory=list, max_length=11)
    structure_models: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    report_profiles: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    continuation_operations: list[ContinuationOperation] = Field(default_factory=list, max_length=3)
    contract_refs: list[PublicIdentifier] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_fact_date_semantics(self) -> "CatalogSourceDescription":
        validate_fact_date_semantics_pair(self.fact_semantics, self.date_semantics)
        return self


class DataHealthRecord(PublicContractModel):
    source_id: PublicIdentifier
    resource_ref: Optional[PublicIdentifier] = None
    fact_semantics: Optional[FactSemantics] = None
    date_semantics: Optional[DateSemantics] = None
    channel: Optional[PublicIdentifier] = None
    app: Optional[PublicIdentifier] = None
    coverage_state: CoverageState
    latest_available_date: Optional[date] = None
    observed_date_range: Optional[DateRange] = None
    as_of_date: Optional[date] = None
    timezone: Optional[ShortLabel] = None
    lag_days: Optional[int] = Field(default=None, ge=0)
    sync_status: Optional[PublicIdentifier] = None
    mapping_status: Optional[ShortLabel] = None
    limitations: list[ShortText] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_fact_date_semantics(self) -> "DataHealthRecord":
        validate_fact_date_semantics_pair(self.fact_semantics, self.date_semantics)
        return self


class KnowledgeHypothesisCard(PublicContractModel):
    hypothesis_id: PublicIdentifier
    title: ShortLabel
    statement: ShortText
    applicable_signals: list[ShortLabel] = Field(default_factory=list, max_length=30)
    evidence_kinds: list[PublicIdentifier] = Field(default_factory=list, max_length=10)
    next_probe_questions: list[ShortText] = Field(default_factory=list, max_length=20)
    action_boundary: ShortText


class KnowledgePackCard(PublicContractModel):
    pack_id: PublicIdentifier
    title: ShortLabel
    version: PublicIdentifier
    summary: ShortText
    topics: list[ShortLabel] = Field(default_factory=list, max_length=40)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    source_quality: KnowledgeSourceQuality
    source_refs: list[ShortText] = Field(default_factory=list, max_length=30)
    reviewed_at: date
    matched_terms: list[ShortLabel] = Field(default_factory=list, max_length=80)
    match_score: float = Field(ge=0.0, le=1.0)
    hypotheses: list[KnowledgeHypothesisCard] = Field(default_factory=list, max_length=50)
    resource_uri: ShortText


class ContextScopeCard(PublicContractModel):
    organization_id: Optional[PublicIdentifier] = None
    apps: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    accounts: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    campaigns: list[PublicIdentifier] = Field(default_factory=list, max_length=50)
    countries: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    verticals: list[ShortLabel] = Field(default_factory=list, max_length=20)

    @field_validator("apps", "channels", "accounts", "campaigns", "countries", "verticals")
    @classmethod
    def validate_unique_scope_values(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class ContextRuleCard(PublicContractModel):
    rule_id: PublicIdentifier
    title: ShortLabel
    rule_type: ContextRuleType
    guidance: ShortText
    applies_to: list[ShortLabel] = Field(default_factory=list, max_length=30)

    @field_validator("applies_to")
    @classmethod
    def validate_applies_to(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "applies_to")


class UserPreferenceCard(PublicContractModel):
    preference_id: PublicIdentifier
    title: ShortLabel
    preference_type: Literal["answer_style", "default_window", "granularity", "format"]
    guidance: ShortText
    source_refs: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("source_refs")
    @classmethod
    def validate_unique_source_refs(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "source_refs")


class CandidatePolicyCard(PublicContractModel):
    allowed_candidate_types: list[CandidateType] = Field(default_factory=list, max_length=5)
    required_gates: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    forbidden_direct_promotions: list[ShortText] = Field(default_factory=list, max_length=20)

    @field_validator("allowed_candidate_types", "required_gates")
    @classmethod
    def validate_unique_candidate_policy(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class ContextCard(PublicContractModel):
    context_id: PublicIdentifier
    title: ShortLabel
    context_kind: ContextKind
    version: PublicIdentifier
    summary: ShortText
    scope: ContextScopeCard
    source_quality: ContextSourceQuality
    source_refs: list[ShortText] = Field(default_factory=list, max_length=30)
    reviewed_at: date
    matched_terms: list[ShortLabel] = Field(default_factory=list, max_length=80)
    match_score: float = Field(ge=0.0, le=1.0)
    included_context_kinds: list[ContextKind] = Field(default_factory=list, max_length=3)
    rules: list[ContextRuleCard] = Field(default_factory=list, max_length=30)
    user_preferences: list[UserPreferenceCard] = Field(default_factory=list, max_length=30)
    candidate_policy: Optional[CandidatePolicyCard] = None
    hard_boundaries: list[ShortText] = Field(default_factory=list, max_length=20)
    resource_uri: ShortText

    @field_validator("source_refs", "matched_terms", "included_context_kinds", "hard_boundaries")
    @classmethod
    def validate_unique_context_lists(cls, values: list[str], info: Any) -> list[str]:
        return _unique_non_empty(values, info.field_name)


class ReportSectionSummary(PublicContractModel):
    section_id: PublicIdentifier
    title: ShortLabel
    section_type: PublicIdentifier
    present: bool
    metric_refs: list[FieldName] = Field(default_factory=list, max_length=100)

    @field_validator("metric_refs")
    @classmethod
    def validate_metric_refs(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "metric_refs")


class CatalogSearchResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_catalog_search"] = "ads_catalog_search"
    source_cards: list[CatalogSourceCard] = Field(default_factory=list, max_length=50)
    unresolved_vocabulary: list[ShortLabel] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_payload(self) -> "CatalogSearchResponse":
        _validate_payload_presence(self.status, bool(self.source_cards), "source_cards")
        if self.status == EvidenceStatus.SUCCESS and self.unresolved_vocabulary:
            raise ValueError("unresolved vocabulary requires partial or empty status")
        return self


class CatalogDescribeResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_catalog_describe"] = "ads_catalog_describe"
    source: Optional[CatalogSourceDescription] = None
    unresolved_vocabulary: list[ShortLabel] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_payload(self) -> "CatalogDescribeResponse":
        _validate_payload_presence(self.status, self.source is not None, "source")
        if self.status == EvidenceStatus.SUCCESS and self.unresolved_vocabulary:
            raise ValueError("unresolved vocabulary requires partial or empty status")
        return self


class DataHealthResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_data_health"] = "ads_data_health"
    records: list[DataHealthRecord] = Field(default_factory=list, max_length=100)
    record_count: int = Field(default=0, ge=0)
    is_truncated: bool = False
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=100)
    result_delivery: Literal["complete", "preview_only", "cache_unavailable"] = "complete"

    @model_validator(mode="after")
    def validate_payload(self) -> "DataHealthResponse":
        _validate_payload_presence(self.status, bool(self.records), "records")
        if self.record_count < len(self.records):
            raise ValueError("record_count must cover every health record")
        expected_truncation = self.record_count > len(self.records)
        if self.is_truncated != expected_truncation:
            raise ValueError("is_truncated must match record_count and records")
        if self.is_truncated:
            if self.result_delivery == "complete":
                self.result_delivery = "preview_only" if self.artifact_refs else "cache_unavailable"
            elif self.result_delivery == "preview_only" and not self.artifact_refs:
                raise ValueError("preview_only health delivery requires a governed result reference")
        elif self.result_delivery != "complete":
            raise ValueError("complete health evidence requires complete result_delivery")
        if self.status in {EvidenceStatus.SUCCESS, EvidenceStatus.PARTIAL}:
            if self.record_count == 0:
                raise ValueError(f"{self.status.value} status requires health records")
        elif self.record_count or self.artifact_refs:
            raise ValueError(f"{self.status.value} status must not include health evidence")
        return self


class KnowledgeSearchResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_knowledge_search"] = "ads_knowledge_search"
    packs: list[KnowledgePackCard] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_payload(self) -> "KnowledgeSearchResponse":
        _validate_payload_presence(self.status, bool(self.packs), "packs")
        return self


class ContextLookupResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_context_lookup"] = "ads_context_lookup"
    context_cards: list[ContextCard] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_payload(self) -> "ContextLookupResponse":
        _validate_payload_presence(self.status, bool(self.context_cards), "context_cards")
        return self


class ReportGenerateResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_report_generate"] = "ads_report_generate"
    report_id: Optional[PublicIdentifier] = None
    report_run_id: Optional[PublicIdentifier] = None
    report_run_ref: Optional[ReportRunRef] = None
    report_date: Optional[date] = None
    primary_window: Optional[DateRange] = None
    audience: Optional[PublicIdentifier] = None
    channel_scope: Optional[PublicIdentifier] = None
    sections: list[ReportSectionSummary] = Field(default_factory=list, max_length=30)
    data_quality_refs: list[ShortText] = Field(default_factory=list, max_length=100)
    decision_ref_count: int = Field(default=0, ge=0)
    followup_anchor_count: int = Field(default=0, ge=0)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=3)
    resource_ref: Optional[PublicIdentifier] = None

    @model_validator(mode="after")
    def validate_report_payload(self) -> "ReportGenerateResponse":
        has_metadata = all(
            (
                self.report_id,
                self.report_run_id,
                self.report_date,
                self.primary_window,
                self.audience,
                self.channel_scope,
            )
        )
        if self.status in {EvidenceStatus.SUCCESS, EvidenceStatus.PARTIAL}:
            if not has_metadata or not self.sections or not 1 <= len(self.artifact_refs) <= 3:
                raise ValueError(
                    f"{self.status.value} report generation requires metadata, sections and artifact refs"
                )
            if len(self.artifact_refs) == 2 and self.artifact_refs[1].kind not in {
                "png_long_image",
                "rendered_asset",
            }:
                raise ValueError("second report artifact must be a PNG rendering surface")
            if len(self.artifact_refs) == 3 and (
                self.artifact_refs[1].kind not in {"png_long_image", "rendered_asset"}
                or self.artifact_refs[2].kind != "feishu_projection_plan"
            ):
                raise ValueError("third report artifact must be a Feishu projection plan")
        elif any(
            (
                has_metadata,
                self.sections,
                self.data_quality_refs,
                self.decision_ref_count,
                self.followup_anchor_count,
                self.artifact_refs,
            )
        ):
            raise ValueError(f"{self.status.value} status must not include report payload")
        return self


def _validate_payload_presence(status: EvidenceStatus, has_payload: bool, field_name: str) -> None:
    if status in {EvidenceStatus.SUCCESS, EvidenceStatus.PARTIAL} and not has_payload:
        raise ValueError(f"{status.value} status requires {field_name}")
    if status in {EvidenceStatus.EMPTY, EvidenceStatus.ERROR} and has_payload:
        raise ValueError(f"{status.value} status must not include {field_name}")


class RowEvidenceEnvelope(AdsEvidenceEnvelope):
    source_id: Optional[PublicIdentifier] = None
    executed_scope: Optional[ExecutedScope] = None
    data_window: Optional[DataWindow] = None
    grain: list[FieldName] = Field(default_factory=list, max_length=40)
    # A failed query did not observe a row set.  Keep that state distinct from
    # a successfully executed query that observed zero rows.
    row_count: Optional[int] = Field(default=None, ge=0)
    rows_preview: list[dict[str, JsonValue]] = Field(default_factory=list, max_length=MAX_PREVIEW_ROWS)
    is_truncated: bool = False
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=20)
    result_delivery: Literal["complete", "preview_only", "cache_unavailable"] = "complete"
    continuation_status: Literal["ready", "unavailable", "not_applicable"] = "not_applicable"
    evidence_publish_status: Literal["ready", "unavailable", "not_requested"] = "not_requested"
    metric_bindings: list[MetricBinding] = Field(default_factory=list, max_length=100)
    resource_outcomes: list["ResourceOutcome"] = Field(default_factory=list, max_length=100)
    conservation: Optional["QueryConservation"] = None
    counting_semantics: Optional[CountingSemantics] = None
    aggregation_owner: Optional[PublicIdentifier] = None
    aggregation_semantics: Optional[
        Literal["provider_exact_row", "sum_of_daily_unique_rows", "sum", "ratio_of_sums"]
    ] = None
    range_deduplicated: Optional[bool] = None
    counting_semantics_disclosure: Optional[ShortText] = None

    @model_validator(mode="after")
    def validate_row_evidence(self) -> "RowEvidenceEnvelope":
        if self.status == EvidenceStatus.ERROR:
            if self.row_count is not None:
                raise ValueError("error status must not claim an observed row_count")
            if self.rows_preview or self.artifact_refs or self.is_truncated:
                raise ValueError("error status must not include row evidence")
            if self.result_delivery != "complete":
                raise ValueError("error status must not claim result delivery")
            return self
        if self.row_count is None:
            # Empty and incomplete-without-rows observations remain real zero
            # row sets; only errors retain null.
            self.row_count = 0
        if self.row_count < len(self.rows_preview):
            raise ValueError("row_count must cover every preview row")
        expected_truncation = self.row_count > len(self.rows_preview)
        if self.is_truncated != expected_truncation:
            raise ValueError("is_truncated must match row_count and rows_preview")
        if self.is_truncated:
            if self.result_delivery == "complete":
                self.result_delivery = "preview_only" if self.artifact_refs else "cache_unavailable"
            elif self.result_delivery == "preview_only" and not (
                self.artifact_refs or getattr(self, "result_handles", ())
            ):
                raise ValueError("preview_only delivery requires a governed result reference")
        elif self.result_delivery != "complete":
            raise ValueError("complete row evidence requires complete result_delivery")
        governed_result_refs = bool(self.artifact_refs) or bool(
            getattr(self, "result_handles", ())
        )
        governed_receipt_refs = bool(getattr(self, "query_receipts", ()))
        if self.continuation_status == "ready" and not (
            governed_result_refs and (governed_receipt_refs or self.artifact_refs)
        ):
            raise ValueError("ready continuation requires a governed result reference")
        if self.status != EvidenceStatus.ERROR and self.source_id is None:
            raise ValueError(f"{self.status.value} status requires source_id")
        if self.status in {EvidenceStatus.SUCCESS, EvidenceStatus.PARTIAL}:
            if self.row_count == 0:
                incomplete_without_rows = (
                    self.status == EvidenceStatus.PARTIAL
                    and self.coverage.state == CoverageState.PARTIAL
                    and bool(self.limitations)
                )
                if not incomplete_without_rows:
                    raise ValueError(f"{self.status.value} status requires evidence rows")
            if not self.rows_preview and not self.artifact_refs:
                if self.row_count:
                    raise ValueError("evidence rows require a preview or artifact")
        elif self.row_count or self.rows_preview or self.artifact_refs:
            raise ValueError(f"{self.status.value} status must not include row evidence")
        return self


class DataQueryResponse(RowEvidenceEnvelope):
    tool_name: Literal["ads_data_query"] = "ads_data_query"
    resource_count: int = Field(default=0, ge=0)
    next_resource_cursor: Optional[PublicIdentifier] = None
    continuation_options: list[QueryContinuationOption] = Field(default_factory=list, max_length=200)
    query_receipts: list[QueryExecutionReceiptRef] = Field(default_factory=list, max_length=100)
    result_handles: list[EphemeralResultHandle] = Field(default_factory=list, max_length=100)
    replay_provenance: Optional[QueryReplayProvenance] = None


class ResourceOutcome(PublicContractModel):
    resource_ref: PublicIdentifier
    status: Literal["ready", "empty", "partial", "stale", "denied", "unavailable"]
    artifact_ref: Optional[ArtifactRef] = None
    limitation: Optional[ShortText] = None


class QueryConservation(PublicContractModel):
    physical_account_count: int = Field(default=0, ge=0)
    projected_app_row_count: int = Field(default=0, ge=0)
    account_level_metrics_conserved: bool = True


class AuthorizationResourceCard(PublicContractModel):
    resource_ref: PublicIdentifier
    resource_kind: PublicIdentifier
    display_name: ShortLabel
    channel: Optional[PublicIdentifier] = None
    currency: Optional[ShortLabel] = None
    currency_status: Literal["missing", "ready", "conflict"] = "missing"
    timezone_name: Optional[ShortLabel] = None
    capability_kinds: list[PublicIdentifier] = Field(default_factory=list, max_length=30)
    query_filters: list[FilterPredicate] = Field(default_factory=list, max_length=10)
    status: Literal["ready", "partial", "unavailable"] = "ready"


class PromotionTargetFacetCard(PublicContractModel):
    facet_ref: PublicIdentifier
    kind: PublicIdentifier
    display_name: ShortLabel
    mapping_status: ShortLabel
    query_facet_only: Literal[True] = True


class CapabilityCard(PublicContractModel):
    capability: PublicIdentifier
    status: Literal["available", "unavailable"] = "available"
    source_id: Optional[PublicIdentifier] = None
    execution_mode: Optional[PublicIdentifier] = None
    contract_ref: Optional[ShortText] = None
    contract_digest: Optional[PublicIdentifier] = None
    unavailable_reason: Optional[ShortText] = None


class DestinationCard(PublicContractModel):
    destination_ref: PublicIdentifier
    display_name: ShortLabel
    destination_type: PublicIdentifier
    status: Literal["ready", "partial", "unavailable"] = "ready"


GuidanceKind = Literal["discovery", "analysis", "continuation", "configuration"]
GuidanceCapability = Literal[
    "capability_context",
    "catalog",
    "health",
    "query",
    "workspace",
    "knowledge",
    "organization_context",
    "report",
]
ProtectedGuidanceBoundary = Literal[
    "permission",
    "metric_semantics",
    "source_authority",
    "approval",
]


class GuidanceStepCard(PublicContractModel):
    step_id: PublicIdentifier
    capability: PublicIdentifier
    objective: ShortText
    optional: bool = False


class ServerGuidanceCard(PublicContractModel):
    guidance_id: PublicIdentifier
    kind: PublicIdentifier
    version: PublicIdentifier
    title: ShortLabel
    summary: ShortText
    required_capabilities: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    channels: list[PublicIdentifier] = Field(default_factory=list, max_length=20)
    steps: list[GuidanceStepCard] = Field(min_length=1, max_length=20)
    protected_boundaries: list[PublicIdentifier] = Field(min_length=4, max_length=4)
    execution_boundary: Literal["read_only"] = "read_only"
    source_refs: list[ShortText] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_governance_boundaries(self) -> "ServerGuidanceCard":
        allowed_kinds = {"discovery", "analysis", "continuation", "configuration", "reporting"}
        allowed_capabilities = {
            "capability_context",
            "catalog",
            "health",
            "query",
            "workspace",
            "knowledge",
            "organization_context",
            "report",
        }
        if self.kind not in allowed_kinds:
            raise ValueError("unsupported server guidance kind")
        if any(step.capability not in allowed_capabilities for step in self.steps):
            raise ValueError("unsupported server guidance capability")
        if set(self.protected_boundaries) != {
            "permission",
            "metric_semantics",
            "source_authority",
            "approval",
        }:
            raise ValueError("server guidance must protect permission, metric, source, and approval")
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("server guidance step ids must be unique")
        if any(
            not re.fullmatch(r"(?:chatgrowing-guidance|ads-catalog|ads-knowledge|ads-contract)://[A-Za-z0-9._~/-]+", source_ref)
            for source_ref in self.source_refs
        ):
            raise ValueError("server guidance source refs must use governed public URIs")
        return self


class CapabilityContextResponse(AdsEvidenceEnvelope):
    tool_name: Literal["ads_capability_context"] = "ads_capability_context"
    principal_context_version: Optional[PublicIdentifier] = None
    generated_at: Optional[datetime] = None
    authorization_resources: list[AuthorizationResourceCard] = Field(default_factory=list, max_length=100)
    promotion_target_facets: list[PromotionTargetFacetCard] = Field(default_factory=list, max_length=100)
    capabilities: list[CapabilityCard] = Field(default_factory=list, max_length=500)
    destinations: list[DestinationCard] = Field(default_factory=list, max_length=100)
    bootstrap_contract_version: Optional[Literal["ChatGrowingBootstrapContract.v1"]] = None
    server_contract_version: Optional[Literal["AdsCapabilityMcpPublicSchema.v3"]] = None
    server_guidance_revision: Optional[str] = None
    server_guidance: list[ServerGuidanceCard] = Field(default_factory=list, max_length=50)
    compatibility_state: Optional[
        Literal["compatible", "upgrade_recommended", "upgrade_required"]
    ] = None
    routine_refresh_action: Optional[Literal["new_task", "reconnect", "plugin_upgrade"]] = None
    next_cursor: Optional[PublicIdentifier] = None

    @model_validator(mode="after")
    def validate_context_payload(self) -> "CapabilityContextResponse":
        if self.server_guidance_revision is not None and not re.fullmatch(
            r"[a-f0-9]{64}", self.server_guidance_revision
        ):
            raise ValueError("server guidance revision must be a SHA-256 digest")
        if self.status in {EvidenceStatus.SUCCESS, EvidenceStatus.PARTIAL}:
            if self.principal_context_version is None or self.generated_at is None:
                raise ValueError("capability context requires version and generated_at")
            if (
                self.bootstrap_contract_version is None
                or self.server_contract_version is None
                or self.server_guidance_revision is None
                or self.compatibility_state is None
                or self.routine_refresh_action is None
            ):
                raise ValueError("capability context requires bootstrap, server, guidance, and compatibility metadata")
        return self


class WorkspaceAnalyzeResponse(RowEvidenceEnvelope):
    tool_name: Literal["ads_workspace_analyze"] = "ads_workspace_analyze"
    evidence_set_refs: list[PublishedEvidenceSetRef] = Field(default_factory=list, max_length=20)
