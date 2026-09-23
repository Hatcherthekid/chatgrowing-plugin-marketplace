#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/material_runtime_common.sh"
if ! material_runtime_ready; then
  printf '%s\n' 'ChatGrowing local helper is not prepared. Agent: run scripts/setup_material_source_mcp.sh from this installed plugin, then reconnect this local MCP. No user-installed Python, FFmpeg, Git or developer tools are needed.' >&2
  exit 78
fi
exec env -i ${material_network_env[@]+"${material_network_env[@]}"} PATH="$material_runtime/bin:/usr/bin:/bin:/usr/sbin:/sbin" HOME="$HOME" LANG="${LANG:-C.UTF-8}" PYTHONNOUSERSITE=1 \
  CHATGROWING_MATERIAL_SERVICE_ORIGIN="${CHATGROWING_MATERIAL_SERVICE_ORIGIN:-https://chatgrowing.com}" \
  "$material_runtime/bin/python3.11" -I "${material_plugin_root}/runtime/material-source/code/apps/material_source_mcp_server.py"
