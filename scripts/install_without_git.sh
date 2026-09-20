#!/usr/bin/env bash
# macOS HTTPS snapshot install; existing local sources require explicit migration.
set -euo pipefail
codex=''
with_materials=false
update_owned=false
migrate_source=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex) codex="${2:-}"; shift 2 ;;
    --with-materials) with_materials=true; shift ;;
    --update-owned-source) update_owned=true; shift ;;
    --migrate-local-source) migrate_source="${2:-}"; [[ -n "$migrate_source" ]] || exit 2; shift 2 ;;
    *) printf '%s\n' 'Usage: install_without_git.sh --codex /absolute/path/to/codex [--with-materials] [--update-owned-source | --migrate-local-source /verified/local/path]' >&2; exit 2 ;;
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
# macOS ships a real JSON parser; do not infer a source from another marketplace.
[[ -x /usr/bin/plutil ]] || { printf '%s\n' 'This installer requires macOS system plutil.' >&2; exit 78; }
json_value() { /usr/bin/plutil -extract "$2" raw -o - "$1" 2>/dev/null; }
[[ "$update_owned" != true || -z "$migrate_source" ]] || { printf '%s\n' 'Choose update or migration, not both.' >&2; exit 2; }
stage="$(mktemp -d "$state/marketplace-download.XXXXXX")"
success=false
previous=''
plugin_install_attempted=false
installed_source="$state/marketplace-http"
cleanup() {
  result=$?
  if [[ "$success" != true && -n "$previous" && -d "$previous/runtime" ]]; then
    if [[ -e "$installed_source" ]]; then mv "$installed_source" "$stage/failed" || exit 74; fi
    mv "$previous/runtime" "$installed_source" || { printf '%s\n' 'Source rollback failed; preserved previous source requires recovery.' >&2; exit 74; }
    rmdir "$previous" || true
    if [[ "$plugin_install_attempted" == true ]]; then printf '%s\n' 'Source files restored. The Host may have partially changed its installed plugin; verify the installed version before retrying. Authorization was not changed by this script.' >&2; fi
  fi
  rm -rf "$stage"
  rmdir "$lock" 2>/dev/null || true
  exit "$result"
}
trap cleanup EXIT
"$codex" plugin marketplace list --json > "$stage/marketplaces.json"
count="$(json_value "$stage/marketplaces.json" marketplaces)"
[[ "$count" =~ ^[0-9]+$ ]] || exit 78
has_source=false
source_kind=''
source_path=''
for ((index=0;index<count;index++)); do
  name="$(json_value "$stage/marketplaces.json" "marketplaces.$index.name")"
  [[ "$name" == chatgrowing ]] || continue
  [[ "$has_source" != true ]] || exit 78
  has_source=true
  source_kind="$(json_value "$stage/marketplaces.json" "marketplaces.$index.marketplaceSource.sourceType" || true)"
  source_path="$(json_value "$stage/marketplaces.json" "marketplaces.$index.marketplaceSource.source")"
done
verify_chatgrowing_source() {
  local root="$1" market="$1/.agents/plugins/marketplace.json" plugin="$1/plugins/chatgrowing/.codex-plugin/plugin.json"
  [[ ! -L "$root" && -d "$root" && -f "$market" && -f "$plugin" ]] &&
    [[ "$(json_value "$market" name)" == chatgrowing && "$(json_value "$market" plugins)" == 1 &&
       "$(json_value "$market" plugins.0.name)" == chatgrowing &&
       "$(json_value "$market" plugins.0.source.source)" == local &&
       "$(json_value "$market" plugins.0.source.path)" == ./plugins/chatgrowing &&
       "$(json_value "$plugin" name)" == chatgrowing &&
       "$(json_value "$root/plugins/chatgrowing/.mcp.json" mcpServers.chatgrowing_ads_read.url)" == https://chatgrowing.com/mcp ]]
}
if [[ -n "$migrate_source" ]]; then
  [[ "$has_source" == true && "$source_kind" == local && "$migrate_source" == /* && ! -L "$migrate_source" && -d "$migrate_source" ]] || { printf '%s\n' 'Migration requires the existing ChatGrowing local source.' >&2; exit 10; }
  migrate_source="$(cd "$migrate_source" && pwd -P)"
  [[ "$source_path" == /* && -d "$source_path" && ! -L "$source_path" ]] || exit 10
  source_path="$(cd "$source_path" && pwd -P)"
  [[ "$source_path" == "$migrate_source" ]] && verify_chatgrowing_source "$source_path" || { printf '%s\n' 'ChatGrowing source identity or migration path mismatch; preserved.' >&2; exit 10; }
  # Dedicated distribution directory only; never a checkout, Host cache or home.
  case "$source_path/" in */plugins/cache/*|*/.tmp/marketplaces/*) printf '%s\n' 'Host-managed cache cannot be migrated.' >&2; exit 10;; esac
  [[ "$source_path" != / && "$source_path" != "$HOME" && ! -e "$source_path/.git" ]] || exit 10
  [[ -z "$(find "$source_path" -type l -print -quit)" ]] || { printf '%s\n' 'Linked source content cannot be migrated.' >&2; exit 10; }
  while IFS= read -r entry; do
    case "${entry##*/}" in .agents|plugins|scripts|.github|website|README.md|INSTALL.md|.chatgrowing-marketplace-release.json|.chatgrowing-oauth-client-repair-evidence.json|.chatgrowing-skill-delta-evidence.json|.chatgrowing-installation-materials.json|.chatgrowing-http-source) ;; *) printf '%s\n' 'Unrecognized source content preserved; migration refused.' >&2; exit 10;; esac
  done < <(find "$source_path" -mindepth 1 -maxdepth 1 -print)
  [[ "$(find "$source_path/plugins" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')" == 1 ]] || exit 10
  installed_source="$source_path"
elif [[ "$has_source" == true ]]; then
  if [[ "$update_owned" != true || "$source_kind" != local || "$source_path" != /* || ! -f "$source_path/.chatgrowing-http-source" ]]; then
    printf '%s\n' 'Existing ChatGrowing source preserved. Use --update-owned-source for an owned snapshot, or --migrate-local-source with the verified legacy local path.' >&2
    exit 10
  fi
  verify_chatgrowing_source "$source_path" || exit 10
  installed_source="$(cd "$source_path" && pwd -P)"
fi
# Never replace the directory holding our lock/downloads, or its ancestors.
case "$state/" in "$installed_source/"*) printf '%s\n' 'Unsafe source location; preserved.' >&2; exit 10;; esac
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 2 --max-time 60 \
  'https://api.github.com/repos/Hatcherthekid/chatgrowing-plugin-marketplace/commits/main' -o "$stage/commit.json"
commit="$(json_value "$stage/commit.json" sha)"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { printf '%s\n' 'Could not resolve the public marketplace commit.' >&2; exit 78; }
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --retry 2 --max-time 300 \
  "https://codeload.github.com/Hatcherthekid/chatgrowing-plugin-marketplace/tar.gz/$commit" -o "$stage/repo.tar.gz"
prefix="chatgrowing-plugin-marketplace-$commit"
while IFS= read -r member; do
  [[ "$member" == "$prefix/"* && "$member" != *'/../'* && "$member" != */.. ]] || { printf '%s\n' 'Unexpected marketplace archive path.' >&2; exit 78; }
done < <(tar -tzf "$stage/repo.tar.gz")
# Links, devices and special files must never be extracted, even with safe names.
tar -tvzf "$stage/repo.tar.gz" > "$stage/archive-types"
while IFS= read -r member; do
  case "$member" in -*|d*) ;; *) printf '%s\n' 'Linked or special archive member rejected.' >&2; exit 78;; esac
done < "$stage/archive-types"
tar -xzf "$stage/repo.tar.gz" -C "$stage"
source_root="$stage/$prefix"
verify_chatgrowing_source "$source_root" || { printf '%s\n' 'Downloaded marketplace identity is invalid.' >&2; exit 78; }
if [[ "$with_materials" == true ]]; then
  /bin/bash "$source_root/plugins/chatgrowing/scripts/setup_material_source_mcp.sh"
fi
# Persist source: the CLI must not reference a temporary directory that disappears.
printf '%s\n' "$commit" > "$source_root/.chatgrowing-http-source"
if [[ -e "$installed_source" ]]; then
  [[ "$has_source" == true && ( "$update_owned" == true || -n "$migrate_source" ) ]] || { printf '%s\n' 'Unregistered snapshot exists; inspect before replacing it.' >&2; exit 78; }
  previous="$(mktemp -d "${installed_source}.previous.XXXXXX")"
  mv "$installed_source" "$previous/runtime"
fi
mv "$source_root" "$installed_source"
if [[ "$has_source" != true ]]; then "$codex" plugin marketplace add "$installed_source" --json; fi
plugin_install_attempted=true
"$codex" plugin add chatgrowing@chatgrowing --json
# A successful CLI exit alone does not prove the installed version changed.
"$codex" plugin list --json > "$stage/installed.json"
expected_version="$(json_value "$installed_source/plugins/chatgrowing/.codex-plugin/plugin.json" version)"
installed_count="$(json_value "$stage/installed.json" installed)"
[[ "$installed_count" =~ ^[0-9]+$ ]] || exit 79
version_verified=false
for ((index=0;index<installed_count;index++)); do
  if [[ "$(json_value "$stage/installed.json" "installed.$index.pluginId")" == chatgrowing@chatgrowing ]]; then
    [[ "$(json_value "$stage/installed.json" "installed.$index.version")" != "$expected_version" ]] || version_verified=true
  fi
done
[[ "$version_verified" == true ]] || { printf '%s\n' 'Installed plugin version verification failed.' >&2; exit 79; }
success=true
if [[ -n "$previous" ]]; then printf '%s\n' "Previous local source preserved at $previous/runtime" >&2; fi
printf '%s\n' 'Plugin files installed without Git. Verify a permitted remote query using existing authorization next; do not log in again unless the Host reports an authentication failure.' >&2
