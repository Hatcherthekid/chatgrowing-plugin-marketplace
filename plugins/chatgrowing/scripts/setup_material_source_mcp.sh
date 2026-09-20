#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/material_runtime_common.sh"
if [[ "${1:-}" == '--print-path' ]]; then printf '%s\n' "$material_runtime"; exit 0; fi
case "$material_platform" in Darwin-arm64|Darwin-x86_64) ;; *) printf '%s\n' 'Automatic material runtime setup is currently supported on macOS Apple Silicon and Intel. Remote ChatGrowing functions remain available.' >&2; exit 78;; esac
# Versioned runtime: never remove or modify a working previous installation.
if material_runtime_ready; then exit 0; fi
umask 077
mkdir -p "$material_state/runtimes" "$material_state/downloads"
lock="${material_runtime}.lock"
locked=false
for ((i=0;i<180;i++)); do
  if mkdir "$lock" 2>/dev/null; then locked=true; break; fi
  if material_runtime_ready; then exit 0; fi
  sleep 1
done
[[ "$locked" == true ]] || { printf '%s\n' 'ChatGrowing setup is busy; retry when the current installation finishes.' >&2; exit 75; }
staging="${material_runtime}.staging.$$"
cleanup() { rm -rf "$staging"; rmdir "$lock" 2>/dev/null || true; }
trap cleanup EXIT
# Another installer may have completed between our initial check and lock acquisition.
if material_runtime_ready; then exit 0; fi
mkdir -p "$staging/bin" "$staging/notices"
printf '%s\n' 'Preparing ChatGrowing private runtime; no system Python, Homebrew or developer tools are required.' >&2
uv_bin=''
while IFS=$'\t' read -r platform component url sha member; do
  [[ "$platform" == "$material_platform" ]] || continue
  [[ "$sha" =~ ^[0-9a-f]{64}$ && "$url" == https://github.com/* ]] || { printf '%s\n' 'Invalid runtime download manifest.' >&2; exit 78; }
  archive="$material_state/downloads/$sha"
  if [[ ! -f "$archive" ]] || [[ "$(material_hash "$archive")" != "$sha" ]]; then
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 2 --connect-timeout 20 --max-time 300 "$url" -o "$staging/download"
    [[ "$(material_hash "$staging/download")" == "$sha" ]] || { printf '%s\n' 'Runtime download checksum mismatch; installation stopped.' >&2; exit 78; }
    mv "$staging/download" "$archive"
  fi
  case "$component" in
    uv)
      # Extract one pinned file, not arbitrary archive paths.
      tar -xOf "$archive" "$member" > "$staging/bin/uv"
      chmod 700 "$staging/bin/uv"; uv_bin="$staging/bin/uv" ;;
    ffmpeg|ffprobe) cp "$archive" "$staging/bin/$component"; chmod 700 "$staging/bin/$component" ;;
    license|media-readme) cp "$archive" "$staging/notices/$component.txt" ;;
    *) printf '%s\n' 'Unknown runtime component.' >&2; exit 78 ;;
  esac
done < "$material_config/downloads.tsv"
[[ -n "$uv_bin" ]] || exit 78
# Ignore global Python, pip/uv configuration and package-index environment overrides.
env -i ${material_network_env[@]+"${material_network_env[@]}"} HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin UV_PYTHON_INSTALL_DIR="$material_state/python" UV_CACHE_DIR="$material_state/uv-cache" \
  "$uv_bin" --no-config venv --managed-python --python 3.11.14 --relocatable "$staging/venv" >&2
env -i ${material_network_env[@]+"${material_network_env[@]}"} HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin UV_CACHE_DIR="$material_state/uv-cache" \
  "$uv_bin" --no-config pip sync --python "$staging/venv/bin/python" --only-binary :all: --require-hashes \
  --default-index https://pypi.org/simple "$material_config/requirements.lock" >&2
"$staging/venv/bin/python" -I -c 'import mcp, httpx; from PIL import Image' >&2
"$staging/bin/ffmpeg" -version >/dev/null
"$staging/bin/ffprobe" -version >/dev/null
printf '%s\n' "$material_revision" > "$staging/.ready"
# Only replace an incomplete installation after its replacement has passed checks.
# Preserve the old directory for diagnosis; roll back if the final rename fails.
repair_dir=''
if [[ -e "$material_runtime" || -L "$material_runtime" ]]; then
  repair_dir="$(mktemp -d "${material_runtime}.incomplete.XXXXXX")"
  mv "$material_runtime" "$repair_dir/runtime"
fi
if ! mv "$staging" "$material_runtime"; then
  if [[ -n "$repair_dir" ]]; then mv "$repair_dir/runtime" "$material_runtime"; rmdir "$repair_dir"; fi
  exit 74
fi
printf '%s\n' 'ChatGrowing local runtime is ready.' >&2
