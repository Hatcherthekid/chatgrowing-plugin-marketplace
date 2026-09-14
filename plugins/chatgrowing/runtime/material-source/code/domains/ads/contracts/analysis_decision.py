"""Host-neutral contracts for ads configuration, classification, and decisions.

The contracts intentionally stop before platform writes or strategy algorithms.
They preserve source provenance, explicit cannot-judge reasons, and the
different grains used by standard ads and TikTok Smart+ materials.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any, Final, Mapping


ADS_DELIVERY_CONFIGURATION_PROFILE_TYPE: Final = "ads_delivery_configuration_profile"
ADS_DELIVERY_CONFIGURATION_PROFILE_VERSION: Final = "v1"
ADS_CLASSIFICATION_RESULT_TYPE: Final = "ads_classification_result"
ADS_CLASSIFICATION_RESULT_VERSION: Final = "v1"
ADS_OBJECT_DIAGNOSIS_TYPE: Final = "ads_object_diagnosis"
ADS_OBJECT_DIAGNOSIS_VERSION: Final = "v1"
ADS_ACTION_CANDIDATE_TYPE: Final = "ads_action_candidate"
ADS_ACTION_CANDIDATE_VERSION: Final = "v1"

CHANNELS: Final = frozenset({"meta", "tiktok", "google_ads"})
SUBJECT_TYPES: Final = frozenset(
    {"account", "campaign", "adgroup", "ad", "smart_plus_ad", "material", "asset"}
)
# Product names remain as compatibility metadata. Shared routing consumes the
# semantic control dimensions below instead of branching on these values.
DELIVERY_MODES: Final = frozenset(
    {"standard", "automated", "smart_plus", "advantage_plus", "unknown"}
)
SEMANTIC_SUBJECT_ROLES: Final = frozenset(
    {
        "account",
        "delivery_container",
        "control_group",
        "delivery_ad",
        "creative_container",
        "creative_unit",
        "asset",
        "unknown",
    }
)
CONTROL_DOMAINS: Final = frozenset(
    {"budget", "bid", "audience", "placement", "creative"}
)
CONTROL_MODES: Final = frozenset(
    {"operator", "platform", "mixed", "not_applicable", "unknown"}
)
CONTROL_SCOPES: Final = frozenset(
    {
        "account",
        "campaign",
        "adgroup",
        "ad",
        "creative_container",
        "creative_unit",
        "asset",
        "not_applicable",
        "unknown",
    }
)
CAPABILITY_NAMES: Final = frozenset(
    {
        "budget",
        "bid",
        "audience",
        "placement",
        "creative",
        "review",
        "attribution",
        "hierarchy",
        "temporal",
    }
)
CAPABILITY_READINESS_STATES: Final = frozenset({"ready", "partial", "blocked"})
CONTROL_LAYERS: Final = frozenset(
    {"campaign", "adgroup", "automated", "not_applicable", "unknown"}
)
BID_STRATEGY_FAMILIES: Final = frozenset(
    {"lowest_cost", "cost_cap", "target", "automated", "manual", "unknown"}
)
AUDIENCE_CONTROL_MODES: Final = frozenset(
    {"manual", "broad", "automated", "mixed", "unknown"}
)
CREATIVE_ASSEMBLY_MODES: Final = frozenset(
    {
        "single_ad_single_material",
        "ad_multi_material",
        "dynamic_assembly",
        "unknown",
    }
)
CREATIVE_OBSERVATION_GRAINS: Final = frozenset(
    {"ad", "material", "shared_asset_envelope", "container_only", "unavailable"}
)
ATTRIBUTION_GRAINS: Final = frozenset(
    {"account", "campaign", "adgroup", "ad", "none"}
)
CONFIG_COMPLETENESS_STATES: Final = frozenset(
    {"ready", "partial", "missing", "stale"}
)
ANALYSIS_DOMAINS: Final = frozenset(
    {
        "business_performance",
        "budget",
        "bid",
        "audience",
        "placement",
        "creative",
        "review",
        "structure",
        "decay",
    }
)
ANALYSIS_LANES: Final = frozenset(
    {
        "freshness",
        "attribution",
        "config_hierarchy",
        "sample_maturity",
        "capacity_delivery",
        "economics",
        "quality",
        "temporal_decay",
        "cause_diagnosis",
    }
)
EVIDENCE_GATE_STATES: Final = frozenset({"ready", "partial", "blocked"})
CAUSE_CONFIDENCE_STATES: Final = frozenset({"blocked", "low", "medium", "high"})
LIFECYCLE_STATES: Final = frozenset(
    {"unknown", "testing", "new", "learning", "mature", "decaying", "recovering"}
)
SAMPLE_STATES: Final = frozenset(
    {"unknown", "sufficient", "weak", "blocked", "immature"}
)
STANDARD_STRUCTURE_TYPES: Final = frozenset({"1:1:1", "1:1:n", "1:n:1", "1:n:m"})
SMART_PLUS_STRUCTURE_TYPES: Final = frozenset({"smart_plus_ad_multi_material"})
BUSINESS_STATE_VALUES: Final = frozenset(
    {
        "healthy",
        "good",
        "acceptable",
        "stable",
        "weak",
        "poor",
        "bad",
        "failed",
        "cannot_judge",
        "not_evaluated",
    }
)
_BLOCKED_BUSINESS_STATES: Final = frozenset({"cannot_judge", "not_evaluated"})
_FRESHNESS_DEPENDENT_ANALYSIS_LANES: Final = frozenset(
    {
        "freshness",
        "capacity_delivery",
        "economics",
        "quality",
        "temporal_decay",
        "cause_diagnosis",
    }
)
_SAMPLE_DEPENDENT_ANALYSIS_LANES: Final = frozenset(
    {"sample_maturity", "economics", "quality", "temporal_decay", "cause_diagnosis"}
)
ACTION_DOMAINS: Final = frozenset(
    {
        "evidence_repair",
        "review_status",
        "observe",
        "budget",
        "bid",
        "creative",
        "audience",
        "placement",
        "structure",
        "copy_rebuild",
        "campaign_replace",
    }
)
ACTION_DOMAIN_ALLOWED_LAYERS: Final = {
    "evidence_repair": SUBJECT_TYPES,
    "review_status": SUBJECT_TYPES,
    "observe": SUBJECT_TYPES,
    "budget": frozenset({"account", "campaign", "adgroup"}),
    "bid": frozenset({"campaign", "adgroup"}),
    "creative": frozenset({"ad", "smart_plus_ad", "material", "asset"}),
    "audience": frozenset({"campaign", "adgroup"}),
    "placement": frozenset({"campaign", "adgroup"}),
    "structure": frozenset({"campaign", "adgroup"}),
    "copy_rebuild": frozenset({"campaign", "adgroup", "ad", "smart_plus_ad"}),
    "campaign_replace": frozenset({"campaign"}),
}
_BLOCKED_GATE_ACTION_DOMAINS: Final = frozenset(
    {"evidence_repair", "review_status", "observe"}
)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name}_required")
    return text


def _normalized_tuple(values: Any, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str) or isinstance(values, Mapping):
        raise ValueError(f"{field_name}_must_be_sequence")
    try:
        items = list(values)
    except TypeError as exc:
        raise ValueError(f"{field_name}_must_be_sequence") from exc
    normalized: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field_name}_must_contain_strings")
        text = item.strip()
        if not text:
            raise ValueError(f"{field_name}_must_not_contain_empty")
        if text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _known(value: Any, allowed: frozenset[str], field_name: str) -> str:
    text = _required_text(value, field_name).lower()
    if text not in allowed:
        raise ValueError(f"unknown_{field_name}:{text}")
    return text


def _iso_date(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name}_must_be_iso_date") from exc
    return text


def _artifact_constant(value: Any, expected: str, field_name: str) -> str:
    text = _required_text(value, field_name)
    if text != expected:
        raise ValueError(f"{field_name}_must_be:{expected}")
    return expected


@dataclass(frozen=True)
class ControlDimension:
    """One independently governed control axis shared by all ad platforms."""

    domain: str
    control_mode: str
    control_layer: str
    evidence_status: str
    strategy_family: str = "unknown"
    constraints: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    source_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", _known(self.domain, CONTROL_DOMAINS, "control_dimension_domain"))
        object.__setattr__(self, "control_mode", _known(self.control_mode, CONTROL_MODES, "control_dimension_mode"))
        object.__setattr__(self, "control_layer", _known(self.control_layer, CONTROL_SCOPES, "control_dimension_layer"))
        object.__setattr__(self, "evidence_status", _known(self.evidence_status, CAPABILITY_READINESS_STATES, "control_dimension_evidence_status"))
        object.__setattr__(self, "strategy_family", str(self.strategy_family or "unknown").strip().lower() or "unknown")
        object.__setattr__(self, "constraints", _normalized_tuple(self.constraints, "control_dimension_constraints"))
        object.__setattr__(self, "missing_evidence", _normalized_tuple(self.missing_evidence, "control_dimension_missing_evidence"))
        object.__setattr__(self, "source_refs", _normalized_tuple(self.source_refs, "control_dimension_source_refs"))
        object.__setattr__(self, "limitations", _normalized_tuple(self.limitations, "control_dimension_limitations"))
        if self.evidence_status == "ready" and not self.source_refs:
            raise ValueError("ready_control_dimension_requires_source_refs")
        if self.evidence_status == "ready" and self.missing_evidence:
            raise ValueError("ready_control_dimension_cannot_have_missing_evidence")
        if self.evidence_status == "ready" and (
            self.control_mode == "unknown" or self.control_layer == "unknown"
        ):
            raise ValueError("ready_control_dimension_requires_known_control")
        if self.evidence_status == "partial" and not (
            self.missing_evidence or self.limitations
        ):
            raise ValueError("partial_control_dimension_requires_explanation")
        if self.evidence_status == "blocked" and not self.missing_evidence:
            raise ValueError("blocked_control_dimension_requires_missing_evidence")


@dataclass(frozen=True)
class CapabilityReadiness:
    """Evidence readiness for a single analysis capability, not a global proxy."""

    capability: str
    status: str
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    source_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", _known(self.capability, CAPABILITY_NAMES, "capability_readiness_name"))
        object.__setattr__(self, "status", _known(self.status, CAPABILITY_READINESS_STATES, "capability_readiness_status"))
        object.__setattr__(self, "missing_evidence", _normalized_tuple(self.missing_evidence, "capability_readiness_missing_evidence"))
        object.__setattr__(self, "source_refs", _normalized_tuple(self.source_refs, "capability_readiness_source_refs"))
        object.__setattr__(self, "limitations", _normalized_tuple(self.limitations, "capability_readiness_limitations"))
        if self.status == "ready" and not self.source_refs:
            raise ValueError("ready_capability_requires_source_refs")
        if self.status == "ready" and self.missing_evidence:
            raise ValueError("ready_capability_cannot_have_missing_evidence")
        if self.status == "partial" and not (
            self.missing_evidence or self.limitations
        ):
            raise ValueError("partial_capability_requires_explanation")
        if self.status == "blocked" and not self.missing_evidence:
            raise ValueError("blocked_capability_requires_missing_evidence")


@dataclass(frozen=True)
class DeliveryConfigurationProfile:
    profile_id: str
    channel: str
    subject_type: str
    subject_id: str
    as_of_date: str
    semantic_subject_role: str = "unknown"
    native_subject_type: str = ""
    native_product_type: str = ""
    delivery_mode: str = "unknown"
    budget_control_layer: str = "unknown"
    bid_control_layer: str = "unknown"
    bid_strategy_family: str = "unknown"
    optimization_point_key: str = ""
    audience_control_mode: str = "unknown"
    creative_assembly_mode: str = "unknown"
    creative_observation_grain: str = "unavailable"
    review_subject_grains: tuple[str, ...] = field(default_factory=tuple)
    structure_type: str = "unknown"
    attribution_grain: str = "none"
    config_completeness: str = "missing"
    config_snapshot_date: str = ""
    config_snapshot_semantics: str = ""
    config_match_status: str = ""
    control_dimensions: tuple[ControlDimension, ...] = field(default_factory=tuple)
    capability_readiness: tuple[CapabilityReadiness, ...] = field(default_factory=tuple)
    source_refs: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    artifact_type: str = ADS_DELIVERY_CONFIGURATION_PROFILE_TYPE
    artifact_version: str = ADS_DELIVERY_CONFIGURATION_PROFILE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _artifact_constant(self.artifact_type, ADS_DELIVERY_CONFIGURATION_PROFILE_TYPE, "configuration_profile_artifact_type"))
        object.__setattr__(self, "artifact_version", _artifact_constant(self.artifact_version, ADS_DELIVERY_CONFIGURATION_PROFILE_VERSION, "configuration_profile_artifact_version"))
        object.__setattr__(self, "profile_id", _required_text(self.profile_id, "configuration_profile_id"))
        object.__setattr__(self, "channel", _known(self.channel, CHANNELS, "configuration_profile_channel"))
        object.__setattr__(self, "subject_type", _known(self.subject_type, SUBJECT_TYPES, "configuration_profile_subject_type"))
        object.__setattr__(self, "subject_id", _required_text(self.subject_id, "configuration_profile_subject_id"))
        object.__setattr__(self, "as_of_date", _iso_date(self.as_of_date, "configuration_profile_as_of_date"))
        object.__setattr__(self, "semantic_subject_role", _known(self.semantic_subject_role, SEMANTIC_SUBJECT_ROLES, "configuration_profile_semantic_subject_role"))
        object.__setattr__(self, "native_subject_type", str(self.native_subject_type or self.subject_type).strip())
        object.__setattr__(self, "native_product_type", str(self.native_product_type or "unknown").strip().lower() or "unknown")
        object.__setattr__(self, "delivery_mode", _known(self.delivery_mode, DELIVERY_MODES, "configuration_profile_delivery_mode"))
        object.__setattr__(self, "budget_control_layer", _known(self.budget_control_layer, CONTROL_LAYERS, "configuration_profile_budget_control_layer"))
        object.__setattr__(self, "bid_control_layer", _known(self.bid_control_layer, CONTROL_LAYERS, "configuration_profile_bid_control_layer"))
        object.__setattr__(self, "bid_strategy_family", _known(self.bid_strategy_family, BID_STRATEGY_FAMILIES, "configuration_profile_bid_strategy_family"))
        object.__setattr__(self, "audience_control_mode", _known(self.audience_control_mode, AUDIENCE_CONTROL_MODES, "configuration_profile_audience_control_mode"))
        object.__setattr__(self, "creative_assembly_mode", _known(self.creative_assembly_mode, CREATIVE_ASSEMBLY_MODES, "configuration_profile_creative_assembly_mode"))
        object.__setattr__(self, "creative_observation_grain", _known(self.creative_observation_grain, CREATIVE_OBSERVATION_GRAINS, "configuration_profile_creative_observation_grain"))
        object.__setattr__(self, "attribution_grain", _known(self.attribution_grain, ATTRIBUTION_GRAINS, "configuration_profile_attribution_grain"))
        object.__setattr__(self, "config_completeness", _known(self.config_completeness, CONFIG_COMPLETENESS_STATES, "configuration_profile_config_completeness"))
        review_grains = _normalized_tuple(self.review_subject_grains, "configuration_profile_review_subject_grains")
        unknown_review_grains = sorted(set(review_grains) - SUBJECT_TYPES)
        if unknown_review_grains:
            raise ValueError(
                "configuration_profile_unknown_review_subject_grains:"
                + ",".join(unknown_review_grains)
            )
        object.__setattr__(self, "review_subject_grains", review_grains)
        object.__setattr__(self, "source_refs", _normalized_tuple(self.source_refs, "configuration_profile_source_refs"))
        object.__setattr__(self, "limitations", _normalized_tuple(self.limitations, "configuration_profile_limitations"))
        object.__setattr__(self, "structure_type", str(self.structure_type or "unknown").strip() or "unknown")
        if self.structure_type != "unknown":
            allowed_structures = (
                SMART_PLUS_STRUCTURE_TYPES
                if self.delivery_mode == "smart_plus"
                else STANDARD_STRUCTURE_TYPES
            )
            if self.structure_type not in allowed_structures:
                raise ValueError(
                    f"unknown_configuration_profile_structure_type:{self.structure_type}"
                )
        object.__setattr__(self, "optimization_point_key", str(self.optimization_point_key or "").strip())
        snapshot_date = str(self.config_snapshot_date or "").strip()
        if snapshot_date:
            snapshot_date = _iso_date(snapshot_date, "configuration_profile_config_snapshot_date")
        object.__setattr__(self, "config_snapshot_date", snapshot_date)
        object.__setattr__(self, "config_snapshot_semantics", str(self.config_snapshot_semantics or "").strip().lower())
        object.__setattr__(self, "config_match_status", str(self.config_match_status or "").strip().lower())
        dimensions = tuple(self.control_dimensions)
        if any(not isinstance(item, ControlDimension) for item in dimensions):
            raise ValueError("configuration_profile_control_dimensions_must_be_typed")
        dimension_domains = [item.domain for item in dimensions]
        if len(dimension_domains) != len(set(dimension_domains)):
            raise ValueError("configuration_profile_duplicate_control_dimension")
        object.__setattr__(self, "control_dimensions", dimensions)
        readiness = tuple(self.capability_readiness)
        if any(not isinstance(item, CapabilityReadiness) for item in readiness):
            raise ValueError("configuration_profile_capability_readiness_must_be_typed")
        readiness_names = [item.capability for item in readiness]
        if len(readiness_names) != len(set(readiness_names)):
            raise ValueError("configuration_profile_duplicate_capability_readiness")
        if dimensions and set(dimension_domains) != CONTROL_DOMAINS:
            missing = sorted(CONTROL_DOMAINS - set(dimension_domains))
            raise ValueError(
                "configuration_profile_incomplete_control_dimensions:" + ",".join(missing)
            )
        if readiness and set(readiness_names) != CAPABILITY_NAMES:
            missing = sorted(CAPABILITY_NAMES - set(readiness_names))
            raise ValueError(
                "configuration_profile_incomplete_capability_readiness:" + ",".join(missing)
            )
        object.__setattr__(self, "capability_readiness", readiness)

        if self.subject_type == "material" and self.attribution_grain != "none":
            raise ValueError("configuration_profile_material_cannot_claim_attribution")
        if self.config_completeness == "ready":
            if not self.source_refs:
                raise ValueError("configuration_profile_ready_requires_source_refs")
            if not dimensions:
                raise ValueError("configuration_profile_ready_requires_control_dimensions")
            if not readiness:
                raise ValueError("configuration_profile_ready_requires_capability_readiness")

        budget_dimension = self.control_for("budget")
        if budget_dimension is not None:
            if budget_dimension.control_layer in CONTROL_LAYERS:
                if self.budget_control_layer != budget_dimension.control_layer:
                    raise ValueError("configuration_profile_budget_layer_conflict")
            elif self.budget_control_layer != "unknown":
                raise ValueError("configuration_profile_budget_layer_conflict")
        bid_dimension = self.control_for("bid")
        if bid_dimension is not None:
            if bid_dimension.control_layer in CONTROL_LAYERS:
                if self.bid_control_layer != bid_dimension.control_layer:
                    raise ValueError("configuration_profile_bid_layer_conflict")
            elif self.bid_control_layer != "unknown":
                raise ValueError("configuration_profile_bid_layer_conflict")
            if self.bid_strategy_family != bid_dimension.strategy_family:
                raise ValueError("configuration_profile_bid_strategy_family_conflict")
        audience_dimension = self.control_for("audience")
        if audience_dimension is not None and self.audience_control_mode != "unknown":
            expected_audience_mode = {
                "manual": "operator",
                "automated": "platform",
                "mixed": "mixed",
                "broad": "mixed",
            }[self.audience_control_mode]
            if audience_dimension.control_mode != expected_audience_mode:
                raise ValueError("configuration_profile_audience_mode_conflict")
            if audience_dimension.strategy_family != self.audience_control_mode:
                raise ValueError("configuration_profile_audience_strategy_family_conflict")
        creative_dimension = self.control_for("creative")
        if creative_dimension is not None and self.creative_assembly_mode != "unknown":
            expected_creative_mode = {
                "single_ad_single_material": "operator",
                "ad_multi_material": "platform",
                "dynamic_assembly": "platform",
            }[self.creative_assembly_mode]
            if creative_dimension.control_mode != expected_creative_mode:
                raise ValueError("configuration_profile_creative_mode_conflict")
            if creative_dimension.strategy_family != self.creative_assembly_mode:
                raise ValueError("configuration_profile_creative_strategy_family_conflict")

        readiness_by_name = {item.capability: item for item in readiness}
        readiness_rank = {"blocked": 0, "partial": 1, "ready": 2}
        for dimension in dimensions:
            capability = readiness_by_name.get(dimension.domain)
            if capability is not None and readiness_rank[capability.status] > readiness_rank[dimension.evidence_status]:
                raise ValueError(
                    f"configuration_profile_{dimension.domain}_capability_exceeds_dimension_evidence"
                )

        review_readiness = readiness_by_name.get("review")
        if review_readiness is not None and review_readiness.status == "ready":
            if not self.review_subject_grains:
                raise ValueError("configuration_profile_ready_review_requires_subject_grains")
        attribution_readiness = readiness_by_name.get("attribution")
        if attribution_readiness is not None and attribution_readiness.status == "ready":
            if self.attribution_grain == "none":
                raise ValueError("configuration_profile_ready_attribution_requires_grain")
            grain_rank = {"account": 0, "campaign": 1, "adgroup": 2, "ad": 3}
            subject_rank = grain_rank.get(self.subject_type)
            attribution_rank = grain_rank.get(self.attribution_grain)
            if (
                subject_rank is None
                or attribution_rank is None
                or attribution_rank < subject_rank
            ):
                raise ValueError(
                    "configuration_profile_ready_attribution_grain_incompatible_with_subject"
                )
        hierarchy_readiness = readiness_by_name.get("hierarchy")
        if hierarchy_readiness is not None and hierarchy_readiness.status == "ready":
            if self.structure_type.lower() == "unknown":
                raise ValueError("configuration_profile_ready_hierarchy_requires_structure")
        temporal_readiness = readiness_by_name.get("temporal")
        if temporal_readiness is not None and temporal_readiness.status == "ready":
            if not self.config_snapshot_date or not self.config_snapshot_semantics:
                raise ValueError("configuration_profile_ready_temporal_requires_snapshot_provenance")
            if self.config_snapshot_semantics != "actual_fetch_date":
                raise ValueError("configuration_profile_ready_temporal_requires_actual_fetch_date")
            if self.config_match_status not in {
                "exact_snapshot",
                "next_day_snapshot",
            }:
                raise ValueError("configuration_profile_ready_temporal_requires_safe_match_status")
            expected_snapshot_date = date.fromisoformat(self.as_of_date)
            if self.config_match_status == "next_day_snapshot":
                expected_snapshot_date += timedelta(days=1)
            if self.config_snapshot_date != expected_snapshot_date.isoformat():
                raise ValueError("configuration_profile_ready_temporal_snapshot_date_mismatch")

    def control_for(self, domain: str) -> ControlDimension | None:
        normalized = str(domain or "").strip().lower()
        return next((item for item in self.control_dimensions if item.domain == normalized), None)

    def readiness_for(self, capability: str) -> CapabilityReadiness | None:
        normalized = str(capability or "").strip().lower()
        return next((item for item in self.capability_readiness if item.capability == normalized), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassificationResult:
    classification_id: str
    subject_type: str
    subject_id: str
    analysis_domain: str
    configuration_profile_ref: str
    lifecycle_state: str
    sample_state: str
    primary_judgment_layer: str
    freshness_status: str = "blocked"
    freshness_evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    sample_evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    diagnostic_layers: tuple[str, ...] = field(default_factory=tuple)
    creative_judgment_grain: str = "unavailable"
    review_judgment_grains: tuple[str, ...] = field(default_factory=tuple)
    allowed_analysis_lanes: tuple[str, ...] = field(default_factory=tuple)
    blocked_analysis_lanes: tuple[str, ...] = field(default_factory=tuple)
    cannot_judge_reasons: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    artifact_type: str = ADS_CLASSIFICATION_RESULT_TYPE
    artifact_version: str = ADS_CLASSIFICATION_RESULT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _artifact_constant(self.artifact_type, ADS_CLASSIFICATION_RESULT_TYPE, "classification_artifact_type"))
        object.__setattr__(self, "artifact_version", _artifact_constant(self.artifact_version, ADS_CLASSIFICATION_RESULT_VERSION, "classification_artifact_version"))
        object.__setattr__(self, "classification_id", _required_text(self.classification_id, "classification_id"))
        object.__setattr__(self, "subject_type", _known(self.subject_type, SUBJECT_TYPES, "classification_subject_type"))
        object.__setattr__(self, "subject_id", _required_text(self.subject_id, "classification_subject_id"))
        object.__setattr__(self, "analysis_domain", _known(self.analysis_domain, ANALYSIS_DOMAINS, "classification_analysis_domain"))
        object.__setattr__(self, "configuration_profile_ref", _required_text(self.configuration_profile_ref, "classification_configuration_profile_ref"))
        object.__setattr__(self, "lifecycle_state", _known(self.lifecycle_state, LIFECYCLE_STATES, "classification_lifecycle_state"))
        object.__setattr__(self, "sample_state", _known(self.sample_state, SAMPLE_STATES, "classification_sample_state"))
        object.__setattr__(self, "freshness_status", _known(self.freshness_status, EVIDENCE_GATE_STATES, "classification_freshness_status"))
        freshness_refs = _normalized_tuple(
            self.freshness_evidence_refs,
            "classification_freshness_evidence_refs",
        )
        sample_refs = _normalized_tuple(
            self.sample_evidence_refs,
            "classification_sample_evidence_refs",
        )
        if self.freshness_status == "ready" and not freshness_refs:
            raise ValueError("classification_ready_freshness_requires_evidence_refs")
        if self.sample_state == "sufficient" and not sample_refs:
            raise ValueError("classification_sufficient_sample_requires_evidence_refs")
        object.__setattr__(self, "freshness_evidence_refs", freshness_refs)
        object.__setattr__(self, "sample_evidence_refs", sample_refs)
        primary = str(self.primary_judgment_layer or "unknown").strip().lower() or "unknown"
        if primary != "unknown" and primary not in SUBJECT_TYPES:
            raise ValueError(f"unknown_classification_primary_judgment_layer:{primary}")
        object.__setattr__(self, "primary_judgment_layer", primary)
        diagnostic_layers = _normalized_tuple(self.diagnostic_layers, "classification_diagnostic_layers")
        unknown_diagnostic_layers = sorted(set(diagnostic_layers) - SUBJECT_TYPES)
        if unknown_diagnostic_layers:
            raise ValueError(
                "classification_unknown_diagnostic_layers:"
                + ",".join(unknown_diagnostic_layers)
            )
        object.__setattr__(self, "diagnostic_layers", diagnostic_layers)
        if primary in diagnostic_layers:
            raise ValueError("classification_primary_layer_cannot_be_diagnostic_layer")
        object.__setattr__(self, "creative_judgment_grain", _known(self.creative_judgment_grain, CREATIVE_OBSERVATION_GRAINS, "classification_creative_judgment_grain"))
        review_grains = _normalized_tuple(self.review_judgment_grains, "classification_review_judgment_grains")
        if set(review_grains) - SUBJECT_TYPES:
            raise ValueError("classification_unknown_review_judgment_grains")
        object.__setattr__(self, "review_judgment_grains", review_grains)
        allowed = _normalized_tuple(self.allowed_analysis_lanes, "classification_allowed_analysis_lanes")
        blocked = _normalized_tuple(self.blocked_analysis_lanes, "classification_blocked_analysis_lanes")
        if set(allowed) - ANALYSIS_LANES or set(blocked) - ANALYSIS_LANES:
            raise ValueError("classification_unknown_analysis_lane")
        if set(allowed) & set(blocked):
            raise ValueError("classification_analysis_lane_cannot_be_allowed_and_blocked")
        if not allowed and not blocked:
            raise ValueError("classification_requires_routed_analysis_lanes")
        object.__setattr__(self, "allowed_analysis_lanes", allowed)
        object.__setattr__(self, "blocked_analysis_lanes", blocked)
        cannot_judge = _normalized_tuple(self.cannot_judge_reasons, "classification_cannot_judge_reasons")
        if primary == "unknown" and not cannot_judge:
            raise ValueError("classification_unknown_primary_layer_requires_cannot_judge")
        if blocked and not cannot_judge:
            raise ValueError("classification_blocked_lanes_require_cannot_judge")
        object.__setattr__(self, "cannot_judge_reasons", cannot_judge)
        evidence_refs = _normalized_tuple(self.evidence_refs, "classification_evidence_refs")
        if allowed and not evidence_refs:
            raise ValueError("classification_allowed_lanes_require_evidence_refs")
        if not set(freshness_refs).issubset(evidence_refs):
            raise ValueError("classification_freshness_refs_must_be_in_evidence_refs")
        if not set(sample_refs).issubset(evidence_refs):
            raise ValueError("classification_sample_refs_must_be_in_evidence_refs")
        if set(allowed) & _FRESHNESS_DEPENDENT_ANALYSIS_LANES:
            if self.freshness_status != "ready":
                raise ValueError("classification_freshness_dependent_lane_requires_ready_gate")
        if set(allowed) & _SAMPLE_DEPENDENT_ANALYSIS_LANES:
            if self.sample_state != "sufficient":
                raise ValueError("classification_sample_dependent_lane_requires_sufficient_sample")
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceGateResult:
    status: str
    limitations: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _known(self.status, EVIDENCE_GATE_STATES, "evidence_gate_status"))
        object.__setattr__(self, "limitations", _normalized_tuple(self.limitations, "evidence_gate_limitations"))
        object.__setattr__(self, "missing_evidence", _normalized_tuple(self.missing_evidence, "evidence_gate_missing_evidence"))
        object.__setattr__(self, "evidence_refs", _normalized_tuple(self.evidence_refs, "evidence_gate_evidence_refs"))
        if self.status == "blocked" and not self.missing_evidence:
            raise ValueError("blocked_evidence_gate_requires_missing_evidence")
        if self.status == "ready" and not self.evidence_refs:
            raise ValueError("ready_evidence_gate_requires_evidence_refs")
        if self.status == "ready" and self.missing_evidence:
            raise ValueError("ready_evidence_gate_cannot_have_missing_evidence")
        if self.status == "partial" and not (
            self.missing_evidence or self.limitations
        ):
            raise ValueError("partial_evidence_gate_requires_explanation")


@dataclass(frozen=True)
class CauseCandidate:
    cause_type: str
    confidence: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    counter_evidence: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    explanatory_scope: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "cause_type", _required_text(self.cause_type, "cause_candidate_type"))
        object.__setattr__(self, "confidence", _known(self.confidence, CAUSE_CONFIDENCE_STATES, "cause_candidate_confidence"))
        object.__setattr__(self, "supporting_evidence", _normalized_tuple(self.supporting_evidence, "cause_candidate_supporting_evidence"))
        object.__setattr__(self, "counter_evidence", _normalized_tuple(self.counter_evidence, "cause_candidate_counter_evidence"))
        object.__setattr__(self, "missing_evidence", _normalized_tuple(self.missing_evidence, "cause_candidate_missing_evidence"))
        object.__setattr__(self, "explanatory_scope", str(self.explanatory_scope or "").strip())
        if self.confidence == "blocked" and not self.missing_evidence:
            raise ValueError("blocked_cause_candidate_requires_missing_evidence")
        if self.confidence == "blocked" and self.supporting_evidence:
            raise ValueError("blocked_cause_candidate_cannot_have_supporting_evidence")
        if self.confidence == "low" and not (
            self.supporting_evidence or self.missing_evidence
        ):
            raise ValueError("low_cause_candidate_requires_supporting_or_missing_evidence")
        if self.confidence in {"medium", "high"} and not self.supporting_evidence:
            raise ValueError("supported_cause_candidate_requires_supporting_evidence")


@dataclass(frozen=True)
class ObjectDiagnosis:
    diagnosis_id: str
    subject_type: str
    subject_id: str
    evidence_gate: EvidenceGateResult
    capacity_state: str
    economics_state: str
    quality_state: str
    primary_conflict: str = ""
    temporal_observation: str = "not_evaluated"
    urgency: str = "not_evaluated"
    cause_candidates: tuple[CauseCandidate, ...] = field(default_factory=tuple)
    primary_cause: str = ""
    limitations: tuple[str, ...] = field(default_factory=tuple)
    recheck_conditions: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    artifact_type: str = ADS_OBJECT_DIAGNOSIS_TYPE
    artifact_version: str = ADS_OBJECT_DIAGNOSIS_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _artifact_constant(self.artifact_type, ADS_OBJECT_DIAGNOSIS_TYPE, "object_diagnosis_artifact_type"))
        object.__setattr__(self, "artifact_version", _artifact_constant(self.artifact_version, ADS_OBJECT_DIAGNOSIS_VERSION, "object_diagnosis_artifact_version"))
        object.__setattr__(self, "diagnosis_id", _required_text(self.diagnosis_id, "object_diagnosis_id"))
        object.__setattr__(self, "subject_type", _known(self.subject_type, SUBJECT_TYPES, "object_diagnosis_subject_type"))
        object.__setattr__(self, "subject_id", _required_text(self.subject_id, "object_diagnosis_subject_id"))
        if not isinstance(self.evidence_gate, EvidenceGateResult):
            raise ValueError("object_diagnosis_evidence_gate_required")
        for field_name in ("capacity_state", "economics_state", "quality_state"):
            object.__setattr__(
                self,
                field_name,
                _known(
                    getattr(self, field_name),
                    BUSINESS_STATE_VALUES,
                    f"object_diagnosis_{field_name}",
                ),
            )
        candidates = tuple(self.cause_candidates)
        if any(not isinstance(item, CauseCandidate) for item in candidates):
            raise ValueError("object_diagnosis_cause_candidates_must_be_typed")
        object.__setattr__(self, "cause_candidates", candidates)
        cause_types = [item.cause_type for item in candidates]
        if len(cause_types) != len(set(cause_types)):
            raise ValueError("object_diagnosis_duplicate_cause_type")
        object.__setattr__(self, "primary_conflict", str(self.primary_conflict or "").strip())
        object.__setattr__(self, "primary_cause", str(self.primary_cause or "").strip())
        object.__setattr__(self, "temporal_observation", _required_text(self.temporal_observation, "object_diagnosis_temporal_observation"))
        object.__setattr__(self, "urgency", _required_text(self.urgency, "object_diagnosis_urgency"))
        object.__setattr__(self, "limitations", _normalized_tuple(self.limitations, "object_diagnosis_limitations"))
        object.__setattr__(self, "recheck_conditions", _normalized_tuple(self.recheck_conditions, "object_diagnosis_recheck_conditions"))
        object.__setattr__(self, "evidence_refs", _normalized_tuple(self.evidence_refs, "object_diagnosis_evidence_refs"))
        if self.evidence_gate.status == "blocked" and (self.primary_conflict or self.primary_cause):
            raise ValueError("blocked_object_diagnosis_cannot_claim_primary_conclusion")
        if self.evidence_gate.status == "blocked" and any(
            getattr(self, field_name) not in _BLOCKED_BUSINESS_STATES
            for field_name in ("capacity_state", "economics_state", "quality_state")
        ):
            raise ValueError("blocked_object_diagnosis_requires_cannot_judge_business_states")
        if self.evidence_gate.status == "blocked" and any(
            item.confidence != "blocked" for item in candidates
        ):
            raise ValueError("blocked_object_diagnosis_cannot_claim_supported_cause")
        if self.primary_cause and self.primary_cause not in {item.cause_type for item in candidates}:
            raise ValueError("object_diagnosis_primary_cause_not_in_candidates")
        if self.primary_cause:
            primary_candidate = next(
                item for item in candidates if item.cause_type == self.primary_cause
            )
            if primary_candidate.confidence == "blocked":
                raise ValueError("object_diagnosis_primary_cause_cannot_be_blocked")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionCandidateContract:
    candidate_id: str
    diagnosis_ref: str
    subject_type: str
    subject_id: str
    action_domain: str
    primary_action: str
    decision_layer: str
    diagnosis_gate_status: str
    preconditions: tuple[str, ...]
    supporting_evidence_refs: tuple[str, ...]
    risk: str
    stop_condition: str
    recheck_condition: str
    secondary_actions: tuple[str, ...] = field(default_factory=tuple)
    conditional_actions: tuple[str, ...] = field(default_factory=tuple)
    prohibited_actions: tuple[str, ...] = field(default_factory=tuple)
    requires_human_review: bool = True
    platform_write_reachable: bool = False
    execution_status: str = "not_executed"
    artifact_type: str = ADS_ACTION_CANDIDATE_TYPE
    artifact_version: str = ADS_ACTION_CANDIDATE_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _artifact_constant(self.artifact_type, ADS_ACTION_CANDIDATE_TYPE, "action_candidate_artifact_type"))
        object.__setattr__(self, "artifact_version", _artifact_constant(self.artifact_version, ADS_ACTION_CANDIDATE_VERSION, "action_candidate_artifact_version"))
        object.__setattr__(self, "candidate_id", _required_text(self.candidate_id, "action_candidate_id"))
        object.__setattr__(self, "diagnosis_ref", _required_text(self.diagnosis_ref, "action_candidate_diagnosis_ref"))
        object.__setattr__(self, "subject_type", _known(self.subject_type, SUBJECT_TYPES, "action_candidate_subject_type"))
        object.__setattr__(self, "subject_id", _required_text(self.subject_id, "action_candidate_subject_id"))
        object.__setattr__(self, "action_domain", _known(self.action_domain, ACTION_DOMAINS, "action_candidate_domain"))
        object.__setattr__(self, "primary_action", _required_text(self.primary_action, "action_candidate_primary_action"))
        layer = str(self.decision_layer or "unknown").strip().lower() or "unknown"
        if layer not in SUBJECT_TYPES:
            raise ValueError(f"unknown_action_candidate_decision_layer:{layer}")
        object.__setattr__(self, "decision_layer", layer)
        object.__setattr__(
            self,
            "diagnosis_gate_status",
            _known(
                self.diagnosis_gate_status,
                EVIDENCE_GATE_STATES,
                "action_candidate_diagnosis_gate_status",
            ),
        )
        for field_name in (
            "preconditions",
            "supporting_evidence_refs",
            "secondary_actions",
            "conditional_actions",
            "prohibited_actions",
        ):
            object.__setattr__(self, field_name, _normalized_tuple(getattr(self, field_name), f"action_candidate_{field_name}"))
        object.__setattr__(self, "risk", _required_text(self.risk, "action_candidate_risk"))
        object.__setattr__(self, "stop_condition", _required_text(self.stop_condition, "action_candidate_stop_condition"))
        object.__setattr__(self, "recheck_condition", _required_text(self.recheck_condition, "action_candidate_recheck_condition"))
        if self.requires_human_review is not True:
            raise ValueError("action_candidate_requires_human_review")
        if self.platform_write_reachable is not False:
            raise ValueError("action_candidate_platform_write_must_be_unreachable")
        if self.execution_status != "not_executed":
            raise ValueError("action_candidate_execution_status_must_be_not_executed")
        if not self.supporting_evidence_refs:
            raise ValueError("action_candidate_supporting_evidence_required")
        if not self.preconditions:
            raise ValueError("action_candidate_preconditions_required")
        if layer not in ACTION_DOMAIN_ALLOWED_LAYERS[self.action_domain]:
            raise ValueError(
                f"action_candidate_domain_layer_incompatible:{self.action_domain}:{layer}"
            )
        if (
            self.diagnosis_gate_status == "blocked"
            and self.action_domain not in _BLOCKED_GATE_ACTION_DOMAINS
        ):
            raise ValueError("blocked_diagnosis_cannot_create_strong_action_candidate")
        prohibited = {item.casefold() for item in self.prohibited_actions}
        if self.primary_action.casefold() in prohibited:
            raise ValueError("action_candidate_primary_action_cannot_be_prohibited")
        if {item.casefold() for item in self.secondary_actions} & prohibited:
            raise ValueError("action_candidate_secondary_action_cannot_be_prohibited")
        if {item.casefold() for item in self.conditional_actions} & prohibited:
            raise ValueError("action_candidate_conditional_action_cannot_be_prohibited")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate_against_diagnosis(self, diagnosis: ObjectDiagnosis) -> None:
        if not isinstance(diagnosis, ObjectDiagnosis):
            raise ValueError("action_candidate_typed_diagnosis_required")
        if self.diagnosis_ref != diagnosis.diagnosis_id:
            raise ValueError("action_candidate_diagnosis_ref_mismatch")
        if (self.subject_type, self.subject_id) != (
            diagnosis.subject_type,
            diagnosis.subject_id,
        ):
            raise ValueError("action_candidate_diagnosis_subject_mismatch")
        if self.diagnosis_gate_status != diagnosis.evidence_gate.status:
            raise ValueError("action_candidate_diagnosis_gate_status_mismatch")


__all__ = [
    "ACTION_DOMAIN_ALLOWED_LAYERS",
    "ACTION_DOMAINS",
    "ANALYSIS_DOMAINS",
    "ANALYSIS_LANES",
    "CAPABILITY_NAMES",
    "CAPABILITY_READINESS_STATES",
    "CONTROL_DOMAINS",
    "CONTROL_MODES",
    "CONTROL_SCOPES",
    "LIFECYCLE_STATES",
    "SAMPLE_STATES",
    "SMART_PLUS_STRUCTURE_TYPES",
    "STANDARD_STRUCTURE_TYPES",
    "ActionCandidateContract",
    "CapabilityReadiness",
    "CauseCandidate",
    "ClassificationResult",
    "ControlDimension",
    "DeliveryConfigurationProfile",
    "EvidenceGateResult",
    "ObjectDiagnosis",
]
