#!/usr/bin/env bash
# Shared by setup and launch. Never invoke system Python or Apple's developer shims.
material_plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
material_config="${material_plugin_root}/runtime-config"
material_state="${CODEX_HOME:-${HOME}/.codex}/chatgrowing"
material_platform="$(uname -s)-$(uname -m)"
material_hash() { shasum -a 256 "$1" | awk '{print $1}'; }
[[ -f "${material_config}/requirements.lock" && -f "${material_config}/downloads.tsv" ]] || { printf '%s\n' 'ChatGrowing packaged runtime manifest is missing.' >&2; exit 78; }
material_revision="$(cat "${material_config}/requirements.lock" "${material_config}/downloads.tsv" "${material_plugin_root}/scripts/setup_material_source_mcp.sh" | shasum -a 256 | awk '{print $1}')"
material_runtime="${material_state}/runtimes/${material_platform}-${material_revision}"
# Keep standard network configuration across the isolated runtime boundary.
# Never print values: proxy URLs can themselves contain credentials.
material_network_env=()
for material_network_key in HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy SSL_CERT_FILE SSL_CERT_DIR; do
  if [[ -n "${!material_network_key:-}" ]]; then
    material_network_env+=("${material_network_key}=${!material_network_key}")
  fi
done

material_runtime_ready() {
  [[ -f "$material_runtime/.ready" && -x "$material_runtime/venv/bin/python" && -x "$material_runtime/bin/ffmpeg" && -x "$material_runtime/bin/ffprobe" ]] &&
    [[ "$(cat "$material_runtime/.ready")" == "$material_revision" ]]
}
