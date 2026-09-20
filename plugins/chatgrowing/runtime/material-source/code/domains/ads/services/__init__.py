"""
广告域服务模块。

包根只做 lazy export。不要在 import `domains.ads.services` 时 eager-load
审批、Meta storage、Google、Feishu、console 等全部服务。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_MODULES = (
    "approval_errors",
    "approval_service",
    "ads_data_refresh_service",
    "ads_table_result_builder",
    "console",
    "ads_provider_capability_profile",
    "ads_learning_loop",
    "ads_learning_loop_review",
    "ads_semantic_layer",
    "ads_clarification_lifecycle",
    "ads_data_product_router",
    "ads_business_quality_reviewer",
    "ads_governed_sql_sandbox",
    "ads_domain_reasoning_kernel",
    "ads_tree_runtime_adapter",
    "ads_hypothesis_runtime",
    "ads_diagnosis_card_builder",
    "ads_meta_scope_guard",
    "ads_attribution_scope_reviewer",
    "ads_delivery_target_dictionary",
    "ads_report_preview_service",
    "ads_artifact_recall_service",
    "execution_candidate_service",
    "execution_precheck_service",
    "execution_row_service",
    "execution_write_service",
    "meta_state_service",
    "meta_data_source_adapter",
    "meta_execution_adapter",
    "passkey_provider",
    "workspace_unified_service",
    "google_uac_text_service",
    "google_uac_creative_media_service",
    "google_asset_weekly_source_artifact_service",
    "google_uac_codex_llm",
    "workspace_snapshot_service",
    "ads_semantic_fact_view_service",
    "tiktok_config_query_service",
    "tiktok_config_change_event_service",
    "tiktok_evidence_query_service",
    "tiktok_report_query_service",
    "tiktok_placement_query_service",
    "tiktok_management_report_service",
    "tiktok_smart_plus_query_service",
    "tiktok_smart_plus_sync_service",
    "tiktok_smart_plus_material_report_sync_service",
    "google_uac_group_binding_service",
    "data_refresh_runner_service",
    "google_uac_tree_analysis_service",
    "aso_console_service",
)


_ALIASES = {
    "get_latest_workspace_source_bundle": ("workspace_unified_service", "get_latest_workspace_source_bundle"),
    "get_workspace_source_bundle": ("workspace_unified_service", "get_workspace_source_bundle"),
    "publish_workspace_artifact": ("workspace_unified_service", "publish_workspace_artifact"),
    "get_latest_workspace_run": ("workspace_unified_service", "get_latest_workspace_run"),
    "get_workspace_rows": ("workspace_unified_service", "get_workspace_rows"),
    "get_workspace_report": ("workspace_unified_service", "get_workspace_report"),
    "get_workspace_columns": ("workspace_unified_service", "get_workspace_columns"),
    "get_workspace_refresh_status": ("workspace_unified_service", "get_workspace_refresh_status"),
    "workspace_ai_chat": ("workspace_unified_service", "workspace_ai_chat"),
    "get_ads_context_bundle_from_store": ("ads_artifact_recall_service", "get_context_bundle"),
    "get_ads_report_artifact_from_store": ("ads_artifact_recall_service", "get_report_artifact"),
    "get_latest_meta_workspace_run": ("meta_data_source_adapter", "get_latest_workspace_run"),
    "get_latest_meta_workspace_source_bundle": ("meta_data_source_adapter", "get_latest_workspace_source_bundle"),
    "get_meta_workspace_columns": ("meta_data_source_adapter", "get_workspace_columns"),
    "get_meta_workspace_report": ("meta_data_source_adapter", "get_workspace_report"),
    "get_meta_workspace_rows": ("meta_data_source_adapter", "get_workspace_rows"),
    "get_meta_workspace_source_bundle": ("meta_data_source_adapter", "get_workspace_source_bundle"),
    "publish_meta_workspace_artifact": ("meta_data_source_adapter", "publish_workspace_artifact"),
}


def _load_module(module_name: str) -> Any:
    return import_module(f"{__name__}.{module_name}")


def __getattr__(name: str) -> Any:
    alias = _ALIASES.get(name)
    if alias:
        module_name, attr_name = alias
        value = getattr(_load_module(module_name), attr_name)
        globals()[name] = value
        return value
    for module_name in _LAZY_MODULES:
        expected_module = f"{__name__}.{module_name}"
        try:
            module = _load_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != expected_module:
                raise
            continue
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "run_local_analysis",
    "ApprovalError",
    "get_ads_semantic_entity",
    "get_ads_semantic_metric",
    "load_ads_semantic_catalog",
    "resolve_ads_semantic_dimensions",
    "resolve_ads_semantic_metrics",
    "validate_ads_semantic_catalog",
]
