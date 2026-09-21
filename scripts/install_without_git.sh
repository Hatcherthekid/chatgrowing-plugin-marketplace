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
umask 077
state="${CODEX_HOME:-${HOME}/.codex}/chatgrowing"
mkdir -p "$state"
state="$(cd "$state" && pwd -P)"
# Kernel lock on an inherited file descriptor: crashes release it automatically.
# Keep the file/inode so concurrent invocations always lock the same object.
process_lock="$state/marketplace-install.flock"
[[ -x /usr/bin/lockf && ! -L "$process_lock" ]] || exit 78
exec 9>>"$process_lock"
/usr/bin/lockf -s -t 0 9 || { printf '%s\n' 'Another ChatGrowing installation is active; retry after it finishes.' >&2; exit 75; }
release_lock() {
  if [[ "$(cat "$state/marketplace-install.lock/pid" 2>/dev/null || true)" == "$$" ]]; then
    rm -f "$state/marketplace-install.lock/pid"
    rmdir "$state/marketplace-install.lock" || true
  fi
  exec 9>&-
}
trap release_lock EXIT
# Compatibility with the previously published mkdir-only lock. Inspect it
# while holding the new process lock, and preserve unknown or active owners.
lock="$state/marketplace-install.lock"
if [[ -e "$lock" || -L "$lock" ]]; then
  [[ -d "$lock" && ! -L "$lock" ]] || exit 75
  owner="$(cat "$lock/pid" 2>/dev/null || true)"
  if [[ "$owner" =~ ^[0-9]+$ ]] && kill -0 "$owner" 2>/dev/null; then
    printf '%s\n' 'Another ChatGrowing installation is active; retry after it finishes.' >&2; exit 75
  fi
  if [[ ! "$owner" =~ ^[0-9]+$ ]]; then
    printf '%s\n' 'Legacy lock owner is unknown; preserved regardless of age. Confirm all old installers have exited before removing the empty legacy lock directory.' >&2
    exit 75
  fi
  rm -f "$lock/pid"
  rmdir "$lock" || exit 75
fi
# Keep the legacy directory while active so older installers also stay out.
mkdir "$lock" || exit 75
printf '%s\n' "$$" > "$lock/pid"
# macOS ships a real JSON parser; do not infer a source from another marketplace.
[[ -x /usr/bin/plutil ]] || { printf '%s\n' 'This installer requires macOS system plutil.' >&2; exit 78; }
json_value() { /usr/bin/plutil -extract "$2" raw -o - "$1" 2>/dev/null; }
[[ "$update_owned" != true || -z "$migrate_source" ]] || { printf '%s\n' 'Choose update or migration, not both.' >&2; exit 2; }
stage="$(mktemp -d "$state/marketplace-download.XXXXXX")"
success=false
previous=''
plugin_install_attempted=false
rebind=false
registration_changed=false
original_source=''
before_version=''
installed_source="$state/marketplace-http"
cleanup() {
  result=$?
  if [[ "$success" != true && -n "$previous" && -d "$previous/runtime" ]]; then
    if [[ -e "$installed_source" ]]; then mv "$installed_source" "$stage/failed" || exit 74; fi
    mv "$previous/runtime" "$installed_source" || { printf '%s\n' 'Source rollback failed; preserved previous source requires recovery.' >&2; exit 74; }
    rmdir "$previous" || true
    if [[ "$plugin_install_attempted" == true ]]; then printf '%s\n' 'Source files restored. The Host may have partially changed its installed plugin; installed state is read back below. Rerun the same command to finish the update. Authorization was not changed by this script.' >&2; fi
  fi
  if [[ "$success" != true && "$registration_changed" == true ]]; then
    # Repair only our own attempted rebind; never erase an unrelated source.
    if "$codex" plugin marketplace list --json > "$stage/recovery-sources.json"; then
      recovery_count="$(json_value "$stage/recovery-sources.json" marketplaces)"
      recovery_source=''
      for ((r=0;r<recovery_count;r++)); do
        if [[ "$(json_value "$stage/recovery-sources.json" "marketplaces.$r.name")" == chatgrowing ]]; then
          recovery_source="$(json_value "$stage/recovery-sources.json" "marketplaces.$r.marketplaceSource.source")"
        fi
      done
      if [[ -z "$recovery_source" || "$recovery_source" == "$installed_source" ]]; then
        if [[ -z "$recovery_source" ]] || "$codex" plugin marketplace remove chatgrowing --json > /dev/null; then
          if "$codex" plugin marketplace add "$original_source" --json > /dev/null; then
            if [[ -n "$before_version" && "$(json_value "$original_source/plugins/chatgrowing/.codex-plugin/plugin.json" version || true)" == "$before_version" ]]; then
              "$codex" plugin add chatgrowing@chatgrowing --json > /dev/null || true
            else
              printf '%s\n' 'Previous source version changed or no plugin was previously installed; automatic plugin reinstall skipped.' >&2
            fi
            printf '%s\n' 'Previous marketplace registration restored; installed version must match the readback below.' >&2
          else
            printf '%s\n' 'Previous registration restoration failed; original source is preserved. Use the recorded original source with official marketplace add before retrying.' >&2
          fi
        fi
      else
        printf '%s\n' 'Marketplace changed concurrently; preserved for inspection.' >&2
      fi
    fi
  fi
  if [[ "$success" != true && ( "$plugin_install_attempted" == true || "$registration_changed" == true ) ]]; then
    if "$codex" plugin list --json > "$stage/recovery-installed.json"; then
      report_installed "$stage/recovery-installed.json" >&2 || true
    else
      printf '%s\n' 'installed_state=unverified; rerun diagnosis before claiming rollback.' >&2
    fi
  fi
  if [[ "$success" == true || ( -n "$previous" && -d "$installed_source" && ! -d "$previous/runtime" ) ]]; then
    rm -f "$state/pending-source-swap.plist"
  fi
  rm -rf "$stage"
  release_lock || true
  exit "$result"
}
trap cleanup EXIT
report_installed() {
  local file="$1" n i found=false
  n="$(json_value "$file" installed)" || return 1
  for ((i=0;i<n;i++)); do
    if [[ "$(json_value "$file" "installed.$i.pluginId")" == chatgrowing@chatgrowing ]]; then
      printf 'installed_version=%s\nenabled=%s\n' "$(json_value "$file" "installed.$i.version")" "$(json_value "$file" "installed.$i.enabled" || echo unknown)"
      found=true
    fi
  done
  [[ "$found" == true ]] || printf '%s\n' 'installed_state=not_listed'
}
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
# Recover a process killed between the two directory renames. The journal
# contains only public source paths, never credentials or shell instructions.
journal="$state/pending-source-swap.plist"
if [[ -f "$journal" && ! -L "$journal" ]]; then
  pending_target="$(json_value "$journal" destination)"
  pending_previous="$(json_value "$journal" previous)"
  [[ "$pending_target" == /* && "$pending_previous" == "$pending_target.previous."* && ! -L "$pending_target" && ! -L "$pending_previous" ]] || exit 74
  if [[ ! -e "$pending_target" ]]; then
    verify_chatgrowing_source "$pending_previous/runtime" || exit 74
    mv "$pending_previous/runtime" "$pending_target"
    rmdir "$pending_previous"
    printf '%s\n' 'Interrupted source swap restored; continuing the requested update.' >&2
  else
    verify_chatgrowing_source "$pending_target" || exit 74
  fi
  rm "$journal"
fi
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
# Recover only from a durable pre-removal receipt. A path alone cannot prove
# which version was installed before the marketplace was removed.
rebind_journal="$state/pending-marketplace-rebind.plist"
if [[ "$has_source" != true && -n "$migrate_source" && -f "$state/previous-marketplace-source.txt" &&
      "$(cat "$state/previous-marketplace-source.txt")" == "$migrate_source" ]]; then
  if [[ ! -f "$rebind_journal" || -L "$rebind_journal" ||
        "$(json_value "$rebind_journal" source || true)" != "$migrate_source" ]]; then
    printf '%s\n' 'Interrupted migration has no verified original-version receipt; automatic recovery stopped before registration.' >&2
    exit 10
  fi
  recovery_version="$(json_value "$rebind_journal" installedVersion)"
  verify_chatgrowing_source "$migrate_source" || exit 10
  if [[ -n "$recovery_version" && "$(json_value "$migrate_source/plugins/chatgrowing/.codex-plugin/plugin.json" version)" != "$recovery_version" ]]; then
    printf '%s\n' 'Interrupted migration source version changed; automatic recovery stopped before registration.' >&2
    exit 10
  fi
  "$codex" plugin marketplace add "$migrate_source" --json
  if [[ -n "$recovery_version" ]]; then
    "$codex" plugin add chatgrowing@chatgrowing --json
    "$codex" plugin list --json > "$stage/resumed-installed.json"
    resumed_count="$(json_value "$stage/resumed-installed.json" installed)"
    [[ "$resumed_count" =~ ^[0-9]+$ ]] || exit 79
    resumed_verified=false
    for ((r=0;r<resumed_count;r++)); do
      if [[ "$(json_value "$stage/resumed-installed.json" "installed.$r.pluginId")" == chatgrowing@chatgrowing &&
            "$(json_value "$stage/resumed-installed.json" "installed.$r.version")" == "$recovery_version" &&
            "$(json_value "$stage/resumed-installed.json" "installed.$r.enabled" || true)" == true ]]; then resumed_verified=true; fi
    done
    [[ "$resumed_verified" == true ]] || { printf '%s\n' 'Interrupted migration restoration unverified; stopped.' >&2; exit 79; }
  fi
  has_source=true; source_kind=local; source_path="$migrate_source"
fi
# Retrying an already completed cache migration is an owned-source update.
if [[ -n "$migrate_source" && "$source_kind" == local && "$source_path" == "$installed_source" &&
      -f "$source_path/.chatgrowing-http-source" && -f "$state/previous-marketplace-source.txt" &&
      "$(cat "$state/previous-marketplace-source.txt")" == "$migrate_source" ]]; then
  migrate_source=''; update_owned=true
fi
if [[ -n "$migrate_source" ]]; then
  [[ "$has_source" == true && "$source_kind" == local && "$migrate_source" == /* && ! -L "$migrate_source" && -d "$migrate_source" ]] || { printf '%s\n' 'Migration requires the existing ChatGrowing local source.' >&2; exit 10; }
  migrate_source="$(cd "$migrate_source" && pwd -P)"
  [[ "$source_path" == /* && -d "$source_path" && ! -L "$source_path" ]] || exit 10
  source_path="$(cd "$source_path" && pwd -P)"
  [[ "$source_path" == "$migrate_source" ]] && verify_chatgrowing_source "$source_path" || { printf '%s\n' 'ChatGrowing source identity or migration path mismatch; preserved.' >&2; exit 10; }
  # Host caches are never modified. Explicit migration re-registers the same
  # marketplace through the official CLI only after a new snapshot is ready.
  case "$source_path/" in
    */.tmp/marketplaces/*) rebind=true; original_source="$source_path" ;;
    */plugins/cache/*) printf '%s\n' 'Installed plugin cache is not a marketplace source; preserved.' >&2; exit 10 ;;
  esac
  [[ "$source_path" != / && "$source_path" != "$HOME" ]] || exit 10
  [[ "$rebind" == true || ! -e "$source_path/.git" ]] || exit 10
  [[ -z "$(find "$source_path" -type l -print -quit)" ]] || { printf '%s\n' 'Linked source content cannot be migrated.' >&2; exit 10; }
  if [[ "$rebind" != true ]]; then
  while IFS= read -r entry; do
    case "${entry##*/}" in .agents|plugins|scripts|.github|website|README.md|INSTALL.md|.chatgrowing-marketplace-release.json|.chatgrowing-oauth-client-repair-evidence.json|.chatgrowing-skill-delta-evidence.json|.chatgrowing-installation-materials.json|.chatgrowing-http-source) ;; *) printf '%s\n' 'Unrecognized source content preserved; migration refused.' >&2; exit 10;; esac
  done < <(find "$source_path" -mindepth 1 -maxdepth 1 -print)
  [[ "$(find "$source_path/plugins" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')" == 1 ]] || exit 10
  installed_source="$source_path"
  fi
elif [[ "$has_source" == true ]]; then
  if [[ "$source_kind" != local || "$source_path" != /* || ! -f "$source_path/.chatgrowing-http-source" ]]; then
    printf '%s\n' 'Existing ChatGrowing source preserved. Git sources use marketplace upgrade then plugin add; legacy local sources use --migrate-local-source with the verified path.' >&2
    exit 10
  fi
  verify_chatgrowing_source "$source_path" || exit 10
  installed_source="$(cd "$source_path" && pwd -P)"
  case "$installed_source/" in */plugins/cache/*|*/.tmp/marketplaces/*) printf '%s\n' 'Owned marker in Host cache does not authorize writes; use explicit --migrate-local-source.' >&2; exit 10;; esac
  update_owned=true
fi
# Never replace the directory holding our lock/downloads, or its ancestors.
case "$state/" in "$installed_source/"*) printf '%s\n' 'Unsafe source location; preserved.' >&2; exit 10;; esac
# Updating is not authorization to reverse an intentionally disabled plugin.
"$codex" plugin list --json > "$stage/before-installed.json"
before_count="$(json_value "$stage/before-installed.json" installed)"
[[ "$before_count" =~ ^[0-9]+$ ]] || exit 78
for ((i=0;i<before_count;i++)); do
  if [[ "$(json_value "$stage/before-installed.json" "installed.$i.pluginId")" == chatgrowing@chatgrowing ]]; then
    before_version="$(json_value "$stage/before-installed.json" "installed.$i.version")"
  fi
  if [[ "$(json_value "$stage/before-installed.json" "installed.$i.pluginId")" == chatgrowing@chatgrowing &&
        "$(json_value "$stage/before-installed.json" "installed.$i.enabled" || true)" == false ]]; then
    printf '%s\n' 'ChatGrowing is disabled; preserved. Resolve the intended enabled state in the Host before updating.' >&2
    exit 10
  fi
done
# Official plugin add cannot pin a historical version. Never remove a working
# installation unless the original source can reinstall that exact version.
verify_rebind_recovery_version() {
  if [[ "$rebind" == true && -n "$before_version" &&
        "$(json_value "$original_source/plugins/chatgrowing/.codex-plugin/plugin.json" version || true)" != "$before_version" ]]; then
    printf '%s\n' 'Migration stopped before deregistration: source and installed versions differ; exact-version recovery is unavailable. Existing installation preserved.' >&2
    return 10
  fi
}
verify_rebind_recovery_version
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
# Persist source: the CLI must not reference a temporary directory that disappears.
printf '%s\n' "$commit" > "$source_root/.chatgrowing-http-source"
if [[ -e "$installed_source" ]]; then
  if [[ "$has_source" != true || "$rebind" == true ]]; then
    # A previous attempt may have staged files but failed to register them.
    verify_chatgrowing_source "$installed_source" && [[ -f "$installed_source/.chatgrowing-http-source" ]] || { printf '%s\n' 'Unregistered snapshot identity is unknown; preserved.' >&2; exit 78; }
  fi
  previous="$(mktemp -d "${installed_source}.previous.XXXXXX")"
  /usr/bin/plutil -create xml1 "$state/pending-source-swap.new"
  /usr/bin/plutil -insert destination -string "$installed_source" "$state/pending-source-swap.new"
  /usr/bin/plutil -insert previous -string "$previous" "$state/pending-source-swap.new"
  mv "$state/pending-source-swap.new" "$journal"
  mv "$installed_source" "$previous/runtime"
fi
mv "$source_root" "$installed_source"
if [[ "$rebind" == true ]]; then
  verify_rebind_recovery_version
  printf '%s\n' "$original_source" > "$state/previous-marketplace-source.txt"
  /usr/bin/plutil -create xml1 "$state/pending-marketplace-rebind.new"
  /usr/bin/plutil -insert source -string "$original_source" "$state/pending-marketplace-rebind.new"
  /usr/bin/plutil -insert installedVersion -string "$before_version" "$state/pending-marketplace-rebind.new"
  mv "$state/pending-marketplace-rebind.new" "$rebind_journal"
  registration_changed=true
  "$codex" plugin marketplace remove chatgrowing --json
fi
if [[ "$has_source" != true || "$rebind" == true ]]; then "$codex" plugin marketplace add "$installed_source" --json; fi
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
    if [[ "$(json_value "$stage/installed.json" "installed.$index.version")" == "$expected_version" && "$(json_value "$stage/installed.json" "installed.$index.enabled" || true)" == true ]]; then version_verified=true; fi
  fi
done
[[ "$version_verified" == true ]] || { printf '%s\n' 'Installed plugin version verification failed.' >&2; exit 79; }
success=true
rm -f "$rebind_journal"
report_installed "$stage/installed.json"
printf '%s\n' 'host_tool_discovery=not_verified' 'business_query=not_attempted' 'host_activation=desktop_restart_required_if_host_was_running_during_cli_update'
printf '%s\n' 'After an external CLI update, fully quit and reopen the desktop Host once before testing in a new task. Creating a task or reloading MCP alone can retain deleted plugin paths on Codex 0.148.0-alpha.9. Do not log out or reinstall to refresh this state.' >&2
if [[ "$with_materials" == true ]]; then
  # Remote installation is already committed; helper failure is independent.
  if /bin/bash "$installed_source/plugins/chatgrowing/scripts/setup_material_source_mcp.sh"; then
    printf '%s\n' 'material_runtime=ready'
  else
    printf '%s\n' 'material_runtime=failed; plugin installation preserved. Retry only setup_material_source_mcp.sh; do not reinstall or log in again.' >&2
    exit 20
  fi
fi
if [[ -n "$previous" ]]; then printf '%s\n' "Previous local source preserved at $previous/runtime" >&2; fi
printf '%s\n' 'Plugin files installed without Git. Verify a permitted remote query using existing authorization next; do not log in again unless the Host reports an authentication failure.' >&2
