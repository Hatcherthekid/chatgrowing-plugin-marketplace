#!/usr/bin/env bash
# Fresh macOS installation from an HTTPS snapshot. Does not modify existing sources.
set -euo pipefail
codex=''
with_materials=false
update_owned=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex) codex="${2:-}"; shift 2 ;;
    --with-materials) with_materials=true; shift ;;
    --update-owned-source) update_owned=true; shift ;;
    *) printf '%s\n' 'Usage: install_without_git.sh --codex /absolute/path/to/codex [--with-materials] [--update-owned-source]' >&2; exit 2 ;;
  esac
done
[[ "$codex" == /* && -x "$codex" ]] || { printf '%s\n' 'Use the verified Codex executable from the installed desktop app.' >&2; exit 2; }
state="${CODEX_HOME:-${HOME}/.codex}/chatgrowing"
mkdir -p "$state"
state="$(cd "$state" && pwd -P)"
lock="$state/marketplace-install.lock"
if ! mkdir "$lock" 2>/dev/null; then
  printf '%s\n' 'Another ChatGrowing installation is active; retry after it finishes.' >&2
  exit 75
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT
# Never replace a colleague's existing marketplace, cache or credentials.
listing="$("$codex" plugin marketplace list --json)"
installed_source="$state/marketplace-http"
has_source=false
if printf '%s' "$listing" | grep -Eq '"name"[[:space:]]*:[[:space:]]*"chatgrowing"'; then
  has_source=true
  if [[ "$update_owned" != true || ! -f "$installed_source/.chatgrowing-http-source" ]] || ! printf '%s' "$listing" | grep -Fq "\"source\": \"$installed_source\""; then
    printf '%s\n' 'Existing ChatGrowing source preserved. For a source installed by this script, use --update-owned-source; otherwise use the existing marketplace update path.' >&2
    exit 10
  fi
fi
stage="$(mktemp -d "$state/marketplace-download.XXXXXX")"
success=false
cleanup() {
  if [[ "$success" != true && -d "$stage/previous" ]]; then
    [[ ! -e "$installed_source" ]] || mv "$installed_source" "$stage/failed"
    mv "$stage/previous" "$installed_source"
  fi
  rm -rf "$stage"
  rmdir "$lock" 2>/dev/null || true
}
trap cleanup EXIT
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 2 --max-time 60 \
  'https://api.github.com/repos/Hatcherthekid/chatgrowing-plugin-marketplace/commits/main' -o "$stage/commit.json"
commit="$(sed -n 's/^  "sha": "\([0-9a-f]*\)",$/\1/p' "$stage/commit.json" | head -1)"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { printf '%s\n' 'Could not resolve the public marketplace commit.' >&2; exit 78; }
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 2 --max-time 300 \
  "https://codeload.github.com/Hatcherthekid/chatgrowing-plugin-marketplace/tar.gz/$commit" -o "$stage/repo.tar.gz"
prefix="chatgrowing-plugin-marketplace-$commit"
while IFS= read -r member; do
  [[ "$member" == "$prefix/"* && "$member" != *'/../'* ]] || { printf '%s\n' 'Unexpected marketplace archive path.' >&2; exit 78; }
done < <(tar -tzf "$stage/repo.tar.gz")
tar -xzf "$stage/repo.tar.gz" -C "$stage"
source_root="$stage/$prefix"
[[ -f "$source_root/.agents/plugins/marketplace.json" && -f "$source_root/plugins/chatgrowing/.codex-plugin/plugin.json" ]] || exit 78
if [[ "$with_materials" == true ]]; then
  /bin/bash "$source_root/plugins/chatgrowing/scripts/setup_material_source_mcp.sh"
fi
# Persist source: the CLI must not reference a temporary directory that disappears.
printf '%s\n' "$commit" > "$source_root/.chatgrowing-http-source"
if [[ -e "$installed_source" ]]; then
  [[ "$has_source" == true && "$update_owned" == true ]] || { printf '%s\n' 'Unregistered snapshot exists; inspect before replacing it.' >&2; exit 78; }
  mv "$installed_source" "$stage/previous"
fi
mv "$source_root" "$installed_source"
if [[ "$has_source" != true ]]; then "$codex" plugin marketplace add "$installed_source" --json; fi
"$codex" plugin add chatgrowing@chatgrowing --json
success=true
printf '%s\n' 'Plugin files installed without Git. Verify ChatGrowing login and a permitted remote query next.' >&2
