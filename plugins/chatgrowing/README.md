# ChatGrowing Agent Plugin

ChatGrowing is a read-only advertising data plugin for Codex. It connects Codex to the
ChatGrowing Remote MCP for governed Meta, Google Ads, TikTok Ads, and AppsFlyer queries,
analysis, monitoring, and reporting.

## Install

Install this reviewed package through the ChatGrowing self-hosted Git marketplace. The
outer distribution repository owns the exact source URL and user-facing installation
prompt; the immutable thin Plugin does not embed a mutable distribution location.

The host opens the OAuth sign-in flow. This path does not require an OpenAI
public-directory or curated Marketplace listing. Users do not copy an authorization URL
or configure a localhost callback.

Start a new Codex task after the Desktop app reports that authentication succeeded.

This release requires Codex CLI/Desktop 0.144.5 or newer. Plugins are not
supported in the Codex IDE extension. The unique `chatgrowing_ads_read` name avoids
overwriting an existing local `ads_read` MCP server.

If a Host can read MCP Resources but does not expose ChatGrowing custom Tools in the
active task, read `ads-contract://host-tool-fallback-v1` and use the governed
`ads-query://execute/{tool_name}{?arguments}` Resource Template. This recovery
path uses the same OAuth, membership, resource scope, validation, deadline, and
artifact ownership as the normal Tool path.

The Git distribution repository may be public, but data is not. Reading ChatGrowing data requires Auth0
sign-in, active organization membership, and an assigned resource scope. This
package contains no backend source code, advertising credentials, tokens, or data.
It provides no advertising-platform write operations.
