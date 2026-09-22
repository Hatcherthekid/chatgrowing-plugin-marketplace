# ChatGrowing Agent Plugin

ChatGrowing connects Codex to one governed Remote Agent Gateway for authorized Meta,
Google Ads, TikTok Ads, and AppsFlyer reading, analysis, monitoring, and reporting. The
same ChatGrowing login can expose permitted material and YouTube actions; those actions
remain protected by server-side capabilities, resource bindings, explicit user intent,
idempotency, and audit.

## Install

Install this reviewed package through the ChatGrowing self-hosted Git marketplace. The
outer distribution repository owns the exact source URL and user-facing installation
prompt; the immutable thin Plugin does not embed a mutable distribution location.

The host opens the OAuth sign-in flow. This path does not require an OpenAI
public-directory or curated Marketplace listing. Users do not copy an authorization URL
or configure a localhost callback.

After the Desktop reports successful authentication, use the current ChatGrowing tools.
If the Host explicitly requires a tool refresh, follow that Host recovery action.

Codex CLI/Desktop 0.144.5 is only the historical package-format baseline, not
proof of OAuth refresh compatibility. Follow INSTALL.md for the tested Host
version and refresh coordination checks; repeated login is not a refresh fix. Plugins are not
supported in the Codex IDE extension. The unique `chatgrowing_ads_read` name avoids
overwriting an existing local `ads_read` MCP server.

If a Host can read MCP Resources but does not expose ChatGrowing custom Tools in the
active task, read `ads-contract://host-tool-fallback-v1` and use the governed
`ads-query://execute/{tool_name}{?arguments}` Resource Template. This recovery
path uses the same OAuth, membership, resource scope, validation, deadline, and
artifact ownership as the normal Tool path.

The Git distribution repository may be public, but data is not. Reading ChatGrowing data requires Auth0
sign-in, active organization membership, and an assigned resource scope. This
package contains the reviewed local file helper required by reference-only material
workflows. It contains no server source, advertising credentials, tokens, or customer data.
YouTube writes require an authenticated, permission-checked submission of a fixed
publication manifest matching the user's explicit request.
