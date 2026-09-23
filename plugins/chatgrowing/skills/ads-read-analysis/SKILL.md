---
name: ads-read-analysis
description: 自由查询和分析当前授权广告数据，支持汇总、比较、排序、诊断和动态下钻；查询计划与续查路径由服务端合同驱动。
---

# Ads · 自由分析

## 入口

每个新任务先调用 `ads_capability_context`。它返回当前 principal 可见的资源、能力、版本、health、typed guidance 和兼容状态。App facet 本身不授予权限；服务端明确返回 App 级授权资源时，使用其 resource_ref 查询全媒体聚合，不能从账户授权或 App 名称推导整 App 权限。不得要求用户先提供固定账户 ID 或预设 App 名称。

若当前 Host 能读取 ChatGrowing MCP Resources、但没有披露依赖的自定义 Tool，先读取 `ads-contract://host-tool-fallback-v1`，再按其中的 `ads-query://execute/{tool_name}{?arguments}` Resource Template 调用同一只读能力。该入口仅用于 Host 恢复，不扩大权限，也不得绕过正常 Tool。

## 工具不可用时的处理

先使用 Host 的工具发现能力查找本插件工具；安装了 Skill 不等于 MCP 已连接。只进行一次正式工具发现和一次适用的连接状态检查。正常业务查询不读取其他任务、聊天历史、钥匙串或 OAuth 凭据，不扫描用户配置，不通过网页搜索代替授权数据。

只在 Host 已提供 ChatGrowing Resource Bridge 时使用它，并严格遵守该桥声明的只读能力；不得猜测资源 URI 或把只读桥当作素材写入入口。正式工具与桥均不可用时，简短报告失败阶段及已观察错误，保留原任务，不循环让用户重装、重登或新建任务。

系统 curl 能访问服务、钥匙串存在记录，都不能证明当前 Host 已连接或身份有效。没有明确的 Host 权限拒绝证据，不归因于沙箱，也不建议开启“完全访问”。禁止提取 Host token 发直连请求、编写临时 Python/Node OAuth/PKCE 桥或另建素材登录。仅在正式客户端明确要求重新认证时，按现有单一 ChatGrowing 登录流程恢复。

## 工作方式

遵循 `Dictionary-first -> Query-plan-first -> SQL/Python execution -> LLM interpretation`：

1. 把自然语言问题拆成范围、日期、grain、指标、维度、比较和期望输出。
2. 按服务端 guidance 发现 catalog、正式定义、可查询字段与 source authority；不在 Skill 记忆工具清单、source ID、公式或平台对象树。
3. 先执行最小充分查询；大范围问题先汇总或排序，再选择有信息增量的对象下钻。
   - 用户说“某渠道 / media source / PID”并给出任意名称时，把名称当作 AppsFlyer 事实字段 `media_source` 的动态值，不能拿它搜索 Catalog 的 source/provider。Catalog 只发现稳定的数据产品和字段；Catalog 无匹配不能证明该媒体来源无数据或无权限。
   - `media_source` 不使用枚举或逐渠道登记。先按用户给出的完整值查询；只有缩写或精确值无结果时，按 `app + media_source` 查询当前授权的全部 AppsFlyer App，基于服务端返回的原始值给出候选。候选不唯一时说明歧义，不猜映射。未指定 App 的存在性/覆盖问题必须扫完全部 AppsFlyer App 资源及资源分页。
4. 每次结果都检查 coverage、freshness、limitations、definition evidence 和 continuation。
5. 已从 capability context 选定物理资源时，数据健康调用必须携带对应 `resource_refs`，避免把单账户检查扩大为同渠道全部授权账户扫描。
6. 续查只能使用服务端返回的 opaque references、父对象 keys 与允许的 transition；不同投放结构可返回不同关系、切分或 profile。
7. `next_resource_cursor` 表示授权物理资源尚未扫描完，必须继续资源分页后才能声称“全部账户”；它与对象下钻 continuation 不同。
8. 需要复杂计算时，在 Host 允许的 Workspace SQL/Python 框架内处理已返回证据，不越权读取底层存储。
9. 先回答结论，再给时间范围、证据、口径、反证、限制和下一步。

## 部分数据的回答

- 先回答查询已经返回的事实，再说明缺失；来源失败或partial不能升级成整个问题cannot_judge。
- 行内metric_availability仅描述事实字段观测，不认证采集是否完整；采集是否失败读取独立source_receipts，没行不等于0或失败。
- metric_comparisons提供服务端计算的共同观测范围结果与分子、分母、输入字段、纳入/排除行数。可按用户问题引用，但必须说明这是部分范围，不是完整账户/App总比率；不同指标或日期不能默认范围一致。
- 需要具体账户/Campaign范围时继续按授权实体查询；不得自行重算比率、根据名称归属数据或用共同观测结果替换全范围值。某个比率不能判断不影响其他基础数据的回答。

## 计数口径

- 用户明确说事件次数、event count 或 PV 时使用 `total_events`；明确说人数、用户数或 UV 时使用 `unique_users`。
- 泛问审批率、通过率、转化率或好人率时默认使用 AppsFlyer UV，并主动说明；只问申请量、审批量等模糊数量时，可并列查询次数与人数并分别说明；只有用户意图无法通过并列展示满足时才追问，不把追问设为取数前置条件。
- 累计多日审批率、通过率、转化率或好人率必须使用 install-cohort UV，默认 D0，用户明确指定时使用 D1/D3；actual UV 只用于单一 actual event date 或按 date 分组的逐日趋势，不得用多日 actual/activity Daily UV Sum 形成一个累计漏斗率。
- 多日或多对象 UV 相加必须称为 `Daily UV Sum / 每日 UV 之和`，并明确说明同一用户跨日可能重复计算，它不是整个日期范围内真正去重的 UV。不得简称为 UV、区间独立用户数或去重用户数。

## 边界

- 模型能看到的数据由权限裁剪决定，模型本身不决定权限。
- 正式指标由服务端计算；不自行重算或用名称猜映射。
- 分版位指标只读服务端正式 placement fact；媒体 action 名称只能说明候选，不能自行升级成业务转化映射。
- 未知、未采集、无权限、同步失败、不可比和真实零必须区分。
- 证据不足时明确 `cannot_judge`；不执行广告平台写入或外部发送。
