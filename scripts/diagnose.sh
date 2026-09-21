#!/usr/bin/env bash
# Target-device diagnostics. No login, refresh, install, credentials or business calls.
set -euo pipefail
codex=''; task_skill=''; thread=''; status_file=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex) codex="${2:-}"; shift 2 ;;
    --task-skill-path) task_skill="${2:-}"; shift 2 ;;
    --thread-id) thread="${2:-}"; shift 2 ;;
    --host-status) status_file="${2:-}"; shift 2 ;;
    *) printf '%s\n' 'Usage: diagnose.sh --codex /desktop/codex [--task-skill-path /path/SKILL.md] [--thread-id UUID | --host-status /native/status.json]' >&2; exit 2 ;;
  esac
done
[[ "$codex" == /* && -x "$codex" && -x /usr/bin/plutil ]] || exit 2
[[ -z "$thread" || "$thread" =~ ^[0-9a-fA-F-]{36}$ ]] || exit 2
[[ -z "$thread" || -z "$status_file" ]] || exit 2
umask 077
scratch="$(mktemp -d "${TMPDIR:-/tmp}/chatgrowing-diagnose.XXXXXX")"
proxy_pid=''
cleanup() { [[ -z "$proxy_pid" ]] || { kill "$proxy_pid" 2>/dev/null || true; wait "$proxy_pid" 2>/dev/null || true; }; rm -rf "$scratch"; }
trap cleanup EXIT
value() { /usr/bin/plutil -extract "$2" raw -o - "$1" 2>/dev/null; }
safe_version() { local v="$1"; [[ "$v" =~ ^[0-9][0-9A-Za-z.+_-]{0,63}$ ]] && printf '%s' "$v" || printf unknown; }
printf '%s\n' 'scope=executing_device_only' 'business_query=not_attempted' 'oauth_refresh=not_tested'
if ! "$codex" plugin list --json > "$scratch/plugins.json" 2> "$scratch/error"; then
  printf '%s\n' 'installation=cli_inspection_failed'; exit 10
fi
n="$(value "$scratch/plugins.json" installed)"; [[ "$n" =~ ^[0-9]+$ ]] || exit 10
version=''; enabled=''
for ((i=0;i<n;i++)); do
  [[ "$(value "$scratch/plugins.json" "installed.$i.pluginId")" == chatgrowing@chatgrowing ]] || continue
  version="$(value "$scratch/plugins.json" "installed.$i.version")"
  enabled="$(value "$scratch/plugins.json" "installed.$i.enabled" || echo unknown)"
  printf 'installed_version=%s\n' "$(safe_version "$version")"
  case "$enabled" in true|false) printf 'enabled=%s\n' "$enabled" ;; *) printf '%s\n' 'enabled=unknown';; esac
  kind="$(value "$scratch/plugins.json" "installed.$i.marketplaceSource.sourceType" || echo unknown)"
  case "$kind" in git|local) printf 'marketplace_source_type=%s\n' "$kind" ;; *) printf '%s\n' 'marketplace_source_type=unknown';; esac
done
if [[ -z "$version" ]]; then printf '%s\n' 'installation=not_listed'; fi
# Resolve the installed cache, not the marketplace's available plugin version.
if [[ "$version" =~ ^[0-9][0-9A-Za-z.+_-]{0,63}$ ]]; then
  root="${CODEX_HOME:-${HOME}/.codex}/plugins/cache/chatgrowing/chatgrowing/$version"
  manifest="$root/.codex-plugin/plugin.json"
  if [[ -f "$manifest" && "$(value "$manifest" version)" == "$version" ]]; then
    printf '%s\n' 'installed_files=present'
    for skill in youtube-material-operations ads-configuration; do
      if [[ -f "$root/skills/$skill/SKILL.md" ]]; then printf '%s=present\n' "$skill"; else printf '%s=missing\n' "$skill"; fi
    done
    if [[ "$(value "$root/.mcp.json" mcpServers.chatgrowing_ads_read.url || true)" == https://chatgrowing.com/mcp ]]; then
      printf '%s\n' 'gateway_manifest=canonical'
    else
      printf '%s\n' 'gateway_manifest=missing_or_conflicting'
    fi
    # Inspect packaged files without sourcing or executing installed scripts.
    # This reports readiness, not the actual task's process configuration.
    printf '%s\n' 'local_configuration_evidence=installed_files_not_task_snapshot'
    for component in scripts/run_material_source_mcp.sh scripts/material_runtime_common.sh scripts/setup_material_source_mcp.sh runtime/material-source/code/apps/material_source_mcp_server.py; do
      if [[ ! -f "$root/$component" ]]; then printf 'local_packaged_file_missing=%s\n' "$component"; fi
    done
    if [[ -f "$root/runtime-config/requirements.lock" && -f "$root/runtime-config/downloads.tsv" && -f "$root/scripts/setup_material_source_mcp.sh" ]]; then
      revision="$(cat "$root/runtime-config/requirements.lock" "$root/runtime-config/downloads.tsv" "$root/scripts/setup_material_source_mcp.sh" | shasum -a 256 | awk '{print $1}')"
      runtime="${CODEX_HOME:-${HOME}/.codex}/chatgrowing/runtimes/$(uname -s)-$(uname -m)-$revision"
      if [[ -f "$runtime/.ready" && "$(cat "$runtime/.ready")" == "$revision" && -x "$runtime/venv/bin/python" && -x "$runtime/bin/ffmpeg" && -x "$runtime/bin/ffprobe" ]]; then
        printf '%s\n' 'local_runtime_files=ready_not_execution_verified'
      else
        printf '%s\n' 'local_runtime_files=missing_or_incomplete' 'local_runtime_missing_does_not_explain_spawn_enoent' 'remote_queries_do_not_require_local_runtime'
      fi
    else
      printf '%s\n' 'local_runtime_files=unverified_packaged_manifest_missing'
    fi
    if [[ -n "$task_skill" ]]; then
      case "$task_skill" in
        "$root"/skills/*/SKILL.md) printf '%s\n' 'task_skill_reference=current' ;;
        *) printf '%s\n' 'task_skill_reference=stale_or_other_source' 'next_task_snapshot=fully_quit_and_reopen_desktop_once_then_new_task' ;;
      esac
    fi
  else
    printf '%s\n' 'installed_files=unverified_layout_or_missing'
  fi
fi
if [[ -n "$task_skill" ]]; then
  if [[ -f "$task_skill" ]]; then printf '%s\n' 'task_skill_file=present'; else printf '%s\n' 'task_skill_file=missing'; fi
fi
# Inspect the EXISTING daemon and requested task. Never start another Host or
# refresh credentials as a substitute for the affected task's connection state.
if [[ -n "$thread" ]]; then
  mkfifo "$scratch/in" "$scratch/out"
  exec 3<>"$scratch/in" 4<>"$scratch/out"
  "$codex" app-server proxy < "$scratch/in" > "$scratch/out" 2> "$scratch/proxy-error" &
  proxy_pid=$!
  read_reply() {
    local wanted="$1" line id deadline=$((SECONDS+15))
    while ((SECONDS<deadline)); do
      if IFS= read -r -t 1 line <&4; then
        printf '%s\n' "$line" > "$scratch/message.json"
        id="$(value "$scratch/message.json" id || true)"
        if [[ "$id" == "$wanted" ]]; then
          /usr/bin/plutil -extract result json -o "$scratch/reply.json" "$scratch/message.json" 2>/dev/null
          return $?
        fi
      elif ! kill -0 "$proxy_pid" 2>/dev/null; then return 1
      fi
    done
    return 1
  }
  printf '%s\n' '{"id":1,"method":"initialize","params":{"clientInfo":{"name":"chatgrowing_diagnose","version":"1.0.0"},"capabilities":{"experimentalApi":true}}}' >&3
  if read_reply 1; then
    printf '%s\n' '{"method":"initialized","params":{}}' >&3
    printf '{"id":2,"method":"mcpServerStatus/list","params":{"threadId":"%s","detail":"full","limit":100}}\n' "$thread" >&3
    if read_reply 2; then status_file="$scratch/reply.json"; printf '%s\n' 'host_evidence=existing_daemon_target_task'; fi
  fi
  if [[ -z "$status_file" ]]; then printf '%s\n' 'host_evidence=unavailable_or_unsupported_proxy'; fi
fi
if [[ -z "$status_file" ]]; then
  printf '%s\n' 'host_connection=unknown' 'tool_discovery=unknown' 'next=inspect_affected_task_native_mcp_status'
  exit 0
fi
# --host-status accepts the unmodified result of native mcpServerStatus/list.
# It is a supplied observation, never interchangeable with our own device probe.
if [[ -z "$thread" ]]; then printf '%s\n' 'host_evidence=supplied_native_status_not_independently_verified'; fi
n="$(value "$status_file" data || true)"; [[ "$n" =~ ^[0-9]+$ ]] || { printf '%s\n' 'host_connection=invalid_status_format'; exit 11; }
found=false
for ((i=0;i<n;i++)); do
  name="$(value "$status_file" "data.$i.name" || true)"
  plugin="$(value "$status_file" "data.$i.pluginId" || true)"
  # Server identity must be exact or tied to this plugin, not arbitrary resources.
  [[ "$name" == chatgrowing_ads_read || ( "$plugin" == chatgrowing@chatgrowing && "$name" == *chatgrowing_ads_read ) ]] || continue
  found=true
  if ! value "$status_file" "data.$i.runtimeStatus" >/dev/null; then
    printf '%s\n' 'host_runtime_field=not_provided_by_host_version'
  fi
  runtime="$(value "$status_file" "data.$i.runtimeStatus" || true)"
  case "$runtime" in notStarted|starting|connected|authenticationRequired|failed|cancelled|disabled) printf 'host_connection=%s\n' "$runtime" ;; *) printf '%s\n' 'host_connection=unknown';; esac
  auth="$(value "$status_file" "data.$i.authStatus" || true)"
  case "$auth" in unknown|unsupported|notLoggedIn|bearerToken|oAuth) printf 'host_auth=%s\n' "$auth" ;; *) printf '%s\n' 'host_auth=unknown';; esac
  for tool in ads_capability_context material_targets; do
    if value "$status_file" "data.$i.tools.$tool.name" >/dev/null; then printf '%s=host_catalog_present\n' "$tool"; else printf '%s=host_catalog_absent\n' "$tool"; fi
  done
  error="$(value "$status_file" "data.$i.toolsError" || true)"
  case "$error" in
    ''|null) printf '%s\n' 'tools_error=not_reported' ;;
    *invalid_grant*|*needs_reauth*) printf '%s\n' 'tools_error=explicit_reauthentication_error' ;;
    *metadata*|*discovery*) printf '%s\n' 'tools_error=discovery_failure' ;;
    *request.send*|*connect*|*TLS*|*DNS*) printf '%s\n' 'tools_error=transport_failure' ;;
    *) printf '%s\n' 'tools_error=present_unclassified' ;;
  esac
  printf '%s\n' 'resource_empty_result_does_not_prove_connection_or_permissions'
done
if [[ "$found" != true ]]; then
  cursor="$(value "$status_file" nextCursor || true)"
  if [[ -n "$cursor" && "$cursor" != null ]]; then
    printf '%s\n' 'host_connection=not_observed_on_partial_page'
  else
    printf '%s\n' 'host_connection=not_reported_for_chatgrowing'
  fi
fi
printf '%s\n' 'task_tool_invocation=not_verified' 'acceptance=not_complete_until_affected_task_queries_succeed'
