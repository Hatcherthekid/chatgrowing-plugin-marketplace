# ChatGrowing Codex Plugin Distribution

This self-hosted marketplace distributes the thin ChatGrowing Agent Plugin for Codex. It contains
plugin metadata, read-only advertising Skills, public assets, and the Remote MCP address.
It does not contain the ChatGrowing backend, advertising credentials, tokens, or customer data.

It supports Git sources and persistent HTTPS snapshots without Git or Apple developer tools.
It does not depend on an OpenAI curated Marketplace listing.

Updates must use the actual registered sourceType, never the directory name. Git sources
use marketplace upgrade followed by plugin add; local sources use the HTTPS installer.
Refreshing a marketplace alone does not update the installed plugin. Updating plugin files
does not require signing in again or reauthorizing Google. See INSTALL.md for legacy local sources.

See [INSTALL.md](INSTALL.md) for installation. Downloading the plugin grants no data
access; users must authenticate and have active ChatGrowing organization and resource access.
