"""Single source of truth for the public Ads Read MCP tool surface."""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from .read_mcp import (
    PUBLIC_TOOL_NAMES,
    CatalogDescribeRequest,
    CatalogDescribeResponse,
    CapabilityContextRequest,
    CapabilityContextResponse,
    CatalogSearchRequest,
    CatalogSearchResponse,
    ContextLookupRequest,
    ContextLookupResponse,
    DataHealthRequest,
    DataHealthResponse,
    DataQueryRequest,
    DataQueryResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    WorkspaceAnalyzeRequest,
    WorkspaceAnalyzeResponse,
)


@dataclass(frozen=True)
class PublicReadToolSpec:
    name: str
    description: str
    request_model: Type[BaseModel]
    response_model: Type[BaseModel]
    idempotent: bool = True

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": _compact_model_schema(
                self.request_model.model_json_schema(mode="validation")
            ),
            "outputSchema": _compact_model_schema(
                self.response_model.model_json_schema(mode="validation")
            ),
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": self.idempotent,
            },
        }


def _compact_model_schema(schema: dict) -> dict:
    """Remove nested presentation titles while preserving contract semantics."""

    def compact(
        value: object,
        *,
        root: bool = False,
        property_map: bool = False,
    ) -> object:
        if isinstance(value, dict):
            return {
                key: compact(
                    item,
                    property_map=key
                    in {"properties", "patternProperties", "$defs", "definitions"},
                )
                for key, item in value.items()
                if root or property_map or key != "title"
            }
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    return compact(deepcopy(schema), root=True)


_PUBLIC_READ_TOOL_SPECS = (
    PublicReadToolSpec(
        name="ads_catalog_search",
        description="搜索可用数据源与 Artifact。",
        request_model=CatalogSearchRequest,
        response_model=CatalogSearchResponse,
    ),
    PublicReadToolSpec(
        name="ads_catalog_describe",
        description="描述数据源字段、指标、口径与限制。",
        request_model=CatalogDescribeRequest,
        response_model=CatalogDescribeResponse,
    ),
    PublicReadToolSpec(
        name="ads_capability_context",
        description="发现授权资源与可用能力。",
        request_model=CapabilityContextRequest,
        response_model=CapabilityContextResponse,
    ),
    PublicReadToolSpec(
        name="ads_data_health",
        description="检查数据覆盖、时效和映射。",
        request_model=DataHealthRequest,
        response_model=DataHealthResponse,
    ),
    PublicReadToolSpec(
        name="ads_data_query",
        description="执行只读查询或证据续查。",
        request_model=DataQueryRequest,
        response_model=DataQueryResponse,
        idempotent=False,
    ),
    PublicReadToolSpec(
        name="ads_workspace_analyze",
        description="对授权 Artifact 做受限分析。",
        request_model=WorkspaceAnalyzeRequest,
        response_model=WorkspaceAnalyzeResponse,
        idempotent=False,
    ),
    PublicReadToolSpec(
        name="ads_knowledge_search",
        description="搜索广告诊断知识与证据要求。",
        request_model=KnowledgeSearchRequest,
        response_model=KnowledgeSearchResponse,
    ),
    PublicReadToolSpec(
        name="ads_context_lookup",
        description="查询组织上下文与偏好。",
        request_model=ContextLookupRequest,
        response_model=ContextLookupResponse,
    ),
    PublicReadToolSpec(
        name="ads_report_generate",
        description="从授权 Evidence Artifact 创建/预览自定义 Report；兼容注册报告，不发送或修改广告。",
        request_model=ReportGenerateRequest,
        response_model=ReportGenerateResponse,
        idempotent=False,
    ),
)

PUBLIC_READ_TOOL_NAMES = tuple(spec.name for spec in _PUBLIC_READ_TOOL_SPECS)
if PUBLIC_READ_TOOL_NAMES != PUBLIC_TOOL_NAMES:
    raise RuntimeError("public Ads Read tool registry drift")


DASHBOARD_BRIDGE_TOOL_DEFINITIONS = (
    {
        "name": "chatgrowing_dashboard_request_analysis",
        "description": "为当前组织已打开的 Dashboard 创建一个短时、持久化的 AI 分析请求，返回 analysis_request_id。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"composition_id": {"type": "string"}}, "required": ["composition_id"]},
        "outputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "chatgrowing_dashboard_get_analysis_bundle",
        "description": "按 analysis_request_id 读取已登录 Dashboard 提交的冻结快照和分析问题。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"analysis_request_id": {"type": "string"}}, "required": ["analysis_request_id"]},
        "outputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "chatgrowing_dashboard_grant_evidence",
        "description": "把当前 principal 通过 Ads Read 生成的 Artifact refs 登记到指定 Dashboard 请求；服务端读取 Artifact 后生成可引用 evidence allowlist。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"analysis_request_id": {"type": "string"}, "input_refs": {"type": "array", "items": {"type": "object"}, "minItems": 1, "maxItems": 20}}, "required": ["analysis_request_id", "input_refs"]},
        "outputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "chatgrowing_dashboard_apply_narrative",
        "description": "将 evidence-bound Narrative Artifact 写回指定 Dashboard 请求；只更新展示 artifact，不修改广告平台。",
        "inputSchema": {"type": "object", "additionalProperties": False, "properties": {"analysis_request_id": {"type": "string"}, "artifact": {"type": "object"}}, "required": ["analysis_request_id", "artifact"]},
        "outputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    },
)
DASHBOARD_BRIDGE_TOOL_NAMES = tuple(
    definition["name"] for definition in DASHBOARD_BRIDGE_TOOL_DEFINITIONS
)
REMOTE_HOST_TOOL_NAMES = (*PUBLIC_READ_TOOL_NAMES, *DASHBOARD_BRIDGE_TOOL_NAMES)


def generated_public_read_tool_definitions() -> list[dict]:
    return deepcopy([spec.schema() for spec in _PUBLIC_READ_TOOL_SPECS])


def generated_public_read_tool_schema_snapshot() -> dict:
    return {
        "schema_version": "AdsCapabilityMcpPublicSchema.v3",
        "publication_state": "published_mcp",
        "tools": generated_public_read_tool_definitions(),
    }


_FROZEN_SCHEMA_PATH = Path(__file__).with_name("ads_capability_mcp_public_schema_v3.json")


def public_read_tool_schema_snapshot() -> dict:
    snapshot = json.loads(_FROZEN_SCHEMA_PATH.read_text(encoding="utf-8"))
    names = tuple(item.get("name") for item in snapshot.get("tools", []))
    if names != PUBLIC_READ_TOOL_NAMES:
        raise RuntimeError("frozen public Ads Read tool registry drift")
    return snapshot


def public_read_tool_definitions() -> list[dict]:
    return deepcopy(public_read_tool_schema_snapshot()["tools"])


def host_public_read_tool_definitions() -> list[dict]:
    """Return the compact MCP discovery surface used by Host tool indexing.

    The frozen schema remains the exact contract authority.  Runtime response
    models still validate every payload; Host disclosure only needs a compact
    envelope so tool discovery is not dominated by nine duplicated response
    schemas.
    """

    definitions = public_read_tool_definitions()
    for definition in definitions:
        title = str((definition.get("outputSchema") or {}).get("title") or "AdsReadResponse")
        definition["outputSchema"] = {
            "title": title,
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "trace_id": {"type": "string"},
            },
            "required": ["status", "trace_id"],
            "additionalProperties": True,
        }
    return definitions


def remote_host_tool_definitions() -> list[dict]:
    """Return the complete Tool surface actually exposed by Remote MCP."""

    return [
        *host_public_read_tool_definitions(),
        *deepcopy(DASHBOARD_BRIDGE_TOOL_DEFINITIONS),
    ]


def remote_host_tool_surface_sha256() -> str:
    payload = json.dumps(
        remote_host_tool_definitions(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
