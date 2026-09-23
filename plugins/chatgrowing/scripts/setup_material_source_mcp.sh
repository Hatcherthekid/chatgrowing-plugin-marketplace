#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/material_runtime_common.sh"
if [[ "${1:-}" == '--print-path' ]]; then printf '%s\n' "$material_runtime"; exit 0; fi
case "$material_platform" in Darwin-arm64|Darwin-x86_64) ;; *) printf '%s\n' 'ChatGrowing local files currently support macOS Apple Silicon and Intel.' >&2; exit 78;; esac
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
[[ "$locked" == true ]] || { printf '%s\n' 'ChatGrowing setup is busy; retry when installation finishes.' >&2; exit 75; }
staging="${material_runtime}.staging.$$"
cleanup() { rm -rf "$staging" "${staging}.download"; rmdir "$lock" 2>/dev/null || true; }
trap cleanup EXIT
if material_runtime_ready; then exit 0; fi

bundle_url=''; bundle_sha=''
while IFS=$'\t' read -r platform url sha; do
  [[ "$platform" == "$material_platform" ]] || continue
  [[ -z "$bundle_url" && "$url" == https://chatgrowing.com/* && "$sha" =~ ^[0-9a-f]{64}$ ]] || {
    printf '%s\n' 'Invalid ChatGrowing runtime manifest.' >&2; exit 78;
  }
  bundle_url="$url"; bundle_sha="$sha"
done < "$material_config/bundles.tsv"
[[ -n "$bundle_url" ]] || { printf '%s\n' 'No ChatGrowing runtime bundle is published for this Mac.' >&2; exit 78; }
archive="$material_state/downloads/$bundle_sha"
if [[ ! -f "$archive" ]] || [[ "$(material_hash "$archive")" != "$bundle_sha" ]]; then
  printf '%s\n' 'Downloading the verified ChatGrowing local helper from chatgrowing.com.' >&2
  curl --fail --silent --show-error --proto '=https' --max-redirs 0 --retry 2 --connect-timeout 20 --max-time 600 \
    "$bundle_url" -o "${staging}.download"
  [[ "$(material_hash "${staging}.download")" == "$bundle_sha" ]] || {
    printf '%s\n' 'ChatGrowing runtime checksum mismatch; installation stopped.' >&2; exit 78;
  }
  mv "${staging}.download" "$archive"
fi
# The archive is release-pinned above; reject path traversal before extraction.
tar -tzf "$archive" | awk '/^\// || /(^|\/)\.\.($|\/)/ { bad=1 } END { exit bad }' || {
  printf '%s\n' 'Invalid runtime archive paths.' >&2; exit 78;
}
mkdir -p "$staging"
tar -xzf "$archive" -C "$staging"
"$staging/bin/python3.11" -I -c 'import mcp,httpx; from PIL import Image' || {
  printf '%s\n' 'ChatGrowing runtime self-check failed.' >&2; exit 78;
}
printf '%s\n' "$material_revision" > "$staging/.ready"
repair_dir=''
if [[ -e "$material_runtime" || -L "$material_runtime" ]]; then
  repair_dir="$(mktemp -d "${material_runtime}.incomplete.XXXXXX")"
  mv "$material_runtime" "$repair_dir/runtime"
fi
if ! mv "$staging" "$material_runtime"; then
  if [[ -n "$repair_dir" ]]; then mv "$repair_dir/runtime" "$material_runtime"; rmdir "$repair_dir"; fi
  exit 74
fi
printf '%s\n' 'ChatGrowing local helper is ready.' >&2
