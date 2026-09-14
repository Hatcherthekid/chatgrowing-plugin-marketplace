#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(cd "${script_dir}/.." && pwd)"
runtime_root="${plugin_root}/runtime/material-source"
python_bin="${CODEX_HOME:-${HOME}/.codex}/chatgrowing/material-source-venv/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  printf '%s\n' 'ChatGrowing local material runtime is not installed. Run scripts/setup_material_source_mcp.sh once.' >&2
  exit 78
fi
exec env -i PATH="${PATH}" HOME="${HOME}" LANG="${LANG:-C.UTF-8}" PYTHONNOUSERSITE=1 \
  CHATGROWING_MATERIAL_SERVICE_ORIGIN="${CHATGROWING_MATERIAL_SERVICE_ORIGIN:-https://chatgrowing.com}" \
  "${python_bin}" "${runtime_root}/code/apps/material_source_mcp_server.py"
