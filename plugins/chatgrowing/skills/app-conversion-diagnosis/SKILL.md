---
name: app-conversion-diagnosis
description: 判断效果变化更像流量、App 转化、归因数据、业务政策还是混合问题，并给出证据边界与广告动作 Gate。
---

# Ads · App 转化诊断

## 入口

按需用 `ads_schema` 了解表，再用 `ads_sql` 查询相关投放与 AF 转化。由当前 principal 的资源范围决定可读数据：显式 AF App 授权允许读取该 App 的全媒体 AF 数据；媒体账户授权只允许对应账户范围。App 名称或查询 facet 本身不授予权限。

若当前 Host 能读取 ChatGrowing MCP Resources、但没有披露依赖的自定义 Tool，先读取 `ads-contract://host-tool-fallback-v1`，再按其中的 `ads-query://execute/{tool_name}{?arguments}` Resource Template 调用同一只读能力。该入口仅用于 Host 恢复，不扩大权限，也不得绕过正常 Tool。

## 编排

1. 明确 App facet、业务日期、时区、cohort window、比较范围和目标指标。
2. 按服务端 guidance 获取相关归因、媒体和业务语义证据，不在 Skill 固化事件、渠道或 source 路由。
3. 使用可比范围区分单一投放问题、跨范围 App 问题、数据问题、业务政策候选或混合信号。
4. 分开呈现支持证据、反证、缺失证据、责任域候选和动作 Gate。
5. 只有新查询能补充有效信息时才修改 SQL 继续下钻；不需要 continuation。

## 边界

- 正式指标和归因口径由服务端提供，模型不重算。
- 映射、freshness、cohort 或权限不满足时，受影响结论为 `cannot_judge`。
- 责任域分流不是具体根因证明，也不授权广告平台写操作。
