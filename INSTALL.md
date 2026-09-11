# 安装 ChatGrowing for Codex

把下面这段交给目标电脑上的 Codex 桌面版：

> 阅读 https://github.com/Hatcherthekid/chatgrowing-plugin-marketplace/blob/main/INSTALL.md，帮我安装 ChatGrowing。复用已有安装和有效授权，从未完成的步骤继续，最后查询一条我有权访问的真实广告数据。遇到故障请读取对应错误并处理，不要把“安装成功”或“登录成功”当成全部完成。

这是给执行安装的 Codex 使用的完整流程。用户不需要 SSH 密钥、GitHub 用户名或完整 Xcode。
当前采用 self-hosted Git marketplace，不依赖 OpenAI public-directory / curated Marketplace。
不是单独复制 Skill：插件还包含 Remote MCP 与 OAuth 配置。Codex IDE extension 不支持这条插件安装流程。
ZIP 免 Git 安装尚未验收，不在本流程中替换已安装来源。

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
最低历史兼容基线为 0.144.5；以当前桌面 CLI 的 `plugin --help` 和 `mcp --help` 确认命令支持。

- 已安装且启用、URL 为 `https://chatgrowing.com/mcp`：跳到连接验证，不先重新登录。
- 已有来源但未安装：复用实际 marketplace 名称，进入安装步骤。
- 已有 Auxeo：保留现场，不删除旧配置或凭据；单独安装 ChatGrowing，验证后再讨论退役。
- 同名 server 指向其他 URL、来源或身份冲突：报告冲突位置，确认归属后处理，不自动覆盖。
- 已安装但 disabled：先确认这是用户意图还是未完成安装，按当前 CLI 帮助或插件 UI 启用，不重装碰运气。

## 2. Git 可用性检查（仅当需要获取 marketplace 时）

已下载本仓库时，macOS/Linux 可运行独立的只读检查：

```bash
/bin/bash scripts/preflight.sh --codex "$BUNDLED_CODEX"
```

尚不能获取 Git 仓库时，先通过 GitHub 文件读取工具或 HTTPS 下载并阅读该脚本，再保存到临时目录执行；
不要为获得诊断脚本先要求 Git，也不要使用 `curl | bash`。无需 Python、Node 或编译。
脚本退出码：0 仅表示 CLI/Git 可用；10/11 为 CLI/Git 未找到；12/13 为已存在的 CLI/Git 执行失败；
14 为 Apple Git 缺少可用 CLT；2 为参数错误。执行失败会返回候选路径、退出码和安全错误分类，不回显可能含凭据的原始输出。
执行失败应先修复权限/运行库/环境，不能当成未安装；若后续候选可用，则正常继续。
可用 `--git /absolute/path/to/git` 检查已发现的运行时 Git。

没有脚本也能按相同顺序检查：

1. 读取 `command -v git`、`type -a git`；macOS 先执行 `xcode-select -p`。
2. 若 macOS 未配置开发工具，不直接执行 `/usr/bin/git`，避免诊断时触发安装弹窗。
3. 检查 PATH 中其他 Git、已存在的 Homebrew Git，以及 Host 已报告的运行时 Git，逐个验证 `--version`。
   不假设每个版本 Codex 都捆绑 Git。Windows 用 `Get-Command git -All`，同时检查 Host 实际提供的运行时路径。
4. 找到可用 Git 后，只对接下来的安装子进程临时把其目录放到 PATH 最前面；不要覆盖全局 PATH 或改 shell 启动文件。
5. 确认检查范围内均无可用 Git，才向用户说明需要系统组件。macOS 可执行 `xcode-select --install`，
   等系统安装完成后再检查 `git --version` 并继续。不能把“已发起安装”写成“依赖已就绪”。

若同机以前装 Auxeo 成功，保留这次的 CLI 版本、Git 路径和失败命令；不要直接判断这台电脑从来没有 Git。

## 3. 添加来源并安装（仅执行尚未完成的步骤）

```bash
"$BUNDLED_CODEX" plugin marketplace add https://github.com/Hatcherthekid/chatgrowing-plugin-marketplace.git --ref main
"$BUNDLED_CODEX" plugin marketplace list --json
"$BUNDLED_CODEX" plugin list --marketplace "$MARKETPLACE" --json
"$BUNDLED_CODEX" plugin add "chatgrowing@$MARKETPLACE"
```

`MARKETPLACE` 必须取上一条实际返回、且指向上述 canonical HTTPS 仓库的名称。
若该桌面版本未提供 `plugin add`，使用桌面插件目录安装这个来源中的 ChatGrowing；不要手写缓存或猜命令。
所有路径与变量须加引号。公开仓库不使用个人 SSH alias，也不向用户索要 GitHub 凭据。
下载错误先按 DNS、TLS、连接超时、Git 不可用分别诊断；仅使用已确认属于用户的代理，不试探随机代理端口。

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
| CLI / Git 缺失 | 环境检查，不重复 OAuth |
| 下载 DNS / TLS / 超时 | 检查安装进程实际网络，不改 Auth0 |
| 正式 MCP invalid_grant | 同一身份重新授权一次并验证，不借他人凭据 |
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
