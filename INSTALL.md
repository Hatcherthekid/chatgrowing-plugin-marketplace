# 安装 ChatGrowing for Codex

把下面这段交给目标电脑上的 Codex 桌面版：

> 阅读 https://github.com/Hatcherthekid/chatgrowing-plugin-marketplace/blob/main/INSTALL.md，帮我安装 ChatGrowing。复用已有安装和有效授权，从未完成的步骤继续，最后查询一条我有权访问的真实广告数据。遇到故障请读取对应错误并处理，不要把“安装成功”或“登录成功”当成全部完成。

这是给执行安装的 Codex 使用的完整流程。用户不需要 SSH 密钥、GitHub 用户名或完整 Xcode。
当前采用 self-hosted marketplace（HTTPS 快照或已有 Git 来源），不依赖 OpenAI public-directory / curated Marketplace。
不是单独复制 Skill：插件还包含 Remote MCP 与 OAuth 配置。Codex IDE extension 不支持这条插件安装流程。
macOS 新安装优先使用下方 HTTPS 快照流程，无需 Git、Python、Node 或 Apple 开发工具；保留已有 Git 来源，不自动切换。

## 1. 确认环境，先读取已有状态

只在用户要使用的电脑上执行；远程沙箱不能替另一台电脑完成本地安装。
定位当前桌面应用捆绑的 Codex CLI，记为绝对路径 `BUNDLED_CODEX`。macOS 常见路径为
`/Applications/ChatGPT.app/Contents/Resources/codex` 或 `/Applications/Codex.app/Contents/Resources/codex`，
必须检查实际存在并执行 `--version`，不要直接使用 PATH 中的另一份 npm/Homebrew CLI。
Windows 从当前桌面应用安装目录定位其捆绑 CLI，不假设与 macOS 路径相同。

```bash
"$BUNDLED_CODEX" --version
"$BUNDLED_CODEX" plugin marketplace list --json
"$BUNDLED_CODEX" plugin list --json
"$BUNDLED_CODEX" mcp get chatgrowing_ads_read --json
```

只提取插件名称、来源、版本、enabled 状态、MCP URL 和错误；不要展示整份个人配置、headers 或凭据。
0.144.5 只是历史插件格式基线，不代表自动续期通过；以当前桌面 CLI 的 `plugin --help` 和 `mcp --help` 确认命令支持。

首次登录前检查 Host 自动续期。2026-09-20 对桌面捆绑 0.155.0-alpha.9 的实测表明：未启用刷新协调时，多连接会重用已轮换的凭据；启用后多连接、刷新后超时重建通过。只读取 `features list` 中的 `mcp_oauth_refresh_coordination` 一行，不读取凭据。若该版本支持且为 false，由安装 Agent 使用官方 `features enable mcp_oauth_refresh_coordination` 开启并回读；它修改 Host 的全局刷新协调选项，需明确告知。已为 true 时不重复修改，也不要求重新登录。旧版本即使识别选项也不保证实现生效；版本和真实续期验收分别记录。未知版本/选项不可用时报告 Host 兼容性缺口，不能循环重连或擅自关闭 Auth0 轮换保护。

- 已安装且启用、URL 为 `https://chatgrowing.com/mcp`：普通使用跳到连接验证，不先重新登录；用户明确要求更新或版本落后时，先完成下方来源感知更新，再核对实际安装版本。
- 已有来源但未安装：复用实际 marketplace 名称，进入安装步骤。
- 已有 Auxeo：保留现场，不删除旧配置或凭据；单独安装 ChatGrowing，验证后再讨论退役。
- 同名 server 指向其他 URL、来源或身份冲突：报告冲突位置，确认归属后处理，不自动覆盖。
- 已安装但 disabled：先确认这是用户意图还是未完成安装，按当前 CLI 帮助或插件 UI 启用，不重装碰运气。

## 2. 新安装无需 Git / 开发工具

先执行第 1 节的已有状态检查。已有 ChatGrowing 来源继续复用，不改变已有授权或强行切换分发来源。

新安装：通过 HTTPS 下载并阅读本仓库 `scripts/install_without_git.sh`，保存到临时文件后执行；不要 `curl | bash`。使用系统已有 Bash/curl/tar 和已核验的 Codex CLI，无需安装 Git、Homebrew、Python 或 Xcode。

```bash
/bin/bash /absolute/path/install_without_git.sh --codex "$BUNDLED_CODEX"
```

该脚本从公开 GitHub API 解析 main 的精确 commit，下载该快照并安装为持久的本地 marketplace。它仅安装插件文件，之后仍须验证 ChatGrowing 登录及远程查询。它不会把“文件安装成功”称为业务可用。

通过本脚本安装的来源，更新时仍运行同一脚本并加 `--update-owned-source`，再新建任务验证版本。已存在 Git 来源继续走原有 marketplace upgrade 和显式 plugin add；不得替换来源、删除凭据或让用户重新 Google 授权来解决安装问题。

只做广告查询、查看频道/视频，不准备本地素材运行环境；本地文件助手未就绪不能阻塞远程验收，也不能据此要求用户安装系统组件。Host 支持按插件禁用单个 MCP 时，可在插件设置中停用 `chatgrowing_material_local`，保留远程 `chatgrowing_ads_read`。

### 用户需要本地文件上传时

由安装 Agent 自动准备一次 ChatGrowing 专用运行环境，不把 Python/Homebrew/Xcode 安装工作交给用户：

- 新安装可给上述脚本加 `--with-materials`。
- 已安装插件则运行实际安装目录中的 `scripts/setup_material_source_mcp.sh`，完成后重新连接本地助手。
- 自动下载固定版本、校验 SHA-256、只安装带哈希的预编译 wheel；Python、FFmpeg 和 FFprobe 放在 ChatGrowing 专用用户目录，不改系统环境，不使用 sudo。
- 当前自动准备范围是 macOS Apple Silicon 与 Intel。其他系统保持远程能力可用，不声称本地文件自动安装已支持。
- 网络失败先按下载阶段处理并重试；失败保留旧运行环境，不回退到源码编译或要求安装开发工具。安装中断或文件缺失时重新运行同一准备脚本：替代环境完整验证后才切换，原不完整目录保留以供诊断，无需手动删除或重新登录。

若坚持使用已有 Git 来源且 Git 不可用，先用 Host 报告的运行时 Git 或 `scripts/preflight.sh --git /verified/path` 检查。禁止为首次安装 ChatGrowing 默认执行 `xcode-select --install`；新安装直接走 HTTPS 快照流程。

## 3. 更新：先区分来源，再更新实际插件

以 `plugin marketplace list --json` 的 `marketplaceSource.sourceType` 为准。目录名含 `-git` 不代表 Git 来源。`marketplace upgrade` 只适用于 Git 来源；不存在 `plugin update` 命令，不要猜测。

### 已登记为 Git

Canonical 仓库为 `https://github.com/Hatcherthekid/chatgrowing-plugin-marketplace.git`。复用实际返回且指向该仓库的 `MARKETPLACE`，不要每次重新登记：

```bash
"$BUNDLED_CODEX" plugin marketplace upgrade "$MARKETPLACE" --json
"$BUNDLED_CODEX" plugin add "chatgrowing@$MARKETPLACE" --json
"$BUNDLED_CODEX" plugin list --marketplace "$MARKETPLACE" --json
```

刷新市场只更新可用版本；再次 `plugin add` 才更新实际安装。保留相同插件身份，不先移除插件或市场，不 logout，不重新授权 Google。若当前 CLI 不支持这些命令，报告具体兼容性缺口，不手写缓存。

### 已登记为 local

不要执行 `marketplace upgrade`，不要因为路径叫 `chatgrowing-git` 而尝试 Git 修复。由 HTTPS 安装器拥有的来源使用：

```bash
/bin/bash /absolute/path/install_without_git.sh --codex "$BUNDLED_CODEX" --update-owned-source
```

旧 local 来源（包括名为 `chatgrowing-git` 的目录）由安装 Agent 从 CLI 返回值取得实际绝对路径并核验后运行：

```bash
/bin/bash /absolute/path/install_without_git.sh --codex "$BUNDLED_CODEX" --migrate-local-source "$VERIFIED_LOCAL_SOURCE"
```

这会校验来源仅包含 ChatGrowing 分发、插件名称及官方 MCP 地址，再在原路径换入 HTTPS 快照，执行官方 `plugin add`。市场名称、路径和插件身份保持不变；原分发目录保留。拒绝 Git checkout、Host 缓存、链接或不明内容，不删除重建市场，不手改已安装缓存，也不改授权。后续更新可用 `--update-owned-source`。下载或校验失败保留旧来源；安装步骤失败则回滚来源目录，但必须重新回读实际安装版本，不能宣称 CLI 的部分写入也被完全回滚。

### 下载失败与连接失败分别处理

HTTPS 快照不使用 raw.githubusercontent.com，但仍需要访问 GitHub API 和 codeload。普通 GitHub 页面可访问不证明这些下载域名可访问。TLS 证书失败不得通过 `curl -k` 或关闭验证绕过；没有验证可用的下载来源时，保留旧版并明确下载未完成，不重复登录或宣称升级成功。

升级结束核对实际 installed version、enabled 和同一 MCP URL。旧任务未刷新工具时，只重载相关工具或新建任务验证，不能把它称为需要再次登录。素材助手准备是独立步骤，远程查询不依赖本地 Python。更新成功也不证明另一设备的 MCP 传输故障已修复。

## 4. 验证连接，再按需授权

先尝试发现并调用 `ads_capability_context`。若没有正式工具，读取 `chatgrowing_ads_read` 的正式启动日志，
识别是未注册、未启动、认证失败、HTTP/协议错误还是工具未披露。
仅在缺少授权或正式客户端明确 `needs_reauth` / `invalid_grant` 时发起 OAuth：

```bash
"$BUNDLED_CODEX" mcp login chatgrowing_ads_read
```

使用发布 `.mcp.json` 中的 CIMD client 与 scopes；不要改 Auth0、手工注册重复 MCP、扩大 scope 或先 logout。
登录前核对可见账户是否为用户目标身份。每次只保留一个登录进程。
需要 Accept 时明确说明是授权 Codex 读取 ChatGrowing；已有同范围授权时继续，不重复索要确认。
登录结束以进程成功退出和实际连接验证为准，页面仍停在授权页不能单独推翻成功结果。
若内置浏览器确实无法完成，在同一电脑的系统 Chrome 打开仍有效的初始授权链接；链接失效才结束旧进程、发起新流程。
不复制中途 consent URL，不展示含 OAuth code/state 的链接，不把凭据写进文件。

## 5. 从连接到真实查询

按照安装的 ads-read-analysis Skill：Capability Context → Catalog Search → Describe → 必要 Health → 最小 Data Query。
从服务端选择当前成员明确授权的一个 resource_ref、实际支持的日期和指标；不硬编码其他用户账户。
返回真实 source-backed 结果及 trace_id，区分真实零、无数据、无权限与失败。

若授权完成但当前任务仍无正式工具：

1. 记录正式 MCP 启动时间与原始错误，不把手动脚本沙箱的 ENOTFOUND 当成正式客户端错误。
2. 有明确启动/认证错误就处理该阶段；若是旧任务未刷新能力，使用 Host 提供的刷新能力，或让用户新建一次任务继续。
   未获新建任务授权时不自动创建；交接只包含步骤状态和安全错误，不包含凭据。
3. 若服务端 tools/list 正常而 Host 不披露工具，可使用已发现的正式 Resource Bridge 做兼容验证。
   Bridge 查询通过单独标为“兼容查询通过，正式工具待验证”，不得报完整安装验收通过。
4. 一次新任务仍失败，立即查正式启动日志并报告可定位错误；不循环要求新建任务、重装或重新登录。

## 6. 完成回执与恢复分流

给用户简短回执：安装版本、安装/授权/正式工具/真实查询各自状态、查询 trace_id（无则明确缺失），
以及仅剩的阻断步骤。不要输出 token、OAuth code、个人完整标识或广告明细作为诊断日志。

| 失败阶段 | 下一步 |
| --- | --- |
| CLI 缺失 | 定位桌面内置 CLI，不重复 OAuth |
| Git 缺失 | 新安装走 HTTPS 快照；已有来源先查 Host 提供的 Git，不默认安装开发工具 |
| 下载 DNS / TLS / 超时 | 检查安装进程实际网络，不改 Auth0 |
| 正式 MCP invalid_grant | 同一身份重新授权一次并验证，不借他人凭据 |
| Token expired 反复出现 | 先核对 Host 刷新协调、offline_access 与认证方刷新结果；单独的过期文本不证明 refresh token 缺失，不重复 Google 授权 |
| OAuth 成功、MCP 启动失败 | 读取正式启动错误、HTTP 状态和可用请求 ID |
| HTTP 403，来源未明 | 先检查 Content-Type、脱敏错误码与来源标记；不能仅凭状态码判断成员权限 |
| Cloudflare/代理拒绝（例如 1010、HTML challenge） | 保留 Ray/request ID、时间和路径，查对应边缘规则；不自动关防护或改 Auth0 |
| ChatGrowing 明确 scope_denied / membership_required | 核对成员或资源授权；不能绕过权限 |
| 工具未披露 | 一次刷新/新任务、正式日志、已发现的兼容桥接 |
| source_unavailable / partial | 数据健康诊断，不重装插件 |

“安装完成、即时使用通过”必须同时满足插件启用、身份有效、正式工具可调用、最小真实查询成功。
没有授权资源时明确“接入完成，等待资源授权”，不能虚构查询成功。
长效稳定另验：真实 access token 到期后刷新及查询、关闭重开、干净 Mac、Auxeo 同机迁移和中断恢复。
后台/定时读取须另有对应授权；不要因一次安装请求自动创建周期任务。
