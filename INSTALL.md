# Install ChatGrowing for Codex

Paste this prompt into Codex:

```text
Please install the ChatGrowing Codex Plugin from
https://github.com/Hatcherthekid/chatgrowing-plugin-marketplace.git, complete the
chatgrowing_ads_read OAuth sign-in, and remind me to start a new Codex task after
installation succeeds.
```

Codex adds the ChatGrowing self-hosted Git marketplace, installs **ChatGrowing**, and
opens the host OAuth flow. This path does not require an OpenAI public-directory or
curated Marketplace listing. Users do not copy an OAuth URL or configure a localhost callback.

After Desktop reports that authentication succeeded, start a new Codex task so
the ChatGrowing skills and MCP tools are loaded. Requires Codex CLI/Desktop 0.144.5 or
newer. The Codex IDE extension does not support plugins.
The unique `chatgrowing_ads_read` name preserves any existing local `ads_read` MCP server.
The Git repository may be public, but ChatGrowing data access still requires an invited organization member and assigned resource scope.
