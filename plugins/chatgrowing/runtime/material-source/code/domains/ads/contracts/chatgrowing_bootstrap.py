"""Stable client bootstrap contract for the ChatGrowing Remote MCP plugin."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CHATGROWING_BOOTSTRAP_SCHEMA_VERSION = "ChatGrowingBootstrapContract.v1"
CHATGROWING_STABLE_ENTRY_TOOL = "ads_capability_context"


class ClientRefreshAction(str, Enum):
    NEW_TASK = "new_task"
    RECONNECT = "reconnect"
    PLUGIN_UPGRADE = "plugin_upgrade"


class PluginUpdateTrigger(str, Enum):
    MCP_ENDPOINT_BREAKING_CHANGE = "mcp_endpoint_breaking_change"
    OAUTH_BREAKING_CHANGE = "oauth_breaking_change"
    BOOTSTRAP_PROTOCOL_BREAKING_CHANGE = "bootstrap_protocol_breaking_change"
    HOST_LOCAL_CAPABILITY_REQUIRED = "host_local_capability_required"


class ServerOwnedCapability(str, Enum):
    AUTHORIZATION_RESOURCES = "authorization_resources"
    SOURCE_AND_FIELD_CATALOG = "source_and_field_catalog"
    METRIC_AND_EVENT_SEMANTICS = "metric_and_event_semantics"
    ANALYSIS_GUIDANCE = "analysis_guidance"
    QUERY_CONTINUATION = "query_continuation"
    KNOWLEDGE_AND_CONTEXT = "knowledge_and_context"
    REPORT_MONITOR_DELIVERY_CONFIGURATION = "report_monitor_delivery_configuration"


class ChatGrowingBootstrapContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal["ChatGrowingBootstrapContract.v1"] = CHATGROWING_BOOTSTRAP_SCHEMA_VERSION
    stable_entry_tool: Literal["ads_capability_context"] = CHATGROWING_STABLE_ENTRY_TOOL
    stable_oauth_scopes: list[Literal["ads.read"]] = Field(default_factory=lambda: ["ads.read"])
    routine_refresh_actions: list[str] = Field(
        default_factory=lambda: [
            ClientRefreshAction.NEW_TASK.value,
            ClientRefreshAction.RECONNECT.value,
        ]
    )
    plugin_update_triggers: list[str] = Field(
        default_factory=lambda: [item.value for item in PluginUpdateTrigger]
    )
    server_owned_capabilities: list[str] = Field(
        default_factory=lambda: [item.value for item in ServerOwnedCapability]
    )
    automatic_installed_plugin_update: Literal[False] = False

    @model_validator(mode="after")
    def validate_frozen_v1_boundary(self) -> "ChatGrowingBootstrapContract":
        if self.stable_oauth_scopes != ["ads.read"]:
            raise ValueError("ChatGrowingBootstrapContract.v1 requires exactly the ads.read scope")
        if self.routine_refresh_actions != [
            ClientRefreshAction.NEW_TASK.value,
            ClientRefreshAction.RECONNECT.value,
        ]:
            raise ValueError("routine refresh actions are frozen to new_task then reconnect")
        if self.plugin_update_triggers != [item.value for item in PluginUpdateTrigger]:
            raise ValueError("plugin update triggers must match the frozen V1 boundary")
        if self.server_owned_capabilities != [item.value for item in ServerOwnedCapability]:
            raise ValueError("server-owned capabilities must match the frozen V1 boundary")
        return self


def default_chatgrowing_bootstrap_contract() -> ChatGrowingBootstrapContract:
    """Return the immutable V1 boundary consumed by server and release tests."""

    return ChatGrowingBootstrapContract()
